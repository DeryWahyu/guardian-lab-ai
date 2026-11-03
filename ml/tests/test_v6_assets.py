"""Original v6 evidence and local partition isolation survive model cleanup."""

import json

import pytest

from guardian_ml.metadata import checksum
from guardian_ml.paths import ROOT


def test_v6_aggregate_results_retain_counts_thresholds_and_positive_only_limits():
    report = json.loads((ROOT / "ml/reports/data-improvement-v6.json").read_text())
    manifest = json.loads((ROOT / "ml/policies/shadow-runtime-manifest.json").read_text())
    assert report["bundle_sha256"] == manifest["bundle_sha256"]
    assert report["thresholds"] == manifest["thresholds"]
    assert sum(report["fit_source_counts"].values()) == report["fit_rows"] == 532793
    for benchmark in report["binary_benchmarks"].values():
        for level in ("warning", "high"):
            result = benchmark["v6"][level]
            counts = result["confusion_matrix"]
            assert sum(counts.values()) == result["rows"]
            assert counts["tp"] + counts["fn"] == result["phishing"]
            assert counts["fp"] + counts["tn"] == result["benign"]
            assert (counts["tp"] + counts["tn"]) / result["rows"] == pytest.approx(
                result["accuracy"]
            )
            assert result["threshold"] == report["thresholds"][level]
    for result in report["new_community_positive_sensitivity"]["v6"].values():
        assert result["tp"] + result["fn"] == result["rows"] == 9269
        assert result["fpr"] is None
        assert result["traffic_precision"] is None
        assert result["binary_accuracy"] is None
    assert report["gold_set_indonesia_available"] is False


def test_local_v6_data_remains_bound_and_all_roles_are_domain_disjoint():
    directory = ROOT / "ml/runs/notebook-tfidf-logistic-v6/data"
    if not directory.exists():
        pytest.skip("Requires original local v6 data caches")
    pd = pytest.importorskip("pandas")
    pytest.importorskip("pyarrow")
    report = json.loads((ROOT / "ml/reports/data-improvement-v6.json").read_text())
    groups, digests = {}, {}
    for name, asset in report["data_manifest"]["outputs"].items():
        path = directory / asset["filename"]
        assert checksum(path) == asset["sha256"]
        columns = ["group", "digest", "label"]
        if name == "development":
            columns.append("partition")
        data = pd.read_parquet(path, columns=columns)
        assert len(data) == asset["rows"] and data.digest.is_unique
        if name == "development":
            assert set(data.partition) == {"fit", "tune", "calibration", "threshold"}
            assert data.groupby("group").partition.nunique().max() == 1
            for role, subset in data.groupby("partition"):
                assert set(subset.label) == {0, 1}
                groups[role], digests[role] = set(subset.group), set(subset.digest)
        else:
            groups[name], digests[name] = set(data.group), set(data.digest)
    roles = list(groups)
    for index, role in enumerate(roles):
        for other in roles[index + 1 :]:
            assert not groups[role].intersection(groups[other])
            assert not digests[role].intersection(digests[other])
