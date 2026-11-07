"""Verify real identity isolation, chronology, artifacts and completed test evidence."""

import argparse
import json
import xml.etree.ElementTree as ET

import pandas as pd

from guardian_ml.metadata import checksum
from guardian_ml.paths import ROOT
from guardian_ml.rich_artifact import RichArtifact
from experiment_v6_expanded_data import now, write_json
import experiment_v6_targeted as previous
import experiment_v6_weighted as study
from v6_development_support import representation_digest


def identities(path):
    frame = pd.read_parquet(path, columns=["core", "group", "digest"])
    return {
        "group": set(frame.group),
        "digest": set(frame.digest),
        "representation_digest": set(frame.core.map(representation_digest)),
    }


def preflight():
    protocol = study.read_json(study.PROTOCOL)
    holdout = study.holdout_binding(protocol)
    if not holdout["data"].get("available"):
        raise ValueError("independent_public_holdout_not_available")
    new = identities(ROOT / holdout["data"]["path"])
    data = study.read_json(previous.RUN / "data-freeze.json")
    paths = [ROOT / data["partitions"][name]["path"] for name in previous.PARTS]
    paths += [
        previous.OLD / "new_test.parquet",
        ROOT
        / "ml/runs/notebook-tfidf-logistic-v6/data/deepurlbench-holdout-v6.parquet",
        ROOT / "ml/runs/notebook-tfidf-logistic-v6/data/phishtank-2026-v6.parquet",
        ROOT / "ml/data/legitphish-v2-v6-qa/sanitized-domain-disjoint.parquet",
    ]
    audited = {}
    for path in paths:
        old = identities(path)
        overlap = {key: len(new[key].intersection(old[key])) for key in new}
        if any(overlap.values()):
            raise ValueError("new_holdout_identity_overlap")
        audited[path.relative_to(ROOT).as_posix()] = {
            "sha256": checksum(path),
            "overlap": overlap,
        }
    result = {
        "completed_at_utc": now(),
        "new_holdout_freeze_sha256": holdout["freeze_sha256"],
        "audited": audited,
        "source_sha256": checksum(__file__),
        "no_model_predictions_performed": True,
    }
    path = study.RUN / "holdout-isolation.json"
    if path.exists():
        raise ValueError("holdout_isolation_already_recorded")
    write_json(path, result)
    print(
        json.dumps(
            {
                "new_holdout_domains": len(new["group"]),
                "audited_files": len(audited),
                "all_identity_overlaps": 0,
            }
        ),
        flush=True,
    )


def final():
    protocol = study.read_json(study.PROTOCOL)
    cache, selected = study.check_selected(protocol)
    report = study.read_json(study.REPORT)
    isolation = study.read_json(study.RUN / "holdout-isolation.json")
    started = study.read_json(study.RUN / "evaluation-started.json")
    subgroup = study.read_json(
        ROOT / "ml/reports/v6-weighted-subgroup-diagnostics.json"
    )
    if selected != report["selected_freeze"] or cache != report["cache_freeze"]:
        raise ValueError("weighted_report_differs_from_frozen_run")
    if checksum(study.RUN / "selected-frozen.json") != started["selected_sha256"]:
        raise ValueError("weighted_selection_changed_after_scoring")
    if (
        not selected["holdout"]["data"]["frozen_at_utc"]
        < isolation["completed_at_utc"]
        < selected["training_started_at_utc"]
        < selected["frozen_at_utc"]
        < subgroup["completed_at_utc"]
        < started["started_at_utc"]
        < report["completed_at_utc"]
    ):
        raise ValueError("weighted_fitting_freeze_and_test_order_invalid")
    if subgroup["selected_freeze_sha256"] != started["selected_sha256"]:
        raise ValueError("subgroup_diagnostics_differ_from_frozen_model_choice")
    if isolation["new_holdout_freeze_sha256"] != selected["holdout"]["freeze_sha256"]:
        raise ValueError("new_holdout_changed_since_isolation_audit")
    for name, asset in isolation["audited"].items():
        if checksum(ROOT / name) != asset["sha256"]:
            raise ValueError("isolated_data_changed")
    if (
        selected["max_saved_prediction_delta"] != 0
        or selected["parity_cases"] < 130
        or selected["max_cached_inference_delta"] > 1e-12
    ):
        raise ValueError("weighted_real_artifact_parity_incomplete")
    tree = ET.parse(study.RUN / "final-tests.xml").getroot()
    totals = {
        key: sum(int(node.get(key, 0)) for node in tree.iter("testsuite"))
        for key in ("tests", "failures", "errors", "skipped")
    }
    if totals["tests"] < 158 or any(
        totals[key] for key in ("failures", "errors", "skipped")
    ):
        raise ValueError("weighted_full_test_suite_not_clean")
    active = RichArtifact()
    vendor = report["cohorts"]["observed_vendor"]["policies"]["active_original"]
    feed = report["cohorts"]["observed_phishtank_positive"]["policies"][
        "active_original"
    ]
    if (
        vendor["confusion_matrix"]["tp"] != 1024
        or feed["confusion_matrix"]["tp"] != 4313
    ):
        raise ValueError("frozen_v6_reference_predictions_changed")
    verification = {
        "verified_at_utc": now(),
        "main_report_sha256": checksum(study.REPORT),
        "audit_sha256": checksum(study.AUDIT),
        "test_totals": totals,
        "test_report_sha256": checksum(study.RUN / "final-tests.xml"),
        "model_selection": selected["selection"],
        "new_holdout_isolation_audited_files": len(isolation["audited"]),
        "fit_calibration_threshold_tune_and_observed_benchmarks_disjoint_from_new_holdout": True,
        "encoder_refit_on_holdouts": False,
        "model_selected_from_test": False,
        "saved_model_parity_cases": selected["parity_cases"],
        "max_saved_model_delta": selected["max_saved_prediction_delta"],
        "max_cached_inference_delta": selected["max_cached_inference_delta"],
        "original_v6_sha256": active.manifest["bundle_sha256"],
        "original_metadata_sha256": active.manifest["frozen_metadata_sha256"],
        "human_gold_or_Indonesia_validation_established": False,
        "production_ready": False,
    }
    write_json(ROOT / "ml/reports/v6-weighted-verification.json", verification)
    print(json.dumps(verification), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stage", choices=["preflight", "final"], required=True)
    args = parser.parse_args()
    {"preflight": preflight, "final": final}[args.stage]()
