"""Development-only policies and paired domain uncertainty for the v7 notebook."""

import numpy as np
import pandas as pd
from sklearn.metrics import average_precision_score

from .evaluation import metrics, operating_point, wilson


def safe_metrics(labels, probabilities, threshold):
    result = metrics(labels, probabilities, threshold)
    if result["benign"] == 0:
        result["fpr"] = None
        result["accuracy"] = None
        result["precision"] = None
        result["f1"] = None
    if result["phishing"] == 0:
        result["recall"] = None
        result["f1"] = None
    cm = result["confusion_matrix"]
    if cm["tp"] + cm["fp"] == 0:
        result["precision"] = None
    return result


def source_point(frame, probabilities, budget, *, confidence=False):
    probabilities = np.asarray(probabilities, dtype=float)
    points = {}
    for source, indices in frame.groupby("training_source").groups.items():
        positions = np.asarray(list(indices))
        y = frame.label.iloc[positions].to_numpy()
        p = probabilities[positions]
        benign = int((y == 0).sum())
        feasible = benign > 0 and wilson(0, benign)[1] <= budget
        allowed = budget
        if confidence and feasible:
            counts = np.arange(benign + 1)
            eligible = counts[np.array([wilson(int(k), benign)[1] for k in counts]) <= budget]
            allowed = float(eligible[-1] / benign)
        point = operating_point(y, p, allowed)
        points[source] = {
            "threshold": point["threshold"],
            "benign_rows": benign,
            "wilson_constraint_applied": confidence and feasible,
            "wilson_constraint_feasible_at_zero_fp": feasible,
            "empirical_fpr_budget_used": allowed,
        }
    threshold = max(item["threshold"] for item in points.values())
    rates = {
        source: safe_metrics(
            frame.label.iloc[list(indices)], probabilities[list(indices)], threshold
        )
        for source, indices in frame.groupby("training_source").groups.items()
    }
    return {
        "threshold": threshold,
        "target_fpr": budget,
        "source_constraints": points,
        "source_rates": rates,
    }


def selection_diagnostics(frame, raw):
    point = source_point(frame, raw, 0.01)
    recalls = [item["recall"] for item in point["source_rates"].values()]
    ap = float(average_precision_score(frame.label, raw))
    return {
        "selection_score": [float(np.mean(recalls)), float(min(recalls)), ap],
        "macro_source_recall": float(np.mean(recalls)),
        "min_source_recall": float(min(recalls)),
        "average_precision": ap,
        "point": point,
    }


def paired_domain_interval(frame, old, new, old_threshold, new_threshold, repeats=1000):
    labels = frame.label.to_numpy()
    records = pd.DataFrame({"group": frame.group.to_numpy()})
    for prefix, probability, threshold in [
        ("old", old, old_threshold),
        ("new", new, new_threshold),
    ]:
        positive = probability >= threshold
        records[prefix + "_tp"] = (labels == 1) & positive
        records[prefix + "_fn"] = (labels == 1) & ~positive
        records[prefix + "_fp"] = (labels == 0) & positive
        records[prefix + "_tn"] = (labels == 0) & ~positive
    values = records.groupby("group", sort=True).sum().to_numpy()
    rng = np.random.default_rng(20261101)
    draws = []
    for _ in range(repeats):
        counts = values[rng.integers(0, len(values), len(values))].sum(axis=0)
        a, b, c, d, e, f, g, h = counts
        draws.append([e / max(1, e + f) - a / max(1, a + b), g / max(1, g + h) - c / max(1, c + d)])
    intervals = np.quantile(draws, [0.025, 0.975], axis=0)
    return {
        "resampling_unit": "registered_domain_private_tenant",
        "repeats": repeats,
        "recall_delta95": intervals[:, 0].tolist(),
        "fpr_delta95": intervals[:, 1].tolist() if (labels == 0).any() else None,
    }
