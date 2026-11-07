"""Source rights filters and group thresholds must not fabricate quality metrics."""

import importlib
import sys

import numpy as np
import pandas as pd
import pytest
import joblib
from sklearn.metrics import brier_score_loss

from guardian_ml.paths import ROOT

sys.path.insert(0, str(ROOT / "scripts"))
support = importlib.import_module("v6_readiness_support")
study = importlib.import_module("experiment_v6_readiness")
dev = importlib.import_module("v6_development_support")
sys.path.pop(0)


def frame(labels):
    return pd.DataFrame({"label": labels, "group": [f"g{i}" for i in range(len(labels))]})


def test_license_filter_is_explicit_and_applies_to_every_partition():
    protocol = {
        "allowed_sources": ["a"],
        "exclude_from_every_fit_and_development_partition": ["nc", "unclear"],
    }
    for part in ["fit", "calibration", "threshold", "tune"]:
        data = pd.DataFrame(
            {"training_source": ["a", "nc", "unclear"], "partition": [part] * 3, "label": [0, 1, 0]}
        )
        assert support.filtered(data, protocol).training_source.tolist() == ["a"]
    with pytest.raises(ValueError, match="unreviewed"):
        support.filtered(pd.DataFrame({"training_source": ["new"]}), protocol)


def test_private_threshold_ties_are_conservative_and_cannot_use_tune():
    data = frame([0] * 100 + [1] * 10).assign(partition="threshold")
    scores = np.array([0.8] * 100 + [0.9] * 10)
    cut = support.private_cutoff(data, scores, 0.01)
    assert cut > 0.8 and int((scores[:100] >= cut).sum()) == 0
    with pytest.raises(ValueError, match="partition"):
        support.private_cutoff(data.assign(partition="tune"), scores, 0.01)
    with pytest.raises(ValueError, match="insufficient"):
        support.private_cutoff(data.iloc[:99], scores[:99], 0.01)


def test_routed_confusion_uses_group_thresholds_but_brier_uses_probabilities():
    data = frame([0, 1, 0, 1])
    probability = np.array([0.7, 0.8, 0.3, 0.6])
    policies = {"general": {"warning": 0.75}, "private": {"warning": 0.5}}
    private = np.array([False, False, True, True])
    flags = support.decisions(probability, private, policies)
    result = support.routed_metrics(data, probability, flags, policies, repeats=20)
    assert result["confusion_matrix"] == {"tn": 2, "fp": 0, "fn": 0, "tp": 2}
    assert result["brier_score"] == pytest.approx(brier_score_loss(data.label, probability))
    assert result["brier_score"] > 0
    assert result["threshold"] is None


@pytest.mark.parametrize("labels", [[], [1, 1], [0, 0]])
def test_single_class_does_not_gain_binary_accuracy_or_precision(labels):
    result = support.routed_metrics(
        frame(labels), np.array([0.8] * len(labels)), np.array([True] * len(labels), dtype=bool), {}
    )
    assert (
        result["accuracy"] is None and result["precision"] is None and result["brier_score"] is None
    )
    if labels == [1, 1]:
        assert result["fpr"] is None


@pytest.mark.parametrize(
    "values,flags", [([np.nan], [True]), ([1.01], [True]), ([0.5], [1]), ([[0.5]], [True])]
)
def test_invalid_routing_scores_fail_closed(values, flags):
    with pytest.raises(ValueError, match="invalid_routed"):
        support.routed_metrics(frame([1]), np.array(values), np.array(flags), {})


def test_real_filtered_partitions_remain_separate_and_exclude_both_sources():
    path = study.RUN / "data-frozen.json"
    if not path.exists():
        pytest.skip("local research data is excluded from Git")
    data = study.parent.read(path)
    frames = []
    for name, asset in data["assets"].items():
        part = pd.read_parquet(
            ROOT / asset["path"],
            columns=["group", "digest", "representation_digest", "training_source", "partition"],
        )
        assert set(part.partition) == {name}
        assert not set(part.training_source) & {"deepurlbench", "iscx2016_replica"}
        frames.append(part)
    dev.assert_separated(frames)


@pytest.mark.parametrize("name", ["baseline", "private_c05", "private_c2"])
def test_real_model_reload_parity_and_routing_uses_bound_encoder(name):
    path = study.RUN / (name + ".joblib")
    if not path.exists():
        pytest.skip("local research artifacts are excluded from Git")
    base_path = study.RUN / "baseline.joblib"
    base = joblib.load(base_path)
    candidate = joblib.load(path)
    probes = [
        "https://example.org/token=short-secret?email=person@example.net",
        "https://tenant.blogspot.com/article",
        "https://example.net/a/b/c/d",
    ]
    prepared = pd.DataFrame({"core": [dev.prepare_experiment_url(x).core for x in probes]})
    matrix = study.matrix_batches(base["encoder"], prepared)
    scores = study.score_matrix(candidate, matrix)
    replay = study.score_matrix(joblib.load(path), matrix)
    assert np.allclose(scores, replay, atol=1e-12, rtol=0)
    assert not candidate["metadata"]["production_ready"]
    if name != "baseline":
        assert candidate["metadata"]["baseline_sha256"] == study.checksum(base_path)
    else:
        original = study.RichArtifact()
        study.assert_original_recipe(base, original.bundle)
