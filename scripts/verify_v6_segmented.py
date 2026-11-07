"""Verify actual artifacts, chronology, exposure, original V6 and test evidence."""

import argparse
import json
from xml.etree import ElementTree as ET

from guardian_ml.metadata import checksum
from guardian_ml.paths import ROOT
from guardian_ml.rich_artifact import RichArtifact
from experiment_v6_expanded_data import now, write_json
import experiment_v6_segmented as study


def preflight():
    cache = study.check_cache()
    result = {
        "checked_at_utc": now(),
        "cache_sha256": checksum(study.RUN / "cache-frozen.json"),
        "all_sidecars": cache["all_current_sidecars"],
        "isolation": cache["isolation"],
        "observed_benchmark_files": len(cache["observed_test_bindings"]),
        "encoder_fit_rows": cache["encoder_fit_rows"],
        "augmentation_available": cache["augmentation_available"],
        "new_fit_counts": cache["new_fit_counts"],
        "max_native_cache_delta": cache["max_native_cached_delta"],
        "production_ready": False,
    }
    write_json(study.RUN / "preflight-verification.json", result)
    print(json.dumps(result), flush=True)


def final():
    cache, selected = study.check_selected()
    report = study.read(study.REPORT)
    started = study.read(study.RUN / "evaluation-started.json")
    training = study.read(study.RUN / "training-started.json")
    diagnostic = study.read(ROOT / "ml/reports/v6-segmented-subgroup-diagnostics.json")
    if report["cache_freeze"] != cache or report["selected_freeze"] != selected:
        raise ValueError("segmented_report_differs_from_frozen_selection")
    if started["selection_sha256"] != checksum(study.RUN / "selected-frozen.json"):
        raise ValueError("segmented_selection_changed_after_evaluation_started")
    if (
        diagnostic["selected_freeze_sha256"] != started["selection_sha256"]
        or diagnostic["used_to_change_selection"]
    ):
        raise ValueError("segmented_subgroup_diagnostics_changed_selection")
    times = [cache["intake"]["data"]["frozen_at_utc"]]
    if cache["phishbench"]:
        times.append(cache["phishbench"]["data"]["frozen_at_utc"])
    times += [
        cache["started_at_utc"],
        cache["frozen_at_utc"],
        training["started_at_utc"],
        selected["frozen_at_utc"],
        diagnostic["completed_at_utc"],
        started["started_at_utc"],
        report["completed_at_utc"],
    ]
    if any(first >= second for first, second in zip(times, times[1:])):
        raise ValueError("segmented_fit_selection_test_chronology_invalid")
    if (
        selected["max_saved_prediction_delta"] != 0
        or selected["max_cached_inference_delta"] > 1e-12
    ):
        raise ValueError("segmented_real_artifact_parity_invalid")
    totals = dict.fromkeys(("tests", "failures", "errors", "skipped"), 0)
    tree = ET.parse(study.RUN / "final-tests.xml").getroot()
    suites = [tree] if tree.tag == "testsuite" else tree.findall("testsuite")
    for suite in suites:
        for key in totals:
            totals[key] += int(suite.get(key, 0))
    if totals["tests"] < 184 or any(
        totals[k] for k in ("failures", "errors", "skipped")
    ):
        raise ValueError("segmented_required_real_artifact_tests_not_all_passed")
    active = RichArtifact()
    vendor = report["cohorts"]["observed_vendor"]["policies"]["active_original"][
        "confusion_matrix"
    ]
    positive = report["cohorts"]["observed_phishtank_positive"]["policies"][
        "active_original"
    ]["confusion_matrix"]
    if vendor != {"tn": 17621, "fp": 168, "fn": 1187, "tp": 1024} or positive != {
        "tn": 0,
        "fp": 0,
        "fn": 4956,
        "tp": 4313,
    }:
        raise ValueError("frozen_v6_historical_prediction_counts_changed")
    artifact = checksum(ROOT / active.manifest["artifact_path"])
    metadata = checksum(ROOT / active.manifest["frozen_metadata_path"])
    if (
        artifact != "f332bcbf7665955677e17daa73c487a7e1572a18d7f465b87e73caaa72e06319"
        or metadata
        != "4d2e6955af24d0507abce7bdfb65c7af7637183d3e26af75beaaa733846a2fb5"
    ):
        raise ValueError("original_frozen_v6_has_changed")
    review_path = ROOT / "ml/reports/v6-segmented-human-review-status.json"
    reviews = study.read(review_path)
    if reviews["development_review"]["complete_attested_pairs"] != 0:
        raise ValueError("actual_review_status_requires_new_human_evidence_audit")
    write_json(
        ROOT / "ml/reports/v6-segmented-verification.json",
        {
            "verified_at_utc": now(),
            "report_sha256": checksum(study.REPORT),
            "test_totals": totals,
            "test_report_sha256": checksum(study.RUN / "final-tests.xml"),
            "selection": selected["selection"],
            "test_used_for_selection": False,
            "chronology_order_verified": True,
            "new_data_and_previous_tests_isolation": cache["isolation"],
            "observed_benchmark_files_audited": len(cache["observed_test_bindings"]),
            "new_sidecars_preserved": len(cache["all_current_sidecars"]),
            "saved_model_parity_cases": selected["parity_cases"],
            "max_saved_model_delta": selected["max_saved_prediction_delta"],
            "max_cached_inference_delta": selected["max_cached_inference_delta"],
            "original_v6_sha256": artifact,
            "original_metadata_sha256": metadata,
            "original_thresholds": active.metadata["thresholds"],
            "human_review_report_sha256": checksum(review_path),
            "human_gold_or_Indonesia_validation_established": False,
            "production_ready": False,
        },
    )
    print(
        json.dumps(
            {
                "test_totals": totals,
                "selected": selected["selection"]["selected"],
                "original_v6_unchanged": True,
                "production_ready": False,
            }
        ),
        flush=True,
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stage", choices=["preflight", "final"], required=True)
    args = parser.parse_args()
    {"preflight": preflight, "final": final}[args.stage]()


if __name__ == "__main__":
    main()
