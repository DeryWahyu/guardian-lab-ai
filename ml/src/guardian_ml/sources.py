"""Read official dataset columns only. Never contact dataset target URLs."""

from __future__ import annotations

import csv
import importlib.util
import io
import json
from zipfile import ZipFile

import pyarrow.parquet as pq
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from .paths import ROOT, REVISION

spec = importlib.util.spec_from_file_location(
    "source_audit",
    ROOT / "scripts/research/audit_url_dataset_sources.py",
)
audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)
assert audit.PINNED_REVISION == REVISION
audit.SESSION.mount(
    "https://",
    HTTPAdapter(
        max_retries=Retry(
            total=3,
            backoff_factor=0.5,
            status_forcelist=[429, 502, 503, 504],
        )
    ),
)


def official_rows():
    tree = json.loads(
        audit.fetch(
            f"https://huggingface.co/api/datasets/{audit.DATASET}/tree/{REVISION}/data?limit=1000"
        )
    )
    files = sorted(
        [item for item in tree if item.get("type") == "file" and item["path"].endswith(".parquet")],
        key=lambda item: (not item["path"].startswith("data/train-"), item["path"]),
    )
    assert len(files) == 77, "Pinned source shard count changed"
    for index, item in enumerate(files):
        split = "train" if item["path"].startswith("data/train-") else "test"
        endpoint = (
            f"https://huggingface.co/datasets/{audit.DATASET}/resolve/{REVISION}/{item['path']}"
        )
        with audit.RangeReader(endpoint, item["size"]) as remote:
            parquet = pq.ParquetFile(remote, pre_buffer=False)
            for batch in parquet.iter_batches(
                batch_size=2048,
                columns=["url", "label", "date"],
                use_threads=False,
            ):
                for row in batch.to_pylist():
                    yield split, row
        if (index + 1) % 10 == 0 or index + 1 == len(files):
            print(f"Official source: {index + 1}/{len(files)} shards", flush=True)


def external_rows():
    # Label semantics are independently documented by the UCI dataset owner.
    archive = audit.fetch(audit.UCI_ZIP)
    import hashlib

    expected = "0a639fd03aea6308c5b1c10c92aa23c2ce1505447a9137271865cd0badc9a59a"
    assert hashlib.sha256(archive).hexdigest() == expected, "UCI source checksum changed"
    with ZipFile(io.BytesIO(archive)) as zipped:
        name = next(name for name in zipped.namelist() if name.endswith(".csv"))
        with zipped.open(name) as stream:
            for row in csv.DictReader(io.TextIOWrapper(stream, encoding="utf-8-sig")):
                assert row["label"] in ("0", "1")
                yield (
                    "external",
                    {
                        "url": row["URL"],
                        "label": ("phish" if row["label"] == "0" else "benign"),
                        "date": None,
                    },
                )
