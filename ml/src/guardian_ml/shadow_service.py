"""Local shadow API; performs no network requests to submitted targets."""

from contextlib import asynccontextmanager
import json
import os
import time

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from pydantic import ValidationError
from starlette.concurrency import run_in_threadpool

from .release_gates import assess_release
from .shadow_contracts import PredictionRequest, ShadowResult
from .shadow_metrics import AggregateMonitor
from .shadow_predictor import ShadowPredictor, unavailable_reply

MAX_BODY_BYTES = 65536


def create_app(*, predictor_factory=None, mode=None):
    selected_mode = mode if mode is not None else os.environ.get("GUARDIAN_ML_MODE", "shadow")
    if selected_mode != "shadow":
        raise ValueError("production_gate_not_satisfied")
    monitor = AggregateMonitor()
    factory = predictor_factory if predictor_factory is not None else ShadowPredictor

    @asynccontextmanager
    async def lifespan(app):
        app.state.predictor = None
        try:
            app.state.predictor = await run_in_threadpool(factory)
        except (OSError, ValueError, KeyError, TypeError, ImportError):
            # Fixed availability state only. Do not log paths or exception/request bodies.
            app.state.predictor = None
        yield
        app.state.predictor = None

    app = FastAPI(
        title="Guardian Lab ML Shadow",
        version="shadow-v6-1",
        docs_url=None,
        redoc_url=None,
        debug=False,
        lifespan=lifespan,
    )
    app.state.monitor = monitor

    def invalid(reason, status_code, started):
        monitor.record(status="invalid_request", elapsed_ms=1000 * (time.perf_counter() - started))
        return JSONResponse(
            {
                "mode": "shadow",
                "status": "invalid_request",
                "reason": reason,
                "production_ready": False,
            },
            status_code=status_code,
        )

    @app.get("/health")
    async def health():
        return {
            "service": "guardian_ml_shadow",
            "mode": "shadow",
            "model_available": getattr(app.state, "predictor", None) is not None,
            "production_ready": False,
            "release_gate": assess_release(),
        }

    @app.get("/metrics")
    async def metrics():
        return monitor.snapshot()

    @app.post(
        "/predict",
        response_model=ShadowResult,
        openapi_extra={
            "requestBody": {
                "required": True,
                "content": {"application/json": {"schema": PredictionRequest.model_json_schema()}},
            }
        },
    )
    async def predict(request: Request):
        started = time.perf_counter()
        if (
            request.headers.get("content-type", "").split(";", 1)[0].strip().lower()
            != "application/json"
        ):
            return invalid("application_json_required", 415, started)
        body = bytearray()
        async for chunk in request.stream():
            if len(body) + len(chunk) > MAX_BODY_BYTES:
                return invalid("request_body_too_large", 413, started)
            body.extend(chunk)
        try:
            payload = json.loads(body.decode("utf-8"))
        except (ValueError, UnicodeError, RecursionError):
            return invalid("invalid_json", 400, started)
        try:
            value = PredictionRequest.model_validate(payload)
        except (ValidationError, RecursionError):
            return invalid("invalid_request_schema", 422, started)
        predictor = getattr(app.state, "predictor", None)
        if predictor is None:
            result = unavailable_reply(value.input_type)
        else:
            try:
                result = await run_in_threadpool(predictor.predict, value.url, value.input_type)
            except (OSError, ValueError, KeyError, TypeError, RuntimeError):
                result = unavailable_reply(value.input_type)
        monitor.record(
            status=result.status,
            input_type=value.input_type,
            risk_band=result.risk_band,
            elapsed_ms=1000 * (time.perf_counter() - started),
        )
        status_code = {"complete": 200, "unsupported_input": 422, "unavailable": 503}[result.status]
        return JSONResponse(result.model_dump(mode="json"), status_code=status_code)

    return app
