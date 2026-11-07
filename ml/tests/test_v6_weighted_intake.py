import importlib
import sys

import pandas as pd
import pytest

from guardian_ml.paths import ROOT

sys.path.insert(0, str(ROOT / "scripts"))
intake = importlib.import_module("intake_v6_weighted_holdout")
sys.path.pop(0)


def test_binary_orientation_requires_exact_published_class_evidence():
    labels = pd.Series([0, 0, 1, None])
    numeric, mapping, counts = intake.checked_label_mapping(labels, {"phishing": 2, "benign": 1})
    assert mapping == {"1": 0, "0": 1}
    assert counts == {"0": 2, "1": 1}
    assert numeric.isna().sum() == 1


def test_mismatched_publisher_counts_stop_instead_of_guessing_case_labels():
    with pytest.raises(ValueError, match="qa_amendment"):
        intake.checked_label_mapping(pd.Series([0, 0, 1]), {"phishing": 7, "benign": 3})


def test_actual_publisher_text_labels_preserve_their_explicit_meaning():
    values, mapping, counts = intake.checked_label_mapping(
        pd.Series(["legitimate", "phishing", "phishing"]), {"phishing": 2, "benign": 1}
    )
    assert values.map(mapping).tolist() == [0, 1, 1]
    assert counts == {"phishing": 2, "legitimate": 1}


@pytest.mark.parametrize("labels", [[0, 0], [0, 1, 2], ["https://example.org/", 1]])
def test_unknown_or_ambiguous_label_schema_does_not_enter_evaluation(labels):
    with pytest.raises(ValueError, match="schema|enum|documented_label"):
        intake.checked_label_mapping(pd.Series(labels), {"phishing": 2, "benign": 1})
