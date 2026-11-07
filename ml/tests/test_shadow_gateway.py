"""Authentication, quotas, bounded work and private error responses for shadow."""

import asyncio
import json
import shutil
import time

import httpx
import pytest
from fastapi.testclient import TestClient

from guardian_ml.gateway_controls import GatewaySettings, TokenBucket, sensitive_path
from guardian_ml.paths import ROOT
from guardian_ml.shadow_gateway import ShadowGateway, create_app, verify_gateway_manifest
from guardian_ml.shadow_predictor import ShadowPredictor
from guardian_ml.shadow_predictor import unavailable_reply
from guardian_ml.rich_artifact import RichArtifact

KEY = "synthetic-gateway-test-key-32-characters"
HEADERS = {"Authorization": "Bearer " + KEY}


class Child:
    def __init__(self, delay=0, body=b'{"production_ready":false}', failure=False):
        self.delay, self.body, self.failure, self.calls = delay, body, failure, 0

    async def __call__(self, scope, receive, send):
        self.calls += 1
        await asyncio.sleep(self.delay)
        if self.failure:
            raise ValueError("SYNTHETIC-PRIVATE-MARKER")
        await send({"type": "http.response.start", "status": 200, "headers": []})
        await send({"type": "http.response.body", "body": self.body})


def gateway(child=None, **kwargs):
    return ShadowGateway(child or Child(), GatewaySettings(key=KEY, **kwargs))


def test_token_bucket_is_bounded_and_refills_without_client_identity_storage():
    clock = [0.0]
    bucket = TokenBucket(60, 2, lambda: clock[0])
    assert bucket.take()[0] and bucket.take()[0]
    assert bucket.take() == (False, 1)
    clock[0] = 1
    assert bucket.take()[0]


@pytest.mark.parametrize(
    "changes",
    [
        {"key": "short"},
        {"key": "x" * 32 + " "},
        {"max_inflight": 0},
        {"requests_per_minute": float("nan")},
        {"inference_timeout": 0},
        {"burst": 1.5},
        {"max_body_bytes": 1000000},
    ],
)
def test_unsafe_settings_fail_without_echoing_secret(changes):
    with pytest.raises(ValueError) as error:
        GatewaySettings(**{"key": KEY, **changes})
    assert KEY not in str(error.value)
    assert KEY not in repr(GatewaySettings(key=KEY))


@pytest.mark.parametrize(
    "path", ["/token=short-secret", "/a;password:short-secret", "/%2574oken%253Dshort-secret"]
)
def test_privacy_assignment_detection_does_not_change_model_view(path):
    assert sensitive_path("https://example.org" + path)
    assert not sensitive_path("https://example.org/path?token=short-secret")
    assert not sensitive_path("https://example.org/token=REDACTED")


def test_unauthenticated_requests_do_not_read_body_or_call_model():
    child = Child()
    app = gateway(child)

    async def invoke():
        async def forbidden_receive():
            pytest.fail("unauthenticated request body must not be read")

        messages = []

        async def send(message):
            messages.append(message)

        await app(
            {"type": "http", "path": "/predict", "method": "POST", "headers": []},
            forbidden_receive,
            send,
        )
        assert messages[0]["status"] == 401

    asyncio.run(invoke())
    assert child.calls == 0


def test_authentication_quota_and_live_probe_are_distinct():
    async def invoke():
        app = gateway(burst=2, requests_per_minute=0.1)
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            assert (await client.get("/live")).status_code == 200
            assert (await client.get("/health")).status_code == 401
            duplicate = await client.get(
                "/health", headers=[("authorization", "Bearer " + KEY)] * 2
            )
            assert duplicate.status_code == 401
            assert (await client.get("/health", headers=HEADERS)).status_code == 200
            assert (await client.get("/health", headers=HEADERS)).status_code == 200
            response = await client.get("/health", headers=HEADERS)
            assert response.status_code == 429 and "retry-after" in response.headers
            assert response.json()["model_score"] is None and response.json()["risk_band"] is None

    asyncio.run(invoke())


def test_concurrency_is_bounded_and_overload_has_no_score():
    async def invoke():
        app = gateway(Child(delay=0.06), max_inflight=1, burst=20)
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            responses = await asyncio.gather(
                *[client.get("/health", headers=HEADERS) for _ in range(6)]
            )
            assert sum(r.status_code == 200 for r in responses) == 1
            assert all(r.json()["model_score"] is None for r in responses if r.status_code == 503)
            assert app.monitor.snapshot()["peak_inflight"] == 1
            assert app.monitor.snapshot()["inflight"] == 0

    asyncio.run(invoke())


def test_timeout_keeps_capacity_until_real_work_finishes():
    async def invoke():
        child = Child(delay=0.08)
        app = gateway(child, max_inflight=1, inference_timeout=0.01)
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            first = await client.get("/health", headers=HEADERS)
            assert first.status_code == 504 and first.json()["model_score"] is None
            assert app.monitor.snapshot()["inflight"] == 1
            second = await client.get("/health", headers=HEADERS)
            assert second.status_code == 503 and child.calls == 1
            await asyncio.sleep(0.1)
            assert app.monitor.snapshot()["inflight"] == 0 and not app.tasks

    asyncio.run(invoke())


def test_timeout_does_not_abandon_the_actual_threadpool_prediction():
    class SlowPredictor:
        calls = 0

        def predict(self, url, input_type):
            self.calls += 1
            time.sleep(0.12)
            return unavailable_reply(input_type)

    predictor = SlowPredictor()
    app = create_app(
        settings=GatewaySettings(key=KEY, max_inflight=1, inference_timeout=0.02),
        predictor_factory=lambda: predictor,
    )
    with TestClient(app) as client:
        response = client.post("/predict", json={"url": "https://example.org"}, headers=HEADERS)
        assert response.status_code == 504
        assert app.monitor.snapshot()["inflight"] == 1
        next_response = client.post(
            "/predict", json={"url": "https://example.org"}, headers=HEADERS
        )
        assert next_response.status_code == 503 and predictor.calls == 1
        time.sleep(0.15)
        assert app.monitor.snapshot()["inflight"] == 0


