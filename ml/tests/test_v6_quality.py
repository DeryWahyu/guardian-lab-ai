"""Quality replay uncertainty keeps domains together and respects missing classes."""

import importlib.util

import numpy as np
import pandas as pd
import pytest

from guardian_ml.paths import ROOT

spec = importlib.util.spec_from_file_location(
    "evaluate_v6_quality", ROOT / "scripts/evaluate_v6_quality.py"
)
quality = importlib.util.module_from_spec(spec)
spec.loader.exec_module(quality)


def test_positive_only_domain_bootstrap_does_not_invent_other_metrics():
    data = pd.DataFrame({"group": ["first", "second", "second", "second"], "label": [1] * 4})
    result = quality.domain_intervals(
        data, np.array([0.9, 0.1, 0.1, 0.1]), 0.5, 100, 7, positive_only=True
    )
    assert result["recall95"] == [0.0, 1.0]
    assert result["valid_repeats"] == 100
    assert not {"fpr95", "precision95", "accuracy95"}.intersection(result)


def test_binary_domain_bootstrap_records_replicates_missing_a_class():
    data = pd.DataFrame({"group": ["benign", "phishing"], "label": [0, 1]})
    result = quality.domain_intervals(data, np.array([0.1, 0.9]), 0.5, 100, 7)
    assert 0 < result["valid_repeats"] < 100
    assert result["discarded_class_absent_repeats"] == 100 - result["valid_repeats"]
    assert result["recall95"] == result["precision95"] == [1.0, 1.0]
    assert result["fpr95"] == [0.0, 0.0]


def test_positive_only_mode_rejects_binary_labels():
    data = pd.DataFrame({"group": ["first", "second"], "label": [0, 1]})
    with pytest.raises(ValueError, match="positive_only_requires_phishing_labels"):
        quality.domain_intervals(data, np.array([0.1, 0.9]), 0.5, 100, 7, positive_only=True)
