"""Blank, incomplete and same-person reviews never establish independent gold."""

import csv
import importlib
import sys

import pytest

from guardian_ml.paths import ROOT

sys.path.insert(0, str(ROOT / "scripts"))
review = importlib.import_module("audit_v6_human_review")
sys.path.pop(0)


def row(**updates):
    result = dict.fromkeys(review.BLIND_COLUMNS, "")
    result.update(
        {"case_id": "opaque-case", "cache_digest": "a" * 64, "cache_filename": "local.parquet"}
    )
    result.update(updates)
    return result


def write(path, value):
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(value))
        writer.writeheader()
        writer.writerow(value)


def complete(**updates):
    return row(
        reviewer_id="actual-reviewer",
        label="uncertain",
        confidence="low",
        human_review_confirmed="true",
        reason_code="insufficient_evidence",
        evidence_ref="publisher-record",
        reviewed_at="2026-11-05T12:00:00+00:00",
        **updates,
    )


def test_blank_and_partial_reviews_are_not_completed():
    assert not review.completed_review(row())
    assert not review.completed_review(row(label="phishing", reviewer_id="person"))
    assert review.completed_review(complete())
    value = complete()
    value["reviewed_at"] = "2026-11-05T12:00:00"
    assert not review.completed_review(value)


def test_two_csvs_with_same_reviewer_do_not_establish_independence(tmp_path):
    first, second = tmp_path / "a.csv", tmp_path / "b.csv"
    write(first, complete())
    write(second, complete())
    result = review.inspect_pair(first, second)
    assert result["same_reviewer_id_pairs_rejected"] == 1
    assert not result["independence_established"] and not result["human_gold_established"]
    assert result["automatic_label_changes"] == 0


def test_blind_pack_cannot_contain_raw_url_or_model_scores(tmp_path):
    first, second = tmp_path / "a.csv", tmp_path / "b.csv"
    write(first, {**row(), "model_score": "0.9"})
    write(second, row())
    with pytest.raises(ValueError, match="blind_and_hash_only"):
        review.inspect_pair(first, second)


def test_review_case_locator_cannot_be_swapped_between_reviewers(tmp_path):
    first, second = tmp_path / "a.csv", tmp_path / "b.csv"
    write(first, row())
    write(second, row(cache_digest="b" * 64))
    with pytest.raises(ValueError, match="locator_mismatch"):
        review.inspect_pair(first, second)
