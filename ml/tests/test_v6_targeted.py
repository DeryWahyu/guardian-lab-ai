"""Protect literal-only intake, privacy, partition isolation and source selection."""

import importlib
import sys

import joblib
import numpy as np
import pandas as pd
import pytest

from guardian_ml.paths import ROOT

sys.path.insert(0, str(ROOT / "scripts"))
intake = importlib.import_module("intake_v6_targeted")
experiment = importlib.import_module("experiment_v6_targeted")
previous_control = importlib.import_module("v6_targeted_previous_control")
sanitizer = importlib.import_module("intake_v6_expansion")
sys.path.pop(0)
COLUMNS = ["rec_id", "url", "website", "result", "created_date"]


def sql(values):
    return (
        "INSERT INTO `index` (`rec_id`, `url`, `website`, `result`, `created_date`) VALUES "
        + values
        + ";"
    ).encode()


def test_literal_sql_handles_quotes_and_multiple_rows_without_execution():
    frame, audit = intake.read_sql_records(
        sql(
            "(1,'https://example.org/a\\'b','1.html',0,'2021-01-01'),(2,'https://example.net/a,b','2.html',1,NULL)"
        ),
        COLUMNS,
    )
    assert len(frame) == 2
    assert frame.url.iloc[0] == "https://example.org/a'b"
    assert frame.url.iloc[1] == "https://example.net/a,b"
    assert frame.created_date.iloc[1] is None
    assert audit["sql_executed"] is False


@pytest.mark.parametrize("value", ["LOAD_FILE('/private')", "1+1", "SLEEP(9)", "@variable"])
def test_sql_expressions_cannot_be_evaluated_or_treated_as_urls(value):
    with pytest.raises(ValueError, match="nonliteral|arity_or_expression"):
        intake.read_sql_records(sql(f"(1,{value},'1.html',0,NULL)"), COLUMNS)


def test_sql_unknown_labels_and_mutable_records_require_review():
    with pytest.raises(ValueError, match="label_schema"):
        intake.read_sql_records(sql("(1,'https://example.org','1.html',2,NULL)"), COLUMNS)
    with pytest.raises(ValueError, match="mutable_sql"):
        intake.read_sql_records(
            sql("(1,'https://example.org','1.html',0,NULL)")
            + b"\nDELETE FROM `index` WHERE rec_id=1;",
            COLUMNS,
        )


def test_sql_schema_reorder_is_rejected_before_any_persistence():
    with pytest.raises(ValueError, match="column_mismatch"):
        intake.read_sql_records(
            sql("(1,'https://example.org','1.html',0,NULL)"), list(reversed(COLUMNS))
        )


def test_sql_url_secrets_are_sanitized_before_cache():
    raw, _ = intake.read_sql_records(
        sql("(1,'https://example.org/password=SHORTSECRET?token=PRIVATE','1.html',0,NULL)"), COLUMNS
    )
    clean, _ = sanitizer.sanitize_source(raw, "pwd2021", "url", "result")
    assert "SHORTSECRET" not in clean.to_json()
    assert "PRIVATE" not in clean.to_json()
    assert "REDACTED" in clean.core.iloc[0]


def test_fitting_source_ablations_preserve_foundation_and_exclude_other_sources():
    frame = pd.DataFrame(
        {
            "partition": ["fit"] * 5,
            "training_source": ["phresh", "mendeley2020", "compphish", "wangchuk", "pwd2021"],
            "label": [0, 1, 1, 0, 0],
        }
    )
    protocol = {"foundation_sources": ["phresh", "mendeley"]}
    result = experiment.fitting_subset(frame, {"add_sources": ["compphish"]}, protocol)
    assert set(result.training_source) == {"phresh", "mendeley2020", "compphish"}
    with pytest.raises(ValueError, match="fitting_partition_only"):
        experiment.fitting_subset(frame.assign(partition="new_test"), {"add_sources": []}, protocol)


def test_pooled_threshold_respects_ties_and_refuses_holdout():
    frame = pd.DataFrame({"partition": ["threshold"] * 5, "label": [0, 0, 0, 0, 1]})
    scores = np.array([0.1, 0.2, 0.2, 0.9, 0.95])
    threshold = experiment.pooled_threshold(frame, scores, 0.25)
    assert np.sum(scores[:4] >= threshold) == 1
    with pytest.raises(ValueError, match="threshold_partition_only"):
        experiment.pooled_threshold(frame.assign(partition="new_test"), scores, 0.25)


