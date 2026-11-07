"""Supplemental comparison at development-matched FPR; original v6 stays intact."""

import argparse
import json

import joblib
import pandas as pd
from threadpoolctl import threadpool_limits

from guardian_ml.metadata import checksum
from guardian_ml.paths import ROOT
from guardian_ml.rich_artifact import RichArtifact
from evaluate_v6_quality import domain_intervals
from experiment_v6_development import paired_intervals
from experiment_v6_expanded_data import PROTOCOL, RUN, check_freeze, source_point
from v6_development_support import predict_bundle
from v6_diagnostic_support import safe_metrics

SUPPLEMENT = ROOT / "ml/reports/v6-expanded-matched-control-protocol.json"
POLICY = RUN / "matched-v6-control.json"
REPORT = ROOT / "ml/reports/v6-expanded-matched-control.json"


def write(path, value):
    path.write_bytes((json.dumps(value, indent=2, allow_nan=False) + "\n").encode())


def freeze():
    if POLICY.exists():
        raise ValueError("matched_control_already_frozen")
    if (ROOT / "ml/reports/v6-expanded-data-evaluation.json").exists():
        raise ValueError("matched_control_must_be_frozen_before_test")
    data = check_freeze()
    protocol = json.loads(PROTOCOL.read_text())
    frame = pd.read_parquet(ROOT / data["partitions"]["threshold"]["path"])
    model = RichArtifact()
    scores = model.predict_cores(frame.core)
    policies = {
        level: source_point(frame, scores, budget, "threshold", protocol)
        for level, budget in (("warning", 0.01), ("high", 0.001))
    }
    from datetime import datetime, timezone

    write(
        POLICY,
        {
            "frozen_at_utc": datetime.now(timezone.utc).isoformat(),
            "supplement_sha256": checksum(SUPPLEMENT),
            "script_sha256": checksum(__file__),
            "data_freeze_sha256": checksum(RUN / "data-freeze.json"),
            "policies": policies,
            "original_model_sha256": model.manifest["bundle_sha256"],
            "original_serving_thresholds": model.metadata["thresholds"],
            "test_predictions_seen": False,
        },
    )
    print(
        "Matched v6 control thresholds fixed before final test; original policy unchanged",
        flush=True,
    )


def evaluate():
    if REPORT.exists():
        raise ValueError("matched_control_report_already_exists")
    policy = json.loads(POLICY.read_text())
    if (
        checksum(SUPPLEMENT) != policy["supplement_sha256"]
        or checksum(__file__) != policy["script_sha256"]
    ):
        raise ValueError("matched_control_protocol_or_source_changed")
    data = check_freeze()
    selected = json.loads((RUN / "selected-frozen.json").read_text())
    if checksum(RUN / "selected-candidate.joblib") != selected["artifact_sha256"]:
        raise ValueError("candidate_changed")
    bundle = joblib.load(RUN / "selected-candidate.joblib")
    model = RichArtifact()
    protocol = json.loads(PROTOCOL.read_text())
    paths = {
        "new_domain_holdout": ROOT / data["partitions"]["new_test"]["path"],
        "observed_vendor": ROOT
        / "ml/runs/notebook-tfidf-logistic-v6/data/deepurlbench-holdout-v6.parquet",
        "observed_phishtank_positive": ROOT
        / "ml/runs/notebook-tfidf-logistic-v6/data/phishtank-2026-v6.parquet",
        "observed_legitphish": ROOT
        / "ml/data/legitphish-v2-v6-qa/sanitized-domain-disjoint.parquet",
    }
    results = {}
    for name, path in paths.items():
        frame = pd.read_parquet(path)
        original, candidate = (
            model.predict_cores(frame.core),
            predict_bundle(bundle, frame.core),
        )
        positive_only = frame.label.eq(1).all()
        levels = {}
        for level in ("warning", "high"):
            control_threshold = policy["policies"][level]["threshold"]
            candidate_threshold = bundle["metadata"]["thresholds"][level]
            row = safe_metrics(frame, original, control_threshold, positive_only)
            row["domain_bootstrap95"] = domain_intervals(
                frame,
                original,
                control_threshold,
                1000,
                protocol["seed"],
                positive_only,
            )
            levels[level] = {
                "v6_matched_control": row,
                "candidate": safe_metrics(
                    frame, candidate, candidate_threshold, positive_only
                ),
                "paired_delta95": paired_intervals(
                    frame,
                    original,
                    candidate,
                    [control_threshold, candidate_threshold],
                    1000,
                    protocol["seed"],
                    positive_only,
                ),
            }
        results[name] = levels
        print("Supplemental matched-policy evaluation: " + name, flush=True)
    write(
        REPORT,
        {
            "policy": policy,
            "cohorts": results,
            "late_declared_before_final_test": True,
            "candidate_selection_changed": False,
            "original_v6_policy_preserved": True,
            "production_ready": False,
        },
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stage", choices=["freeze", "evaluate"], required=True)
    args = parser.parse_args()
    with threadpool_limits(limits=4):
        freeze() if args.stage == "freeze" else evaluate()


if __name__ == "__main__":
    main()
