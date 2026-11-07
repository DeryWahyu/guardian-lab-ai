"""Research-only source filtering, private-host routing and honest routed metrics."""

import numpy as np

from evaluate_v6_quality import domain_intervals
from v6_development_support import require_partition
from v6_diagnostic_support import safe_metrics
from v6_weighted_support import classifier_weights

CALIBRATION_KEYS = (
    "brier_score",
    "log_loss",
    "average_precision",
    "roc_auc",
    "reliability_bins",
    "ece_10_fixed_bins",
)


def filtered(frame, protocol):
    source = frame.training_source
    known = set(protocol["allowed_sources"]) | set(
        protocol["exclude_from_every_fit_and_development_partition"]
    )
    if not set(source) <= known:
        raise ValueError("unreviewed_training_source")
    return frame.loc[source.isin(protocol["allowed_sources"])].reset_index(drop=True)


def private_weights(frame):
    result = classifier_weights(frame, "source_sqrt_domain_class_soft")
    result = np.clip(result, 0.2, 5)
    return result / result.mean()


def private_cutoff(frame, scores, budget):
    require_partition(frame, "threshold")
    scores = np.asarray(scores)
    if (
        scores.ndim != 1
        or len(scores) != len(frame)
        or not np.isfinite(scores).all()
        or np.any((scores < 0) | (scores > 1))
    ):
        raise ValueError("invalid_private_threshold_scores")
    negative = np.sort(scores[frame.label.eq(0).to_numpy()])
    if len(negative) < 100 or not 0 <= budget < 1:
        raise ValueError("private_threshold_evidence_insufficient")
    allowed = int(np.floor(len(negative) * budget))
    return float(np.nextafter(negative[-allowed - 1], np.inf))


def decisions(probability, private, policies, level="warning"):
    return np.asarray(probability) >= np.where(
        private, policies["private"][level], policies["general"][level]
    )


def routed_metrics(frame, probability, flags, policies, repeats=0, seed=20261101):
    probability, flags = np.asarray(probability), np.asarray(flags)
    if (
        probability.ndim != 1
        or flags.ndim != 1
        or len(probability) != len(frame)
        or len(flags) != len(frame)
        or not np.isfinite(probability).all()
        or np.any((probability < 0) | (probability > 1))
        or flags.dtype != bool
        or not frame.label.isin([0, 1]).all()
    ):
        raise ValueError("invalid_routed_prediction")
    positive_only = len(frame) > 0 and frame.label.eq(1).all()
    result = safe_metrics(frame, flags.astype(float), 0.5, positive_only)
    calibrated = safe_metrics(frame, probability, 0.5, positive_only)
    for key in CALIBRATION_KEYS:
        if key in calibrated:
            result[key] = calibrated[key]
        else:
            result.pop(key, None)
    if frame.label.nunique() < 2:
        for key in (
            "accuracy",
            "precision",
            "brier_score",
            "log_loss",
            "balanced_accuracy",
            "average_precision",
            "roc_auc",
            "ece_10_fixed_bins",
        ):
            result[key] = None
    result["threshold"] = None
    result["policy_thresholds"] = policies
    result["domain_bootstrap95"] = (
        domain_intervals(frame, flags.astype(float), 0.5, repeats, seed, positive_only)
        if repeats and len(frame) and frame.label.eq(1).any()
        else None
    )
    return result


def development(frame, probability, flags, private, policies, protocol):
    require_partition(frame, "tune")
    sources = {
        s: routed_metrics(
            f,
            probability[frame.training_source.eq(s).to_numpy()],
            flags[frame.training_source.eq(s).to_numpy()],
            policies,
        )
        for s, f in frame.groupby("training_source")
    }
    supported = [
        m
        for m in sources.values()
        if m["phishing"] >= protocol["min_phishing_per_source_for_macro_recall"]
    ]
    return {
        "sources": sources,
        "macro_recall": float(np.mean([m["recall"] for m in supported])),
        "macro_brier": float(np.mean([m["brier_score"] for m in sources.values()])),
        "private": routed_metrics(
            frame.loc[private], probability[private], flags[private], policies
        ),
        "overall": routed_metrics(frame, probability, flags, policies),
    }


def choose(results):
    native, matched = results["baseline"], results["private_matched"]
    details, eligible = {}, []
    for name in (n for n in results if n not in ("baseline", "private_matched")):
        r = results[name]
        supported = [s for s, m in r["sources"].items() if m["phishing"] >= 20]
        source_loss = min(
            r["sources"][s]["recall"] - native["sources"][s]["recall"]
            for s in supported
        )
        fpr_gain = max(
            r["sources"][s]["fpr"] - native["sources"][s]["fpr"]
            for s in r["sources"]
            if r["sources"][s]["benign"] >= 100
        )
        gain = r["private"]["recall"] - matched["private"]["recall"]
        passed = (
            gain >= 0.02
            and r["private"]["recall"] >= native["private"]["recall"] - 0.005
            and r["private"]["fpr"]
            <= min(native["private"]["fpr"], matched["private"]["fpr"]) + 0.0025
            and r["macro_recall"] >= native["macro_recall"] - 0.005
            and source_loss >= -0.03
            and r["macro_brier"] <= native["macro_brier"] + 0.001
            and fpr_gain <= 0.0025
        )
        details[name] = {
            "private_recall_gain_vs_matched": gain,
            "private_recall_delta_vs_native": r["private"]["recall"]
            - native["private"]["recall"],
            "worst_source_recall_delta": source_loss,
            "max_source_fpr_increase": fpr_gain,
            "passed": passed,
        }
        if passed:
            eligible.append(name)

    def rank(n):
        return results[n]["private"]["recall"], -results[n]["macro_brier"]

    diagnostic = max(details, key=rank)
    return {
        "selected": max(eligible, key=rank) if eligible else "baseline",
        "diagnostic": max(eligible, key=rank) if eligible else diagnostic,
        "details": details,
        "tune_only": True,
        "production_ready": False,
    }
