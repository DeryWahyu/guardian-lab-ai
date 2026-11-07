"""Privacy, partition discipline, regression gates and real-artifact parity."""

import importlib
import json
import sys

import joblib
import numpy as np
import pandas as pd
import pytest

from guardian_ml.paths import ROOT

sys.path.insert(0, str(ROOT / "scripts"))
support = importlib.import_module("v6_segmented_support")
intake = importlib.import_module("intake_v6_segmented")
sys.path.pop(0)


def fitting():
    return pd.DataFrame(
        {
            "core": [
                f"https://tenant{i % 8}.example.org/{'account' if i % 2 else 'articles'}/common/document{i % 5}"
                for i in range(80)
            ],
            "partition": ["fit"] * 80,
            "training_source": ["a"] * 40 + ["b"] * 40,
            "label": [i % 2 for i in range(80)],
            "group": [f"group{i}" for i in range(80)],
        }
    )


def specification():
    return {
        "source_cap": 80,
        "total_cap": 80,
        "host_features": 200,
        "subdomain_features": 100,
        "path_features": 200,
    }


@pytest.fixture(scope="module")
def encoder():
    return support.fit_segment_encoder(fitting(), specification(), 42)


def test_secret_assignments_queries_fragments_credentials_never_enter_views():
    with pytest.raises(ValueError):
        support.split_cores(["https://alice:PRIVATEPASSWORD@example.org/articles"])
    fields = support.split_cores(
        ["https://example.org/password=SHORTSECRET?token=QUERYSECRET#FRAGMENTSECRET"]
    )
    text = " ".join(fields["host"] + fields["subdomain"] + fields["path"])
    assert "SECRET" not in text.upper() and "PRIVATEPASSWORD" not in text.upper()
    assert "redacted" in text.lower()


def test_scheme_query_and_fragment_have_identical_features(encoder):
    matrix = support.extra_matrix(
        encoder,
        [
            "http://example.org/common/document?x=one#part",
            "https://example.org/common/document?x=two#other",
        ],
    )
    assert (matrix[0] != matrix[1]).nnz == 0


def test_host_subdomain_path_are_separate_and_numeric_values_finite():
    fields = support.split_cores(["https://tenant.example.org/articles/reset"])
    assert fields["host"] == ["tenant.example.org"]
    assert fields["subdomain"] == ["tenant"]
    assert fields["path"] == ["/articles/reset"]
    assert fields["structure"].shape == (1, len(support.STRUCTURE))
    assert np.isfinite(fields["structure"]).all()


@pytest.mark.parametrize("partition", ["tune", "calibration", "threshold", "new_test"])
def test_encoder_rejects_holdout_fitting(partition):
    with pytest.raises(ValueError, match="partition"):
        support.fit_segment_encoder(fitting().assign(partition=partition), specification(), 42)


def test_transform_does_not_learn_holdout_tokens_or_mutate_encoder(encoder):
    before = {key: dict(encoder[key].vocabulary_) for key in ("host", "subdomain", "path")}
    support.extra_matrix(encoder, ["https://unseensubdomain.example.net/neverobservedholdouttoken"])
    assert all(encoder[key].vocabulary_ == value for key, value in before.items())
    assert "neverobservedholdouttoken" not in encoder["path"].vocabulary_


def test_root_only_training_paths_still_have_a_valid_offline_feature_space():
    frame = fitting()
    frame["core"] = [f"https://tenant{i % 8}.example.org/" for i in range(len(frame))]
    fitted = support.fit_segment_encoder(frame, specification(), 42)
    matrix = support.extra_matrix(fitted, ["https://newtenant.example.org/"])
    assert matrix.shape[0] == 1 and matrix.nnz > 0 and np.isfinite(matrix.data).all()