def test_tune_selection_refuses_final_holdout():
    with pytest.raises(ValueError, match="selection_tune_partition_only"):
        experiment.tune_diagnostics(
            pd.DataFrame({"partition": ["new_test"]}), np.array([0.4]), 0.5, {}
        )


def test_selection_cannot_hide_source_regression_in_higher_average():
    def row(first, second):
        return {
            "macro_source_recall": (first + second) / 2,
            "minimum_source_recall": min(first, second),
            "source_rates": {
                "a": {"recall": first, "phishing": 100},
                "b": {"recall": second, "phishing": 100},
            },
            "overall": {"average_precision": 0.9},
        }

    baseline = row(0.5, 0.5)
    results = {
        "regression": {"strict_source_1pct": row(0.9, 0.3)},
        "improvement": {"strict_source_1pct": row(0.55, 0.55)},
    }
    selected = experiment.select_candidate(
        results, baseline, {"min_phishing_per_source_for_macro_recall": 20}
    )
    assert selected["eligible"] == ["improvement"]
    assert selected["candidate"] == "improvement"
    assert selected["selected_on"] == "tune_only"


def test_changed_sources_fail_before_loading_any_model(tmp_path, monkeypatch):
    run = tmp_path / "run"
    run.mkdir()
    experiment.write_json(
        run / "data-freeze.json", {"protocol_sha256": "changed", "source_hashes": {}}
    )
    monkeypatch.setattr(experiment, "RUN", run)
    monkeypatch.setattr(
        experiment,
        "RichArtifact",
        lambda: pytest.fail("must reject source drift before model loading"),
    )
    with pytest.raises(ValueError, match="source_or_protocol_changed"):
        experiment.check_freeze()


def test_previous_control_cannot_be_declared_after_test_scoring(tmp_path, monkeypatch):
    output = tmp_path / "report.json"
    output.write_text("{}")
    monkeypatch.setattr(previous_control, "REPORT", output)
    with pytest.raises(ValueError, match="before_targeted_test_scoring"):
        previous_control.freeze()


def test_previous_control_rejects_changed_artifact_before_prediction(tmp_path, monkeypatch):
    from guardian_ml.metadata import checksum

    frozen = tmp_path / "frozen.json"
    artifact = tmp_path / "artifact.bin"
    artifact.write_bytes(b"changed")
    experiment.write_json(
        frozen,
        {
            "source_sha256": checksum(previous_control.__file__),
            "protocol_sha256": checksum(previous_control.PROTOCOL),
            "previous_artifact_sha256": "wrong",
        },
    )
    monkeypatch.setattr(previous_control, "FROZEN", frozen)
    monkeypatch.setattr(previous_control, "PREVIOUS_ARTIFACT", artifact)
    monkeypatch.setattr(previous_control, "OUTPUT", tmp_path / "absent.json")
    monkeypatch.setattr(previous_control, "check_freeze", lambda: {})
    monkeypatch.setattr(
        previous_control.joblib,
        "load",
        lambda *_: pytest.fail("must reject tamper before model loading"),
    )
    with pytest.raises(ValueError, match="previous_control_binding_changed"):
        previous_control.evaluate()


def test_real_targeted_saved_model_parity(tmp_path):
    import json

    selected_path = experiment.RUN / "selected-frozen.json"
    if not selected_path.exists():
        pytest.skip("local ignored targeted artifact not installed")
    frozen = experiment.check_freeze()
    selected = json.loads(selected_path.read_text())
    original = joblib.load(ROOT / selected["artifact"])
    cache = pd.read_parquet(ROOT / frozen["partitions"]["threshold"]["path"], columns=["core"])
    probes = cache.core.iloc[:128].tolist() + [
        "http://example.org/password=SHORTSECRET",
        "https://example.org/password=SHORTSECRET",
    ]
    before = experiment.predict_bundle(original, probes)
    target = tmp_path / "roundtrip.joblib"
    joblib.dump(original, target, compress=3)
    restored = joblib.load(target)
    after = experiment.predict_bundle(restored, probes)
    assert np.array_equal(before, after)
    assert after[-1] == after[-2]
    assert restored["metadata"]["production_ready"] is False
