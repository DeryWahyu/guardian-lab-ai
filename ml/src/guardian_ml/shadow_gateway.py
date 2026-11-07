"""Authenticated, bounded ASGI wrapper; the frozen v6 service remains shadow."""

import asyncio
from importlib.metadata import version
import json
import os
import secrets
import time

from .gateway_controls import (
    GatewaySettings,
    GatewayMonitor,
    TokenBucket,
    key_digest,
    sensitive_path,
)
from .metadata import checksum
from .paths import ROOT
from .rich_artifact import INFERENCE_DEPENDENCIES, workspace_path
from .shadow_service import create_app as create_shadow_app

SOURCE_FILES = frozenset(
    {"ml/src/guardian_ml/gateway_controls.py", "ml/src/guardian_ml/shadow_gateway.py"}
)
GATEWAY_DEPENDENCIES = frozenset({"fastapi", "starlette", "pydantic", "uvicorn"})


def verify_gateway_manifest(root=ROOT):
    manifest = json.loads(
        (root / "ml/policies/shadow-gateway-manifest.json").read_text(encoding="utf-8")
    )
    core_path = root / "ml/policies/shadow-serving-manifest.json"
    if (
        manifest.get("schema_version") != "shadow-gateway-v1"
        or manifest.get("production_ready") is not False
    ):
        raise ValueError("gateway_manifest_schema_invalid")
    if checksum(core_path) != manifest.get("parent_manifest_sha256"):
        raise ValueError("gateway_parent_manifest_changed")
    core = json.loads(core_path.read_text(encoding="utf-8"))
    if set(manifest.get("source_hashes", {})) != SOURCE_FILES:
        raise ValueError("gateway_source_manifest_incomplete")
    for name, expected in manifest["source_hashes"].items():
        if checksum(workspace_path(root, name)) != expected:
            raise ValueError("gateway_source_checksum_mismatch")
    dependencies = manifest.get("gateway_dependencies", {})
    if (
        set(dependencies) != GATEWAY_DEPENDENCIES
        or {n: version(n) for n in dependencies} != dependencies
    ):
        raise ValueError("gateway_dependency_versions_mismatch")
    if (
        manifest.get("inference_dependencies") != core.get("inference_dependencies")
        or set(manifest.get("inference_dependencies", {})) != INFERENCE_DEPENDENCIES
        or {n: version(n) for n in manifest["inference_dependencies"]}
        != manifest["inference_dependencies"]
    ):
        raise ValueError("gateway_inference_dependencies_changed")
    return manifest


