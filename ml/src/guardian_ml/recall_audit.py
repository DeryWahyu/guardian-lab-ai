"""Development-only error slices; model disagreement never assigns ground truth."""

import numpy as np
import pandas as pd

from .features import feature_row
from .preprocessing import EXTRACT, prepare_url
from .structural_evaluation import safe_metrics


def error_flags(cores):
    records = []
    for core in cores:
        item = prepare_url(core)
        if item.core != core:
            raise ValueError("canonical_core_required")
        values = feature_row(item)
        records.append(
            {
                "private_hosting": bool(EXTRACT(item.host).is_private),
                "homepage": item.path == "/",
                "short_path": len(item.path) <= 12,
                "long_url": len(core.split("://", 1)[1]) > 120,
                "punycode": "xn--" in item.host,
                "indonesia_suffix": item.host.endswith(".id"),
                "many_host_labels": values["host_labels"] >= 4,
                "deep_path": values["path_depth"] >= 3,
                "lexically_plain": not any(
                    values[name]
                    for name in ["keyword_count", "brand_count", "punycode", "ip_literal"]
                ),
            }
        )
    return pd.DataFrame(records)


def error_slices(frame, probabilities, thresholds, flags):
    if set(frame.partition) != {"tune"}:
        raise ValueError("error_diagnosis_requires_development_tune")
    frame = frame.reset_index(drop=True)
    flags = flags.reset_index(drop=True)
    masks = {"all": np.ones(len(frame), dtype=bool)}
    masks.update(
        {"source:" + s: frame.training_source.eq(s) for s in sorted(frame.training_source.unique())}
    )
    for name in flags:
        masks[name + ":yes"] = flags[name].to_numpy(dtype=bool)
        masks[name + ":no"] = ~flags[name].to_numpy(dtype=bool)
    results, cases = {}, frame[["digest", "group", "label", "training_source"]].copy()
    for model, values in probabilities.items():
        values = np.asarray(values)
        positive = values >= thresholds[model]
        cases[model + "_error"] = np.select(
            [(frame.label == 1) & ~positive, (frame.label == 0) & positive],
            ["false_negative", "false_positive"],
            default="correct",
        )
        results[model] = {
            name: safe_metrics(frame.label[mask], values[mask], thresholds[model])
            for name, mask in masks.items()
            if np.asarray(mask).any()
        }
    for name in flags:
        cases[name] = flags[name]
    return results, cases
