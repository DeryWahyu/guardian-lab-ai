"""Leakage, scheme parity and real frozen-family comparison checks."""

import json

import joblib
import numpy as np
import pandas as pd
import pytest
from threadpoolctl import threadpool_limits

from guardian_ml.family_audit import assert_external, code_hash
from guardian_ml.family_features import fit_shared_encoder, shared_matrix, source_weights
from guardian_ml.family_scores import probabilities
from guardian_ml.metadata import checksum
from guardian_ml.paths import ROOT
from guardian_ml.v8_selection import fit_text_encoder


def test_shared_transform_is_fit_only_and_preserves_scheme_parity():
    cores = [f"https://sample{i}.example.org/login/account{i}" for i in range(80)]
    sources = ["fixture"] * len(cores)
    with threadpool_limits(limits=2):
        text = fit_text_encoder(cores, sources, np.ones((80, 33)), partition="fit")
        with pytest.raises(ValueError, match="fitting_partition"):
            fit_shared_encoder(text, cores, sources, partition="test", components=4)
        shared = fit_shared_encoder(text, cores, sources, partition="fit", components=4)
        components = shared["svd"].components_.copy()
        vocabulary = dict(text["word"].vocabulary_)
        matrix = shared_matrix(
            shared,
            ["http://example.org/tuneonlymarker", "https://example.org/tuneonlymarker"],
        )
    assert matrix.shape == (2, 42)
    assert np.array_equal(matrix[0], matrix[1])
    assert np.array_equal(components, shared["svd"].components_)
    assert vocabulary == text["word"].vocabulary_
    assert "tuneonlymarker" not in vocabulary


def test_source_weights_give_equal_total_weight_without_using_labels():
    sources = pd.Series(["large"] * 8 + ["small"] * 2)
    values = source_weights(sources)
    assert values.mean() == pytest.approx(1)
    assert values[sources.eq("large")].sum() == pytest.approx(values[sources.eq("small")].sum())


def test_benchmark_cannot_reuse_a_domain_or_url_from_development():
    development = pd.DataFrame({"group": ["example.org"], "digest": ["known"]})
    for frame in [
        pd.DataFrame({"group": ["example.org"], "digest": ["new"]}),
        pd.DataFrame({"group": ["example.net"], "digest": ["known"]}),
    ]:
        with pytest.raises(ValueError, match="in_development"):
            assert_external(frame, development)


def test_frozen_real_comparison_is_bound_and_offline_predictions_match():
    run = ROOT / "ml/runs/notebook-model-comparison-v9"
    frozen_path = run / "reports/frozen-v9.json"
    if not frozen_path.exists():
        pytest.skip("Requires completed local v9 comparison")
    frozen = json.loads(frozen_path.read_text())
    report = json.loads((run / "reports/evaluation-v9.json").read_text())
    assert report["frozen_sha256"] == checksum(frozen_path)
    assert report["spec_sha256"] == frozen["spec_sha256"]
    spec = frozen["specification"]
    assert code_hash(ROOT / "guardian_lab_url_qr_comparison_v9.ipynb") == spec["code_sha256"]
    for path, digest in spec["source_hashes"].items():
        assert checksum(ROOT / path) == digest
    parent = ROOT / "ml/runs/notebook-tfidf-logistic-v8"
    parent_frozen = json.loads((parent / "reports/frozen-v8.json").read_text())
    assert checksum(parent / "data/development-v8.parquet") == spec["development_sha256"]
    assert spec["development_sha256"] == parent_frozen["metadata"]["development_sha256"]
    for asset in spec["benchmark_assets"].values():
        assert checksum(ROOT / asset["path"]) == asset["sha256"]
    assert frozen["frozen_at_utc"] < report["completed_at_utc"]
    assert not report["new_independent_test"] and not report["production_ready"]
    for path, digest in frozen["protected"].items():
        assert checksum(ROOT / path) == digest
    probes = ["http://example.org/login", "https://example.org/login"]
    for name, entry in frozen["models"].items():
        path = ROOT / entry["path"]
        assert checksum(path) == entry["sha256"]
        first, second = joblib.load(path), joblib.load(path)
        with threadpool_limits(limits=2):
            a, b = probabilities(first, probes), probabilities(second, probes)
        assert np.array_equal(a, b) and a[0] == a[1]
        assert np.isfinite(a).all()
        if name.startswith("shared_"):
            assert first["shared_encoder"]["fit_rows"] == 535504
            assert first["shared_encoder"]["fit_partition"] == "fit"
        policy = first["comparison_metadata"]["thresholds"]
        assert policy["high"] >= policy["warning"]
    for benchmark in report["benchmarks"].values():
        assert benchmark["previously_observed"]
        assert not benchmark["used_for_v9_training_selection_calibration_threshold"]
    positive = report["benchmarks"]["observed_phishtank_positive"]
    for model in positive["models"].values():
        assert model["levels"]["warning"]["accuracy"] is None
        assert model["levels"]["warning"]["fpr"] is None
        assert model["levels"]["warning"]["precision"] is None
