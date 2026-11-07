"""Fit-only nested sampling, independent weight ablations and tune-only gates."""

import hashlib

import numpy as np
import pandas as pd

from v6_development_support import require_partition
from v6_diagnostic_support import safe_metrics
from v6_indonesia_external_support import structure_masks
from v6_weighted_support import classifier_weights


def nested_fit(frame, fraction, salt):
    require_partition(frame, "fit")
    if not 0 < fraction <= 1:
        raise ValueError("invalid_learning_fraction")
    groups = sorted(
        set(frame.group), key=lambda g: hashlib.sha256((salt + g).encode()).digest()
    )
    selected = set(groups[: max(1, int(len(groups) * fraction))])
    result = frame.loc[frame.group.isin(selected)].reset_index(drop=True)
    if set(result.label) != {0, 1}:
        raise ValueError("learning_fraction_missing_class")
    return result


def weights(frame, mode):
    base = classifier_weights(frame, "source_equal_domain_sqrt")
    if mode == "base":
        return base
    masks = structure_masks(frame)
    if mode == "private_phishing_x2":
        boosted = masks["private_hosting"] & frame.label.eq(1)
    elif mode == "hard_benign_x2":
        boosted = (
            masks["long_url_over_120"] | masks["deep_path_at_least_4"]
        ) & frame.label.eq(0)
    else:
        raise ValueError("unknown_learning_weight_mode")
    raw = pd.Series(base * np.where(boosted, 2.0, 1.0), index=frame.index)
    result = raw / raw.groupby(frame.training_source).transform("sum")
    return (result / result.mean()).to_numpy()


def slices(frame, scores, threshold):
    return {
        name: safe_metrics(
            frame.loc[mask], np.asarray(scores)[mask.to_numpy()], threshold
        )
        for name, mask in structure_masks(frame).items()
    }


def choose(results, names):
    baseline = results["control"]
    eligible_detection, eligible_calibration, details = [], [], {}
    for name in names:
        row = results[name]
        a, b = row["primary"], baseline["primary"]
        supported = [s for s, m in a["source_rates"].items() if m["phishing"] >= 20]
        gain = a["macro_source_recall"] - b["macro_source_recall"]
        loss = min(
            a["source_rates"][s]["recall"] - b["source_rates"][s]["recall"]
            for s in supported
        )
        brier = a["macro_source_brier"] - b["macro_source_brier"]
        worst_brier = max(
            a["source_rates"][s]["brier_score"] - b["source_rates"][s]["brier_score"]
            for s in a["source_rates"]
        )
        fpr = max(
            a["source_rates"][s]["fpr"] - b["source_rates"][s]["fpr"]
            for s in a["source_rates"]
            if a["source_rates"][s]["benign"] >= 100
        )
        structure = {}
        for key in ("private_hosting", "non_private_hosting"):
            am, bm = row["slices"][key], baseline["slices"][key]
            structure[key] = {
                "recall_delta": am["recall"] - bm["recall"]
                if am["phishing"] >= 20
                else None,
                "fpr_delta": am["fpr"] - bm["fpr"] if am["benign"] >= 100 else None,
            }
        guard = all(
            (s["recall_delta"] is None or s["recall_delta"] >= -0.005)
            and (s["fpr_delta"] is None or s["fpr_delta"] <= 0.0025)
            for s in structure.values()
        )
        common = guard and worst_brier <= 0.005 and fpr <= 0.0025
        detection = common and gain >= 0.02 and loss >= -0.03 and brier <= 0.001
        calibration = common and gain >= -0.005 and loss >= -0.005 and brier <= -0.002
        if detection:
            eligible_detection.append(name)
        if calibration:
            eligible_calibration.append(name)
        details[name] = {
            "macro_recall_delta": gain,
            "worst_source_recall_delta": loss,
            "macro_brier_delta": brier,
            "worst_source_brier_delta": worst_brier,
            "worst_source_fpr_delta": fpr,
            "structure": structure,
            "structure_guard": guard,
            "detection_gate": detection,
            "calibration_gate": calibration,
        }

    def rank(name):
        r = results[name]["primary"]
        return (
            r["macro_source_recall"],
            r["minimum_source_recall"],
            -r["macro_source_brier"],
        )

    if eligible_detection:
        selected = max(eligible_detection, key=rank)
    elif eligible_calibration:
        selected = min(
            eligible_calibration,
            key=lambda n: results[n]["primary"]["macro_source_brier"],
        )
    else:
        selected = "control"
    return {
        "selected": selected,
        "diagnostic": selected if selected != "control" else max(names, key=rank),
        "gate_passed": selected != "control",
        "details": details,
        "selection_data": "tune_only",
        "test_used_for_selection": False,
        "production_ready": False,
    }
