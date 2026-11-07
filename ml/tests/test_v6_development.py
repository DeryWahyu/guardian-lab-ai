"""Privacy, data isolation and decision guards for the separate LR experiment."""

import importlib
import sys

import numpy as np
import pandas as pd
import pytest

from guardian_ml.paths import ROOT
from guardian_ml.preprocessing import InvalidUrl, prepare_url

sys.path.insert(0, str(ROOT / "scripts"))
research = importlib.import_module("v6_development_support")
runner = importlib.import_module("experiment_v6_development")
sys.path.pop(0)


@pytest.mark.parametrize(
    "path",
    [
        "/password=SHORTVALUE",
        "/password/SHORTVALUE",
        "/reset;token=SHORTVALUE",
        "/%70assword%3DSHORTVALUE",
        "/%2570assword%253DSHORTVALUE",
        "/api-key:SHORTVALUE",
        "/reset;token=SHORTVALUE;otp=OTHERSECRET",
        "/login?token=SHORTVALUE#OTHERSECRET",
    ],
)
def test_experiment_redacts_short_path_assignments_and_is_idempotent(path):
    result = research.prepare_experiment_url("https://example.org" + path)
    assert "SHORTVALUE" not in result.core and "OTHERSECRET" not in result.core
    assert research.prepare_experiment_url(result.core).core == result.core
    assert prepare_url(result.core).core == result.core
    assert result.group == "example.org"


def test_frozen_parser_is_not_silently_replaced():
    url = "https://example.org/password=SHORTVALUE"
    assert "SHORTVALUE" in prepare_url(url).core
    assert "SHORTVALUE" not in research.prepare_experiment_url(url).core


def test_unsupported_experiment_input_has_fixed_error_without_input():
    with pytest.raises(InvalidUrl) as error:
        research.prepare_experiment_url("https://user:SHORTVALUE@example.org/")
    assert "SHORTVALUE" not in str(error.value)


@pytest.mark.parametrize("identity", ["group", "digest", "representation_digest"])
def test_separation_guard_rejects_each_identity_overlap(identity):
    first = pd.DataFrame({"group": ["a"], "digest": ["b"], "representation_digest": ["c"]})
    second = pd.DataFrame({"group": ["d"], "digest": ["e"], "representation_digest": ["f"]})
    second.loc[0, identity] = first.loc[0, identity]
    with pytest.raises(ValueError, match="partition_overlap_" + identity):
        research.assert_separated([first, second])


def test_fit_curation_quarantines_conflicts_without_relabel_and_rejects_holdout():
    frame = pd.DataFrame(
        {
            "partition": ["fit"] * 5,
            "digest": ["e", "d", "c", "b", "a"],
            "representation_digest": ["conflict", "conflict", "same", "same", "unique"],
            "label": [0, 1, 1, 1, 0],
        }
    )
    clean, report = research.curate_fit(frame)
    assert clean.digest.tolist() == ["a", "b"]
    assert clean.label.tolist() == [0, 1]
    assert report["conflicting_fit_rows_quarantined"] == 2
    assert report["consistent_duplicate_fit_rows_removed"] == 1
    with pytest.raises(ValueError, match="unexpected_partition_for_fit"):
        research.curate_fit(frame.assign(partition="tune"))


def test_encoder_cannot_fit_holdout_and_has_no_holdout_vocabulary():
    fit = pd.DataFrame(
        {
            "core": ["https://example.org/common/train"] * 4
            + ["https://example.com/common/fit"] * 4,
            "training_source": ["synthetic"] * 8,
            "partition": ["fit"] * 8,
        }
    )
    encoder, _ = research.fit_encoder(fit, 7)
    vocab_before = dict(encoder["word"].vocabulary_)
    research.feature_matrix(encoder, ["https://example.net/unseenholdouttoken"])
    assert encoder["word"].vocabulary_ == vocab_before
    assert "unseenholdouttoken" not in vocab_before
    with pytest.raises(ValueError, match="unexpected_partition_for_fit"):
        research.fit_encoder(fit.assign(partition="calibration"), 7)


def test_threshold_respects_source_budget_with_ties_and_wrong_partition_rejected():
    frame = pd.DataFrame(
        {
            "label": [0] * 100 + [1] * 4,
            "training_source": ["a"] * 104,
            "partition": ["threshold"] * 104,
        }
    )
    scores = np.array([0.2] * 98 + [0.8, 0.8] + [0.9] * 4)
    result = research.source_threshold(frame, scores, 0.01, "threshold")
    assert result["threshold"] > 0.8
    assert result["source_rates"]["a"]["fpr"] == 0
    assert result["source_rates"]["a"]["recall"] == 1
    with pytest.raises(ValueError, match="unexpected_partition_for_threshold"):
        research.source_threshold(frame.assign(partition="fit"), scores, 0.01, "threshold")


def test_source_class_weights_balance_training_mass_within_each_source():
    fit = pd.DataFrame(
        {
            "partition": ["fit"] * 8,
            "training_source": ["a"] * 4 + ["b"] * 4,
            "label": [0, 0, 0, 1, 0, 1, 1, 1],
        }
    )
    weights = research.fit_weights(fit, "source_class")
    for source in ("a", "b"):
        selected = fit.training_source.eq(source)
        assert weights[selected & fit.label.eq(0)].sum() == pytest.approx(
            weights[selected & fit.label.eq(1)].sum()
        )


def test_candidate_selection_rejects_hidden_source_regression():
    def result(macro, first, second):
        return {
            "macro_source_recall": macro,
            "minimum_source_recall": min(first, second),
            "overall": {"average_precision": 0.9},
            "source_rates": {"a": {"recall": first}, "b": {"recall": second}},
        }

    baseline = result(0.5, 0.5, 0.5)
    candidates = {"regression": result(0.6, 0.9, 0.3), "improvement": result(0.54, 0.53, 0.55)}
    selection = research.select_candidate(candidates, baseline)
    assert selection["candidate"] == "improvement"
    assert selection["eligible_candidates"] == ["improvement"]


def test_positive_only_experiment_report_does_not_invent_fpr_precision_or_accuracy():
    frame = pd.DataFrame({"group": ["a", "b"], "label": [1, 1]})
    result = runner.summarize(frame, np.array([0.1, 0.9]), 0.5, positive_only=True)
    assert result["recall"] == 0.5
    assert result["fpr"] is result["precision"] is result["accuracy"] is None
    with pytest.raises(ValueError, match="positive_only_requires_phishing_labels"):
        runner.summarize(frame.assign(label=[0, 1]), np.array([0.1, 0.9]), 0.5, positive_only=True)


def test_paired_bootstrap_identical_predictions_have_zero_delta():
    frame = pd.DataFrame({"group": ["a", "b", "c", "d"], "label": [0, 1, 0, 1]})
    scores = np.array([0.1, 0.9, 0.7, 0.1])
    result = runner.paired_intervals(frame, scores, scores, [0.5, 0.5], 100, 7)
    assert result["recall_delta95"] == result["fpr_delta95"] == [0, 0]
