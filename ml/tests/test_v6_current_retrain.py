"""Original-v6 cloning must not inherit learned state or fit on holdouts."""

import importlib
import sys

import joblib
import numpy as np
import pandas as pd
import pytest
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler

from guardian_ml.paths import ROOT
from guardian_ml.rich_features import numeric_values

sys.path.insert(0, str(ROOT / "scripts"))
support = importlib.import_module("v6_current_retrain_support")
development = importlib.import_module("v6_development_support")
study = importlib.import_module("experiment_v6_current_retrain")
sys.path.pop(0)


def original_recipe():
    return {
        "encoder": {
            "char": TfidfVectorizer(
                analyzer="char", ngram_range=(2, 5), min_df=1, max_features=100000, dtype=np.float32
            ).fit(["heldoutquartz"]),
            "word": TfidfVectorizer(
                ngram_range=(1, 2), min_df=1, max_features=20000, dtype=np.float32
            ).fit(["heldoutquartz"]),
            "scaler": StandardScaler(with_mean=False).fit(
                numeric_values(["https://heldoutquartz.example.org/a"])
            ),
        },
        "classifier": LogisticRegression(
            C=2, solver="liblinear", max_iter=300, random_state=20261101
        ),
        "calibrator": LogisticRegression(C=1000, max_iter=200, random_state=20261101),
    }


def fit_frame():
    return pd.DataFrame(
        {
            "core": [f"https://example.org/article/{i}" for i in range(12)],
            "training_source": ["a"] * 8 + ["b"] * 4,
            "partition": ["fit"] * 12,
            "label": [0, 1] * 6,
            "group": [f"g{i}" for i in range(12)],
        }
    )


def test_encoder_is_refitted_only_from_fitting_and_original_is_unchanged():
    original = original_recipe()
    original_words = dict(original["encoder"]["word"].vocabulary_)
    frame = fit_frame()
    encoder, count = support.fit_original_encoder(
        original,
        frame,
        {"seed": 20261101, "recipe": {"vocabulary_source_cap": 100, "vocabulary_fit_limit": 100}},
    )
    assert count == len(frame)
    assert "heldoutquartz" not in encoder["word"].vocabulary_
    assert original["encoder"]["word"].vocabulary_ == original_words
    assert np.allclose(
        encoder["scaler"].scale_,
        StandardScaler(with_mean=False).fit(numeric_values(frame.core)).scale_,
    )
    for key in encoder:
        assert encoder[key] is not original["encoder"][key]
        assert encoder[key].get_params() == original["encoder"][key].get_params()


@pytest.mark.parametrize("partition", ["tune", "calibration", "threshold", "new_test"])
def test_original_recipe_refuses_holdouts(partition):
    with pytest.raises(ValueError, match="partition"):
        support.fit_original_encoder(original_recipe(), fit_frame().assign(partition=partition), {})


def test_source_weighting_matches_v6_and_does_not_equalize_source_mass_or_use_labels():
    frame = fit_frame()
    weights = development.fit_weights(frame, "source_sqrt")
    assert np.isclose(weights.mean(), 1)
    assert np.isclose(weights[:8].sum() / weights[8:].sum(), np.sqrt(2))
    assert np.array_equal(
        weights, development.fit_weights(frame.assign(label=1 - frame.label), "source_sqrt")
    )


def test_threshold_policy_preserves_original_rule_without_nested_thresholds():
    frame = fit_frame().assign(partition="threshold")
    scores = np.linspace(0.05, 0.95, len(frame))
    result = study.policies(frame, scores, {"thresholds": {"warning": 0.01, "high": 0.001}})
    for level in result:
        assert np.isscalar(result[level]["threshold"])
        assert (
            result[level]["threshold"]
            == development.source_threshold(
                frame, scores, 0.01 if level == "warning" else 0.001, "threshold"
            )["threshold"]
        )
    assert result["warning"]["threshold"] <= result["high"]["threshold"]


def test_recipe_guard_rejects_classifier_and_vocabulary_changes():
    original = original_recipe()
    changed = original_recipe()
    support.assert_original_recipe(changed, original)
    changed["classifier"].C = 8
    with pytest.raises(ValueError, match="recipe_changed"):
        support.assert_original_recipe(changed, original)
    changed = original_recipe()
    changed["encoder"]["word"].max_features = 30000
    with pytest.raises(ValueError, match="recipe_changed"):
        support.assert_original_recipe(changed, original)


def test_privacy_and_domain_identity_are_preserved_for_retraining():
    frame = pd.DataFrame(
        {
            "core": ["https://example.org/token=short-secret?email=person@example.net"],
            "group": ["example.org"],
        }
    )
    sanitized, audit = development.transform_frame(frame)
    assert audit["changed_cores"] == 1
    assert (
        "short-secret" not in sanitized.to_json()
        and "person@example.net" not in sanitized.to_json()
    )
    assert sanitized.group.tolist() == frame.group.tolist()


@pytest.mark.parametrize("scores", [[np.nan], [1.01], [-0.1], [], [[0.5]]])
def test_invalid_saved_scores_are_rejected(scores):
    with pytest.raises(ValueError, match="invalid_predictions"):
        support.check_scores(scores, 1)


@pytest.mark.parametrize("arm", study.ARMS)
def test_real_original_recipe_and_saved_prediction_parity(arm):
    path = study.RUN / (arm + ".joblib")
    if not path.exists():
        pytest.skip("research model binaries are local only")
    original = joblib.load(ROOT / study.read(study.PROTOCOL)["original_artifact"])
    first = joblib.load(path)
    support.assert_original_recipe(first, original)
    probes = [
        "https://example.org/token=short-secret?email=person@example.net",
        "https://tenant.blogspot.com/a/b/c/d",
        "http://example.net/article",
    ]
    scores = development.predict_bundle(first, probes)
    replay = development.predict_bundle(
        joblib.load(path), [development.prepare_experiment_url(x).core for x in probes]
    )
    assert np.allclose(scores, replay, atol=1e-12, rtol=0)
    assert not first["metadata"]["production_ready"]