def test_client_cancellation_keeps_running_work_accounted_for():
    async def invoke():
        app = gateway(Child(delay=0.1), max_inflight=1)
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            request = asyncio.create_task(client.get("/health", headers=HEADERS))
            await asyncio.sleep(0.01)
            request.cancel()
            with pytest.raises(asyncio.CancelledError):
                await request
            assert app.monitor.snapshot()["inflight"] == 1
            await asyncio.sleep(0.12)
            assert app.monitor.snapshot()["inflight"] == 0 and not app.tasks

    asyncio.run(invoke())


def test_body_deadline_and_chunked_actual_size_are_enforced():
    async def invoke():
        child = Child()
        app = gateway(child, body_timeout=0.01, max_body_bytes=16)
        messages = []

        async def send(m):
            messages.append(m)

        async def slow():
            await asyncio.sleep(0.1)
            return {"type": "http.request", "body": b"{}"}

        scope = {
            "type": "http",
            "path": "/predict",
            "method": "POST",
            "headers": [(b"authorization", ("Bearer " + KEY).encode())],
        }
        await app(scope, slow, send)
        assert messages[0]["status"] == 408
        events = iter(
            [
                {"type": "http.request", "body": b"a" * 10, "more_body": True},
                {"type": "http.request", "body": b"b" * 10},
            ]
        )

        async def receive():
            return next(events)

        messages.clear()
        await app(scope, receive, send)
        assert messages[0]["status"] == 413 and child.calls == 0

    asyncio.run(invoke())


@pytest.mark.parametrize(
    "child", [Child(body=b"SYNTHETIC-PRIVATE-MARKER" * 5000), Child(failure=True)]
)
def test_failed_or_oversized_inference_does_not_leak_partial_output(child, capsys, caplog):
    async def invoke():
        app = gateway(child)
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.get("/health", headers=HEADERS)
            assert response.status_code == 503
            assert "SYNTHETIC-PRIVATE-MARKER" not in response.text

    asyncio.run(invoke())
    captured = capsys.readouterr()
    assert "SYNTHETIC-PRIVATE-MARKER" not in captured.out + captured.err + caplog.text


def test_manifest_rejects_tampered_sources_and_partial_dependencies(tmp_path):
    manifest = json.loads((ROOT / "ml/policies/shadow-gateway-manifest.json").read_text())
    paths = ["ml/policies/shadow-serving-manifest.json", *manifest["source_hashes"]]
    for name in paths:
        target = tmp_path / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / name, target)
    path = tmp_path / "ml/policies/shadow-gateway-manifest.json"
    path.write_text(json.dumps(manifest))
    verify_gateway_manifest(tmp_path)
    partial = {
        **manifest,
        "inference_dependencies": {"numpy": manifest["inference_dependencies"]["numpy"]},
    }
    path.write_text(json.dumps(partial))
    with pytest.raises(ValueError, match="dependencies_changed"):
        verify_gateway_manifest(tmp_path)
    path.write_text(json.dumps(manifest))
    (tmp_path / next(iter(manifest["source_hashes"]))).write_text("changed")
    with pytest.raises(ValueError, match="checksum_mismatch"):
        verify_gateway_manifest(tmp_path)


def test_real_frozen_model_supported_prediction_parity_and_sensitive_abstention(capsys, caplog):
    original = ROOT / "ml/runs/notebook-tfidf-logistic-v6/artifacts/url-core-logistic-v6.joblib"
    if not original.exists():
        pytest.skip("frozen v6 binary is local only")
    predictor = ShadowPredictor(RichArtifact())
    app = create_app(
        settings=GatewaySettings(key=KEY, burst=100), predictor_factory=lambda: predictor
    )
    cases = [
        "https://example.org/login?token=SYNTHETIC-PRIVATE-MARKER",
        "https://tenant.blogspot.com/a/b/c/d",
        "http://example.net/article",
        "https://xn--bcher-kva.de/path",
    ]
    with TestClient(app) as client:
        for url in cases:
            expected = predictor.predict(url, "QR")
            response = client.post(
                "/predict", json={"url": url, "input_type": "QR"}, headers=HEADERS
            )
            assert response.json() == expected.model_dump(mode="json")
            assert "SYNTHETIC-PRIVATE-MARKER" not in response.text
        blocked = client.post(
            "/predict", json={"url": "https://example.org/token=short-secret"}, headers=HEADERS
        )
        assert blocked.status_code == 422 and blocked.json()["model_score"] is None
        assert blocked.json()["risk_band"] is None and "short-secret" not in blocked.text
        metrics = client.get("/gateway-metrics", headers=HEADERS).json()
        assert metrics["online_recall"] is None and metrics["peak_inflight"] <= 2
        assert KEY not in json.dumps(metrics)
    captured = capsys.readouterr()
    assert KEY not in captured.out + captured.err + caplog.text


def test_factory_fails_closed_without_key_or_with_production_mode(monkeypatch):
    monkeypatch.delenv("GUARDIAN_SHADOW_GATEWAY_KEY", raising=False)
    with pytest.raises(ValueError, match="configuration_invalid"):
        create_app()
    monkeypatch.setenv("GUARDIAN_ML_MODE", "production")
    with pytest.raises(ValueError, match="production_gate_not_satisfied"):
        create_app(settings=GatewaySettings(key=KEY))
