"""No URL echo, no unsafe fallback, bounded requests, and aggregate-only monitoring."""

from concurrent.futures import ThreadPoolExecutor
import asyncio
import json

import pytest

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient
from pydantic import ValidationError

from guardian_ml.paths import ROOT
from guardian_ml.release_gates import assess_release
from guardian_ml.rich_artifact import RichArtifact
from guardian_ml.shadow_contracts import GeekView, HumanView, ShadowResult
from guardian_ml.shadow_metrics import AggregateMonitor
from guardian_ml.shadow_predictor import ShadowPredictor
from guardian_ml.shadow_service import MAX_BODY_BYTES, create_app


@pytest.fixture(scope="module")
def predictor():
    path = ROOT / "ml/runs/notebook-tfidf-logistic-v6/artifacts/url-core-logistic-v6.joblib"
    if not path.exists():
        pytest.skip("Requires local frozen v6 artifact")
    return ShadowPredictor(RichArtifact())


def test_shadow_api_real_model_and_no_target_echo(predictor):
    with TestClient(create_app(predictor_factory=lambda: predictor)) as client:
        health = client.get("/health").json()
        assert health["model_available"] and not health["production_ready"]
        payload = {
            "url": "https://example.org/login?token=SYNTHETIC-PRIVATE-MARKER",
            "input_type": "QR",
        }
        reply = client.post("/predict", json=payload)
        body = reply.json()
        assert reply.status_code == 200 and body["status"] == "complete"
        assert body["input_type"] == "QR" and body["decision"] == "needs_review"
        assert not body["geek"]["qr_image_decoded_by_service"]
        assert "SYNTHETIC-PRIVATE-MARKER" not in reply.text and "example.org" not in reply.text
        assert body["model_score"] == predictor.predict(payload["url"], "QR").model_score


@pytest.mark.parametrize(
    "payload",
    [
        {"url": 123},
        {"url": "https://example.org", "secret": "SYNTHETIC-PRIVATE-MARKER"},
        {"url": "https://example.org", "input_type": "SYNTHETIC-PRIVATE-MARKER"},
        {"url": "x" * 16385},
        [],
        {},
    ],
)
def test_invalid_schema_never_echoes_input(payload):
    with TestClient(create_app(predictor_factory=lambda: None)) as client:
        reply = client.post("/predict", json=payload)
        assert reply.status_code == 422
        assert reply.json()["reason"] == "invalid_request_schema"
        assert "SYNTHETIC-PRIVATE-MARKER" not in reply.text
        assert "example.org" not in reply.text


def test_body_size_and_content_type_and_invalid_json():
    with TestClient(create_app(predictor_factory=lambda: None)) as client:
        assert (
            client.post(
                "/predict", content="{}", headers={"content-type": "text/plain"}
            ).status_code
            == 415
        )
        malformed = client.post(
            "/predict",
            content='{"url":"SYNTHETIC-PRIVATE-MARKER"',
            headers={"content-type": "application/json"},
        )
        assert malformed.status_code == 400 and "SYNTHETIC-PRIVATE-MARKER" not in malformed.text
        oversized = client.post(
            "/predict",
            content=b"x" * (MAX_BODY_BYTES + 1),
            headers={"content-type": "application/json"},
        )
        assert oversized.status_code == 413


def test_unavailable_model_is_not_low_and_does_not_log_exception(capsys, caplog):
    def unavailable():
        raise FileNotFoundError("SYNTHETIC-PRIVATE-MARKER")

    with TestClient(create_app(predictor_factory=unavailable)) as client:
        reply = client.post("/predict", json={"url": "https://example.org"})
        assert reply.status_code == 503
        assert reply.json()["status"] == "unavailable"
        assert reply.json()["risk_band"] is None and reply.json()["model_score"] is None
        assert "SYNTHETIC-PRIVATE-MARKER" not in reply.text
    captured = capsys.readouterr()
    assert "SYNTHETIC-PRIVATE-MARKER" not in captured.out + captured.err + caplog.text


def test_streamed_body_without_content_length_is_bounded():
    import httpx

    async def run_request():
        async def chunks():
            yield b"x" * (MAX_BODY_BYTES // 2)
            yield b"x" * (MAX_BODY_BYTES // 2)
            yield b"SYNTHETIC-PRIVATE-MARKER"

        transport = httpx.ASGITransport(app=create_app(predictor_factory=lambda: None))
        async with httpx.AsyncClient(transport=transport, base_url="http://shadow.test") as client:
            reply = await client.post(
                "/predict", content=chunks(), headers={"content-type": "application/json"}
            )
        assert "content-length" not in reply.request.headers
        assert reply.status_code == 413
        assert reply.json()["reason"] == "request_body_too_large"
        assert "SYNTHETIC-PRIVATE-MARKER" not in reply.text

    asyncio.run(run_request())


def test_prediction_failure_is_unavailable_without_echo(capsys, caplog):
    class BrokenPredictor:
        def predict(self, url, input_type):
            raise RuntimeError("SYNTHETIC-PRIVATE-MARKER")

    with TestClient(create_app(predictor_factory=BrokenPredictor)) as client:
        reply = client.post("/predict", json={"url": "https://example.org"})
        assert reply.status_code == 503
        assert reply.json()["risk_band"] is None and reply.json()["model_score"] is None
        assert "SYNTHETIC-PRIVATE-MARKER" not in reply.text
        counters = client.get("/metrics").json()
        assert counters["by_status"] == {"unavailable": 1}
    captured = capsys.readouterr()
    assert "SYNTHETIC-PRIVATE-MARKER" not in captured.out + captured.err + caplog.text


def test_unsupported_url_never_becomes_low(predictor):
    with TestClient(create_app(predictor_factory=lambda: predictor)) as client:
        reply = client.post("/predict", json={"url": "file:///tmp/example"})
        assert reply.status_code == 422
        assert reply.json()["status"] == "unsupported_input"
        assert reply.json()["model_score"] is None and reply.json()["risk_band"] is None


def test_production_mode_cannot_bypass_gate(monkeypatch):
    monkeypatch.setenv("GUARDIAN_ML_MODE", "production")
    with pytest.raises(ValueError, match="production_gate_not_satisfied"):
        create_app()
    gate = assess_release()
    assert not gate["production_ready"] and gate["pending_evidence"]
    assert any(f["status"] == "failed" for f in gate["findings"])


def test_response_contract_rejects_low_on_unavailable():
    with pytest.raises(ValidationError, match="unsupported_or_unavailable_cannot_be_low_risk"):
        ShadowResult(
            status="unavailable",
            input_type="URL",
            risk_band="LOW",
            model_score=0,
            human=HumanView(title="Unavailable", explanation="Needs review"),
            geek=GeekView(),
        )


def test_monitor_is_aggregate_only_and_thread_safe():
    monitor = AggregateMonitor()

    def record(_):
        monitor.record(status="complete", input_type="URL", risk_band="LOW", elapsed_ms=5)

    with ThreadPoolExecutor(max_workers=4) as pool:
        list(pool.map(record, range(100)))
    snapshot = monitor.snapshot()
    assert snapshot["total_requests"] == 100
    assert snapshot["latency_histogram"]["le_10_ms"] == 100
    assert snapshot["quality_metrics"] == {"precision": None, "recall": None, "fpr": None}
    assert (
        not snapshot["individual_events_persisted"] and not snapshot["target_identifiers_persisted"]
    )
    assert not any(
        name in json.dumps(snapshot).lower()
        for name in ["example.org", "email", "token", "user_id"]
    )
    with pytest.raises(TypeError):
        monitor.record(status="complete", elapsed_ms=1, url="https://example.org")
