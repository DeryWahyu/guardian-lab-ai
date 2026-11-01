"""Published TR-OP URL text intake with resumable sanitized checkpoints."""

from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
import sqlite3
from threading import local

import pandas as pd
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from .metadata import checksum
from .preprocessing import InvalidUrl, prepare_url
from .zip_ranges import fetch_member

SOURCE = "https://www.dropbox.com/scl/fi/z1liysgw42g9apcsp1v3i/TR-OP.zip?rlkey=9ovjwzteon3gp6v1yff1pdjrt&dl=1"
REVISION = "899982c9f0eef0f2ef758cbee96d2ceff0bd5e9a"
ARCHIVE_BYTES = 3672983157
STATE = local()


def hash_text(text):
    return hashlib.sha256(text.encode()).hexdigest()


def partition(group):
    value = int(hash_text("v8-domain:" + group), 16) % 100
    return next(
        name
        for limit, name in [
            (50, "fit"),
            (60, "tune"),
            (70, "calibration"),
            (80, "threshold"),
            (100, "new_test"),
        ]
        if value < limit
    )


def read_case(info):
    if not hasattr(STATE, "session"):
        STATE.session = requests.Session()
        STATE.session.headers["User-Agent"] = "GuardianLab-URL-Research/1.0 (dataset text only)"
        STATE.session.mount(
            "https://",
            HTTPAdapter(
                max_retries=Retry(
                    total=2, backoff_factor=0.5, status_forcelist=[429, 500, 502, 503, 504]
                )
            ),
        )
    identifier = hash_text(info.filename)
    try:
        endpoint = SOURCE.replace("www.dropbox.com", "dl.dropboxusercontent.com")
        raw = fetch_member(
            STATE.session,
            endpoint + "&guardian_range=" + str(info.header_offset),
            info,
            ARCHIVE_BYTES,
        )
        text = raw.decode("utf-8-sig").strip()
        if len(text.splitlines()) != 1:
            return {"id": identifier, "status": "unsupported_text_format"}
        item = prepare_url(text)
        return {
            "id": identifier,
            "status": "valid",
            "raw_projection_sha256": hashlib.sha256(raw).hexdigest(),
            "record": {
                "core": item.core,
                "digest": item.digest,
                "group": item.group,
                "label": int(info.filename.startswith("openphish_5000/")),
                "training_source": "knowphish_tr_op",
                "partition": partition(item.group),
                "date": "",
                "source_split": "published_manual_benchmark",
            },
        }
    except InvalidUrl:
        return {"id": identifier, "status": "unsupported_privacy_screening"}
    except (requests.RequestException, OSError):
        return {"id": identifier, "status": "transport_failed"}
    except (ValueError, UnicodeError):
        return {"id": identifier, "status": "format_or_integrity_failed"}


