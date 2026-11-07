"""Bind final technical checks to completed reports, artifacts and exposure state."""

from importlib.metadata import version
import json
import xml.etree.ElementTree as ET

import pandas as pd

from guardian_ml.metadata import checksum
from guardian_ml.paths import ROOT
from guardian_ml.rich_artifact import RichArtifact
from experiment_v6_expanded_data import write_json, now
from experiment_v6_targeted import RUN, REPORT, PARTS, check_freeze
from v6_development_support import assert_separated


def main():
    data = check_freeze()
    selected = json.loads((RUN / "selected-frozen.json").read_text())
    report = json.loads(REPORT.read_text())
    previous = json.loads(
        (ROOT / "ml/reports/v6-targeted-previous-control.json").read_text()
    )
    started = json.loads((RUN / "evaluation-started.json").read_text())
    if selected != report["selected_freeze"] or data != report["data_freeze"]:
        raise ValueError("reported_data_or_selection_differ_from_frozen_run")
    if checksum(ROOT / selected["artifact"]) != selected["artifact_sha256"]:
        raise ValueError("selected_model_artifact_changed")
    if checksum(REPORT) != previous["main_report_sha256"]:
        raise ValueError("main_report_changed_after_previous_control")
    if checksum(RUN / "selected-frozen.json") != started["selected_freeze_sha256"]:
        raise ValueError("selection_changed_after_test_started")
    if (
        not previous["control_freeze"]["frozen_at_utc"]
        < selected["frozen_at_utc"]
        < started["started_at_utc"]
        < report["completed_at_utc"]
    ):
        raise ValueError("control_selection_and_test_freeze_order_invalid")
    if selected["max_reload_delta"] != 0 or selected["parity_cases"] < 130:
        raise ValueError("real_saved_model_parity_incomplete")
    assert_separated(
        [
            pd.read_parquet(
                ROOT / data["partitions"][name]["path"],
                columns=["group", "digest", "representation_digest"],
            )
            for name in PARTS
        ]
    )
    test_path = RUN / "final-tests.xml"
    suites = ET.parse(test_path).getroot()
    totals = {
        key: sum(int(suite.get(key, 0)) for suite in suites.iter("testsuite"))
        for key in ["tests", "failures", "errors", "skipped"]
    }
    if totals["tests"] < 132 or any(
        totals[key] for key in ["failures", "errors", "skipped"]
    ):
        raise ValueError("technical_suite_incomplete_or_not_clean")
    active = RichArtifact()
    vendor = report["cohorts"]["observed_vendor"]["policies"]["v6_original"]
    feed = report["cohorts"]["observed_phishtank_positive"]["policies"]["v6_original"]
    if (
        vendor["confusion_matrix"]["tp"] != 1024
        or feed["confusion_matrix"]["tp"] != 4313
    ):
        raise ValueError("original_v6_regression_reference_changed")
    verification = {
        "verified_at_utc": now(),
        "main_report_sha256": checksum(REPORT),
        "previous_control_report_sha256": checksum(
            ROOT / "ml/reports/v6-targeted-previous-control.json"
        ),
        "selected_model_sha256": selected["artifact_sha256"],
        "frozen_v6_model_sha256": active.manifest["bundle_sha256"],
        "frozen_v6_metadata_sha256": active.manifest["frozen_metadata_sha256"],
        "runtime_versions": {
            name: version(name) for name in active.manifest["inference_dependencies"]
        },
        "tests": totals,
        "test_report_sha256": checksum(test_path),
        "domain_digest_representation_isolation": True,
        "all_exposure_hashes_unchanged": True,
        "control_and_selection_frozen_before_test_scoring": True,
        "real_artifact_parity_cases": selected["parity_cases"],
        "max_saved_model_prediction_delta": selected["max_reload_delta"],
        "production_ready": False,
        "Indonesia_gold_established": False,
        "technical_checks_do_not_establish_label_truth_or_detection_quality": True,
    }
    write_json(ROOT / "ml/reports/v6-targeted-verification.json", verification)
    print(json.dumps(verification), flush=True)


if __name__ == "__main__":
    main()
