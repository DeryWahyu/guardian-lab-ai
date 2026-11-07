"""Research-only weighting, selection and aggregate error review helpers."""

import hashlib

import numpy as np
import pandas as pd

from guardian_ml.preprocessing import EXTRACT
from v6_development_support import fit_weights, require_partition
from v6_diagnostic_support import export_review_queues, safe_metrics


def classifier_weights(frame, mode):
    require_partition(frame, "fit")
    if set(frame.label) != {0, 1}:
        raise ValueError("weighted_fit_requires_two_classes")
    groups = frame.groupby("group").group.transform("size").to_numpy(float)
    weights = fit_weights(frame, "source_sqrt") / np.sqrt(groups)
    if mode == "source_equal_domain_sqrt":
        raw = pd.Series(1 / np.sqrt(groups), index=frame.index)
        totals = raw.groupby(frame.training_source).transform("sum").to_numpy()
        weights = raw.to_numpy() / totals
    elif mode == "source_sqrt_domain_class_soft":
        sizes = frame.training_source.map(
            frame.training_source.value_counts()
        ).to_numpy(float)
        cells = (
            frame.groupby(["training_source", "label"])
            .label.transform("size")
            .to_numpy(float)
        )
        weights *= np.sqrt(sizes / (2 * cells))
    elif mode != "source_sqrt_domain_sqrt":
        raise ValueError("unknown_weighted_classifier_mode")
    if not np.isfinite(weights).all() or (weights <= 0).any():
        raise ValueError("invalid_classifier_weights")
    return weights / weights.mean()


def calibration_weights(frame, mode):
    require_partition(frame, "calibration")
    if mode == "row_sigmoid":
        return np.ones(len(frame))
    if mode != "source_equal_sigmoid":
        raise ValueError("unknown_calibration_mode")
    counts = frame.training_source.map(frame.training_source.value_counts()).to_numpy(
        float
    )
    weights = 1 / counts
    return weights / weights.mean()


def summarize_tune(frame, scores, threshold, protocol):
    require_partition(frame, "tune")
    sources = {
        name: safe_metrics(
            sub, scores[frame.training_source.eq(name).to_numpy()], threshold
        )
        for name, sub in frame.groupby("training_source")
    }
    supported = [
        m
        for m in sources.values()
        if m["phishing"] >= protocol["min_phishing_per_source_for_macro_recall"]
    ]
    return {
        "source_rates": sources,
        "macro_source_recall": float(np.mean([m["recall"] for m in supported])),
        "minimum_source_recall": float(min(m["recall"] for m in supported)),
        "macro_source_brier": float(
            np.mean([m["brier_score"] for m in sources.values()])
        ),
        "overall": safe_metrics(frame, scores, threshold),
    }


def choose_research_candidate(results, baseline):
    detection, calibration, details = [], [], {}
    for name, row in results.items():
        if name == "control_native":
            continue
        supported = [
            source for source, m in row["source_rates"].items() if m["phishing"] >= 20
        ]
        recall_loss = min(
            row["source_rates"][s]["recall"] - baseline["source_rates"][s]["recall"]
            for s in supported
        )
        brier_loss = max(
            row["source_rates"][s]["brier_score"]
            - baseline["source_rates"][s]["brier_score"]
            for s in row["source_rates"]
        )
        gain = row["macro_source_recall"] - baseline["macro_source_recall"]
        brier_gain = baseline["macro_source_brier"] - row["macro_source_brier"]
        d = gain >= 0.02 and recall_loss >= -0.05 and brier_gain >= -0.01
        c = (
            gain >= -0.005
            and recall_loss >= -0.005
            and brier_gain >= 0.005
            and brier_loss <= 0.02
        )
        if d:
            detection.append(name)
        if c:
            calibration.append(name)
        details[name] = {
            "macro_recall_delta": gain,
            "worst_source_recall_delta": recall_loss,
            "macro_brier_reduction": brier_gain,
            "worst_source_brier_increase": brier_loss,
            "detection_gate": d,
            "calibration_gate": c,
        }

    def ranking(name):
        return (
            results[name]["macro_source_recall"],
            results[name]["minimum_source_recall"],
            -results[name]["macro_source_brier"],
        )

    challengers = [name for name in results if name != "control_native"]
    best = max(challengers, key=ranking)
    if detection:
        selected = max(detection, key=ranking)
    elif calibration:
        selected = max(
            calibration,
            key=lambda name: (
                -results[name]["macro_source_brier"],
                results[name]["macro_source_recall"],
            ),
        )
    else:
        selected = "control_native"
    return {
        "selected": selected,
        "evaluated_candidate": selected if selected != "control_native" else best,
        "detection_eligible": detection,
        "calibration_eligible": calibration,
        "development_gate_passed": bool(detection or calibration),
        "details": details,
        "selection_data": "tune_only",
        "production_ready": False,
    }


def structural_audit(frame, scores, threshold):
    require_partition(frame, "tune")
    body = frame.core.str.replace(r"^https?://", "", regex=True)
    hosts = body.str.split("/", n=1).str[0]
    flags = {
        "long_url": body.str.len().gt(120),
        "deep_path": body.str.count("/").ge(4),
        "private_hosting": hosts.map(lambda host: bool(EXTRACT(host).is_private)),
        "punycode": hosts.str.contains("xn--", regex=False),
        "redacted": frame.core.str.contains("REDACTED", regex=False),
    }
    result = {}
    for name, values in flags.items():
        result[name] = {}
        for value in [False, True]:
            mask = values.eq(value)
            subset = frame.loc[mask]
            if len(subset):
                result[name][str(value)] = safe_metrics(
                    subset,
                    scores[mask.to_numpy()],
                    threshold,
                    positive_only=subset.label.eq(1).all(),
                )
    return result


def development_review_queue(frame, scores, threshold, directory):
    require_partition(frame, "tune")
    pred = np.asarray(scores) >= threshold
    reasons = {
        "false_negative": frame.label.eq(1).to_numpy() & ~pred,
        "false_positive": frame.label.eq(0).to_numpy() & pred,
    }
    conflicts = frame.groupby("representation_digest").label.nunique()
    reasons["publisher_representation_conflict"] = frame.representation_digest.isin(
        conflicts[conflicts > 1].index
    ).to_numpy()
    coordinator, blind = [], []
    for reason, mask in reasons.items():
        subset = frame.loc[mask].sort_values("digest")
        if reason != "publisher_representation_conflict":
            subset = (
                subset.drop_duplicates("group")
                .groupby("training_source", sort=True)
                .head(12)
            )
        for row in subset.itertuples():
            case = (
                "v6w-" + hashlib.sha256((reason + row.digest).encode()).hexdigest()[:20]
            )
            locator = {
                "case_id": case,
                "cache_digest": row.digest,
                "cache_filename": "ml/runs/v6-targeted-20261105/tune.parquet",
            }
            blind.append(locator)
            coordinator.append(
                {
                    **locator,
                    "reason": reason,
                    "source": row.training_source,
                    "publisher_label": int(row.label),
                    "label_evidence": "publisher_only_not_new_human_gold",
                }
            )
    export_review_queues(directory, pd.DataFrame(coordinator), pd.DataFrame(blind))
    return {
        "review_cases": len(blind),
        "reasons": pd.Series([r["reason"] for r in coordinator])
        .value_counts()
        .to_dict(),
        "completed_human_reviews": 0,
        "automatic_relabeling": False,
        "sampling": "development errors only; never an independent gold sampling frame",
    }
