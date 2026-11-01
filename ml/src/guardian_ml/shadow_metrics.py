"""Thread-safe aggregate telemetry; no event records or target identifiers."""

from collections import Counter
import math
from threading import Lock


class AggregateMonitor:
    def __init__(self):
        self._lock = Lock()
        self._statuses = Counter()
        self._input_types = Counter()
        self._bands = Counter()
        self._latency_buckets = Counter()

    def record(self, *, status, input_type="UNKNOWN", risk_band=None, elapsed_ms):
        if status not in {"complete", "unsupported_input", "unavailable", "invalid_request"}:
            raise ValueError("unknown_telemetry_status")
        if input_type not in {"URL", "QR", "UNKNOWN"}:
            raise ValueError("unknown_telemetry_input_type")
        if risk_band not in {None, "LOW", "MEDIUM", "HIGH"}:
            raise ValueError("unknown_telemetry_band")
        if not math.isfinite(elapsed_ms) or elapsed_ms < 0:
            raise ValueError("invalid_telemetry_duration")
        bucket = next(
            (f"le_{limit}_ms" for limit in (10, 50, 200, 1000) if elapsed_ms <= limit),
            "over_1000_ms",
        )
        with self._lock:
            self._statuses[status] += 1
            self._input_types[input_type] += 1
            if risk_band is not None:
                self._bands[risk_band] += 1
            self._latency_buckets[bucket] += 1

    def snapshot(self):
        with self._lock:
            return {
                "total_requests": sum(self._statuses.values()),
                "by_status": dict(self._statuses),
                "by_input_type": dict(self._input_types),
                "by_risk_band": dict(self._bands),
                "latency_histogram": dict(self._latency_buckets),
                "quality_metrics": {"precision": None, "recall": None, "fpr": None},
                "quality_status": "no_reviewed_online_ground_truth",
                "target_identifiers_persisted": False,
                "individual_events_persisted": False,
            }