def prepare_source(root):
    from remotezip import RemoteZip

    root = Path(root)
    folder = root / "ml/data/expansion-v8"
    folder.mkdir(parents=True, exist_ok=True)
    output, manifest_path = folder / "tr-op-curated.parquet", folder / "tr-op-manifest.json"
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text())
        if checksum(output) != manifest["output_sha256"]:
            raise ValueError("source_cache_checksum_mismatch")
        return manifest
    registry = root / "ml/data/indonesia-gold/registry/known-exposure.sqlite"
    snapshot = folder / "exposure-before-v8.sqlite"
    if not snapshot.exists():
        shutil.copyfile(registry, snapshot)
    response = requests.get(
        f"https://raw.githubusercontent.com/imethanlee/KnowPhish/{REVISION}/README.md", timeout=30
    )
    response.raise_for_status()
    if "z1liysgw42g9apcsp1v3i" not in response.text:
        raise ValueError("publisher_dataset_link_mismatch")
    with RemoteZip(SOURCE) as zipped:
        infos = [i for i in zipped.infolist() if i.filename.endswith("/info.txt")]
    if len(infos) != 10000:
        raise ValueError("publisher_archive_case_count_changed")
    index_hash = hashlib.sha256()
    for info in sorted(infos, key=lambda i: i.filename):
        index_hash.update(
            json.dumps(
                [info.filename, info.CRC, info.header_offset, info.compress_size, info.file_size]
            ).encode()
        )
    candidates, stats = [], Counter()
    with sqlite3.connect("file:" + snapshot.as_posix() + "?mode=ro", uri=True) as db:
        for info in infos:
            stats["metadata_cases"] += 1
            tokens = info.filename.split("/")[1].rsplit("+", 3)
            if len(tokens) != 4:
                stats["unsupported_metadata"] += 1
                continue
            try:
                item = prepare_url(tokens[1])
            except InvalidUrl:
                stats["unsupported_metadata"] += 1
                continue
            if db.execute(
                "SELECT 1 FROM domain_hashes WHERE value=?", (hash_text(item.group),)
            ).fetchone():
                stats["metadata_known_domain_excluded"] += 1
                continue
            candidates.append(info)
    candidates.sort(key=lambda i: hash_text(i.filename))
    checkpoint = folder / "sanitized-intake.jsonl"
    binding = {
        "archive_index_sha256": index_hash.hexdigest(),
        "registry_sha256": checksum(snapshot),
        "parser_sha256": checksum(root / "ml/src/guardian_ml/preprocessing.py"),
        "split": "v8-domain:50-60-70-80-100",
    }
    binding_path = folder / "intake-binding.json"
    if binding_path.exists():
        if json.loads(binding_path.read_text()) != binding:
            raise ValueError("intake_checkpoint_binding_mismatch")
    else:
        binding_path.write_text(json.dumps(binding, indent=2) + "\n")
    completed = {}
    if checkpoint.exists():
        for line in checkpoint.read_text(encoding="utf-8").splitlines():
            record = json.loads(line)
            if record["status"] not in {"transport_failed", "format_or_integrity_failed"}:
                completed[record["id"]] = record
    pending = [i for i in candidates if hash_text(i.filename) not in completed]
    print(
        "Dataset intake: eligible metadata",
        len(candidates),
        "; pending text reads",
        len(pending),
        flush=True,
    )
    with (
        checkpoint.open("a", encoding="utf-8") as handle,
        ThreadPoolExecutor(max_workers=8) as pool,
    ):
        for number, result in enumerate(pool.map(read_case, pending), 1):
            completed[result["id"]] = result
            handle.write(json.dumps(result, ensure_ascii=True) + "\n")
            handle.flush()
            if number % 250 == 0 or number == len(pending):
                print("Dataset text checked", number, "/", len(pending), flush=True)
    errors = Counter(r["status"] for r in completed.values())
    if errors["transport_failed"] or errors["format_or_integrity_failed"]:
        print("Incomplete intake; fixed-reason counts", dict(errors), flush=True)
        raise ValueError("source_intake_incomplete_retry_preserved_checkpoint")
    rows = []
    with sqlite3.connect("file:" + snapshot.as_posix() + "?mode=ro", uri=True) as db:
        for result in completed.values():
            if result["status"] != "valid":
                continue
            item = result["record"]
            if (
                db.execute("SELECT 1 FROM url_hashes WHERE value=?", (item["digest"],)).fetchone()
                or db.execute(
                    "SELECT 1 FROM domain_hashes WHERE value=?", (hash_text(item["group"]),)
                ).fetchone()
            ):
                stats["actual_url_or_domain_known_excluded"] += 1
                continue
            rows.append(item)
    frame = pd.DataFrame(rows)
    conflicts = set(frame.groupby("digest").label.nunique().loc[lambda x: x > 1].index)
    stats["conflicting_digests"] = len(conflicts)
    frame = frame[~frame.digest.isin(conflicts)].sort_values("digest")
    stats["duplicate_rows"] = int(frame.digest.duplicated().sum())
    frame = frame.drop_duplicates("digest")
    count = len(frame)
    frame = frame.groupby("group", sort=False).head(5).reset_index(drop=True)
    stats["domain_cap_removed"] = count - len(frame)
    frame.to_parquet(output, index=False)
    manifest = {
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "source": "knowphish_tr_op",
        "source_repository_commit": REVISION,
        "readme_sha256": hashlib.sha256(response.content).hexdigest(),
        "source_url": SOURCE,
        "archive_bytes": ARCHIVE_BYTES,
        **binding,
        "source_index_cases": 10000,
        "text_candidates": len(candidates),
        "intake_status_counts": dict(errors),
        "audit_counts": dict(stats),
        "rows": len(frame),
        "groups": int(frame.group.nunique()),
        "partition_class_counts": frame.groupby(["partition", "label"])
        .size()
        .rename("rows")
        .reset_index()
        .to_dict("records"),
        "output_path": output.relative_to(root).as_posix(),
        "output_sha256": checksum(output),
        "label_tier": "paper_reports_manual_validation_no_two_independent_case_sheets",
        "rights": "public_author_research_release_no_production_or_redistribution_claim",
        "metadata_previously_inspected_v7": True,
        "target_visits": 0,
        "limitations": [
            "Historical 2023 data, not Indonesian gold.",
            "Metadata prefilter excludes known hosts without inspecting their redirect URLs.",
            "Domain split, not independent publisher/feed or temporal holdout.",
            "No whole-archive checksum under bounded member projection; index and member CRC/projection hashes recorded.",
        ],
        "projection_digest_sha256": hash_text(
            json.dumps(
                sorted((r["id"], r.get("raw_projection_sha256")) for r in completed.values())
            )
        ),
    }
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest
