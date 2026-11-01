import numpy as np
from guardian_ml.evaluation import metrics, operating_point, wilson, calibrate, apply_calibration


def test_operating_point_respects_ties_and_false_positive_budget():
    y = np.array([0, 0, 0, 0, 1, 1, 1, 1])
    values = np.array([0.1, 0.2, 0.3, 0.8, 0.8, 0.9, 0.95, 0.99])
    point = operating_point(y, values, 0.0)
    assert point["empirical_fpr"] == 0
    assert point["recall"] == 0.75
    assert point["threshold"] > 0.8


def test_zero_observed_false_positives_has_nonzero_uncertainty():
    lower, upper = wilson(0, 1000)
    assert lower == 0 and upper > 0.003


def test_reliability_bins_do_not_double_count_boundaries():
    y = np.array([0, 0, 0, 1, 1, 1])
    values = np.array([0.0, 0.1, 0.2, 0.8, 0.9, 1.0])
    result = metrics(y, values, 0.5)
    assert sum(item["rows"] for item in result["reliability_bins"]) == len(y)
    assert result["fpr"] == 0 and result["recall"] == 1


def test_calibration_outputs_remain_valid_outside_observed_score_range():
    rng = np.random.default_rng(12)
    raw = rng.uniform(0.01, 0.99, 1000)
    y = (raw + rng.normal(0, 0.1, 1000) > 0.5).astype(int)
    groups = np.array([f"synthetic-{i}" for i in range(1000)])
    fitted, report = calibrate(y, raw, groups)
    predicted = apply_calibration(fitted, np.array([0.0, 1.0, 0.5]))
    assert np.isfinite(predicted).all() and ((predicted >= 0) & (predicted <= 1)).all()
    assert report["production_prevalence_calibrated"] is False
