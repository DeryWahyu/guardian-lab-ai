"""Assess research evidence; missing human evidence is never an implicit approval."""

import json
from pathlib import Path

from .paths import ROOT


def assess_release(root=ROOT):
    root = Path(root)
    policy = json.loads((root / "ml/policies/url-qr-release-gates.json").read_text())
    report_path = root / "ml/reports/data-improvement-v6.json"
    pending = [
        "independent_indonesian_human_gold_set",
        "two_human_reviews_privacy_provenance_and_adjudication",
        "campaign_time_segment_and_regression_review",
        "contemporary_benign_traffic_evidence",
    ]
    findings = []
    if report_path.exists():
        report = json.loads(report_path.read_text())
        vendor = report["binary_benchmarks"]["new_deepurlbench_domain_holdout"]["v6"]["warning"]
        community = report["new_community_positive_sensitivity"]["v6"]["warning"]
        for name, passed, value, target in [
            (
                "vendor_recall_lower95",
                vendor["recall_wilson95_rows_iid_assumption"][0]
                >= policy["recall_lower_wilson95_min"],
                vendor["recall_wilson95_rows_iid_assumption"][0],
                policy["recall_lower_wilson95_min"],
            ),
            (
                "vendor_fpr_upper95",
                vendor["fpr_wilson95_rows_iid_assumption"][1] <= policy["fpr_upper_wilson95_max"],
                vendor["fpr_wilson95_rows_iid_assumption"][1],
                policy["fpr_upper_wilson95_max"],
            ),
            (
                "community_recall_lower95",
                community["recall_wilson95_rows_iid_assumption"][0]
                >= policy["recall_lower_wilson95_min"],
                community["recall_wilson95_rows_iid_assumption"][0],
                policy["recall_lower_wilson95_min"],
            ),
        ]:
            findings.append(
                {
                    "criterion": name,
                    "status": "passed" if passed else "failed",
                    "observed": value,
                    "target": target,
                }
            )
    else:
        pending.append("measured_evaluation_report")
    return {
        "status": "not_ready",
        "production_ready": False,
        "shadow_allowed": policy["allow_shadow_service"],
        "policy_version": policy["schema_version"],
        "findings": findings,
        "pending_evidence": pending,
        "interpretation": "Research measurements do not replace Indonesian human-validation evidence.",
    }
