"""Verify completed external evaluation without rerunning or selecting from final scores."""

from datetime import datetime
import json
import sqlite3
import xml.etree.ElementTree as ET

import pandas as pd

from guardian_ml.metadata import checksum
from guardian_ml.paths import ROOT
from guardian_ml.rich_artifact import RichArtifact
import evaluate_v6_indonesia_external as study
from experiment_v6_expanded_data import now, write_json
from v6_development_support import representation_digest


def main():
    frozen = study.check_freeze()
    report = study.read(study.REPORT)
    evidence_path = ROOT / "ml/reports/v6-indonesia-evidence-status.json"
    evidence = study.read(evidence_path)
    if evidence["external_report_sha256"] != checksum(study.REPORT):
        raise ValueError("external_evidence_census_binding_mismatch")
    from audit_v6_indonesia_evidence import census

    if evidence["indonesia_inputs"] != census(
        ROOT / "ml/data/indonesia-gold/input", ROOT / "ml/templates"
    ):
        raise ValueError("external_indonesia_evidence_inputs_changed")
    started = study.read(study.RUN / "evaluation-started.json")
    if started["freeze_sha256"] != checksum(study.DATA / "frozen.json"):
        raise ValueError("external_freeze_replaced_after_prediction")
    chronology = [
        frozen["started_at_utc"],
        frozen["frozen_at_utc"],
        started["started_at_utc"],
        report["completed_at_utc"],
    ]
    moments = [datetime.fromisoformat(value) for value in chronology]
    if moments != sorted(moments):
        raise ValueError("external_evaluation_chronology_invalid")
    if report["intake_freeze"] != frozen or report["protocol"] != study.read(
        study.PROTOCOL
    ):
        raise ValueError("external_report_binding_mismatch")
    frame = pd.read_parquet(ROOT / frozen["assets"]["reserved"]["path"])
    urls = set(frame.digest) | set(frame.core.map(representation_digest))
    domains = set(frame.group.map(study.digest))
    audit = {}
    # Check against the actual pre-intake exposure snapshot; own sidecar must contain
    # every supported row and is intentionally not treated as pre-intake exposure.
    for name in frozen["prior_exposure_hashes"]:
        path = ROOT / name
        if path.suffix == ".sqlite":
            with sqlite3.connect(
                path.resolve().as_uri() + "?mode=ro", uri=True
            ) as connection:
                url_overlap = sum(
                    value in urls
                    for (value,) in connection.execute("SELECT value FROM url_hashes")
                )
                group_overlap = sum(
                    value in domains
                    for (value,) in connection.execute(
                        "SELECT value FROM domain_hashes"
                    )
                )
        else:
            old = pd.read_parquet(path, columns=["core", "group", "digest"])
            url_overlap = len(
                urls & (set(old.digest) | set(old.core.map(representation_digest)))
            )
            group_overlap = len(domains & set(old.group.map(study.digest)))
        if url_overlap or group_overlap:
            raise ValueError("external_reserved_cases_have_prior_exposure")
        audit[name] = {
            "url_or_representation_overlap": url_overlap,
            "domain_overlap": group_overlap,
        }
    for name in frozen["actual_identity_hashes"]:
        old = pd.read_parquet(ROOT / name, columns=["core", "group", "digest"])
        overlap = {
            "url_or_representation_overlap": len(
                urls & (set(old.digest) | set(old.core.map(representation_digest)))
            ),
            "domain_overlap": len(domains & set(old.group.map(study.digest))),
        }
        if any(overlap.values()):
            raise ValueError("external_reserved_cases_overlap_actual_partition")
        audit[name] = overlap
    supported = pd.read_parquet(ROOT / frozen["assets"]["supported"]["path"])
    with sqlite3.connect(
        study.SIDECAR.resolve().as_uri() + "?mode=ro", uri=True
    ) as connection:
        registered_urls = {
            row[0] for row in connection.execute("SELECT value FROM url_hashes")
        }
        registered_domains = {
            row[0] for row in connection.execute("SELECT value FROM domain_hashes")
        }
    if (
        not (set(supported.digest) | set(supported.representation_digest))
        <= registered_urls
        or not set(supported.group.map(study.digest)) <= registered_domains
    ):
        raise ValueError("external_supported_exposure_not_fully_registered")
    xml_path = study.RUN / "final-tests.xml"
    suites = list(ET.parse(xml_path).getroot().iter("testsuite"))
    tests = {
        key: sum(int(suite.attrib.get(key, 0)) for suite in suites)
        for key in ("tests", "failures", "errors", "skipped")
    }
    if tests["tests"] < 202 or any(
        tests[key] for key in ("failures", "errors", "skipped")
    ):
        raise ValueError("external_verification_test_suite_incomplete")
    active = RichArtifact()
    if (
        checksum(ROOT / active.manifest["frozen_metadata_path"])
        != "4d2e6955af24d0507abce7bdfb65c7af7637183d3e26af75beaaa733846a2fb5"
    ):
        raise ValueError("original_v6_metadata_changed")
    if (
        report["actual_model_fits"]
        or report["test_used_for_model_selection"]
        or report["production_ready"]
    ):
        raise ValueError("external_evaluation_misstates_scope")
    for entry in report["saved_model_parity"].values():
        if max(entry["active_max_delta"], entry["research_max_delta"]) > 1e-12:
            raise ValueError("external_prediction_parity_failed")
    result = {
        "verified_at_utc": now(),
        "report_sha256": checksum(study.REPORT),
        "source_sha256": checksum(__file__),
        "test_report_sha256": checksum(xml_path),
        "tests": tests,
        "chronology_verified": True,
        "reserved_rows": len(frame),
        "reserved_domains": int(frame.group.nunique()),
        "isolation": audit,
        "all_supported_rows_registered": True,
        "saved_model_parity": report["saved_model_parity"],
        "original_v6_metadata_and_binary_unchanged": True,
        "independent_indonesia_gold_evaluation_completed": False,
        "human_validation": evidence,
        "human_evidence_status_sha256": checksum(evidence_path),
        "production_ready": False,
    }
    write_json(ROOT / "ml/reports/v6-indonesia-external-verification.json", result)
    print(
        json.dumps(
            {
                "tests": tests,
                "isolated_reserved_rows": len(frame),
                "audited_sources_and_caches": len(audit),
                "production_ready": False,
            }
        )
    )


if __name__ == "__main__":
    main()
