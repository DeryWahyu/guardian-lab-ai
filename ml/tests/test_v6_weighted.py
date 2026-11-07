"""Weighting must preserve labels, partitions, privacy and source regression gates."""

import importlib
import sys

import numpy as np
import pandas as pd
import pytest

from guardian_ml.paths import ROOT

sys.path.insert(0, str(ROOT / "scripts"))
support = importlib.import_module("v6_weighted_support")
experiment = importlib.import_module("experiment_v6_weighted")
sys.path.pop(0)


def fitting_frame():
    return pd.DataFrame(
        {
            "partition": ["fit"] * 8,
            "training_source": ["a"] * 5 + ["b"] * 3,
            "group": ["repeat"] * 3 + ["a3", "a4", "b0", "b1", "b2"],
            "label": [0, 1, 1, 1, 1, 0, 1, 1],
        },
        index=np.arange(8) * 7,
    )


def test_equal_source_mass_and_domain_reweighting_are_both_preserved():
    frame = fitting_frame()
    original = frame.copy(deep=True)
    weights = support.classifier_weights(frame, "source_equal_domain_sqrt")
    assert np.isclose(weights.mean(), 1)
    assert np.isclose(weights[:5].sum(), weights[5:].sum())
    assert weights[0] < weights[3]
    assert frame.equals(original)


def test_soft_class_weights_emphasize_minority_without_changing_labels():
    frame = fitting_frame().assign(group=[f"unique-{i}" for i in range(8)])
    weights = support.classifier_weights(frame, "source_sqrt_domain_class_soft")
    assert weights[0] > weights[1]
    assert np.isfinite(weights).all() and (weights > 0).all()
    assert frame.label.tolist() == [0, 1, 1, 1, 1, 0, 1, 1]


@pytest.mark.parametrize("partition", ["tune", "calibration", "new_test"])
def test_classification_weights_cannot_be_fitted_using_holdouts(partition):
    with pytest.raises(ValueError, match="partition"):
        support.classifier_weights(
            fitting_frame().assign(partition=partition), "source_sqrt_domain_sqrt"
        )


def test_equal_source_calibration_is_label_independent_and_partition_guarded():
    frame = fitting_frame().assign(partition="calibration")
    weights = support.calibration_weights(frame, "source_equal_sigmoid")
    assert np.isclose(weights[:5].sum(), weights[5:].sum())
    assert np.array_equal(
        weights,
        support.calibration_weights(frame.assign(label=1 - frame.label), "source_equal_sigmoid"),
    )
    with pytest.raises(ValueError, match="partition"):
        support.calibration_weights(frame.assign(partition="new_test"), "source_equal_sigmoid")


def metric(first, second, brier=0.1):
    return {
        "macro_source_recall": (first + second) / 2,
        "minimum_source_recall": min(first, second),
        "macro_source_brier": brier,
        "source_rates": {
            "a": {"phishing": 100, "recall": first, "brier_score": brier},
            "b": {"phishing": 100, "recall": second, "brier_score": brier},
        },
    }


def test_higher_average_cannot_hide_a_large_source_regression():
    baseline = metric(0.5, 0.5)
    selected = support.choose_research_candidate(
        {
            "control_native": baseline,
            "harmful": metric(0.9, 0.3),
            "helpful": metric(0.55, 0.55, 0.095),
        },
        baseline,
    )
    assert selected["selected"] == "helpful"
    assert selected["detection_eligible"] == ["helpful"]


def test_calibration_can_improve_without_claiming_better_phishing_ranking():
    baseline = metric(0.5, 0.5)
    selected = support.choose_research_candidate(
        {"control_native": baseline, "calibrated": metric(0.5, 0.5, 0.09)}, baseline
    )
    assert selected["selected"] == "calibrated"
    assert selected["detection_eligible"] == []
    assert selected["calibration_eligible"] == ["calibrated"]
    assert selected["production_ready"] is False


