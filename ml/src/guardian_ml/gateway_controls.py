"""Bounded, target-free controls for an authenticated internal shadow gateway."""

from collections import Counter
from dataclasses import dataclass, field
import hashlib
import math
import re
import threading
import time
from urllib.parse import unquote, urlsplit

SENSITIVE_ASSIGNMENT = re.compile(
    r"(?:^|[/;&])(?:password|passwd|pwd|token|secret|otp|pin|session|authorization|"
    r"email|phone|mobile|nik|account|credential|access[_-]?token|api[_-]?key)"
    r"(?:=|:)([^/;&]+)",
    re.I,
)


@dataclass(frozen=True)
class GatewaySettings:
    key: str = field(repr=False)
    requests_per_minute: float = 60
    burst: int = 10
    max_inflight: int = 2
    inference_timeout: float = 5
    body_timeout: float = 3
    max_body_bytes: int = 65536
    max_response_bytes: int = 65536

    def __post_init__(self):
        if (
            not isinstance(self.key, str)
            or not 32 <= len(self.key) <= 256
            or not self.key.isascii()
            or any(c.isspace() for c in self.key)
        ):
            raise ValueError("gateway_strong_key_required")
        bounds = (
            (self.requests_per_minute, 0.1, 10000),
            (self.burst, 1, 10000),
            (self.max_inflight, 1, 32),
            (self.inference_timeout, 0.005, 30),
            (self.body_timeout, 0.005, 30),
            (self.max_body_bytes, 1, 65536),
            (self.max_response_bytes, 1024, 262144),
        )
        if any(
            isinstance(v, bool)
            or not isinstance(v, (float, int))
            or not math.isfinite(v)
            or not lo <= v <= hi
            for v, lo, hi in bounds
        ):
            raise ValueError("gateway_limits_invalid")
        if any(
            type(v) is not int
            for v in (self.burst, self.max_inflight, self.max_body_bytes, self.max_response_bytes)
        ):
            raise ValueError("gateway_integer_limit_required")


class TokenBucket:
    def __init__(self, rate, capacity, clock=time.monotonic):
        self.rate, self.capacity, self.clock = rate / 60, capacity, clock
        self.tokens, self.last, self.lock = float(capacity), clock(), threading.Lock()

    def take(self):
        with self.lock:
            now = self.clock()
            self.tokens = min(self.capacity, self.tokens + max(0, now - self.last) * self.rate)
            self.last = now
            if self.tokens < 1:
                return False, max(1, math.ceil((1 - self.tokens) / self.rate))
            self.tokens -= 1
            return True, 0


class GatewayMonitor:
    def __init__(self, capacity):
        self.capacity, self.inflight, self.peak = capacity, 0, 0
        self.counts, self.lock = Counter(), threading.Lock()
        self.latency_buckets = [0] * 6
        self.latency_sum_ms = 0.0

    def enter(self):
        with self.lock:
            if self.inflight >= self.capacity:
                return False
            self.inflight += 1
            self.peak = max(self.peak, self.inflight)
            return True

    def leave(self):
        with self.lock:
            self.inflight -= 1

    def record(self, outcome, elapsed_ms):
        with self.lock:
            self.counts[outcome] += 1
            self.latency_sum_ms += elapsed_ms
            i = next(
                (i for i, cutoff in enumerate((10, 50, 100, 500, 1000)) if elapsed_ms <= cutoff), 5
            )
            self.latency_buckets[i] += 1

    def snapshot(self):
        with self.lock:
            return {
                "mode": "shadow",
                "production_ready": False,
                "inflight": self.inflight,
                "peak_inflight": self.peak,
                "capacity": self.capacity,
                "counts": dict(self.counts),
                "latency_bucket_upper_ms": [10, 50, 100, 500, 1000, None],
                "latency_bucket_counts": list(self.latency_buckets),
                "latency_sum_ms": self.latency_sum_ms,
                "online_precision": None,
                "online_recall": None,
                "online_fpr": None,
            }


def key_digest(key):
    return hashlib.sha256(key.encode("ascii")).digest()


def sensitive_path(value):
    """Abstain before frozen inference; never silently change frozen features."""
    if not isinstance(value, str) or len(value) > 16384:
        return False
    try:
        path = urlsplit(value if "://" in value else "https://" + value).path
    except ValueError:
        return False
    decoded = unquote(unquote(path))
    return any(m[1] != "REDACTED" for m in SENSITIVE_ASSIGNMENT.finditer(decoded))
