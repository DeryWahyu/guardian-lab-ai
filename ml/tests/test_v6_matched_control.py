"""Supplemental controls cannot be introduced after final tests or mutated silently."""

import importlib
import json
import sys

import pytest

from guardian_ml.paths import ROOT

sys.path.insert(0, str(ROOT / "scripts"))
control = importlib.import_module("v6_expanded_matched_control")
sys.path.pop(0)


def test_control_freeze_refuses_to_start_after_final_test_report(tmp_path, monkeypatch):
    report = tmp_path / "ml/reports/v6-expanded-data-evaluation.json"
    report.parent.mkdir(parents=True)
    report.write_text("{}")
    monkeypatch.setattr(control, "ROOT", tmp_path)
    monkeypatch.setattr(control, "POLICY", tmp_path / "new-control.json")
    with pytest.raises(ValueError, match="matched_control_must_be_frozen_before_test"):
        control.freeze()


def test_control_evaluation_rejects_changed_protocol_before_loading_models(tmp_path, monkeypatch):
    supplement = tmp_path / "supplement.json"
    supplement.write_text("{}")
    policy = tmp_path / "control.json"
    policy.write_text(json.dumps({"supplement_sha256": "mismatch", "script_sha256": "mismatch"}))
    monkeypatch.setattr(control, "POLICY", policy)
    monkeypatch.setattr(control, "SUPPLEMENT", supplement)
    monkeypatch.setattr(control, "REPORT", tmp_path / "absent-report.json")
    with pytest.raises(ValueError, match="matched_control_protocol_or_source_changed"):
        control.evaluate()
