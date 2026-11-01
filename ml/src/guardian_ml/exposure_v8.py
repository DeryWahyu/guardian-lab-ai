"""Completed v8 provenance validation before registry exposure is extended."""

import hashlib
import json
from pathlib import Path

import pyarrow.parquet as pq

from .metadata import checksum


def completed_v8_inventory(root):
    root = Path(root)
    run = root / "ml/runs/notebook-tfidf-logistic-v8"
    paths = {
        "frozen": run / "reports/frozen-v8.json",
        "evaluated": run / "reports/evaluation-v8.json",
        "source": run / "reports/frozen-data-test-manifest.json",
        "protocol": run / "reports/notebook-protocol.json",
        "model": run / "artifacts/url-core-logistic-v8.joblib",
        "notebook": root / "guardian_lab_url_qr_expansion_v8.ipynb",
    }
    if not all(p.is_file() for p in paths.values()):
        return None
    docs = {
        name: json.loads(path.read_text(encoding="utf-8"))
        for name, path in paths.items()
        if name != "model"
    }
    frozen, evaluated, protocol, source = (
        docs[k] for k in ["frozen", "evaluated", "protocol", "source"]
    )
    code_hash = hashlib.sha256(
        "\n\n".join(
            "".join(c["source"]) if isinstance(c["source"], list) else c["source"]
            for c in docs["notebook"]["cells"]
            if c["cell_type"] == "code"
        ).encode()
    ).hexdigest()
    manifest_sha = checksum(paths["source"])
    if (
        frozen["code_sha256"] != code_hash
        or evaluated["code_sha256"] != code_hash
        or frozen["spec_sha256"] != evaluated["spec_sha256"]
        or frozen["spec_sha256"] != protocol["spec_sha256"]
        or checksum(paths["model"]) != frozen["bundle_sha256"]
        or evaluated["bundle_sha256"] != frozen["bundle_sha256"]
        or frozen["source_manifest_sha256"] != manifest_sha
        or evaluated["manifest_sha256"] != manifest_sha
        or protocol["specification"]["data_test_manifest_sha256"] != manifest_sha
    ):
        return None
    for name, expected in frozen["source_hashes"].items():
        path = (root / name).resolve()
        if not path.is_relative_to(root.resolve()) or checksum(path) != expected:
            return None
    expected_files, inventory = set(), []
    for role, item in source["outputs"].items():
        filename = item["filename"]
        if Path(filename).name != filename or not filename.endswith(".parquet"):
            return None
        path = run / "data" / filename
        if not path.is_file() or checksum(path) != item["sha256"]:
            return None
        expected_files.add(path.resolve())
        inventory.append(
            {
                "role": "v8:" + role,
                "path": path.relative_to(root).as_posix(),
                "sha256": item["sha256"],
                "rows": pq.ParquetFile(path).metadata.num_rows,
            }
        )
    if expected_files != {p.resolve() for p in run.rglob("*.parquet")}:
        return None
    return {
        "inventory": inventory,
        "provenance": {
            "run": run.name,
            "spec_sha256": frozen["spec_sha256"],
            "source_manifest_sha256": manifest_sha,
            "source_scope": "all_manifested_development_holdout_and_sanitized_intake_exposure_indexed",
        },
    }
