"""Register completed pre-training intake and verified data reuse, without inventing training."""

import json
from pathlib import Path

import pyarrow.parquet as pq

from .family_audit import code_hash
from .metadata import checksum


def completed_v9_reuse(root):
    root = Path(root)
    run = root / "ml/runs/notebook-model-comparison-v9"
    frozen_path = run / "reports/frozen-v9.json"
    if not frozen_path.is_file():
        return None
    frozen = json.loads(frozen_path.read_text())
    evaluated = json.loads((run / "reports/evaluation-v9.json").read_text())
    if evaluated["frozen_sha256"] != checksum(frozen_path) or any(run.rglob("*.parquet")):
        return None
    spec = frozen["specification"]
    if code_hash(root / "guardian_lab_url_qr_comparison_v9.ipynb") != spec["code_sha256"]:
        return None
    for name, digest in {**spec["source_hashes"], **frozen["protected"]}.items():
        if checksum(root / name) != digest:
            return None
    for item in frozen["models"].values():
        if checksum(root / item["path"]) != item["sha256"]:
            return None
    return {
        "run": run.name,
        "source_scope": "verified_v8_data_and_observed_benchmarks_only",
        "spec_sha256": frozen["spec_sha256"],
        "new_urls": 0,
    }


def completed_v10_intake(root):
    root = Path(root)
    run = root / "ml/runs/notebook-recall-cnn-v10"
    path = run / "reports/public-intake-manifest.json"
    audit_path = run / "reports/development-error-audit.json"
    if not path.is_file() or not audit_path.is_file():
        return None
    manifest = json.loads(path.read_text())
    audit = json.loads(audit_path.read_text())
    if checksum(root / "ai-agent-docs/recall-cnn-v10-plan.md") != manifest["protocol_sha256"]:
        return None
    if checksum(run / "reports/development-audit-protocol.md") != audit["protocol_sha256"]:
        return None
    if checksum(root / "ml/src/guardian_ml/recall_audit.py") != audit["audit_source_sha256"]:
        return None
    expected, inventory = set(), []
    entries = {
        **manifest["outputs"],
        "development_error_cases": {"path": audit["cases_path"], "sha256": audit["cases_sha256"]},
    }
    for role, item in entries.items():
        file = (root / item["path"]).resolve()
        if not file.is_relative_to(run.resolve()) or checksum(file) != item["sha256"]:
            return None
        schema = pq.ParquetFile(file)
        if not {"digest", "group"}.issubset(schema.schema.names):
            return None
        expected.add(file)
        inventory.append(
            {
                "role": "v10:" + role,
                "path": file.relative_to(root).as_posix(),
                "sha256": item["sha256"],
                "rows": schema.metadata.num_rows,
            }
        )
    if expected != {p.resolve() for p in run.rglob("*.parquet")}:
        return None
    return {
        "inventory": inventory,
        "provenance": {
            "run": run.name,
            "source_scope": "completed_intake_not_model_training",
            "intake_manifest_sha256": checksum(path),
            "cnn_trained": False,
        },
    }
