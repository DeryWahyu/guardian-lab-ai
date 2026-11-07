"""Pinned raw-URL intake; register all sanitized exposure and reserve domain holdout."""

import io
import json

import pandas as pd

from guardian_ml.metadata import checksum
from guardian_ml.paths import ROOT
from evaluate_legitphish_v6 import collect_exposure, write_sidecar
from experiment_v6_expanded_data import curate_new, now, write_json
from intake_v6_expansion import sanitize_source
from v6_pinned_download import download_pinned

AMENDMENT = ROOT / "ml/reports/v6-segmented-source-amendment.json"
DIRECTORY = ROOT / "ml/data/v6-segmented-new-holdout"


def map_labels(frame, specification):
    column = specification["label_column"]
    if len(frame) != specification["rows"]:
        raise ValueError("new_publisher_row_count_mismatch")
    counts = {
        str(k): int(v) for k, v in frame[column].value_counts(dropna=False).items()
    }
    if counts != specification["label_counts"]:
        raise ValueError("new_publisher_literal_label_totals_mismatch")
    return counts


def main():
    if (DIRECTORY / "frozen.json").exists():
        raise ValueError("segmented_intake_already_frozen")
    amendment = json.loads(AMENDMENT.read_text())
    if checksum(ROOT / amendment["parent_protocol"]) != amendment["parent_sha256"]:
        raise ValueError("segmented_parent_protocol_changed")
    source = amendment["source"]
    print(
        "Checking all historical exposure, every sidecar and original v6 caches",
        flush=True,
    )
    urls, domains, exposures = collect_exposure()
    content = download_pinned(source)
    raw = pd.read_csv(
        io.BytesIO(content), usecols=[source["url_column"], source["label_column"]]
    )
    counts = map_labels(raw, source)
    print("Sanitizing pinned publisher URLs in memory", flush=True)
    supported, audit = sanitize_source(
        raw, "stealthphisher", source["url_column"], source["label_column"]
    )
    supported["label"] = supported.publisher_label.map(source["label_mapping"])
    if supported.label.isna().any():
        raise ValueError("new_publisher_label_unmapped")
    supported["label"] = supported.label.astype(int)
    supported = supported.drop(columns="publisher_label")
    del raw, content
    novel, curation = curate_new([supported], urls, domains, amendment["curation"])
    DIRECTORY.mkdir(parents=True, exist_ok=True)
    supported_path = DIRECTORY / "supported.parquet"
    supported.to_parquet(supported_path, index=False)
    partitions = {}
    for name in ("fit", "new_test"):
        frame = novel.loc[novel.partition.eq(name)].reset_index(drop=True)
        path = DIRECTORY / (name + ".parquet")
        frame.to_parquet(path, index=False)
        partitions[name] = {
            "path": path.relative_to(ROOT).as_posix(),
            "sha256": checksum(path),
            "rows": len(frame),
            "groups": int(frame.group.nunique()),
            "classes": {str(k): int(v) for k, v in frame.label.value_counts().items()},
        }
    sidecar = write_sidecar(
        ROOT / "ml/data/exposure-sidecars/stealthphisher-segmented-20261105.sqlite",
        supported,
    )
    frozen = {
        "frozen_at_utc": now(),
        "available": bool(partitions["new_test"]["rows"]),
        "protocol_path": AMENDMENT.relative_to(ROOT).as_posix(),
        "protocol_sha256": checksum(AMENDMENT),
        "source_hashes": {
            name: checksum(ROOT / name)
            for name in (
                "scripts/intake_v6_segmented.py",
                "scripts/intake_v6_expansion.py",
                "scripts/evaluate_legitphish_v6.py",
                "scripts/experiment_v6_expanded_data.py",
                "scripts/v6_development_support.py",
                "scripts/v6_pinned_download.py",
                "ml/src/guardian_ml/preprocessing.py",
            )
        },
        "prior_exposure_hashes": exposures,
        "sidecar": sidecar,
        "partitions": partitions,
        "supported_path": supported_path.relative_to(ROOT).as_posix(),
        "supported_sha256": checksum(supported_path),
        "intake": audit,
        "curation": curation,
        "publisher_literal_label_counts": counts,
        "publisher_mapping": source["label_mapping"],
        "raw_file_sha256_verified": True,
        "human_gold": False,
        "Indonesia_gold": False,
        "contemporary_temporal_holdout": False,
        "publisher_also_used_in_augmentation_training": True,
        "production_ready": False,
    }
    write_json(DIRECTORY / "frozen.json", frozen)
    write_json(
        ROOT / "ml/provenance/stealthphisher-segmented-exposure.json",
        {
            "sidecar": sidecar,
            "intake_freeze_sha256": checksum(DIRECTORY / "frozen.json"),
            "scope": "all supported sanitized publisher inputs, including exclusions, fit and reserved holdout",
            "future_novelty_audits_must_include": True,
        },
    )
    print(
        json.dumps({"intake": audit, "curation": curation, "partitions": partitions}),
        flush=True,
    )


if __name__ == "__main__":
    main()
