"""Inspect official dataset assets; persist metadata and aggregate counts only.

This research utility never visits dataset URLs, saves raw URL rows, trains a
model, or downloads HTML columns. The default inspects a bounded PhreshPhish
sample; --full-phresh checks all URL columns. Neither verifies every label.
Dependencies: requests and pyarrow.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import re
from collections import Counter
from collections.abc import Iterable
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import unquote, urlsplit
from zipfile import ZipFile

import pyarrow
import pyarrow.parquet as pq
import requests


ROOT = Path(__file__).resolve().parents[2]
REPORT = ROOT / "ai-agent-docs/research/url-dataset-source-audit.json"
DATASET = "phreshphish/phreshphish"
PINNED_REVISION = "eca603e0ecd4f698f8d4d226c088659e72681239"
UCI_ZIP = "https://archive.ics.uci.edu/static/public/967/phiusiil+phishing+url+dataset.zip"
MAX_BYTES = 80 * 1024 * 1024
SESSION = requests.Session()
SESSION.headers["User-Agent"] = "GuardianLab-Dataset-Research/1.0 (metadata and aggregate audit)"
TRANSFERRED = 0


def fetch(url: str, *, start: int | None = None, end: int | None = None) -> bytes:
    global TRANSFERRED
    headers = {} if start is None else {"Range": f"bytes={start}-{end}"}
    with SESSION.get(url, headers=headers, timeout=(15, 60), stream=True) as response:
        response.raise_for_status()
        if start is not None and response.status_code != 206:
            raise RuntimeError("Dataset host did not honor a bounded range request")
        remaining = MAX_BYTES - TRANSFERRED
        if remaining <= 0:
            raise RuntimeError("Research transfer budget exceeded")
        data = response.raw.read(remaining + 1, decode_content=True)
    TRANSFERRED += len(data)
    if TRANSFERRED > MAX_BYTES:
        raise RuntimeError("Research transfer budget exceeded")
    if start is not None and len(data) != end - start + 1:
        raise RuntimeError("Unexpected byte-range response length")
    return data


class RangeReader(io.RawIOBase):
    def __init__(self, url: str, size: int):
        self.url, self.size, self.position = url, size, 0

    def readable(self) -> bool:
        return True

    def seekable(self) -> bool:
        return True

    def tell(self) -> int:
        return self.position

    def seek(self, offset: int, whence: int = 0) -> int:
        if whence not in (0, 1, 2):
            raise ValueError("Invalid seek mode")
        origin = 0 if whence == 0 else self.position if whence == 1 else self.size
        position = origin + offset
        if position < 0:
            raise ValueError("Negative seek")
        self.position = position
        return position

    def read(self, size: int = -1) -> bytes:
        amount = self.size - self.position if size < 0 else min(size, self.size - self.position)
        if amount <= 0:
            return b""
        data = fetch(self.url, start=self.position, end=self.position + amount - 1)
        self.position += len(data)
        return data


def summarize(
    rows: Iterable[dict[str, object]],
    url_key: str,
    label_key: str,
    previous_split_hashes: set[str] | None = None,
) -> dict[str, object]:
    by_label: dict[str, Counter[str]] = {}
    seen: dict[str, str] = {}
    conflicts: set[str] = set()
    duplicates = 0
    cross_split_overlap = 0
    dates: list[str] = []
    lengths: list[int] = []
    row_count = 0
    sensitive = re.compile(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}|\b\d{16}\b|(?:\+62|62|0)8\d{7,11}")
    for row in rows:
        row_count += 1
        url = str(row.get(url_key, ""))
        label = str(row.get(label_key, ""))
        counts = by_label.setdefault(label, Counter())
        counts["rows"] += 1
        digest = hashlib.sha256(url.encode()).hexdigest()
        duplicates += digest in seen
        if digest in seen and seen[digest] != label:
            conflicts.add(digest)
        seen[digest] = label
        if previous_split_hashes is not None:
            cross_split_overlap += digest in previous_split_hashes
        try:
            parsed = urlsplit(url if "://" in url else "https://" + url)
            counts["with_query"] += bool(parsed.query)
            counts["with_fragment"] += bool(parsed.fragment)
            counts["host_suffix_id"] += (parsed.hostname or "").endswith(".id")
            counts["with_userinfo"] += parsed.username is not None
        except ValueError:
            counts["parse_errors"] += 1
        counts["without_explicit_http_scheme"] += not url.lower().startswith(
            ("http://", "https://")
        )
        counts["sensitive_pattern_candidates"] += bool(sensitive.search(unquote(url)))
        lengths.append(len(url))
        if row.get("date") is not None:
            dates.append(str(row["date"]))
    lengths.sort()
    if previous_split_hashes is not None:
        previous_split_hashes.update(seen)
    return {
        "rows_inspected": row_count,
        "labels": {key: dict(value) for key, value in sorted(by_label.items())},
        "exact_url_duplicate_rows_within_inspected_data": duplicates,
        "exact_url_label_conflicts": len(conflicts),
        "exact_url_rows_present_in_previous_split": cross_split_overlap,
        "date_min": min(dates) if dates else None,
        "date_max": max(dates) if dates else None,
        "url_length_median": lengths[len(lengths) // 2] if lengths else None,
        "url_length_p95": (
            lengths[min(len(lengths) - 1, int(len(lengths) * 0.95))] if lengths else None
        ),
        "url_length_max": max(lengths) if lengths else None,
        "notes": [
            "Sensitive patterns are screening candidates, not confirmed personal data.",
            "A .id hostname does not prove an Indonesian target or label correctness.",
            "Sample duplicate counts do not measure whole-corpus or cross-source leakage.",
        ],
    }


def audit_phiusiil() -> dict[str, object]:
    zipped = fetch(UCI_ZIP)
    with ZipFile(io.BytesIO(zipped)) as archive:
        names = [name for name in archive.namelist() if name.lower().endswith(".csv")]
        if len(names) != 1:
            raise RuntimeError("Unexpected UCI CSV file layout")
        with archive.open(names[0]) as source:
            reader = csv.DictReader(
                io.TextIOWrapper(source, encoding="utf-8-sig", newline="")
            )
            fields = list(reader.fieldnames or [])
            summary = summarize(reader, "URL", "label")
    return {
        "source": UCI_ZIP,
        "archive_bytes": len(zipped),
        "archive_sha256": hashlib.sha256(zipped).hexdigest(),
        "csv_member": names[0],
        "columns": fields,
        "timestamp_columns": [
            name for name in fields if "date" in name.lower() or "time" in name.lower()
        ],
        "label_mapping_from_official_uci_documentation": {"0": "phishing", "1": "benign"},
        "scope": (
            "Complete CSV URL/label structural audit; "
            "not a verification of every ground-truth label"
        ),
        "summary": summary,
    }


def audit_phreshphish(full: bool = False) -> dict[str, object]:
    metadata = json.loads(fetch(f"https://huggingface.co/api/datasets/{DATASET}"))
    tree_url = (
        f"https://huggingface.co/api/datasets/{DATASET}"
        f"/tree/{PINNED_REVISION}/data?limit=1000"
    )
    tree = json.loads(fetch(tree_url))
    files = {item["path"]: item for item in tree if item.get("type") == "file"}
    samples = []
    previous_split_hashes: set[str] = set()
    for split in ("train", "test"):
        paths = sorted(
            name for name in files
            if name.startswith(f"data/{split}-") and name.endswith(".parquet")
        )
        if full:
            def iter_rows() -> Iterable[dict[str, object]]:
                for index, path in enumerate(paths):
                    url = (
                        f"https://huggingface.co/datasets/{DATASET}"
                        f"/resolve/{PINNED_REVISION}/{path}"
                    )
                    remote = RangeReader(url, files[path]["size"])
                    parquet = pq.ParquetFile(remote, pre_buffer=False)
                    for group in range(parquet.metadata.num_row_groups):
                        table = parquet.read_row_group(
                            group, columns=["url", "label", "date", "lang"],
                            use_threads=False,
                        )
                        yield from table.to_pylist()
                    remote.close()
                    if (index + 1) % 10 == 0:
                        print(
                            f"phreshphish {split}: {index + 1}/{len(paths)} shards inspected",
                            flush=True,
                        )
            summary = summarize(iter_rows(), "url", "label", previous_split_hashes)
            samples.append({
                "split": split,
                "scope": "All official shards, projected URL/label/date/lang only; no HTML",
                "shards_inspected": len(paths),
                "summary": summary,
            })
            continue
        path = paths[0]
        url = (
            f"https://huggingface.co/datasets/{DATASET}"
            f"/resolve/{PINNED_REVISION}/{path}"
        )
        remote = RangeReader(url, files[path]["size"])
        parquet = pq.ParquetFile(remote, pre_buffer=False)
        columns = [name for name in ("url", "label", "date", "lang") if name in parquet.schema_arrow.names]
        table = parquet.read_row_group(0, columns=columns, use_threads=False)
        samples.append({
            "split": split,
            "path": path,
            "asset_bytes": files[path]["size"],
            "file_rows": parquet.metadata.num_rows,
            "file_row_groups": parquet.metadata.num_row_groups,
            "schema": {field.name: str(field.type) for field in parquet.schema_arrow},
            "projected_columns": columns,
            "scope": "First row group of first official shard only; not random or representative",
            "summary": summarize(table.to_pylist(), "url", "label"),
        })
    return {
        "repository": DATASET,
        "pinned_revision": PINNED_REVISION,
        "head_revision_at_inspection": metadata.get("sha"),
        "repository_last_modified": metadata.get("lastModified"),
        "gated": metadata.get("gated"),
        "card_license": metadata.get("cardData", {}).get("license"),
        "parquet_file_count": sum(name.endswith(".parquet") for name in files),
        "listed_asset_bytes": sum(item["size"] for item in files.values()),
        "samples": samples,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--full-phresh", action="store_true",
        help="Audit all PhreshPhish URL columns, reusing the previous UCI report",
    )
    options = parser.parse_args()
    if options.full_phresh:
        report = json.loads(REPORT.read_text(encoding="utf-8"))
        report["full_audit_checked_at_utc"] = datetime.now(timezone.utc).isoformat()
        report["phreshphish_full"] = audit_phreshphish(full=True)
        report["full_audit_transferred_bytes"] = TRANSFERRED
        REPORT.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print("phreshphish: complete URL-column audit saved", flush=True)
        return
    report: dict[str, object] = {
        "checked_at_utc": datetime.now(timezone.utc).isoformat(),
        "purpose": "Dataset source selection, not model training or an accuracy benchmark",
        "raw_url_rows_persisted": False,
        "live_targets_visited": False,
        "pyarrow_version": pyarrow.__version__,
    }
    for name, audit in (("phiusiil", audit_phiusiil), ("phreshphish", audit_phreshphish)):
        try:
            report[name] = audit()
            print(f"{name}: aggregate audit completed", flush=True)
        except Exception as error:
            report[name] = {"status": "failed", "error_type": type(error).__name__}
            print(f"{name}: {type(error).__name__}; no request or row data logged", flush=True)
    report["transferred_bytes"] = TRANSFERRED
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(str(REPORT.relative_to(ROOT)), flush=True)


if __name__ == "__main__":
    main()
