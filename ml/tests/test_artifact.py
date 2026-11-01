"""Run against the real local trained bundle; no prediction oracle or fake model."""

import json
import shutil

import pytest

from guardian_ml.paths import ARTIFACTS
from guardian_ml.predictor import Predictor

pytestmark = pytest.mark.skipif(
    not (ARTIFACTS / "manifest.json").exists(),
    reason="Requires a locally trained real artifact",
)


def test_real_model_url_qr_query_and_reload_parity():
    model = Predictor()
    value = "https://example.org/login?email=person%40example.net"
    url = model.predict(value, "URL")
    qr = model.predict(value, "QR")
    assert 0 <= url["phishing_probability"] <= 1
    assert url["phishing_probability"] == qr["phishing_probability"]
    assert (
        url["phishing_probability"]
        == model.predict("https://example.org/login")["phishing_probability"]
    )
    assert url == Predictor().predict(value)
    assert "person" not in json.dumps(url)


def test_corrupted_bundle_is_rejected_before_deserialization(tmp_path):
    shutil.copy(ARTIFACTS / "manifest.json", tmp_path / "manifest.json")
    manifest = json.loads((tmp_path / "manifest.json").read_text())
    shutil.copy(ARTIFACTS / manifest["bundle_filename"], tmp_path / manifest["bundle_filename"])
    with (tmp_path / manifest["bundle_filename"]).open("ab") as stream:
        stream.write(b"corrupt")
    with pytest.raises(ValueError, match="checksum mismatch"):
        Predictor(tmp_path)


def test_incompatible_schema_is_rejected(tmp_path):
    manifest = json.loads((ARTIFACTS / "manifest.json").read_text())
    manifest["feature_schema"] = ["different_schema"]
    (tmp_path / "manifest.json").write_text(json.dumps(manifest))
    shutil.copy(ARTIFACTS / manifest["bundle_filename"], tmp_path / manifest["bundle_filename"])
    with pytest.raises(ValueError, match="Feature schema mismatch"):
        Predictor(tmp_path)
