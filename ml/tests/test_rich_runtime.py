"""Real frozen-v6 parity, source/schema rejection, and offline abstention."""

import json
import shutil
import socket

import joblib
import numpy as np
import pytest

from guardian_ml.metadata import checksum
from guardian_ml.paths import ROOT
from guardian_ml.rich_artifact import ArtifactRejected, RichArtifact, workspace_path


@pytest.fixture(scope="module")
def artifact():
    path = ROOT / "ml/runs/notebook-tfidf-logistic-v6/artifacts/url-core-logistic-v6.joblib"
    if not path.exists():
        pytest.skip("Requires the local frozen v6 training artifact")
    return RichArtifact()


def trusted_copy(tmp_path):
    manifest = json.loads((ROOT / "ml/policies/shadow-runtime-manifest.json").read_text())
    paths = [
        "ml/policies/shadow-runtime-manifest.json",
        *manifest["source_hashes"],
        manifest["artifact_path"],
        manifest["frozen_metadata_path"],
    ]
    for relative in paths:
        destination = tmp_path / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / relative, destination)
    return manifest


def test_real_runtime_matches_frozen_notebook_synthetic_reference(artifact):
    from guardian_ml.preprocessing import prepare_url

    reference = json.loads((ROOT / "ml/provenance/v6-runtime-reference.json").read_text())
    assert reference["artifact_sha256"] == artifact.manifest["bundle_sha256"]
    assert reference["training_notebook_code_sha256"] == artifact.metadata["code_sha256"]
    cores = [prepare_url(case["url"]).core for case in reference["cases"]]
    assert cores == [case["core"] for case in reference["cases"]]
    expected = np.array([case["probability"] for case in reference["cases"]])
    assert float(np.max(np.abs(artifact.predict_cores(cores) - expected))) < 1e-12


def test_checksum_rejected_before_deserialization(artifact, tmp_path, monkeypatch):
    manifest = trusted_copy(tmp_path)
    model = tmp_path / manifest["artifact_path"]
    with model.open("ab") as stream:
        stream.write(b"corrupt")
    monkeypatch.setattr(joblib, "load", lambda *_: pytest.fail("Untrusted binary deserialized"))
    with pytest.raises(ArtifactRejected, match="model_checksum_mismatch"):
        RichArtifact(tmp_path)


def test_source_change_rejected(artifact, tmp_path):
    trusted_copy(tmp_path)
    path = tmp_path / "ml/src/guardian_ml/rich_features.py"
    path.write_text(path.read_text() + "\n# source changed\n")
    with pytest.raises(ArtifactRejected, match="runtime_source_checksum_mismatch"):
        RichArtifact(tmp_path)


def test_schema_rejected(artifact, tmp_path):
    manifest = trusted_copy(tmp_path)
    manifest["schema_version"] = "unknown"
    (tmp_path / "ml/policies/shadow-runtime-manifest.json").write_text(json.dumps(manifest))
    with pytest.raises(ArtifactRejected, match="unsupported_feature_schema"):
        RichArtifact(tmp_path)


def test_incompatible_numeric_schema_rejected(artifact, tmp_path):
    manifest = trusted_copy(tmp_path)
    model_path = tmp_path / manifest["artifact_path"]
    bundle = joblib.load(model_path)
    bundle["encoder"]["scaler"].n_features_in_ += 1
    joblib.dump(bundle, model_path, compress=3)
    frozen_path = tmp_path / manifest["frozen_metadata_path"]
    frozen = json.loads(frozen_path.read_text())
    frozen["bundle_sha256"] = checksum(model_path)
    frozen_path.write_text(json.dumps(frozen))
    manifest["bundle_sha256"] = frozen["bundle_sha256"]
    manifest["frozen_metadata_sha256"] = checksum(frozen_path)
    (tmp_path / "ml/policies/shadow-runtime-manifest.json").write_text(json.dumps(manifest))
    with pytest.raises(ArtifactRejected, match="numeric_feature_schema_mismatch"):
        RichArtifact(tmp_path)


