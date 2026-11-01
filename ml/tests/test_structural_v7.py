"""Fit-only transforms, offline feature parity and frozen candidate persistence."""

import json
import socket

import joblib
import numpy as np
import pandas as pd
import pytest

from guardian_ml.metadata import checksum
from guardian_ml.exposure_v7 import completed_v7_inventory
from guardian_ml.paths import ROOT
from guardian_ml.preprocessing import prepare_url
from guardian_ml.structural_evaluation import safe_metrics, source_point
from guardian_ml.structural_features import (
    StructuralEncoder,
    probabilities,
    structural_values,
)


def synthetic_cores():
    return [
        prepare_url("https://example.org/" + "section/" * i + "login").core for i in range(1, 17)
    ]


@pytest.mark.parametrize("kind", ["linear", "spline"])
def test_transform_is_offline_scheme_free_and_does_not_learn_from_test(kind, monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("Network forbidden during feature extraction")

    monkeypatch.setattr(socket, "create_connection", forbidden)
    blocks = structural_values(synthetic_cores())
    encoder = StructuralEncoder(kind).fit(blocks, partition="fit")
    means = encoder.numeric_scaler.mean_.copy()
    knots = None if encoder.spline is None else encoder.spline.bsplines_[0].t.copy()
    probes = ["http://example.org/login", "https://example.org/login"]
    features = encoder.transform(structural_values(probes)).toarray()
    assert np.array_equal(features[0], features[1])
    assert np.isfinite(features).all()
    encoder.transform(structural_values(["https://alice.github.io/" + "segment/" * 100]))
    assert np.array_equal(encoder.numeric_scaler.mean_, means)
    if knots is not None:
        assert np.array_equal(encoder.spline.bsplines_[0].t, knots)
    with pytest.raises(ValueError, match="fitting_partition"):
        StructuralEncoder(kind).fit(blocks, partition="test")


def test_features_require_sanitized_core_and_keep_private_tenant_context():
    with pytest.raises(ValueError, match="canonical_core_required"):
        structural_values(["https://example.org/?token=SYNTHETIC"])
    _, flags, _ = structural_values(["https://alice.github.io/", "https://example.org/"])
    assert flags[0, 0] == 1 and flags[1, 0] == 0


def test_positive_only_report_never_invents_false_alarm_or_precision():
    report = safe_metrics([1, 1, 1], np.array([0.1, 0.8, 0.9]), 0.5)
    assert report["recall"] == pytest.approx(2 / 3)
    assert all(report[name] is None for name in ["fpr", "accuracy", "precision", "f1"])


def test_small_source_confidence_constraint_is_reported_infeasible():
    frame = pd.DataFrame({"label": [0, 0, 1, 1], "training_source": ["tiny"] * 4})
    point = source_point(frame, np.array([0.1, 0.2, 0.8, 0.9]), 0.01, confidence=True)
    constraint = point["source_constraints"]["tiny"]
    assert not constraint["wilson_constraint_feasible_at_zero_fp"]
    assert not constraint["wilson_constraint_applied"]
    assert point["source_rates"]["tiny"]["fpr"] == 0


def test_feasible_confidence_policy_respects_wilson_upper_bound():
    frame = pd.DataFrame(
        {
            "label": [0] * 1000 + [1] * 100,
            "training_source": ["large"] * 1100,
        }
    )
    raw = np.r_[np.linspace(0, 1, 1000), np.full(100, 0.99)]
    point = source_point(frame, raw, 0.01, confidence=True)
    assert point["source_constraints"]["large"]["wilson_constraint_applied"]
    assert point["source_rates"]["large"]["fpr_wilson95_rows_iid_assumption"][1] <= 0.01


def test_exposure_inventory_rejects_incomplete_run(tmp_path):
    assert completed_v7_inventory(tmp_path) is None


def test_actual_completed_run_requires_matching_artifact_for_exposure(monkeypatch):
    from guardian_ml import exposure_v7

    path = ROOT / "ml/runs/notebook-tfidf-logistic-v7/reports/evaluation-v7.json"
    if not path.exists():
        pytest.skip("Requires the local completed v7 evaluation")
    inventory = completed_v7_inventory(ROOT)
    assert inventory is not None
    assert {item["role"] for item in inventory["inventory"]} == {"v7:fit", "v7:new_phish360"}
    actual_checksum = exposure_v7.checksum

    def corrupt_checksum(path):
        return "0" * 64 if path.name == "url-core-logistic-v7.joblib" else actual_checksum(path)

    monkeypatch.setattr(exposure_v7, "checksum", corrupt_checksum)
    assert completed_v7_inventory(ROOT) is None


def test_actual_frozen_v7_save_reload_and_url_qr_parity(tmp_path):
    folder = ROOT / "ml/runs/notebook-tfidf-logistic-v7"
    metadata_path = folder / "reports/frozen-v7.json"
    if not metadata_path.exists():
        pytest.skip("Requires the local frozen v7 training artifact")
    frozen = json.loads(metadata_path.read_text())
    path = folder / "artifacts/url-core-logistic-v7.joblib"
    assert checksum(path) == frozen["bundle_sha256"]
    bundle = joblib.load(path)
    probes = ["http://example.org/login", "https://example.org/login"]
    expected = probabilities(bundle, probes)
    assert expected[0] == expected[1]
    destination = tmp_path / "roundtrip.joblib"
    joblib.dump(bundle, destination)
    assert np.array_equal(expected, probabilities(joblib.load(destination), probes))
    assert bundle["metadata"] == frozen["metadata"]
    for relative, digest in frozen["source_hashes"].items():
        assert checksum(ROOT / relative) == digest
