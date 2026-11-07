"""Validate frozen v6 integrity and optionally replay its two local holdouts."""

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path

import numpy as np

from guardian_ml.evaluation import metrics, wilson
from guardian_ml.metadata import checksum
from guardian_ml.paths import ROOT
from guardian_ml.preprocessing import prepare_url
from guardian_ml.rich_artifact import RichArtifact
from guardian_ml.shadow_predictor import ShadowPredictor


def validate(*, evaluate_local=False):
    artifact = RichArtifact()
    reference_path = ROOT / "ml/provenance/v6-runtime-reference.json"
    reference = json.loads(reference_path.read_text(encoding="utf-8"))
    assert reference["artifact_sha256"] == artifact.manifest["bundle_sha256"]
    assert (
        reference["training_notebook_code_sha256"] == artifact.metadata["code_sha256"]
    )
    cores = [prepare_url(case["url"]).core for case in reference["cases"]]
    assert cores == [case["core"] for case in reference["cases"]]
    expected = np.array([case["probability"] for case in reference["cases"]])
    actual = artifact.predict_cores(cores)
    delta = float(np.max(np.abs(expected - actual)))
    assert delta < reference["absolute_tolerance"]
    predictor = ShadowPredictor(artifact)
    assert (
        predictor.predict("https://example.org/login", "URL").model_score
        == predictor.predict("https://example.org/login", "QR").model_score
    )
    report = {
        "validated_at_utc": datetime.now(timezone.utc).isoformat(),
        "scope": "frozen_v6_only_no_training_or_threshold_selection",
        "model_version": artifact.metadata["version"],
        "artifact_sha256": artifact.manifest["bundle_sha256"],
        "frozen_metadata_sha256": artifact.manifest["frozen_metadata_sha256"],
        "runtime_manifest_sha256": checksum(
            ROOT / "ml/policies/shadow-runtime-manifest.json"
        ),
        "serving_manifest_sha256": checksum(
            ROOT / "ml/policies/shadow-serving-manifest.json"
        ),
        "thresholds": artifact.metadata["thresholds"],
        "serving_thresholds": artifact.decision_thresholds,
        "decision_policy_version": artifact.decision_policy_version,
        "synthetic_reference_cases": len(cores),
        "maximum_probability_delta_from_original_notebook": delta,
        "url_qr_parity": True,
        "production_ready": False,
    }
    if evaluate_local:
        import pandas as pd

        original = json.loads(
            (ROOT / "ml/reports/data-improvement-v6.json").read_text()
        )
        data_dir = ROOT / "ml/runs/notebook-tfidf-logistic-v6/data"
        replay = {}
        for name in ("new_deepurlbench_holdout", "new_phishtank_positive"):
            asset = original["data_manifest"]["outputs"][name]
            path = data_dir / asset["filename"]
            assert checksum(path) == asset["sha256"]
            data = pd.read_parquet(path, columns=["core", "label"])
            assert len(data) == asset["rows"]
            scores = artifact.predict_cores(data.core)
            levels = {}
            for level, threshold in artifact.metadata["thresholds"].items():
                if name == "new_phishtank_positive":
                    assert data.label.eq(1).all()
                    tp = int((scores >= threshold).sum())
                    result = {
                        "rows": len(data),
                        "tp": tp,
                        "fn": len(data) - tp,
                        "recall": tp / len(data),
                        "recall_wilson95_rows_iid_assumption": wilson(tp, len(data)),
                        "accuracy": None,
                        "precision": None,
                        "fpr": None,
                    }
                    previous = original["new_community_positive_sensitivity"]["v6"][
                        level
                    ]
                    assert tp == previous["tp"] and result["fn"] == previous["fn"]
                else:
                    result = metrics(data.label, scores, threshold)
                    previous = original["binary_benchmarks"][
                        "new_deepurlbench_domain_holdout"
                    ]["v6"][level]
                    assert result["confusion_matrix"] == previous["confusion_matrix"]
                assert abs(result["recall"] - previous["recall"]) < 1e-12
                levels[level] = result
            replay[name] = levels
        report["replayed_original_v6_holdouts"] = replay
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evaluate-local", action="store_true")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = validate(evaluate_local=args.evaluate_local)
    serialized = json.dumps(report, indent=2, allow_nan=False) + "\n"
    if args.output:
        args.output.write_text(serialized, encoding="utf-8")
        print(f"v6 validation passed; aggregate report: {args.output}")
    else:
        print(serialized)


if __name__ == "__main__":
    main()
