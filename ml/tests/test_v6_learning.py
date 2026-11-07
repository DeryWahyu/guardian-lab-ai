"""Guard fitting separation, privacy, structured weighting and model selection."""

import copy
import importlib
import sys

import numpy as np
import pandas as pd
import pytest
import joblib

from guardian_ml.paths import ROOT

sys.path.insert(0, str(ROOT / "scripts"))
support = importlib.import_module("v6_learning_support")
intake = importlib.import_module("intake_v6_learning")
sanitize = importlib.import_module("intake_v6_expansion").sanitize_source
curation = importlib.import_module("experiment_v6_expanded_data")
development = importlib.import_module("v6_development_support")
sys.path.pop(0)


def frame():
    return pd.DataFrame(
        {
            "partition": ["fit"] * 16,
            "training_source": ["a"] * 8 + ["b"] * 8,
            "group": [f"domain-{i}" for i in range(8) for _ in range(2)],
            "label": [0, 1] * 8,
            "core": ["https://example.org/a/b/c/d", "https://tenant.blogspot.com/login"] * 8,
        },
        index=np.arange(16) * 3,
    )


def test_nested_curve_keeps_whole_groups_is_label_independent_and_order_stable():
    data = frame()
    previous = set()
    for fraction in (0.25, 0.5, 0.75, 1.0):
        selected = support.nested_fit(data, fraction, "fixed:")
        assert previous <= set(selected.group)
        assert selected.groupby("group").size().eq(2).all()
        assert len(selected.group.unique()) == int(8 * fraction)
        changed = support.nested_fit(
            data.sample(frac=1).assign(label=1 - data.label), fraction, "fixed:"
        )
        assert set(changed.group) == set(selected.group)
        previous = set(selected.group)


@pytest.mark.parametrize("partition", ["calibration", "threshold", "tune", "ebbu_external"])
def test_learning_helpers_refuse_holdout_fitting(partition):
    data = frame().assign(partition=partition)
    with pytest.raises(ValueError, match="partition"):
        support.nested_fit(data, 0.5, "fixed:")
    with pytest.raises(ValueError, match="partition"):
        support.weights(data, "private_phishing_x2")


def test_weighting_does_not_change_labels_or_source_mass():
    data = frame()
    original = data.copy(deep=True)
    for mode, favored in [("private_phishing_x2", 1), ("hard_benign_x2", 0)]:
        weights = support.weights(data, mode)
        assert np.isclose(weights.mean(), 1)
        assert np.isclose(weights[:8].sum(), weights[8:].sum())
        assert np.isclose(weights[favored] / weights[1 - favored], 2)
        assert data.equals(original)


def metric(recall=0.5, private_recall=0.5):
    m = {"phishing": 100, "benign": 200, "recall": recall, "fpr": 0.01, "brier_score": 0.1}
    return {
        "primary": {
            "macro_source_recall": recall,
            "minimum_source_recall": recall,
            "macro_source_brier": 0.1,
            "source_rates": {"a": m, "b": m.copy()},
        },
        "slices": {
            "private_hosting": {**m, "recall": private_recall},
            "non_private_hosting": m.copy(),
        },
    }


def test_average_gain_cannot_hide_private_hosting_regression():
    result = support.choose({"control": metric(), "bad": metric(0.6, 0.4)}, ["bad"])
    assert result["selected"] == "control"
    assert not result["details"]["bad"]["structure_guard"]


def test_curve_models_cannot_win_and_source_regression_blocks_candidate():
    bad = metric(0.6)
    bad["primary"]["source_rates"]["b"]["recall"] = 0.4
    results = {
        "control": metric(),
        "curve_25": metric(0.99, 0.99),
        "bad": bad,
        "good": metric(0.53, 0.51),
    }
    before = copy.deepcopy(results)
    decision = support.choose(results, ["bad", "good"])
    assert decision["selected"] == "good"
    assert not decision["details"]["bad"]["detection_gate"]
    assert results == before


def test_intake_rejects_target_hosts_before_network(monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("network should never be attempted")

    monkeypatch.setattr(intake.requests, "get", forbidden)
    with pytest.raises(ValueError, match="unapproved"):
        intake.download({"download_url": "https://target.example.org/dataset"})


def test_new_intake_redacts_short_secrets_and_excludes_scheme_aliases():
    raw = pd.DataFrame(
        {
            "url": [
                "https://example.org/token=short-secret?email=someone@example.net",
                "http://example.org/token=short-secret",
            ],
            "label": [0, 1],
        }
    )
    cleaned, _ = sanitize(raw, "synthetic", "url", "label")
    assert "short-secret" not in cleaned.to_json()
    assert "someone@example.net" not in cleaned.to_json()
    cleaned["label"] = cleaned.publisher_label.astype(int)
    result, audit = curation.curate_new(
        [cleaned],
        set(),
        set(),
        {"split_salt": "fixed:", "group_buckets": {"fit": 100}, "max_rows_per_domain": 5},
    )
    assert result.empty
    assert audit["conflict_representations"] == 1


def test_threshold_uses_separate_partition_and_handles_ties_conservatively():
    data = pd.DataFrame(
        {
            "partition": ["threshold"] * 4,
            "training_source": ["a"] * 4,
            "group": ["g1", "g2", "g3", "g4"],
            "label": [0, 0, 0, 1],
        }
    )
    scores = np.array([0.2, 0.8, 0.8, 0.9])
    point = curation.source_point(
        data, scores, 1 / 3, "threshold", {"min_benign_per_source_for_threshold": 1}
    )
    assert point["threshold"] > 0.8
    assert not (scores[:3] >= point["threshold"]).any()
    with pytest.raises(ValueError, match="partition"):
        curation.source_point(
            data.assign(partition="tune"),
            scores,
            0.01,
            "threshold",
            {"min_benign_per_source_for_threshold": 1},
        )


@pytest.mark.parametrize(
    "name",
    [
        "curve_25",
        "curve_50",
        "curve_75",
        "regularization_c05",
        "regularization_c8",
        "private_phishing_x2",
        "hard_benign_x2",
        "plus_iscx_fit",
    ],
)
def test_real_learning_artifact_reload_preserves_private_sanitized_predictions(name):
    path = ROOT / "ml/runs/v6-learning-20261106" / (name + ".joblib")
    if not path.exists():
        pytest.skip("research artifacts intentionally excluded from Git")
    raw = [
        "https://example.org/token=short-secret?email=someone@example.net",
        "https://tenant.blogspot.com/a/b/c/d",
        "http://example.net/ordinary",
    ]
    cleaned = [development.prepare_experiment_url(value).core for value in raw]
    first = development.predict_bundle(joblib.load(path), raw)
    second = development.predict_bundle(joblib.load(path), cleaned)
    assert np.allclose(first, second, atol=1e-12, rtol=0)
    assert np.isfinite(first).all() and np.all((first >= 0) & (first <= 1))
