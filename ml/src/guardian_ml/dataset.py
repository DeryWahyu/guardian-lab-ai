"""Three audit passes: ingestion, canonical/group curation, independent re-read."""

from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

from .paths import DATA, REPORTS, REVISION, REPRESENTATION, ensure_directories
from .preprocessing import prepare_url, InvalidUrl, EMAIL, PHONE, NUMBER, TOKEN
from . import sources


def sha256_file(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def ingest():
    counters = Counter()
    reasons = Counter()
    writer = None
    buffer = []
    staging = DATA / "sanitized-staging.parquet"
    for source, row in list_sources():
        label = row["label"]
        assert label in ("phish", "benign")
        counters[f"{source}_{label}_raw"] += 1
        try:
            parsed = prepare_url(row["url"])
        except InvalidUrl as error:
            reasons[f"{source}_{label}_{error}"] += 1
            continue
        counters[f"{source}_{label}_accepted"] += 1
        counters[f"{source}_{label}_redacted_rows"] += int(parsed.redactions > 0)
        buffer.append(
            {
                "core": parsed.core,
                "digest": parsed.digest,
                "group": parsed.group,
                "label": int(label == "phish"),
                "date": str(row["date"] or ""),
                "source_split": source,
            }
        )
        if len(buffer) == 4096:
            writer = flush(buffer, writer, staging)
            buffer.clear()
    if buffer:
        writer = flush(buffer, writer, staging)
    if writer:
        writer.close()
    assert counters["train_benign_raw"] == 276729
    assert counters["train_phish_raw"] == 221526
    assert counters["test_benign_raw"] == 91260
    assert counters["test_phish_raw"] == 76800
    assert counters["external_benign_raw"] == 134850
    assert counters["external_phish_raw"] == 100945
    return {
        "ingestion": dict(counters),
        "rejected_by_reason_and_class": dict(reasons),
        "transferred_bytes": sources.audit.TRANSFERRED,
    }


def list_sources():
    yield from sources.official_rows()
    yield from sources.external_rows()


def flush(buffer, writer, path):
    table = pa.Table.from_pylist(buffer)
    if writer is None:
        writer = pq.ParquetWriter(path, table.schema, compression="zstd")
    writer.write_table(table)
    return writer


def counts(frame):
    return {
        "rows": len(frame),
        "benign": int((frame.label == 0).sum()),
        "phishing": int((frame.label == 1).sum()),
        "groups": frame.group.nunique(),
    }


def curate():
    frame = pd.read_parquet(DATA / "sanitized-staging.parquet")
    original = len(frame)
    conflicts = frame.groupby("digest", sort=False).label.nunique()
    bad = set(conflicts[conflicts > 1].index)
    frame = frame[~frame.digest.isin(bad)].copy()
    removed_conflicts = original - len(frame)
    before_dedup = len(frame)
    frame = frame.sort_values("date").drop_duplicates(["source_split", "digest"], keep="last")
    dedup_removed = before_dedup - len(frame)
    official = frame[frame.source_split == "test"].copy()
    train = frame[frame.source_split == "train"].copy()
    external = frame[frame.source_split == "external"].copy()
    collision = train.digest.isin(set(official.digest))
    overlap_removed = int(collision.sum())
    train = train[~collision].copy()
    boundary = official.date.min()
    boundary_removed = int((train.date >= boundary).sum())
    train = train[train.date < boundary].copy()
    cutoff = train.date.sort_values().iloc[int(len(train) * 0.70)]
    fit = train[train.date < cutoff].copy()
    validation = train[train.date >= cutoff].copy()
    known = set(fit.group)
    removed_known = int(validation.group.isin(known).sum())
    validation = validation[~validation.group.isin(known)].copy()

    # Independent group allocation within the newer validation period.
    def bucket(group):
        return int(hashlib.sha256(("guardian-v1:" + group).encode()).hexdigest()[:8], 16) % 4

    allocations = validation.group.map(bucket)
    fit["partition"] = "fit"
    validation["partition"] = allocations.map(
        {0: "calibration", 1: "threshold", 2: "tune", 3: "tune"}
    )
    development = pd.concat([fit, validation], ignore_index=True)
    known = set(development.group)
    official["partition"] = "test"
    official["novel_domain"] = ~official.group.isin(known)
    # Remove source overlap before cross-source metrics; retain novelty marker.
    excluded_external = external.digest.isin(set(development.digest) | set(official.digest))
    external = external[~excluded_external].copy()
    external["partition"] = "external"
    external["novel_domain"] = ~external.group.isin(known | set(official.group))
    development["novel_domain"] = False
    final = pd.concat([development, official, external], ignore_index=True)
    final.to_parquet(DATA / "curated.parquet", index=False, compression="zstd")
    detail = {
        "canonical_conflicting_hashes": len(bad),
        "rows_removed_for_label_conflicts": removed_conflicts,
        "within_source_canonical_duplicate_rows_removed": dedup_removed,
        "train_rows_overlapping_official_test_canonical_url_removed": overlap_removed,
        "train_rows_on_or_after_test_boundary_removed": boundary_removed,
        "test_boundary_exclusive_for_train": boundary,
        "validation_start_inclusive": cutoff,
        "validation_rows_with_fit_domain_removed": removed_known,
        "external_rows_overlapping_development_or_official_url_removed": int(
            excluded_external.sum()
        ),
        "partitions": {name: counts(part) for name, part in final.groupby("partition")},
        "test_novel_domain": counts(official[official.novel_domain]),
        "external_novel_domain": counts(external[external.novel_domain]),
        "campaign_overlap": "Not certified: campaign labels unavailable; domain is a proxy only",
    }
    return detail


def independent_audit():
    frame = pd.read_parquet(DATA / "curated.parquet")
    checks = {}
    checks["canonical_urls_unique_per_partition"] = not frame.duplicated(
        ["partition", "digest"]
    ).any()
    checks["digest_matches_saved_core"] = bool(
        (
            frame.core.map(lambda value: hashlib.sha256(value.encode()).hexdigest()) == frame.digest
        ).all()
    )
    checks["no_query_or_fragment"] = not frame.core.str.contains(r"[?#]", regex=True).any()
    checks["no_screened_pii_or_token"] = not any(
        pattern.search(value) for value in frame.core for pattern in (EMAIL, PHONE, NUMBER, TOKEN)
    )
    groups = {}
    digests = {}
    for name in ("fit", "tune", "calibration", "threshold"):
        part = frame[frame.partition == name]
        checks[f"{name}_has_two_supported_classes"] = (
            min(int((part.label == 0).sum()), int((part.label == 1).sum())) >= 200
        )
        groups[name] = set(part.group)
        digests[name] = set(part.digest)
    checks["development_groups_pairwise_disjoint"] = all(
        not groups[left] & groups[right] for left in groups for right in groups if left < right
    )
    checks["development_urls_pairwise_disjoint"] = all(
        not digests[left] & digests[right] for left in digests for right in digests if left < right
    )
    dev = frame[frame.partition.isin(groups)]
    test = frame[frame.partition == "test"]
    checks["no_development_url_in_test"] = not set(dev.digest) & set(test.digest)
    checks["strict_time_fit_before_validation"] = (
        frame[frame.partition == "fit"].date.max()
        < frame[frame.partition.isin(["tune", "calibration", "threshold"])].date.min()
    )
    checks["strict_time_development_before_test"] = dev.date.max() < test.date.min()
    novel = test[test.novel_domain]
    checks["main_test_domain_disjoint"] = not set(dev.group) & set(novel.group)
    sample = frame.sample(min(2000, len(frame)), random_state=20261101)
    checks["representation_idempotent_sample_2000"] = all(
        prepare_url(value).core == value for value in sample.core
    )
    checks["saved_groups_match_offline_psl_sample_2000"] = all(
        prepare_url(row.core).group == row.group for row in sample.itertuples()
    )
    checks = {name: bool(value) for name, value in checks.items()}
    (REPORTS / "independent-checks.json").write_text(json.dumps(checks, indent=2) + "\n")
    assert all(checks.values()), "Independent audit failed: " + ",".join(
        name for name, value in checks.items() if not value
    )
    return checks


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--reuse-staging", action="store_true")
    options = parser.parse_args()
    ensure_directories()
    report = {
        "source_revision": REVISION,
        "representation_version": REPRESENTATION,
        "checked_at_utc": datetime.now(timezone.utc).isoformat(),
        "raw_urls_persisted": False,
        "live_targets_visited": False,
    }
    if options.reuse_staging:
        report.update(json.loads((REPORTS / "data-audit.json").read_text()))
    else:
        report.update(ingest())
    (REPORTS / "data-audit.json").write_text(json.dumps(report, indent=2) + "\n")
    report["curation"] = curate()
    (REPORTS / "data-audit.json").write_text(json.dumps(report, indent=2) + "\n")
    report["independent_checks"] = independent_audit()
    report["curated_sha256"] = sha256_file(DATA / "curated.parquet")
    (REPORTS / "data-audit.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report["curation"], indent=2), flush=True)
    print("All independent data checks passed. No model has been trained yet.", flush=True)


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        # Input-bearing exception messages and request tracebacks stay out of logs.
        print(f"Data pipeline stopped: {type(error).__name__}", flush=True)
        raise SystemExit(1) from None
