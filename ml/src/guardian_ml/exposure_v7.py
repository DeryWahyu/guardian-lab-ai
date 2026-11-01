"""Validate completed v7 provenance before adding its data to the exposure index."""

import hashlib
import json
from pathlib import Path

import pyarrow.parquet as pq

from .metadata import checksum


def completed_v7_inventory(root):
    root = Path(root)
    run = root / "ml/runs/notebook-tfidf-logistic-v7"
    files = {
        "frozen": run / "reports/frozen-v7.json",
        "evaluation": run / "reports/evaluation-v7.json",
        "source": run / "reports/frozen-new-test-manifest.json",
        "protocol": run / "reports/notebook-protocol.json",
        "audit": run / "reports/development-audit.json",
        "model": run / "artifacts/url-core-logistic-v7.joblib",
        "notebook": root / "guardian_lab_url_qr_structural_v7.ipynb",
    }
    if not all(path.is_file() for path in files.values()):
        return None
    documents = {
        name: json.loads(files[name].read_text(encoding="utf-8"))
        for name in ["frozen", "evaluation", "source", "protocol", "audit", "notebook"]
    }
    frozen, evaluated = documents["frozen"], documents["evaluation"]
    source, protocol = documents["source"], documents["protocol"]
    code_hash = hashlib.sha256(
        "\n\n".join(
            "".join(c["source"]) if isinstance(c["source"], list) else c["source"]
            for c in documents["notebook"]["cells"]
            if c["cell_type"] == "code"
        ).encode()
    ).hexdigest()
    source_hash = checksum(files["source"])
    if (
        frozen["spec_sha256"] != protocol["spec_sha256"]
        or frozen["spec_sha256"] != evaluated["spec_sha256"]
        or frozen["code_sha256"] != code_hash
        or evaluated["code_sha256"] != code_hash
        or checksum(files["model"]) != frozen["bundle_sha256"]
        or evaluated["bundle_sha256"] != frozen["bundle_sha256"]
        or evaluated["new_test_manifest_sha256"] != source_hash
        or protocol["specification"]["new_test_sha256"] != source["output_sha256"]
    ):
        return None
    for relative, expected in frozen["source_hashes"].items():
        path = (root / relative).resolve()
        if not path.is_relative_to(root.resolve()) or checksum(path) != expected:
            return None
    records = [
        ("fit", run / "data/fit-v7.parquet", documents["audit"]["fit_sha256"]),
        ("new_phish360", run / "data/phish360-new.parquet", source["output_sha256"]),
    ]
    if {path.resolve() for path in run.rglob("*.parquet")} != {
        path.resolve() for _, path, _ in records
    }:
        return None
    if (
        frozen["metadata"]["fit_sha256"] != documents["audit"]["fit_sha256"]
        or frozen["metadata"]["new_test_sha256"] != source["output_sha256"]
        or protocol["specification"]["data_audit"] != documents["audit"]
    ):
        return None
    inventory = []
    for role, path, expected in records:
        if not path.is_file() or checksum(path) != expected:
            return None
        inventory.append(
            {
                "role": "v7:" + role,
                "path": path.relative_to(root).as_posix(),
                "sha256": expected,
                "rows": pq.ParquetFile(path).metadata.num_rows,
            }
        )
    return {
        "inventory": inventory,
        "provenance": {
            "run": run.name,
            "spec_sha256": frozen["spec_sha256"],
            "source_manifest_sha256": source_hash,
            "source_scope": "all_manifested_persisted_sources_indexed",
        },
    }
