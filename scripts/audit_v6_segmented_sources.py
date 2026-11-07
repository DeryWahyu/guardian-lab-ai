"""Inspect pinned publisher schemas in memory; never display or retain raw URL rows."""

import argparse
import io
import json

import pandas as pd

from guardian_ml.paths import ROOT
from evaluate_legitphish_v6 import download_bytes, write_json
from experiment_v6_expanded_data import now

OUTPUT = ROOT / "ml/reports/v6-segmented-source-schema-audit.json"
ASSETS = {
    "stealthphisher": {
        "release": "https://data.mendeley.com/datasets/m2479kmybx/1",
        "filename": "StealthPhisher2025.csv",
        "download_url": "https://data.mendeley.com/public-files/datasets/m2479kmybx/files/71fe498a-ad6f-4204-b4ad-5d8d4d1ca0f3/file_downloaded",
        "bytes": 93319036,
        "sha256": "e6d9cb9a8ef87a8bdab24c0f4e22dfd5c77acc8fe7b5cb190fa62c0b5aaa25c8",
        "publisher_claimed_rows": 336749,
        "publisher_claimed_benign": 160943,
        "publisher_claimed_phishing": 175806,
        "license": "CC BY 4.0",
    },
    "phishbench_external": {
        "release": "https://data.mendeley.com/datasets/2ctjcnm9kn/2",
        "filename": "Phishing Detection External Evaluation Dataset (1000 URLs).csv",
        "download_url": "https://data.mendeley.com/public-files/datasets/2ctjcnm9kn/files/d7ac8833-833c-41e1-9662-09794abe1639/file_downloaded",
        "bytes": 104074,
        "sha256": "df25f4cae492c91cdca83887737a3d1672df71ebe8b581eeac21715a704b869f",
        "publisher_claimed_rows": 1000,
        "publisher_claimed_benign": 500,
        "publisher_claimed_phishing": 500,
        "license": "CC BY 4.0",
    },
}


def inspect(frame):
    columns = [str(col).strip() for col in frame.columns]
    url_columns = [
        col for col in columns if col.lower() in {"url", "urls", "raw_url", "website"}
    ]
    labels = [
        col
        for col in frame.columns
        if str(col).strip().lower()
        in {"label", "class", "classlabel", "status", "type"}
    ]
    frequencies = {}
    for col in labels:
        counts = frame[col].value_counts(dropna=False)
        if len(counts) > 12 or any(
            len(str(key)) > 30 or "://" in str(key) for key in counts.index
        ):
            frequencies[str(col)] = {"requires_schema_review": True}
        else:
            frequencies[str(col)] = {str(k): int(v) for k, v in counts.items()}
    return {
        "rows": len(frame),
        "columns": columns,
        "url_columns": url_columns,
        "label_counts": frequencies,
        "url_only_eligible": len(url_columns) == 1 and len(labels) == 1,
        "model_predictions_performed": False,
        "raw_urls_persisted": False,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", choices=list(ASSETS))
    args = parser.parse_args()
    output = (
        OUTPUT
        if args.source is None
        else OUTPUT.with_name("v6-segmented-" + args.source + "-schema-audit.json")
    )
    if output.exists():
        raise ValueError("publisher_schema_audit_already_recorded")
    results = {}
    for name, asset in ASSETS.items():
        if args.source is not None and args.source != name:
            continue
        try:
            content = download_bytes(asset)
        except ValueError as error:
            results[name] = {
                "asset": asset,
                "status": "rejected_integrity",
                "error_code": str(error),
                "model_predictions_performed": False,
            }
        else:
            frame = pd.read_csv(io.BytesIO(content), encoding="utf-8-sig")
            results[name] = {"asset": asset, **inspect(frame)}
            del content, frame
        print(json.dumps({"source": name, **results[name]}), flush=True)
    write_json(
        output,
        {"completed_at_utc": now(), "sources": results, "production_ready": False},
    )


if __name__ == "__main__":
    main()
