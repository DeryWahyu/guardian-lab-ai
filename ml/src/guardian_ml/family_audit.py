"""Data and immutable-run checks for the observed-benchmark v9 experiment."""

import hashlib
import json

from .preprocessing import prepare_url


def write_json(path, value):
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def value_hash(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


def code_hash(path):
    cells = json.loads(path.read_text(encoding="utf-8"))["cells"]
    return hashlib.sha256(
        "\n\n".join("".join(c["source"]) for c in cells if c["cell_type"] == "code").encode()
    ).hexdigest()


def audit_development(frame):
    expected = {"fit": 535504, "tune": 84545, "calibration": 40635, "threshold": 47219}
    actual = frame.partition.value_counts().to_dict()
    if actual != expected or not frame.digest.is_unique:
        raise ValueError("development_partition_or_uniqueness_mismatch")
    if frame.groupby("group").partition.nunique().max() != 1:
        raise ValueError("development_domain_overlap")
    if set(frame.label.unique()) != {0, 1}:
        raise ValueError("unsupported_labels")
    for row in frame[["core", "digest", "group"]].itertuples(index=False):
        parsed = prepare_url(row.core)
        if (parsed.core, parsed.digest, parsed.group) != (row.core, row.digest, row.group):
            raise ValueError("canonical_digest_domain_mismatch")
    return {
        "partition_rows": actual,
        "unique_domains": int(frame.group.nunique()),
        "canonical_digest_domain_verified": True,
        "domain_disjoint_roles": True,
    }


def assert_external(frame, development):
    if not set(frame.group).isdisjoint(development.group):
        raise ValueError("benchmark_domain_in_development")
    if not set(frame.digest).isdisjoint(development.digest):
        raise ValueError("benchmark_url_in_development")