class ShadowGateway:
    def __init__(self, child, settings):
        self.child, self.settings = child, settings
        self.digest = key_digest(settings.key)
        self.bucket = TokenBucket(settings.requests_per_minute, settings.burst)
        self.monitor = GatewayMonitor(settings.max_inflight)
        self.tasks = set()

    async def response(self, send, code, reason, started, retry_after=None):
        self.monitor.record(reason, 1000 * (time.perf_counter() - started))
        payload = {
            "mode": "shadow",
            "status": "unsupported_input" if reason == "privacy_sensitive_path" else "unavailable",
            "reason": reason,
            "production_ready": False,
            "needs_further_review": True,
            "model_score": None,
            "risk_band": None,
        }
        body = json.dumps(payload, separators=(",", ":")).encode()
        headers = [
            (b"content-type", b"application/json"),
            (b"content-length", str(len(body)).encode()),
            (b"cache-control", b"no-store"),
        ]
        if code == 401:
            headers.append((b"www-authenticate", b"Bearer"))
        if retry_after is not None:
            headers.append((b"retry-after", str(retry_after).encode()))
        await send({"type": "http.response.start", "status": code, "headers": headers})
        await send({"type": "http.response.body", "body": body})

    async def read_body(self, receive):
        body = bytearray()
        while True:
            message = await receive()
            if message["type"] == "http.disconnect":
                raise ValueError("client_disconnected")
            if message["type"] != "http.request":
                raise ValueError("invalid_request_event")
            chunk = message.get("body", b"")
            if len(body) + len(chunk) > self.settings.max_body_bytes:
                raise OverflowError("body_limit")
            body.extend(chunk)
            if not message.get("more_body", False):
                return bytes(body)

    async def dispatch(self, scope, body):
        sent, total, consumed = [], 0, False

        async def receive():
            nonlocal consumed
            if consumed:
                return {"type": "http.disconnect"}
            consumed = True
            return {"type": "http.request", "body": body, "more_body": False}

        async def capture(message):
            nonlocal total
            total += len(message.get("body", b""))
            if total > self.settings.max_response_bytes:
                raise OverflowError("gateway_response_limit")
            sent.append(message)
            if len(sent) > 128:
                raise OverflowError("gateway_response_event_limit")

        try:
            await self.child(scope, receive, capture)
            if (
                not sent
                or sent[0]["type"] != "http.response.start"
                or sent[-1].get("more_body", False)
            ):
                return None
            return sent
        except Exception:
            return None
        finally:
            self.tasks.discard(asyncio.current_task())
            self.monitor.leave()

    async def __call__(self, scope, receive, send):
        if scope["type"] == "lifespan":
            await self.child(scope, receive, send)
            return
        if scope["type"] != "http":
            await send({"type": "websocket.close", "code": 1008})
            return
        started = time.perf_counter()
        if scope.get("path") == "/live" and scope.get("method") == "GET":
            body = b'{"mode":"shadow","status":"alive","production_ready":false}'
            await send(
                {
                    "type": "http.response.start",
                    "status": 200,
                    "headers": [
                        (b"content-type", b"application/json"),
                        (b"cache-control", b"no-store"),
                    ],
                }
            )
            await send({"type": "http.response.body", "body": body})
            return
        credentials = [v for k, v in scope.get("headers", []) if k.lower() == b"authorization"]
        supplied = credentials[0] if len(credentials) == 1 else b""
        authenticated = False
        if supplied.startswith(b"Bearer ") and 7 < len(supplied) <= 263:
            try:
                authenticated = secrets.compare_digest(
                    key_digest(supplied[7:].decode("ascii")), self.digest
                )
            except (UnicodeError, ValueError):
                pass
        if not authenticated:
            return await self.response(send, 401, "authentication_required", started)
        allowed, retry = self.bucket.take()
        if not allowed:
            return await self.response(send, 429, "quota_exceeded", started, retry)
        if scope.get("path") == "/gateway-metrics" and scope.get("method") == "GET":
            body = json.dumps(self.monitor.snapshot()).encode()
            await send(
                {
                    "type": "http.response.start",
                    "status": 200,
                    "headers": [
                        (b"content-type", b"application/json"),
                        (b"cache-control", b"no-store"),
                    ],
                }
            )
            await send({"type": "http.response.body", "body": body})
            return
        if (scope.get("path"), scope.get("method")) not in {
            ("/predict", "POST"),
            ("/health", "GET"),
            ("/metrics", "GET"),
            ("/openapi.json", "GET"),
        }:
            return await self.response(send, 404, "route_unavailable", started)
        try:
            body = await asyncio.wait_for(self.read_body(receive), self.settings.body_timeout)
        except TimeoutError:
            return await self.response(send, 408, "body_timeout", started)
        except OverflowError:
            return await self.response(send, 413, "request_body_too_large", started)
        except (ValueError, RuntimeError):
            return await self.response(send, 400, "request_unavailable", started)
        if scope.get("path") == "/predict":
            try:
                parsed = json.loads(body)
                if isinstance(parsed, dict) and sensitive_path(parsed.get("url")):
                    return await self.response(send, 422, "privacy_sensitive_path", started)
            except (ValueError, UnicodeError, RecursionError):
                pass
        if not self.monitor.enter():
            return await self.response(send, 503, "inference_capacity_exceeded", started, 1)
        task = asyncio.create_task(self.dispatch(scope, body))
        self.tasks.add(task)
        try:
            done, _ = await asyncio.wait({task}, timeout=self.settings.inference_timeout)
        except BaseException:
            # Client cancellation must not release the slot while computation runs.
            raise
        if not done:
            return await self.response(send, 504, "inference_timeout", started, 1)
        messages = task.result()
        if messages is None:
            return await self.response(send, 503, "inference_unavailable", started)
        status = messages[0]["status"]
        self.monitor.record("forwarded_" + str(status), 1000 * (time.perf_counter() - started))
        for message in messages:
            if message["type"] == "http.response.start":
                message = {
                    **message,
                    "headers": [*message.get("headers", []), (b"cache-control", b"no-store")],
                }
            await send(message)


def create_app(*, settings=None, predictor_factory=None):
    verify_gateway_manifest()
    if settings is None:
        try:
            settings = GatewaySettings(
                key=os.environ.get("GUARDIAN_SHADOW_GATEWAY_KEY", ""),
                requests_per_minute=float(os.environ.get("GUARDIAN_GATEWAY_RPM", "60")),
                burst=int(os.environ.get("GUARDIAN_GATEWAY_BURST", "10")),
                max_inflight=int(os.environ.get("GUARDIAN_GATEWAY_MAX_INFLIGHT", "2")),
                inference_timeout=float(os.environ.get("GUARDIAN_GATEWAY_TIMEOUT", "5")),
            )
        except (TypeError, ValueError):
            raise ValueError("gateway_configuration_invalid") from None
    return ShadowGateway(create_shadow_app(predictor_factory=predictor_factory), settings)
