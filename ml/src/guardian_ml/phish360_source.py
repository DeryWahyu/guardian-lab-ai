"""Column-only Phish360 intake; only sanitized URL cores are persisted."""

from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sqlite3

import pandas as pd
import pyarrow.parquet as pq

from .metadata import checksum
from .preprocessing import InvalidUrl, prepare_url
from .sources import audit

ASSETS = [
    (0, "legit", "1nsiCIAZoBOSs9bEEXq78Nveu6Q90SLzr", 500062998),
    (1, "phish", "1RVVwm0dwBvKzTenV4nnMbBEp60IYeMUO", 137932113),
]


def prepare_test_source(root):
    root = Path(root)
    folder = root / "ml/data/structural-v7"
    folder.mkdir(parents=True, exist_ok=True)
    manifest_path = folder / "phish360-manifest.json"
    output_path = folder / "phish360-new.parquet"
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text())
        if checksum(root / manifest["output_path"]) != manifest["output_sha256"]:
            raise ValueError("frozen_source_cache_checksum_mismatch")
        return manifest
    if output_path.exists():
        raise ValueError("unmanifested_source_cache_requires_audit")
    registry = root / "ml/data/indonesia-gold/registry/known-exposure.sqlite"
    records, assets, stats = [], [], Counter()
    with sqlite3.connect("file:" + registry.as_posix() + "?mode=ro", uri=True) as db:
        for label, name, identifier, size in ASSETS:
            endpoint = (
                "https://drive.usercontent.google.com/download?id="
                + identifier
                + "&export=download&confirm=t"
            )
            with audit.RangeReader(endpoint, size) as remote:
                parquet = pq.ParquetFile(remote, pre_buffer=False)
                projection = parquet.read(
                    columns=["URL", "Class", "html_text_language"], use_threads=False
                ).to_pandas()
                footer_size = parquet.metadata.serialized_size
                remote.seek(size - footer_size - 8)
                footer_hash = hashlib.sha256(remote.read(footer_size + 8)).hexdigest()
            projection_hash, classes = hashlib.sha256(), Counter()
            for row in projection.to_dict("records"):
                projection_hash.update(
                    json.dumps(row, sort_keys=True, ensure_ascii=True, default=str).encode()
                )
                projection_hash.update(b"\n")
                classes[str(row["Class"])] += 1
                if row["Class"] != name:
                    raise ValueError("source_asset_label_mapping_mismatch")
                stats["raw_rows"] += 1
                try:
                    item = prepare_url(row["URL"])
                except (InvalidUrl, TypeError):
                    stats["unsupported_privacy_screening"] += 1
                    continue
                if db.execute("SELECT 1 FROM url_hashes WHERE value=?", (item.digest,)).fetchone():
                    stats["known_url"] += 1
                    continue
                group_hash = hashlib.sha256(item.group.encode()).hexdigest()
                if db.execute(
                    "SELECT 1 FROM domain_hashes WHERE value=?", (group_hash,)
                ).fetchone():
                    stats["known_domain"] += 1
                    continue
                records.append(
                    {
                        "core": item.core,
                        "digest": item.digest,
                        "group": item.group,
                        "label": label,
                        "training_source": "phish360",
                        "partition": "new_external_test",
                        "source_asset": name,
                        "language": str(row["html_text_language"]),
                        "date": "",
                    }
                )
            assets.append(
                {
                    "asset": name,
                    "drive_file_id": identifier,
                    "source_url": endpoint,
                    "bytes": size,
                    "parquet_footer_sha256": footer_hash,
                    "projected_url_class_language_sha256": projection_hash.hexdigest(),
                    "rows": len(projection),
                    "class_counts": dict(classes),
                    "mapped_project_label": label,
                    "columns_read": ["URL", "Class", "html_text_language"],
                }
            )
    frame = pd.DataFrame(records)
    conflicts = set(frame.groupby("digest").label.nunique().loc[lambda x: x > 1].index)
    stats["conflict_hashes"] = len(conflicts)
    frame = frame[~frame.digest.isin(conflicts)].sort_values("digest")
    stats["duplicates_removed"] = int(frame.digest.duplicated().sum())
    frame = frame.drop_duplicates("digest")
    before_cap = len(frame)
    frame = frame.groupby("group", sort=False).head(5).head(20000).reset_index(drop=True)
    stats["domain_cap_removed"] = before_cap - len(frame)
    for core in frame.core:
        assert prepare_url(core).core == core
    frame.to_parquet(output_path, index=False)
    manifest = {
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "source": "Phish360",
        "source_repository_commit": "01a0f2d6be31f1e90dedb0775ce2327d870ae638",
        "source_page": "https://web.cs.hacettepe.edu.tr/~selman/phish360-dataset/",
        "paper": "https://doi.org/10.3390/app16020751",
        "label_tier": "published_author_manual_curation_claim_not_two_independent_case_reviews",
        "usage": "authors_public_academic_research_release_no_redistribution_or_production_rights_claim",
        "collection_date_evidence": "source_page_2020_to_2023_paper_2020_to_2024_discrepancy_no_row_timestamps",
        "assets": assets,
        "registry_before_sha256": checksum(registry),
        "registry_manifest_before_sha256": checksum(registry.with_name("manifest.json")),
        "audit": dict(stats),
        "rows": len(frame),
        "class_counts": {str(k): int(v) for k, v in frame.label.value_counts().items()},
        "groups": int(frame.group.nunique()),
        "output_path": output_path.relative_to(root).as_posix(),
        "output_sha256": checksum(output_path),
        "scope": "new_source_group_disjoint_historical_url_only_not_indonesian_gold",
        "target_visits": 0,
        "limitations": [
            "No per-case adjudication sheets or agreement statistics released.",
            "Dataset paper and source page collection-period descriptions differ.",
            "Whole original file SHA256 unavailable under column projection; footer and projected-column hashes recorded.",
            "Any Indonesian language subset is a language tag, not independent evidence of Indonesian targeting.",
            "Campaign/time independence beyond domain exclusion is unverified.",
        ],
    }
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest
