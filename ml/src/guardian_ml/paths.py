"""Portable workspace locations and immutable source identity."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
DATA = ROOT / "ml/data"
REPORTS = ROOT / "ml/reports"
ARTIFACTS = ROOT / "ml/artifacts"
REVISION = "eca603e0ecd4f698f8d4d226c088659e72681239"
SEED = 20261101
REPRESENTATION = "url-core-redacted-v1"


def ensure_directories() -> None:
    for directory in (DATA, REPORTS, ARTIFACTS):
        directory.mkdir(parents=True, exist_ok=True)
