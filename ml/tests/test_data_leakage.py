"""The audit must reject leakage even when row counts and labels look valid."""

import hashlib

import pandas as pd
import pytest

from guardian_ml import dataset
from guardian_ml.preprocessing import prepare_url


@pytest.fixture
def synthetic_data(tmp_path, monkeypatch):
    rows = []
    dates = {
        "fit": "2024-12-01",
        "tune": "2025-01-01",
        "calibration": "2025-01-01",
        "threshold": "2025-01-01",
        "test": "2025-09-08",
    }
    for partition, date in dates.items():
        for index in range(400):
            parsed = prepare_url(f"https://{partition}-{index}.example/path")
            rows.append(
                {
                    "core": parsed.core,
                    "digest": parsed.digest,
                    "group": parsed.group,
                    "label": index % 2,
                    "date": date,
                    "partition": partition,
                    "novel_domain": partition == "test",
                }
            )
    frame = pd.DataFrame(rows)
    monkeypatch.setattr(dataset, "DATA", tmp_path)
    monkeypatch.setattr(dataset, "REPORTS", tmp_path)
    return frame, tmp_path / "curated.parquet"


def test_independent_audit_accepts_supported_disjoint_data(synthetic_data):
    frame, path = synthetic_data
    frame.to_parquet(path, index=False)
    assert all(dataset.independent_audit().values())


def test_independent_audit_rejects_a_shared_development_domain(synthetic_data):
    frame, path = synthetic_data
    frame.loc[frame.partition.eq("calibration").idxmax(), "group"] = frame.group.iloc[0]
    frame.to_parquet(path, index=False)
    with pytest.raises(AssertionError, match="development_groups_pairwise_disjoint"):
        dataset.independent_audit()


def test_independent_audit_rejects_a_future_training_row(synthetic_data):
    frame, path = synthetic_data
    frame.loc[0, "date"] = "2026-01-01"
    frame.to_parquet(path, index=False)
    with pytest.raises(AssertionError, match="strict_time_development_before_test"):
        dataset.independent_audit()


def test_independent_audit_rejects_an_exact_test_url_in_training(synthetic_data):
    frame, path = synthetic_data
    index = frame.partition.eq("test").idxmax()
    frame.loc[index, ["core", "group"]] = frame.loc[0, ["core", "group"]].to_numpy()
    frame.loc[index, "digest"] = hashlib.sha256(frame.core.iloc[0].encode()).hexdigest()
    frame.to_parquet(path, index=False)
    with pytest.raises(AssertionError, match="no_development_url_in_test"):
        dataset.independent_audit()