def test_dependency_version_rejected(artifact, monkeypatch):
    monkeypatch.setattr("guardian_ml.rich_artifact.version", lambda _: "incompatible")
    with pytest.raises(ArtifactRejected, match="dependency_versions_mismatch"):
        RichArtifact()


@pytest.mark.parametrize("change", ["empty", "missing", "extra", "version"])
def test_inference_dependency_subset_cannot_weaken_training_binding(artifact, tmp_path, change):
    manifest = trusted_copy(tmp_path)
    dependencies = manifest["inference_dependencies"]
    if change == "empty":
        dependencies.clear()
    elif change == "missing":
        dependencies.pop("numpy")
    elif change == "extra":
        dependencies["unrelated"] = "0"
    else:
        dependencies["numpy"] = "incompatible"
    (tmp_path / "ml/policies/shadow-runtime-manifest.json").write_text(json.dumps(manifest))
    with pytest.raises(ArtifactRejected, match="inference_dependency_schema_mismatch"):
        RichArtifact(tmp_path)


def test_inference_does_not_require_training_only_packages(artifact, monkeypatch):
    from importlib.metadata import version

    def runtime_version(name):
        assert name not in {"pyarrow", "matplotlib", "catboost", "xgboost", "torch"}
        return version(name)

    monkeypatch.setattr("guardian_ml.rich_artifact.version", runtime_version)
    restored = RichArtifact()
    assert restored.metadata["thresholds"] == artifact.metadata["thresholds"]


def test_workspace_path_cannot_escape(tmp_path):
    with pytest.raises(ArtifactRejected, match="outside_workspace"):
        workspace_path(tmp_path, "../outside.joblib")
    with pytest.raises(ArtifactRejected, match="invalid_artifact_relative_path"):
        workspace_path(tmp_path, str(tmp_path / "outside.joblib"))


def test_url_qr_and_scheme_parity_without_network(artifact, monkeypatch):
    pytest.importorskip("pydantic")
    from guardian_ml.shadow_predictor import ShadowPredictor

    def reject_network(*args, **kwargs):
        raise AssertionError("Inference attempted network access")

    monkeypatch.setattr(socket, "create_connection", reject_network)
    predictor = ShadowPredictor(artifact)
    a = predictor.predict("http://example.org/login", "URL")
    b = predictor.predict("https://example.org/login", "QR")
    assert a.model_score == b.model_score
    assert a.decision == "needs_review" and not a.production_ready


def test_sensitive_context_not_echoed_and_error_is_not_low(artifact):
    pytest.importorskip("pydantic")
    from guardian_ml.shadow_predictor import ShadowPredictor

    predictor = ShadowPredictor(artifact)
    result = predictor.predict(
        "https://example.org/email/person%40example.net?token=SYNTHETIC-PRIVATE-MARKER#secret"
    )
    serialized = result.model_dump_json()
    assert "SYNTHETIC-PRIVATE-MARKER" not in serialized
    assert "person" not in serialized and "example.org" not in serialized
    assert "query_context_excluded" in result.reason_codes
    invalid = predictor.predict("http://127.0.0.1/")
    assert invalid.status == "unsupported_input"
    assert invalid.risk_band is None and invalid.model_score is None


def test_structural_flags_never_override_model_score(artifact):
    pytest.importorskip("pydantic")
    from guardian_ml.preprocessing import prepare_url
    from guardian_ml.shadow_predictor import ShadowPredictor

    url = "https://example.github.io/" + "path/" * 25
    reply = ShadowPredictor(artifact).predict(url)
    assert "private_hosting_tenant_requires_context" in reply.reason_codes
    assert "long_url_requires_context" in reply.reason_codes
    assert reply.model_score == float(artifact.predict_cores([prepare_url(url).core])[0])
