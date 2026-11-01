"""Verify frozen comparison artifacts and measure local end-to-end inference."""

from datetime import datetime, timezone
from pathlib import Path
import time

from catboost import CatBoostClassifier
import joblib
import numpy as np
import pandas as pd
from threadpoolctl import threadpool_limits

from guardian_ml.family_audit import code_hash, write_json
from guardian_ml.family_features import shared_matrix
from guardian_ml.family_scores import probabilities
from guardian_ml.metadata import checksum
from guardian_ml.paths import ROOT


def validate():
    import json

    run = ROOT / "ml/runs/notebook-model-comparison-v9"
    frozen_path = run / "reports/frozen-v9.json"
    frozen = json.loads(frozen_path.read_text())
    spec = frozen["specification"]
    assert (
        code_hash(ROOT / "guardian_lab_url_qr_comparison_v9.ipynb")
        == spec["code_sha256"]
    )
    for path, digest in {**spec["source_hashes"], **frozen["protected"]}.items():
        assert checksum(ROOT / path) == digest
    for asset in spec["benchmark_assets"].values():
        assert checksum(ROOT / asset["path"]) == asset["sha256"]
    benchmark = pd.read_parquet(
        ROOT / spec["benchmark_assets"]["observed_phish360"]["path"]
    )
    probes = benchmark.sample(64, random_state=20261101).core.tolist()
    results = {}
    for name, entry in frozen["models"].items():
        path = ROOT / entry["path"]
        assert checksum(path) == entry["sha256"]
        bundle = joblib.load(path)
        milliseconds = []
        with threadpool_limits(limits=4):
            for _ in range(3):
                probabilities(bundle, probes[:1])
            for core in probes:
                started = time.perf_counter()
                scores = probabilities(bundle, [core])
                milliseconds.append(1000 * (time.perf_counter() - started))
                assert np.isfinite(scores).all()
            item = {
                "artifact_bytes": path.stat().st_size,
                "end_to_end_batch1_rows": len(probes),
                "latency_ms_p50": float(np.percentile(milliseconds, 50)),
                "latency_ms_p95": float(np.percentile(milliseconds, 95)),
                "latency_scope": "local warm batch-one, feature extraction and calibration included",
                "production_latency_claim": False,
            }
            if name == "shared_catboost":
                native = run / "artifacts/catboost-selected.cbm"
                bundle["classifier"].save_model(str(native), format="cbm")
                restored = CatBoostClassifier()
                restored.load_model(str(native), format="cbm")
                matrix = shared_matrix(bundle["shared_encoder"], probes)
                a = bundle["classifier"].predict_proba(matrix, thread_count=4)
                b = restored.predict_proba(matrix, thread_count=4)
                assert np.array_equal(a, b)
                item.update(
                    {
                        "native_classifier_path": str(native.relative_to(ROOT)),
                        "native_classifier_sha256": checksum(native),
                        "native_classifier_exact_probability_parity": True,
                        "native_classifier_needs_frozen_encoder_and_calibrator": True,
                    }
                )
        assert checksum(path) == entry["sha256"]
        results[name] = item
    book = json.loads((ROOT / "guardian_lab_url_qr_comparison_v9.ipynb").read_text())
    code_cells = [c for c in book["cells"] if c["cell_type"] == "code"]
    assert all(c["execution_count"] is not None for c in code_cells)
    assert not any(
        out["output_type"] == "error"
        for c in code_cells
        for out in c.get("outputs", [])
    )
    report = {
        "verified_at_utc": datetime.now(timezone.utc).isoformat(),
        "validator_sha256": checksum(Path(__file__)),
        "frozen_sha256": checksum(frozen_path),
        "evaluation_sha256": checksum(run / "reports/evaluation-v9.json"),
        "code_cells_executed": len(code_cells),
        "notebook_errors": 0,
        "models": results,
        "inference_thread_limit": 4,
        "benchmark_latency_rows_previously_observed": True,
    }
    write_json(ROOT / "ml/reports/model-comparison-validation-v9.json", report)
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    validate()
