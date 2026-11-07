"""Acquire a new publisher holdout without downloading the image archive."""

import hashlib
import io
import json

import pandas as pd

from guardian_ml.metadata import checksum
from guardian_ml.paths import ROOT
from evaluate_legitphish_v6 import collect_exposure, write_sidecar
from experiment_v6_expanded_data import curate_new, now, write_json
from intake_v6_expansion import sanitize_source
from v6_remote_zip import open_publisher_archive, read_pinned_member

PROTOCOL = ROOT / "ml/reports/v6-weighted-holdout-intake-amended.json"
DIRECTORY = ROOT / "ml/data/v6-weighted-new-holdout"
SOURCES = [
    "scripts/intake_v6_weighted_holdout.py",
    "scripts/v6_remote_zip.py",
    "scripts/intake_v6_expansion.py",
    "scripts/v6_development_support.py",
    "scripts/evaluate_legitphish_v6.py",
    "scripts/experiment_v6_expanded_data.py",
    "ml/reports/v6-weighted-holdout-intake-protocol.json",
    "ml/reports/v6-weighted-holdout-schema-inspection.json",
]


def checked_label_mapping(labels, published):
    text = labels.astype("string").str.strip().str.lower()
    if set(text.dropna()).issubset({"legitimate", "phishing"}) and text.notna().any():
        counts = {str(k): int(v) for k, v in text.value_counts().items()}
        if counts != {
            "legitimate": published["benign"],
            "phishing": published["phishing"],
        }:
            raise ValueError(
                "publisher_class_totals_need_qa_amendment_before_prediction"
            )
        return text, {"legitimate": 0, "phishing": 1}, counts
    numeric = pd.to_numeric(labels, errors="coerce")
    if (numeric.isna() & labels.notna()).any():
        raise ValueError("publisher_label_schema_needs_explicit_review")
    if not numeric.dropna().isin([0, 1, -1]).all():
        raise ValueError("unknown_publisher_label_enum")
    counts = {str(int(k)): int(v) for k, v in numeric.dropna().value_counts().items()}
    if len(counts) != 2:
        raise ValueError("publisher_requires_two_documented_label_values")
    matches = {
        role: [label for label, n in counts.items() if n == size]
        for role, size in published.items()
    }
    if (
        any(len(values) != 1 for values in matches.values())
        or matches["benign"] == matches["phishing"]
    ):
        raise ValueError("publisher_class_totals_need_qa_amendment_before_prediction")
    mapping = {matches["benign"][0]: 0, matches["phishing"][0]: 1}
    return numeric.astype("Int64").astype("string"), mapping, counts


def main():
    if (DIRECTORY / "frozen.json").exists():
        raise ValueError("new_holdout_already_frozen")
    protocol = json.loads(PROTOCOL.read_text())
    prior_urls, prior_domains, prior_hashes = collect_exposure()
    handle, archive = open_publisher_archive(protocol["asset"])
    content = read_pinned_member(archive, protocol["asset"]["member"])
    if hashlib.sha256(content).hexdigest() != protocol["asset"]["member_sha256"]:
        raise ValueError("new_holdout_csv_sha256_mismatch")
    raw = pd.read_csv(io.BytesIO(content), sep=protocol["csv"]["delimiter"])
    numeric, mapping, counts = checked_label_mapping(
        raw.label, protocol["published_class_counts"]
    )
    # Numeric orientation is a documented schema cross-check, not a change to case truth.
    source = raw.loc[numeric.notna(), ["url", "label"]].copy()
    source["label"] = numeric.loc[numeric.notna()].astype(str)
    sanitized, intake = sanitize_source(source, "zenodo_websites_v2", "url", "label")
    sanitized["label"] = sanitized.publisher_label.map(mapping)
    if sanitized.label.isna().any():
        raise ValueError("unmapped_publisher_holdout_label")
    sanitized["label"] = sanitized.label.astype(int)
    sanitized = sanitized.drop(columns="publisher_label")
    del raw, source, content, numeric
    DIRECTORY.mkdir(parents=True, exist_ok=True)
    # Freeze the source schema and evidence before any scoring; never use model outputs for mapping.
    write_json(
        DIRECTORY / "label-schema.json",
        {
            "source": protocol["release"],
            "publisher_label_counts": counts,
            "project_mapping": mapping,
            "evidence": "exact agreement with publisher phishing/benign totals; inherited source labels, not human verification",
            "frozen_at_utc": now(),
            "model_predictions_performed": False,
        },
    )
    policy = {
        "split_salt": "v6-weighted-all-new-holdout:",
        "group_buckets": {"new_test": 100},
        "max_rows_per_domain": protocol["max_rows_per_domain"],
    }
    novel, curation = curate_new([sanitized], prior_urls, prior_domains, policy)
    novel["partition"] = "new_test"
    supported_path, holdout_path = (
        DIRECTORY / "supported.parquet",
        DIRECTORY / "holdout.parquet",
    )
    sanitized.to_parquet(supported_path, index=False)
    novel.to_parquet(holdout_path, index=False)
    sidecar = write_sidecar(
        ROOT / "ml/data/exposure-sidecars/zenodo-websites-v2-20261105.sqlite", sanitized
    )
    freeze = {
        "frozen_at_utc": now(),
        "available": bool(len(novel)),
        "protocol_sha256": checksum(PROTOCOL),
        "protocol_path": PROTOCOL.relative_to(ROOT).as_posix(),
        "source_hashes": {name: checksum(ROOT / name) for name in SOURCES},
        "prior_exposure_hashes": prior_hashes,
        "sidecar": sidecar,
        "path": holdout_path.relative_to(ROOT).as_posix(),
        "sha256": checksum(holdout_path),
        "supported_path": supported_path.relative_to(ROOT).as_posix(),
        "supported_sha256": checksum(supported_path),
        "rows": len(novel),
        "groups": int(novel.group.nunique()),
        "classes": {str(k): int(v) for k, v in novel.label.value_counts().items()},
        "intake": intake,
        "curation": curation,
        "publisher_mapping": mapping,
        "member_sha256_verified": True,
        "whole_archive_md5_recomputed": False,
        "archive_bytes": handle.size,
        "downloaded_bytes": handle.bytes_downloaded,
        "network_range_requests": handle.requests_made,
        "all_retained_rows_reserved_not_for_training": True,
        "independent_campaigns_established": False,
        "human_gold": False,
        "Indonesia_gold": False,
        "production_ready": False,
    }
    write_json(DIRECTORY / "frozen.json", freeze)
    write_json(
        ROOT / "ml/provenance/zenodo-websites-v2-exposure.json",
        {
            "sidecar": sidecar,
            "holdout_freeze_sha256": checksum(DIRECTORY / "frozen.json"),
            "scope": "all sanitized intake, including excluded and held-out cases",
            "future_novelty_audits_must_include": True,
        },
    )
    print(
        json.dumps(
            {
                "rows": len(novel),
                "classes": freeze["classes"],
                "groups": freeze["groups"],
                "curation": curation,
                "downloaded_bytes": handle.bytes_downloaded,
                "archive_bytes": handle.size,
                "publisher_label_counts": counts,
            }
        ),
        flush=True,
    )


if __name__ == "__main__":
    main()
