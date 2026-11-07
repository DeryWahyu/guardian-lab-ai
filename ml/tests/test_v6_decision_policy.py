"""User threshold changes bands while preserving scores, abstention and provenance."""

import json
from types import SimpleNamespace

import numpy as np
import pytest
from fastapi.testclient import TestClient

from guardian_ml.paths import ROOT
from guardian_ml.preprocessing import prepare_url
from guardian_ml.rich_artifact import RichArtifact
from guardian_ml.shadow_predictor import ShadowPredictor
from guardian_ml.shadow_service import create_app

ORIGINAL = {"warning": 0.904713285827399, "high": 0.9884744926236343}
ACTIVE = {"warning": 0.5, "high": ORIGINAL["high"]}


def fixed_predictor(score):
    artifact = SimpleNamespace(
        metadata={
            "version": "notebook-url-core-v6",
            "thresholds": dict(ORIGINAL),
            "high_enabled": True,
        },
        manifest={"bundle_sha256": "synthetic-model-hash"},
        decision_thresholds=dict(ACTIVE),
        decision_policy_version="v6-user-warning-0.5-20261107",
        predict_cores=lambda cores: np.full(len(cores), score),
    )
    return ShadowPredictor(artifact)


@pytest.mark.parametrize(
    "score,band",
    [
        (np.nextafter(0.5, 0), "LOW"),
        (0.5, "MEDIUM"),
        (0.8, "MEDIUM"),
        (np.nextafter(ORIGINAL["high"], 0), "MEDIUM"),
        (ORIGINAL["high"], "HIGH"),
        (1.0, "HIGH"),
    ],
)
def test_api_threshold_boundaries_and_privacy(score, band):
    predictor = fixed_predictor(score)
    with TestClient(create_app(predictor_factory=lambda: predictor)) as client:
        for input_type in ("URL", "QR"):
            response = client.post(
                "/predict",
                json={
                    "url": "https://example.org/login?token=SYNTHETIC-PRIVATE-MARKER",
                    "input_type": input_type,
                },
            )
            body = response.json()
            assert response.status_code == 200
            assert body["model_score"] == score and body["risk_band"] == band
            assert body["geek"]["thresholds"] == ACTIVE
            assert body["geek"]["frozen_thresholds"] == ORIGINAL
            assert body["geek"]["decision_policy_version"] == "v6-user-warning-0.5-20261107"
            assert not body["production_ready"] and body["decision"] == "needs_review"
            assert (
                "example.org" not in response.text
                and "SYNTHETIC-PRIVATE-MARKER" not in response.text
            )
    assert predictor.artifact.metadata["thresholds"] == ORIGINAL


def test_new_threshold_never_scores_unsupported_input():
    predictor = fixed_predictor(1.0)
    predictor.artifact.predict_cores = lambda _: pytest.fail("unsupported input reached model")
    result = predictor.predict("file:///private")
    assert result.status == "unsupported_input"
    assert result.model_score is None and result.risk_band is None
    assert result.geek.thresholds is None and result.geek.frozen_thresholds is None


def test_real_v6_scores_remain_identical_and_changed_bands_are_explicit():
    path = ROOT / "ml/runs/notebook-tfidf-logistic-v6/artifacts/url-core-logistic-v6.joblib"
    if not path.exists():
        pytest.skip("Requires original frozen v6 binary")
    artifact = RichArtifact()
    predictor = ShadowPredictor(artifact)
    reference = json.loads((ROOT / "ml/provenance/v6-runtime-reference.json").read_text())
    cores = [prepare_url(case["url"]).core for case in reference["cases"]]
    batch = artifact.predict_cores(cores)
    np.testing.assert_allclose(
        batch,
        [case["probability"] for case in reference["cases"]],
        atol=reference["absolute_tolerance"],
        rtol=0,
    )
    changed = 0
    for case, core in zip(reference["cases"], cores):
        reply = predictor.predict(case["url"])
        # Compare equal batch shapes: float32 normalization can round scalar and batch
        # features differently even in the unchanged original runtime.
        scalar = float(artifact.predict_cores([core])[0])
        assert reply.model_score == scalar
        expected = "HIGH" if scalar >= ACTIVE["high"] else "MEDIUM" if scalar >= 0.5 else "LOW"
        assert reply.risk_band == expected
        changed += 0.5 <= scalar < ORIGINAL["warning"]
    assert changed > 0
    assert artifact.metadata["thresholds"] == ORIGINAL
    assert artifact.decision_thresholds == ACTIVE
