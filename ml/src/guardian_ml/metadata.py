"""Portable manifests: versions, hashes, and aggregate statistics only."""

from datetime import datetime, timezone
import hashlib
from importlib.metadata import version
import json
import math
from pathlib import Path
import platform

import numpy as np
import tldextract

from .paths import ROOT

PACKAGES = (
    "catboost",
    "joblib",
    "numpy",
    "pandas",
    "pyarrow",
    "requests",
    "scikit-learn",
    "scipy",
    "tldextract",
    "xgboost",
    "threadpoolctl",
    "requests-file",
    "filelock",
    "urllib3",
    "idna",
    "certifi",
    "matplotlib",
    "psutil",
)


def checksum(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def psl_identity():
    snapshot = Path(tldextract.__file__).parent / ".tld_set_snapshot"
    return {
        "package": version("tldextract"),
        "snapshot_sha256": checksum(snapshot),
        "private_suffixes": True,
        "network_refresh": False,
    }


def environment():
    return {
        "python": platform.python_version(),
        "platform": platform.system(),
        "dependencies": {name: version(name) for name in PACKAGES},
        "psl": psl_identity(),
    }


def source_hashes():
    return {
        str(path.relative_to(ROOT)).replace("\\", "/"): checksum(path)
        for path in sorted((ROOT / "ml/src/guardian_ml").glob("*.py"))
    }


def clean(value):
    if isinstance(value, dict):
        return {str(key): clean(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [clean(item) for item in value]
    if isinstance(value, np.ndarray):
        return clean(value.tolist())
    if isinstance(value, np.generic):
        return clean(value.item())
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def dump_json(path, data):
    path.write_text(json.dumps(clean(data), indent=2, allow_nan=False) + "\n", encoding="utf-8")


def now():
    return datetime.now(timezone.utc).isoformat()