def test_failed_development_gate_retains_control_and_freezes_challenger_separately():
    baseline = metric(0.5, 0.5)
    selected = support.choose_research_candidate(
        {"control_native": baseline, "failed": metric(0.51, 0.51, 0.13)}, baseline
    )
    assert selected["selected"] == "control_native"
    assert selected["evaluated_candidate"] == "failed"
    assert not selected["development_gate_passed"]


def test_review_packs_do_not_persist_targets_scores_or_fabricated_reviewers(tmp_path):
    frame = pd.DataFrame(
        {
            "partition": ["tune"] * 4,
            "core": ["https://example.org/password=SHORTSECRET"] * 4,
            "digest": [f"synthetic-{i}" for i in range(4)],
            "group": [f"g{i}" for i in range(4)],
            "representation_digest": ["conflict", "conflict", "third", "fourth"],
            "training_source": ["synthetic"] * 4,
            "label": [1, 0, 1, 0],
        }
    )
    directory = tmp_path / "review"
    summary = support.development_review_queue(
        frame, np.array([0.1, 0.9, 0.9, 0.1]), 0.5, directory
    )
    assert summary["completed_human_reviews"] == 0
    for path in directory.glob("*.csv"):
        assert "SHORTSECRET" not in path.read_text()
        assert "https://" not in path.read_text()
    blind = pd.read_csv(directory / "conflict-reviewer-a.csv")
    assert "publisher_label" not in blind and "score" not in blind
    assert blind.reviewer_id.isna().all() and blind.label.isna().all()


def test_source_drift_is_rejected_before_loading_models_or_matrices(tmp_path, monkeypatch):
    experiment.write_json(
        tmp_path / "cache-frozen.json", {"protocol_sha256": "bad", "source_hashes": {}}
    )
    monkeypatch.setattr(experiment, "RUN", tmp_path)
    monkeypatch.setattr(
        experiment, "current_control", lambda *_: pytest.fail("must reject source drift first")
    )
    with pytest.raises(ValueError, match="source_or_protocol_changed"):
        experiment.check_cache({})


def test_a_new_holdout_or_explicit_unavailability_record_is_required_before_fitting(tmp_path):
    with pytest.raises(ValueError, match="required_before_fitting"):
        experiment.holdout_binding({"new_holdout_freeze": str(tmp_path / "not-created.json")})


def test_real_weighted_artifact_reload_and_cached_inference_parity(tmp_path):
    import joblib
    from scipy.sparse import load_npz

    selected_path = experiment.RUN / "selected-frozen.json"
    if not selected_path.exists():
        pytest.skip("ignored local weighted research artifact not installed")
    protocol = experiment.read_json(experiment.PROTOCOL)
    cache, selected = experiment.check_selected(protocol)
    record = selected["records"][selected["selection"]["evaluated_candidate"]]
    bundle = joblib.load(ROOT / record["artifact"])
    cores = (
        pd.read_parquet(ROOT / cache["assets"]["threshold"]["input_path"], columns=["core"])
        .core.iloc[:128]
        .tolist()
    )
    probes = cores + [
        "http://example.org/password=SHORTSECRET",
        "https://example.org/password=SHORTSECRET",
    ]
    before = experiment.predict_bundle(bundle, probes)
    copy = tmp_path / "weighted-roundtrip.joblib"
    joblib.dump(bundle, copy, compress=3)
    restored = joblib.load(copy)
    after = experiment.predict_bundle(restored, probes)
    assert np.array_equal(before, after)
    assert after[-1] == after[-2]
    matrix = load_npz(ROOT / cache["assets"]["threshold"]["matrix_path"])[:128]
    cached = experiment.calibrated(
        restored["classifier"].predict_proba(matrix)[:, 1], restored["calibrator"]
    )
    assert np.allclose(cached, after[:128], rtol=0, atol=1e-12)
    assert restored["metadata"]["production_ready"] is False
