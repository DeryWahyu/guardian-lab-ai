"""Protect external evidence from suffix spoofing, leakage and unsupported claims."""

import csv
import importlib
import json
import sys

import numpy as np
import pandas as pd
import pytest

from guardian_ml.paths import ROOT

sys.path.insert(0, str(ROOT / "scripts"))
support = importlib.import_module("v6_indonesia_external_support")
experiment = importlib.import_module("evaluate_v6_indonesia_external")
intake = importlib.import_module("intake_v6_expansion")
curation = importlib.import_module("experiment_v6_expanded_data")
sys.path.pop(0)


def frame(labels):
    return pd.DataFrame({"label": labels, "group": [f"group-{i}" for i in range(len(labels))]})


def test_regional_filter_uses_hostname_boundary_not_path_or_brand():
    data = pd.DataFrame(
        {
            "core": [
                "https://example.co.id/page",
                "https://example.id:8443/page",
                "https://example.id.other.org/page",
                "https://example.org/indonesia/example.id",
                "https://id.example.org/",
                "https://EXAMPLE.ID/",
            ]
        }
    )
    assert support.structure_masks(data)["id_suffix_proxy"].tolist() == [
        True,
        True,
        False,
        False,
        False,
        True,
    ]


def test_single_class_or_empty_does_not_get_binary_accuracy_or_precision():
    for labels, scores in [([], []), ([1, 1], [0.2, 0.9]), ([0, 0], [0.2, 0.3])]:
        result = support.diagnostic_metrics(frame(labels), scores, 0.8, repeats=20)
        assert result["accuracy"] is None
        assert result["precision"] is None
        assert result["brier_score"] is None
    assert support.diagnostic_metrics(frame([1, 1]), [0.2, 0.9], 0.8, 20)["fpr"] is None
    benign = support.diagnostic_metrics(frame([0, 0]), [0.2, 0.3], 0.8, 20)
    assert benign["recall"] is None
    assert benign["fpr_wilson95_rows_iid_assumption"][1] > 0.65


@pytest.mark.parametrize(
    "scores,labels",
    [([np.nan], [1]), ([1.1], [1]), ([-0.1], [0]), ([[0.5]], [1]), ([], [1]), ([0.5], [2])],
)
def test_bad_scores_and_labels_fail_closed(scores, labels):
    with pytest.raises(ValueError, match="invalid_external_diagnostic_input"):
        support.diagnostic_metrics(frame(labels), scores, 0.8)


def test_external_intake_privacy_and_identity_exclusion():
    raw = pd.DataFrame(
        {
            "url": [
                "https://one.example.org/token=short-secret?email=private@example.com",
                "http://one.example.org/token=short-secret",
                "https://two.example.org/other",
                "https://new.example.net/article",
                "http://new.example.net/article",
            ],
            "type": ["legitimate", "legitimate", "phishing", "legitimate", "phishing"],
        }
    )
    data, _ = intake.sanitize_source(raw, "synthetic", "url", "type")
    serialized = data.to_json()
    assert "short-secret" not in serialized and "private@example.com" not in serialized
    assert data.representation_digest.iloc[0] == data.representation_digest.iloc[1]
    data["label"] = data.publisher_label.map({"legitimate": 0, "phishing": 1})
    novel, audit = curation.curate_new(
        [data],
        set(),
        {experiment.digest("example.org")},
        {
            "max_rows_per_domain": 5,
            "split_salt": "test:",
            "group_buckets": {"new_test": 100},
        },
    )
    assert len(novel) == 0
    assert audit["conflict_representations"] == 1
    assert audit["prior_url_or_domain_excluded"] == 2


def write_csv(path, rows, fields):
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def test_empty_inputs_never_produce_indonesia_gold_metrics(tmp_path):
    result = support.audit_human_inputs(tmp_path)
    assert result["indonesia_gold_metrics"] is None
    assert not result["indonesia_gold_established"] and not result["production_ready"]


def test_same_person_and_orphan_reviews_are_reported_without_private_rows(tmp_path):
    write_csv(tmp_path / "candidates.csv", [{"sample_id": "case-1"}], ["sample_id"])
    review = {
        "sample_id": "case-1",
        "reviewer_id": "one-person",
        "label": "phishing",
        "confidence": "high",
        "reason_code": "evidence",
        "evidence_ref": "private-evidence",
        "human_review_confirmed": "true",
        "reviewed_at": "2026-11-06T03:00:00+00:00",
    }
    write_csv(tmp_path / "reviewer-a.csv", [review], list(review))
    write_csv(
        tmp_path / "reviewer-b.csv", [review, {**review, "sample_id": "unknown"}], list(review)
    )
    result = support.audit_human_inputs(tmp_path)
    assert result["issues"]["same_reviewer_pair"] == 1
    assert result["issues"]["orphan_reviews"] == 1
    assert result["syntactically_complete_distinct_id_pairs"] == 0
    assert "private-evidence" not in json.dumps(result)


def test_two_ids_are_not_automatic_proof_of_human_independence(tmp_path):
    write_csv(tmp_path / "candidates.csv", [{"sample_id": "case-1"}], ["sample_id"])
    for name, reviewer_id in [("reviewer-a", "person-a"), ("reviewer-b", "person-b")]:
        review = {
            "sample_id": "case-1",
            "reviewer_id": reviewer_id,
            "label": "benign",
            "confidence": "high",
            "reason_code": "evidence",
            "evidence_ref": "source-ref",
            "human_review_confirmed": "true",
            "reviewed_at": "2026-11-06T03:00:00+00:00",
        }
        write_csv(tmp_path / (name + ".csv"), [review], list(review))
    result = support.audit_human_inputs(tmp_path)
    assert result["syntactically_complete_distinct_id_pairs"] == 1
    assert not result["independent_human_identity_established"]
    assert result["indonesia_gold_metrics"] is None


def test_changed_file_bindings_stop_evaluation(tmp_path, monkeypatch):
    monkeypatch.setattr(experiment, "ROOT", tmp_path)
    (tmp_path / "artifact").write_bytes(b"changed")
    with pytest.raises(ValueError, match="binding_changed"):
        experiment.verify_files({"artifact": "a" * 64})
