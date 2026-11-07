"""Compare with the preceding frozen research candidate without selecting from test."""

import argparse
import json

import joblib
import pandas as pd
from threadpoolctl import threadpool_limits

from guardian_ml.metadata import checksum
from guardian_ml.paths import ROOT
from evaluate_v6_quality import domain_intervals
from experiment_v6_development import paired_intervals
from experiment_v6_expanded_data import now, write_json
from experiment_v6_targeted import RUN, OLD, REPORT, check_freeze
from v6_development_support import predict_bundle
from v6_diagnostic_support import safe_metrics

PROTOCOL = ROOT / "ml/reports/v6-targeted-previous-control-protocol.json"
FROZEN = RUN / "previous-control-frozen.json"
PREVIOUS_REPORT = ROOT / "ml/reports/v6-expanded-data-evaluation.json"
PREVIOUS_ARTIFACT = OLD / "selected-candidate.joblib"
OUTPUT = ROOT / "ml/reports/v6-targeted-previous-control.json"


def freeze():
    if REPORT.exists() or (RUN / "evaluation-started.json").exists() or FROZEN.exists():
        raise ValueError("previous_control_must_freeze_before_targeted_test_scoring")
    previous = json.loads((OLD / "selected-frozen.json").read_text())
    if checksum(PREVIOUS_ARTIFACT) != previous["artifact_sha256"]:
        raise ValueError("previous_expanded_artifact_changed")
    data = check_freeze()
    write_json(
        FROZEN,
        {
            "frozen_at_utc": now(),
            "protocol_sha256": checksum(PROTOCOL),
            "source_sha256": checksum(__file__),
            "previous_artifact_sha256": checksum(PREVIOUS_ARTIFACT),
            "previous_report_sha256": checksum(PREVIOUS_REPORT),
            "new_holdout_sha256": data["partitions"]["new_test"]["sha256"],
            "observed_test_hashes": data["observed_test_hashes"],
            "previous_warning": previous["threshold_selection"]["warning"]["threshold"],
            "changes_candidate_selection": False,
        },
    )
    print(
        "Previous research candidate control frozen before new final scoring",
        flush=True,
    )


def evaluate():
    frozen = json.loads(FROZEN.read_text())
    data = check_freeze()
    if OUTPUT.exists():
        raise ValueError("previous_control_report_already_exists")
    for expected, path in [
        ("source_sha256", __file__),
        ("protocol_sha256", PROTOCOL),
        ("previous_artifact_sha256", PREVIOUS_ARTIFACT),
        ("previous_report_sha256", PREVIOUS_REPORT),
    ]:
        if checksum(path) != frozen[expected]:
            raise ValueError("previous_control_binding_changed")
    if frozen["new_holdout_sha256"] != data["partitions"]["new_test"]["sha256"]:
        raise ValueError("previous_control_holdout_changed")
    selected = json.loads((RUN / "selected-frozen.json").read_text())
    if checksum(ROOT / selected["artifact"]) != selected["artifact_sha256"]:
        raise ValueError("new_selected_artifact_changed")
    main = json.loads(REPORT.read_text())
    previous_report = json.loads(PREVIOUS_REPORT.read_text())
    frame = pd.read_parquet(ROOT / data["partitions"]["new_test"]["path"])
    previous = joblib.load(PREVIOUS_ARTIFACT)
    candidate = joblib.load(ROOT / selected["artifact"])
    old_scores = predict_bundle(previous, frame.core)
    new_scores = predict_bundle(candidate, frame.core)
    threshold = selected["candidate_policies"][selected["selection"]["candidate"]][
        "strict_source_1pct"
    ]["threshold"]
    previous_metrics = safe_metrics(frame, old_scores, frozen["previous_warning"])
    previous_metrics["domain_bootstrap95"] = domain_intervals(
        frame, old_scores, frozen["previous_warning"], 1000, 20261105
    )
    results = {
        "new_pwd_domain_holdout": {
            "rows": len(frame),
            "previous_candidate": previous_metrics,
            "new_candidate": main["cohorts"]["new_pwd_domain_holdout"]["policies"][
                "candidate_strict_source_1pct"
            ],
            "paired_delta_new_minus_previous": paired_intervals(
                frame,
                old_scores,
                new_scores,
                [frozen["previous_warning"], threshold],
                1000,
                20261105,
                False,
            ),
        }
    }
    mapping = {
        "observed_expanded_domain_holdout": "new_domain_holdout",
        "observed_vendor": "observed_vendor",
        "observed_phishtank_positive": "observed_phishtank_positive",
        "observed_legitphish": "observed_legitphish",
    }
    for key, previous_key in mapping.items():
        prior = previous_report["cohorts"][previous_key]
        current = main["cohorts"][key]
        if prior["rows"] != current["rows"]:
            raise ValueError("previous_aggregate_cohort_count_mismatch")
        results[key] = {
            "rows": current["rows"],
            "previously_observed": True,
            "previous_candidate": prior["models"]["candidate"]["warning"],
            "new_candidate": current["policies"]["candidate_strict_source_1pct"],
            "previous_metrics_reused_from_hash_bound_aggregate_report": True,
        }
    write_json(
        OUTPUT,
        {
            "completed_at_utc": now(),
            "control_freeze": frozen,
            "main_report_sha256": checksum(REPORT),
            "cohorts": results,
            "production_ready": False,
            "selection_changed_after_test": False,
        },
    )
    print("Previous research candidate comparison complete", flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stage", choices=["freeze", "evaluate"], required=True)
    args = parser.parse_args()
    with threadpool_limits(limits=2):
        {"freeze": freeze, "evaluate": evaluate}[args.stage]()
