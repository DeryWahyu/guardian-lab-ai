"""Diagnostic reports preserve missing evidence, privacy and partition boundaries."""

import importlib
import sys

import numpy as np
import pandas as pd
import pytest

from guardian_ml.paths import ROOT
from guardian_ml.rich_artifact import RichArtifact

sys.path.insert(0, str(ROOT / "scripts"))
diagnostics = importlib.import_module("v6_diagnostic_support")
runner = importlib.import_module("evaluate_v6_diagnostics")
sys.path.pop(0)


def test_single_class_diagnostic_does_not_invent_missing_class_rate():
    frame = pd.DataFrame({"group": ["one", "two"], "label": [1, 1]})
    scores = np.array([0.2, 0.8])
    positive = diagnostics.safe_metrics(frame, scores, 0.5, positive_only=True)
    assert positive["accuracy"] is positive["precision"] is positive["fpr"] is None
    assert positive["recall"] == 0.5
    binary_slice = diagnostics.safe_metrics(frame, scores, 0.5)
    assert binary_slice["fpr"] is None
    negative = diagnostics.safe_metrics(frame.assign(label=0), scores, 0.5)
    assert negative["recall"] is None
    with pytest.raises(ValueError, match="positive_only_requires_phishing_labels"):
        diagnostics.safe_metrics(frame.assign(label=[0, 1]), scores, 0.5, positive_only=True)


def test_empty_diagnostic_slice_is_not_reported_as_perfect_zero_error():
    frame = pd.DataFrame({"group": pd.Series(dtype=str), "label": pd.Series(dtype=int)})
    result = diagnostics.safe_metrics(frame, np.array([]), 0.5)
    assert result["rows"] == 0
    assert result["fpr"] is result["recall"] is result["accuracy"] is None


def threshold_frames():
    frame = pd.DataFrame(
        {
            "partition": ["threshold"] * 105,
            "group": [f"g{i}" for i in range(105)],
            "digest": [f"d{i}" for i in range(105)],
            "training_source": ["source"] * 105,
            "label": [0] * 100 + [1] * 5,
        }
    )
    tune = frame.assign(
        partition="tune", group=[f"t{i}" for i in range(105)], digest=[f"u{i}" for i in range(105)]
    )
    return frame, tune


def test_tune_scores_cannot_change_threshold_selected_from_separate_partition():
    threshold, tune = threshold_frames()
    scores = np.linspace(0.01, 0.99, len(threshold))
    first = diagnostics.threshold_diagnostics(threshold, scores, tune, scores, [0.01, 0.05])
    second = diagnostics.threshold_diagnostics(threshold, scores, tune, 1 - scores, [0.01, 0.05])
    assert [item["threshold"] for item in first] == [item["threshold"] for item in second]
    assert first[0]["tune"]["recall"] != second[0]["tune"]["recall"]
    assert all(item["selected_for_serving"] is False for item in first)


@pytest.mark.parametrize("identity", ["group", "digest"])
def test_threshold_diagnostic_rejects_overlap(identity):
    threshold, tune = threshold_frames()
    tune.loc[0, identity] = threshold.loc[0, identity]
    with pytest.raises(ValueError, match="diagnostic_threshold_overlap"):
        diagnostics.threshold_diagnostics(
            threshold, np.linspace(0, 1, 105), tune, np.linspace(0, 1, 105), [0.01]
        )


def test_conflict_audit_and_blind_exports_do_not_invent_labels_or_expose_targets(tmp_path):
    frame = pd.DataFrame(
        {
            "core": ["http://example.org/", "https://example.org/", "https://example.net/path"],
            "digest": ["hash-a", "hash-b", "hash-c"],
            "group": ["example.org", "example.org", "example.net"],
            "label": [0, 1, 0],
            "partition": ["fit"] * 3,
            "training_source": ["one", "two", "one"],
            "date": ["2026-01-01", "2026-01-02", ""],
            "source_split": ["train"] * 3,
        }
    )
    summary, coordinator, blind = diagnostics.label_conflict_audit(frame)
    assert summary["conflicting_representations"] == 1
    assert summary["conflicting_rows"] == 2
    assert summary["cross_source_representations"] == 1
    assert summary["exact_cached_core_conflicts"] == 0
    assert summary["labels_changed"] == summary["true_labels_verified"] == 0
    directory = tmp_path / "review"
    diagnostics.export_review_queues(directory, coordinator, blind)
    for suffix in ("a", "b"):
        text = (directory / f"conflict-reviewer-{suffix}.csv").read_text()
        assert (
            "example.org" not in text
            and "publisher_label" not in text
            and "model_score" not in text
        )
        pack = pd.read_csv(directory / f"conflict-reviewer-{suffix}.csv")
        assert pack.label.isna().all() and pack.reviewer_id.isna().all()


def test_export_rejects_accidental_target_field(tmp_path):
    blind = pd.DataFrame(
        {
            "case_id": ["case"],
            "cache_digest": ["hash"],
            "cache_filename": ["cache"],
            "url": ["SYNTHETIC"],
        }
    )
    with pytest.raises(ValueError, match="unexpected_blind_review_fields"):
        diagnostics.export_review_queues(tmp_path / "review", pd.DataFrame(), blind)


def test_presence_of_review_rows_does_not_prove_independent_review_or_gold(tmp_path):
    (tmp_path / "input").mkdir()
    (tmp_path / "input/indonesia-reviewer-a.csv").write_text(
        "sample_id,reviewer_id\ncase,unverified\n"
    )
    result = diagnostics.indonesia_inventory(tmp_path)
    assert result["actual_input_rows"]["reviewer_a"] == 1
    assert result["independent_reviewer_identity_verified"] is False
    assert result["independent_final_holdout_available"] is False
    assert result["verified_gold_rows"] is None


def test_real_saved_v6_diagnostic_scores_match_loader_and_ignore_query_scheme():
    path = ROOT / "ml/runs/notebook-tfidf-logistic-v6/artifacts/url-core-logistic-v6.joblib"
    if not path.exists():
        pytest.skip("trusted local v6 artifact not installed")
    artifact = RichArtifact()
    frame = pd.DataFrame(
        {"core": ["https://example.org/", "http://example.org/", "https://example.org/login"]}
    )
    scores, flags = runner.scores_and_flags(artifact, frame)
    assert np.allclose(scores, artifact.predict_cores(frame.core), rtol=0, atol=1e-12)
    assert scores[0] == scores[1]
    assert flags.root_path.tolist() == [True, True, False]
