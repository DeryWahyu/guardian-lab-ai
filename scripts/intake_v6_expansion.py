"""Acquire only pinned public URL/label files; persist sanitized candidates."""

import argparse
from collections import Counter
import io
import json

import pandas as pd

from guardian_ml.paths import ROOT
from guardian_ml.metadata import checksum
from guardian_ml.preprocessing import InvalidUrl
from evaluate_legitphish_v6 import download_bytes, write_json
from v6_development_support import prepare_experiment_url, representation_digest

PROTOCOL = ROOT / "ml/reports/v6-expansion-20261105-protocol.json"
DIRECTORY = ROOT / "ml/data/v6-expansion-20261105"


def sanitize_source(frame, source, url_column, label_column):
    counts, records = Counter(), []
    labels = frame[label_column]
    # Keep original label values; explicit mapping is separately approved from source evidence.
    frequencies = {
        str(key): int(value) for key, value in labels.value_counts(dropna=False).items()
    }
    if any(len(key) > 40 or "://" in key for key in frequencies):
        raise ValueError("unexpected_label_column_refuse_to_print_values")
    for url, label in zip(frame[url_column], labels):
        if pd.isna(label):
            counts["missing_label"] += 1
            continue
        try:
            parsed = prepare_experiment_url(url)
        except InvalidUrl as error:
            counts["unsupported_" + str(error)] += 1
            continue
        records.append(
            {
                "core": parsed.core,
                "digest": parsed.digest,
                "group": parsed.group,
                "representation_digest": representation_digest(parsed.core),
                "publisher_label": str(label),
                "training_source": source,
            }
        )
    return pd.DataFrame(records), {
        "raw_rows": len(frame),
        "label_counts": frequencies,
        "columns": list(frame.columns),
        "exclusions": dict(counts),
        "sanitized_rows": len(records),
    }


def main():
    args = argparse.ArgumentParser(description=__doc__).parse_args()
    del args
    protocol = json.loads(PROTOCOL.read_text())
    for name, asset in protocol["sources"].items():
        output = DIRECTORY / (name + "-sanitized.parquet")
        if output.exists():
            print("Retaining completed intake: " + name, flush=True)
            continue
        content = download_bytes(asset)
        if asset["filename"].endswith(".xlsx"):
            frame = pd.read_excel(io.BytesIO(content))
        else:
            frame = pd.read_csv(io.BytesIO(content))
        columns = list(frame.columns)
        url_candidates = [
            col
            for col in columns
            if str(col).strip().lower() in ("url", "raw_url", "urls")
        ]
        label_candidates = [
            col
            for col in columns
            if str(col).strip().lower()
            in ("label", "classlabel", "class", "status", "type")
        ]
        if len(url_candidates) != 1 or len(label_candidates) != 1:
            print(
                json.dumps(
                    {
                        "source": name,
                        "status": "schema_review_required",
                        "columns": columns,
                    }
                ),
                flush=True,
            )
            continue
        retained, audit = sanitize_source(
            frame, name, url_candidates[0], label_candidates[0]
        )
        del content, frame
        retained.to_parquet(output, index=False)
        audit["cache_sha256"] = checksum(output)
        audit["intake_source_sha256"] = checksum(__file__)
        write_json(
            DIRECTORY / (name + "-intake.json"),
            {
                **audit,
                "asset": asset,
                "url_column": url_candidates[0],
                "label_column": label_candidates[0],
                "labels_mapped": False,
                "targets_visited": False,
                "raw_urls_persisted": False,
            },
        )
        print(json.dumps({"source": name, **audit}), flush=True)


if __name__ == "__main__":
    main()
