"""Container readiness checks model availability, not production promotion."""

import json
from urllib.request import urlopen

try:
    with urlopen("http://127.0.0.1:8001/health", timeout=2) as response:
        health = json.load(response)
except (OSError, ValueError):
    raise SystemExit(1) from None

ready = (
    isinstance(health, dict)
    and health.get("model_available") is True
    and health.get("mode") == "shadow"
    and health.get("production_ready") is False
)
raise SystemExit(0 if ready else 1)
