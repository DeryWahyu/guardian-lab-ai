"""Synthetic in-process load test and real frozen-artifact parity; no live targets."""

import asyncio
from collections import Counter
import secrets
import time

import httpx
import numpy as np

from guardian_ml.gateway_controls import GatewaySettings
from guardian_ml.metadata import checksum
from guardian_ml.paths import ROOT
from guardian_ml.rich_artifact import RichArtifact
from guardian_ml.shadow_gateway import create_app, verify_gateway_manifest
from guardian_ml.shadow_predictor import ShadowPredictor
from experiment_v6_expanded_data import now, write_json

OUTPUT = ROOT / "ml/reports/v6-shadow-gateway-load-test.json"


async def phase(predictor, name, requests, concurrency):
    # Ephemeral synthetic backend credential is never written to output.
    key = secrets.token_urlsafe(48)
    app = create_app(
        settings=GatewaySettings(
            key=key, requests_per_minute=10000, burst=1000, max_inflight=2
        ),
        predictor_factory=lambda: predictor,
    )
    gate = asyncio.Semaphore(concurrency)
    cases = [
        "https://example.org/login",
        "https://example.net/a/b/c/d",
        "https://tenant.blogspot.com/article",
        "https://xn--bcher-kva.de/path",
    ]
    statuses, latency, success_latency, deltas = Counter(), [], [], []
    async with app.child.router.lifespan_context(app.child):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://synthetic-test"
        ) as client:

            async def one(index):
                async with gate:
                    url = cases[index % len(cases)]
                    started = time.perf_counter()
                    response = await client.post(
                        "/predict",
                        json={"url": url, "input_type": "QR" if index % 2 else "URL"},
                        headers={"Authorization": "Bearer " + key},
                    )
                    elapsed = 1000 * (time.perf_counter() - started)
                    latency.append(elapsed)
                    statuses[response.status_code] += 1
                    result = response.json()
                    if response.status_code == 200:
                        success_latency.append(elapsed)
                        expected = predictor.predict(url, "QR" if index % 2 else "URL")
                        deltas.append(abs(expected.model_score - result["model_score"]))
                        if (
                            expected.risk_band != result["risk_band"]
                            or result["production_ready"]
                        ):
                            raise ValueError("gateway_prediction_contract_changed")
                    elif (
                        result["model_score"] is not None
                        or result["risk_band"] is not None
                    ):
                        raise ValueError("gateway_failure_has_model_score")

            await asyncio.gather(*(one(i) for i in range(requests)))
    snapshot = app.monitor.snapshot()
    if (
        snapshot["inflight"]
        or snapshot["peak_inflight"] > 2
        or (deltas and max(deltas) > 1e-12)
    ):
        raise ValueError("gateway_bound_or_prediction_parity_failed")
    if name == "steady" and statuses != Counter({200: requests}):
        raise ValueError("gateway_steady_load_failed")
    return {
        "name": name,
        "requests": requests,
        "client_concurrency": concurrency,
        "statuses": {str(k): v for k, v in sorted(statuses.items())},
        "latency_ms": {
            "p50": float(np.quantile(latency, 0.5)),
            "p95": float(np.quantile(latency, 0.95)),
            "p99": float(np.quantile(latency, 0.99)),
            "max": max(latency),
        },
        "real_prediction_parity_cases": len(deltas),
        "successful_latency_ms": {
            "p50": float(np.quantile(success_latency, 0.5)),
            "p95": float(np.quantile(success_latency, 0.95)),
            "p99": float(np.quantile(success_latency, 0.99)),
        }
        if success_latency
        else None,
        "prediction_parity_max_delta": max(deltas) if deltas else None,
        "gateway_counters": snapshot,
    }


async def main():
    if OUTPUT.exists():
        raise ValueError("gateway_load_report_must_not_overwrite")
    manifest = verify_gateway_manifest()
    predictor = ShadowPredictor(RichArtifact())
    phases = []
    for args in [("steady", 100, 2), ("saturation", 160, 16)]:
        result = await phase(predictor, *args)
        phases.append(result)
        print(
            {
                "phase": args[0],
                "statuses": result["statuses"],
                "p95_ms": result["latency_ms"]["p95"],
            },
            flush=True,
        )
    write_json(
        OUTPUT,
        {
            "completed_at_utc": now(),
            "script_sha256": checksum(__file__),
            "gateway_manifest_sha256": checksum(
                ROOT / "ml/policies/shadow-gateway-manifest.json"
            ),
            "parent_runtime_manifest_sha256": manifest["parent_manifest_sha256"],
            "model_sha256": predictor.artifact.manifest["bundle_sha256"],
            "phases": phases,
            "synthetic_only": True,
            "network_server_started": False,
            "live_targets_visited": False,
            "scope": "in-process ASGI on this workstation, not deployed network/TLS/cross-worker load evidence",
            "production_ready": False,
        },
    )


if __name__ == "__main__":
    asyncio.run(main())
