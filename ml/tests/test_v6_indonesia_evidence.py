"""Use actual prefixed template filenames; never silently overlook review files."""

import importlib
import sys

import pytest

from guardian_ml.paths import ROOT

sys.path.insert(0, str(ROOT / "scripts"))
audit = importlib.import_module("audit_v6_indonesia_evidence")
sys.path.pop(0)


def test_census_reads_all_prescribed_prefixed_inputs(tmp_path):
    templates = ROOT / "ml/templates"
    for name in audit.NAMES:
        (tmp_path / name).write_bytes((templates / name).read_bytes())
    result = audit.census(tmp_path, templates)
    assert len(result) == 5
    assert all(value["exists"] and value["rows"] == 0 for value in result.values())
    assert all("sha256" in value for value in result.values())


def test_census_rejects_wrong_schema(tmp_path):
    (tmp_path / "indonesia-candidates.csv").write_text("url,label\n", encoding="utf-8")
    with pytest.raises(ValueError, match="schema_mismatch"):
        audit.census(tmp_path, ROOT / "ml/templates")