def test_beta_and_sigmoid_are_monotone_and_reject_invalid_probabilities():
    frame = fitting().assign(partition="calibration")
    raw = np.where(frame.label.eq(1), 0.8, 0.2)
    for kind in ("source_equal_sigmoid", "source_equal_beta"):
        calibrator = support.fit_calibrator(frame, raw, kind, 42)
        values = support.calibrated(np.linspace(0.001, 0.999, 100), calibrator, kind)
        assert np.all(np.diff(values) > 0)
        calibrator.coef_[0, 0] = -1
        with pytest.raises(ValueError, match="monotone"):
            support.calibrated(raw, calibrator, kind)
    with pytest.raises(ValueError, match="probabilities"):
        support.calibration_design([np.nan, 0.5], "source_equal_beta")
    with pytest.raises(ValueError, match="partition"):
        support.fit_calibrator(frame.assign(partition="new_test"), raw, "source_equal_sigmoid", 42)


def summary(recall=0.5, brier=0.1, fpr=0.005):
    return {
        "macro_source_recall": recall,
        "minimum_source_recall": recall,
        "macro_source_brier": brier,
        "source_rates": {
            "a": {
                "phishing": 100,
                "benign": 1000,
                "recall": recall,
                "fpr": fpr,
                "brier_score": brier,
            }
        },
    }


def rules():
    return json.loads((ROOT / "ml/reports/v6-segmented-20261105-protocol.json").read_text())[
        "selection"
    ]


@pytest.mark.parametrize("bad", [{"fpr": 0.009}, {"brier": 0.107}])
def test_recall_gain_cannot_override_false_alarm_or_score_regression(bad):
    baseline = summary()
    result = support.choose_candidate(
        {"control_native": baseline, "harmful": summary(recall=0.6, **bad)}, baseline, rules()
    )
    assert result["selected"] == "control_native" and not result["development_gate_passed"]
    assert result["diagnostic"] == "harmful"


def test_calibration_gate_can_pass_without_claiming_better_ranking():
    baseline = summary()
    result = support.choose_candidate(
        {"control_native": baseline, "calibrated": summary(brier=0.097)}, baseline, rules()
    )
    assert result["selected"] == "calibrated"
    assert result["details"]["calibrated"]["calibration_gate"]
    assert not result["details"]["calibrated"]["detection_gate"]


def test_publisher_literal_mapping_rejects_missing_or_unknown_cases():
    spec = {"label_column": "Label", "rows": 2, "label_counts": {"Phishing": 1, "Legitimate": 1}}
    assert (
        intake.map_labels(pd.DataFrame({"Label": ["Phishing", "Legitimate"]}), spec)
        == spec["label_counts"]
    )
    with pytest.raises(ValueError, match="label_totals"):
        intake.map_labels(pd.DataFrame({"Label": ["Phishing", "unknown"]}), spec)


@pytest.mark.skipif(
    not (ROOT / "ml/runs/v6-segmented-20261105/selected-frozen.json").exists(),
    reason="local research artifact required",
)
def test_real_segmented_saved_model_matches_cache_and_http_https():
    sys.path.insert(0, str(ROOT / "scripts"))
    experiment = importlib.import_module("experiment_v6_segmented")
    replay = importlib.import_module("v6_historical_replay")
    sys.path.pop(0)
    cache, selected = replay.load_segmented_for_parity()
    record = selected["records"][selected["evaluated_candidate"]]
    original, restored = experiment.load_bundle(record), joblib.load(ROOT / record["artifact"])
    if record.get("native"):
        restored = experiment.wrap_native(restored)
    frame = pd.read_parquet(ROOT / cache["assets"]["tune"]["input_path"], columns=["core"])
    probes = frame.core.iloc[:128].tolist() + [
        "http://example.org/password=SHORTSECRET",
        "https://example.org/password=SHORTSECRET",
    ]
    first, second = (
        support.predict_segmented(original, probes),
        support.predict_segmented(restored, probes),
    )
    assert np.array_equal(first, second) and first[-1] == first[-2]
    assert selected["max_cached_inference_delta"] <= 1e-12
