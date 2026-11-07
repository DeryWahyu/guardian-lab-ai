"""Report aggregate structural coverage of added data without model scores or URLs."""

import pandas as pd

from guardian_ml.paths import ROOT
from guardian_ml.preprocessing import EXTRACT
from experiment_v6_expanded_data import now, write_json


def profile(path):
    frame = pd.read_parquet(path, columns=["core", "label", "group"])
    body = frame.core.str.replace(r"^https?://", "", regex=True)
    host = body.str.split("/", n=1).str[0]
    masks = {
        "long_url_over_120": body.str.len().gt(120),
        "deep_path_at_least_4": body.str.count("/").ge(4),
        "private_hosting": host.map(lambda text: bool(EXTRACT(text).is_private)),
        "punycode": host.str.contains("xn--", regex=False),
    }
    return {
        "rows": len(frame),
        "groups": int(frame.group.nunique()),
        "classes": {str(k): int(v) for k, v in frame.label.value_counts().items()},
        "structure": {
            name: {
                "benign": int((mask & frame.label.eq(0)).sum()),
                "phishing": int((mask & frame.label.eq(1)).sum()),
            }
            for name, mask in masks.items()
        },
    }


def main():
    result = {
        "completed_at_utc": now(),
        "model_scores_used": False,
        "publisher_labels_only": True,
        "data": {},
    }
    for name, relative in {
        "original_fit": "ml/runs/v6-targeted-20261105/fit.parquet",
        "additional_fit": "ml/data/v6-segmented-new-holdout/fit.parquet",
        "new_stealth_holdout": "ml/data/v6-segmented-new-holdout/new_test.parquet",
    }.items():
        result["data"][name] = profile(ROOT / relative)
    write_json(ROOT / "ml/reports/v6-segmented-data-coverage.json", result)
    print("Aggregate data coverage exported", flush=True)


if __name__ == "__main__":
    main()
