"""Reserve exposure-audited PhishBench publisher URLs; never train on this intake."""

import io
import json

import pandas as pd

from guardian_ml.metadata import checksum
from guardian_ml.paths import ROOT
from evaluate_legitphish_v6 import collect_exposure, download_bytes, write_sidecar
from experiment_v6_expanded_data import curate_new, now, write_json
from intake_v6_expansion import sanitize_source
from intake_v6_segmented import map_labels

PROTOCOL = ROOT / "ml/reports/v6-segmented-phishbench-intake-protocol.json"
DIRECTORY = ROOT / "ml/data/v6-segmented-phishbench"


def main():
    if (DIRECTORY / "frozen.json").exists():
        raise ValueError("phishbench_intake_already_frozen")
    stealth = ROOT / "ml/data/v6-segmented-new-holdout/frozen.json"
    if not stealth.exists():
        raise ValueError(
            "stealth_exposure_required_before_independent_publisher_intake"
        )
    protocol = json.loads(PROTOCOL.read_text())
    source = protocol["source"]
    urls, domains, exposures = collect_exposure()
    content = download_bytes(source)
    raw = pd.read_csv(
        io.BytesIO(content), usecols=[source["url_column"], source["label_column"]]
    )
    counts = map_labels(raw, source)
    supported, audit = sanitize_source(
        raw, "phishbench_external", source["url_column"], source["label_column"]
    )
    supported["label"] = supported.publisher_label.map(source["label_mapping"])
    if supported.label.isna().any():
        raise ValueError("phishbench_unmapped_publisher_label")
    supported["label"] = supported.label.astype(int)
    supported = supported.drop(columns="publisher_label")
    del raw, content
    novel, curation = curate_new([supported], urls, domains, protocol["curation"])
    DIRECTORY.mkdir(parents=True, exist_ok=True)
    partitions = {}
    for name, frame in (("supported", supported), ("new_test", novel)):
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
        ROOT / "ml/data/exposure-sidecars/phishbench-segmented-20261105.sqlite",
        supported,
    )
    freeze = {
        "frozen_at_utc": now(),
        "available": bool(len(novel)),
        "protocol_path": PROTOCOL.relative_to(ROOT).as_posix(),
        "protocol_sha256": checksum(PROTOCOL),
        "source_hashes": {
            name: checksum(ROOT / name)
            for name in (
                "scripts/intake_v6_phishbench.py",
                "scripts/intake_v6_segmented.py",
                "scripts/intake_v6_expansion.py",
                "scripts/evaluate_legitphish_v6.py",
                "scripts/experiment_v6_expanded_data.py",
                "scripts/v6_development_support.py",
            )
        },
        "prior_exposure_hashes": exposures,
        "sidecar": sidecar,
        "partitions": {"new_test": partitions["new_test"]},
        "supported_path": partitions["supported"]["path"],
        "supported_sha256": partitions["supported"]["sha256"],
        "intake": audit,
        "curation": curation,
        "publisher_literal_label_counts": counts,
        "publisher_mapping": source["label_mapping"],
        "raw_file_sha256_verified": True,
        "all_retained_rows_reserved_for_testing": True,
        "human_gold": False,
        "Indonesia_gold": False,
        "production_ready": False,
    }
    write_json(DIRECTORY / "frozen.json", freeze)
    write_json(
        ROOT / "ml/provenance/phishbench-segmented-exposure.json",
        {
            "sidecar": sidecar,
            "intake_freeze_sha256": checksum(DIRECTORY / "frozen.json"),
            "scope": "all supported sanitized publisher inputs, including excluded and reserved test rows",
            "future_novelty_audits_must_include": True,
        },
    )
    print(
        json.dumps({"intake": audit, "curation": curation, "partitions": partitions}),
        flush=True,
    )


if __name__ == "__main__":
    main()
