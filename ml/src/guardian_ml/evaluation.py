"""Metrics, empirical FPR operating points, and documented uncertainty."""

import numpy as np
from scipy.special import logit
from sklearn.isotonic import IsotonicRegression
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    average_precision_score,
    brier_score_loss,
    confusion_matrix,
    log_loss,
    roc_auc_score,
    roc_curve,
)


def wilson(successes, total):
    if total == 0:
        return [None, None]
    z = 1.959963984540054
    rate = successes / total
    denominator = 1 + z * z / total
    center = (rate + z * z / (2 * total)) / denominator
    half = z * np.sqrt(rate * (1 - rate) / total + z * z / (4 * total * total)) / denominator
    return [
        0.0 if successes == 0 else float(max(0, center - half)),
        1.0 if successes == total else float(min(1, center + half)),
    ]


def operating_point(y, probability, budget=0.001):
    y = np.asarray(y)
    probability = np.asarray(probability, dtype=float)
    fpr, recall, thresholds = roc_curve(y, probability, drop_intermediate=False)
    eligible = np.flatnonzero(fpr <= budget)
    # Thresholds are descending; the last eligible point maximizes sensitivity.
    index = eligible[-1]
    threshold = float(thresholds[index])
    if not np.isfinite(threshold):
        threshold = float(np.nextafter(1.0, 2.0))
    return {
        "threshold": threshold,
        "empirical_fpr": float(fpr[index]),
        "recall": float(recall[index]),
        "target_fpr": budget,
    }


def metrics(y, probability, threshold):
    y = np.asarray(y, dtype=int)
    probability = np.asarray(probability, dtype=float)
    assert np.isfinite(probability).all()
    prediction = probability >= threshold
    tn, fp, fn, tp = confusion_matrix(y, prediction, labels=[0, 1]).ravel()

    def ratio(a, b):
        return float(a / b) if b else 0.0

    result = {
        "rows": len(y),
        "benign": int(tn + fp),
        "phishing": int(tp + fn),
        "threshold": float(threshold),
        "confusion_matrix": {"tn": int(tn), "fp": int(fp), "fn": int(fn), "tp": int(tp)},
        "accuracy": ratio(tp + tn, len(y)),
        "precision": ratio(tp, tp + fp),
        "recall": ratio(tp, tp + fn),
        "fpr": ratio(fp, tn + fp),
        "f1": ratio(2 * tp, 2 * tp + fp + fn),
        "brier_score": float(brier_score_loss(y, probability)),
        "log_loss": float(log_loss(y, np.clip(probability, 1e-7, 1 - 1e-7), labels=[0, 1])),
        "fpr_wilson95_rows_iid_assumption": wilson(fp, fp + tn),
        "recall_wilson95_rows_iid_assumption": wilson(tp, tp + fn),
    }
    if len(np.unique(y)) == 2:
        result["average_precision"] = float(average_precision_score(y, probability))
        result["roc_auc"] = float(roc_auc_score(y, probability))
    bins = []
    bucket = np.minimum((probability * 10).astype(int), 9)
    for index in range(10):
        lower = index / 10
        subset = bucket == index
        if subset.any():
            bins.append(
                {
                    "lower": round(float(lower), 1),
                    "rows": int(subset.sum()),
                    "mean_probability": float(probability[subset].mean()),
                    "phishing_fraction": float(y[subset].mean()),
                }
            )
    result["reliability_bins"] = bins
    return result


def apply_calibration(calibrator, raw):
    values = np.clip(raw, 1e-7, 1 - 1e-7)
    if calibrator["method"] == "isotonic":
        return calibrator["model"].predict(values)
    return calibrator["model"].predict_proba(logit(values).reshape(-1, 1))[:, 1]


def calibrate(y, raw, groups):
    import hashlib

    groups = np.asarray(groups)
    mask = np.array(
        [int(hashlib.sha256(value.encode()).hexdigest()[:8], 16) % 2 == 0 for value in groups]
    )
    assert len(set(groups[mask]) & set(groups[~mask])) == 0
    assert len(np.unique(y[mask])) == len(np.unique(y[~mask])) == 2
    results = {}
    fitted = {}
    values = np.clip(raw, 1e-7, 1 - 1e-7)
    for name in ("sigmoid", "isotonic"):
        model = (
            LogisticRegression(C=1000, max_iter=200, random_state=20261101)
            if name == "sigmoid"
            else IsotonicRegression(out_of_bounds="clip")
        )
        model.fit(
            logit(values[mask]).reshape(-1, 1) if name == "sigmoid" else values[mask], y[mask]
        )
        fitted[name] = {"method": name, "model": model}
        results[name] = float(
            brier_score_loss(y[~mask], apply_calibration(fitted[name], values[~mask]))
        )
    name = min(results, key=results.get)
    winner = fitted[name]["model"]
    winner.fit(logit(values).reshape(-1, 1) if name == "sigmoid" else values, y)
    return {"method": name, "model": winner}, {
        "internal_group_holdout_brier": results,
        "selected": name,
        "rows": len(y),
        "probability_reference": "curated PhreshPhish calibration distribution",
        "production_prevalence_calibrated": False,
    }


def group_bootstrap(y, probability, groups, threshold, repeats=200):
    import pandas as pd

    y = np.asarray(y)
    positive = probability >= threshold
    frame = pd.DataFrame(
        {
            "group": groups,
            "tn": (y == 0) & ~positive,
            "fp": (y == 0) & positive,
            "fn": (y == 1) & ~positive,
            "tp": (y == 1) & positive,
        }
    )
    counts = frame.groupby("group", sort=True)[["tn", "fp", "fn", "tp"]].sum().to_numpy()
    rng = np.random.default_rng(20261101)
    draws = []
    for _ in range(repeats):
        tn, fp, fn, tp = counts[rng.integers(0, len(counts), len(counts))].sum(axis=0)
        draws.append([fp / max(1, fp + tn), tp / max(1, tp + fn), tp / max(1, tp + fp)])
    intervals = np.quantile(draws, [0.025, 0.975], axis=0)
    return {
        "resampling_unit": "PSL registered domain/private tenant",
        "repeats": repeats,
        "fpr95": intervals[:, 0].tolist(),
        "recall95": intervals[:, 1].tolist(),
        "precision95": intervals[:, 2].tolist(),
    }
