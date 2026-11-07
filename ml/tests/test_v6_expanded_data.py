"""New sources must stay private, exposure-aware and isolated from model selection."""

import importlib
import sys

import numpy as np
import pandas as pd
import pytest

from guardian_ml.paths import ROOT

sys.path.insert(0, str(ROOT / "scripts"))
expansion = importlib.import_module("experiment_v6_expanded_data")
intake = importlib.import_module("intake_v6_expansion")
sys.path.pop(0)


def protocol():
    return {
        "split_salt": "synthetic-split:",
        "group_buckets": {
            "fit": 60,
            "tune": 75,
            "calibration": 82,
            "threshold": 90,
            "new_test": 100,
        },
        "max_rows_per_domain": 2,
        "min_benign_per_source_for_threshold": 100,
        "min_phishing_per_source_for_macro_recall": 20,
    }


def synthetic_frame():
    frame = pd.DataFrame(
        {
            "url": [
                "https://example.org/password=SHORTSECRET",
                "https://example.org/login?token=SHORTSECRET",
                "http://example.net/",
                "https://example.net/",
                "https://example.com/one",
            ],
            "class": [1, 0, 0, 1, 0],
        }
    )
    result, _ = intake.sanitize_source(frame, "synthetic", "url", "class")
    result["label"] = result.publisher_label.astype(int)
    return result.drop(columns="publisher_label")


def test_source_sanitization_redacts_before_any_dataset_persistence():
    frame = synthetic_frame()
    assert "SHORTSECRET" not in frame.to_json()
    assert any("REDACTED" in core for core in frame.core)


def test_merged_sources_quarantine_conflicts_and_exclude_exposed_domains():
    frame = synthetic_frame()
    retained, report = expansion.curate_new(
        [frame], set(), {expansion.digest("example.com")}, protocol()
    )
    assert report["conflict_representations"] == 1
    assert report["conflicting_rows"] == 2
    assert set(retained.group) == {"example.org"}
    assert retained.groupby("group").partition.nunique().max() == 1
    assert report["prior_url_or_domain_excluded"] == 1


def test_group_split_is_stable_and_label_independent():
    frame = synthetic_frame().loc[lambda data: data.group.eq("example.org")]
    first, _ = expansion.curate_new([frame], set(), set(), protocol())
    second, _ = expansion.curate_new(
        [frame.assign(label=1 - frame.label)], set(), set(), protocol()
    )
    assert first.partition.tolist() == second.partition.tolist()
    assert first.digest.tolist() == second.digest.tolist()


def test_expanded_encoder_refuses_to_fit_on_holdout():
    with pytest.raises(ValueError, match="encoder_fit_partition_only"):
        expansion.make_encoder(pd.DataFrame({"partition": ["new_test"]}), {})


def test_positive_only_source_does_not_manufacture_a_false_positive_rate():
    frame = pd.DataFrame(
        {
            "partition": ["threshold"] * 124,
            "group": [f"g{i}" for i in range(124)],
            "label": [0] * 100 + [1] * 24,
            "training_source": ["binary"] * 104 + ["positive"] * 20,
        }
    )
    scores = np.array([0.1] * 100 + [0.9] * 24)
    point = expansion.source_point(frame, scores, 0.01, "threshold", protocol())
    assert point["source_rates"]["positive"]["fpr"] is None
    assert point["source_rates"]["positive"]["precision"] is None
    assert point["source_rates"]["positive"]["recall"] == 1
    assert "positive" in point["sources_without_sufficient_benign_for_constraint"]


def test_source_point_cannot_use_final_holdout_for_threshold_selection():
    frame = pd.DataFrame({"partition": ["new_test"]})
    with pytest.raises(ValueError, match="source_point_partition_violation"):
        expansion.source_point(frame, np.array([0.5]), 0.01, "threshold", protocol())


def test_expanded_selection_rejects_source_regression_even_with_larger_average():
    def row(macro, first, second):
        return {
            "macro_source_recall": macro,
            "minimum_source_recall": min(first, second),
            "source_rates": {
                "one": {"recall": first, "phishing": 100},
                "two": {"recall": second, "phishing": 100},
            },
            "overall": {"average_precision": 0.9},
        }

    baseline = row(0.5, 0.5, 0.5)
    result = expansion.choose(
        {"regression": row(0.6, 0.9, 0.3), "improvement": row(0.55, 0.55, 0.55)}, baseline
    )
    assert result["candidate"] == "improvement"
    assert result["eligible"] == ["improvement"]
