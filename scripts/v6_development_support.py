"""Isolated research helpers; never imported by the frozen v6 service."""

from dataclasses import replace
import hashlib
import re
from urllib.parse import quote, unquote

import numpy as np
import pandas as pd
from scipy.special import logit
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.preprocessing import StandardScaler

from guardian_ml.evaluation import metrics
from guardian_ml.preprocessing import EXTRACT, InvalidUrl, prepare_url
from guardian_ml.rich_features import feature_matrix, numeric_values

REPRESENTATION = "url-core-path-assignment-redacted-experiment-1"
ASSIGNMENT = re.compile(
    r"(?P<prefix>^|[/;&])(?P<key>password|passwd|pwd|token|secret|otp|pin|session|"
    r"authorization|email|phone|mobile|nik|account|credential|access[_-]?token|"
    r"api[_-]?key)(?P<separator>=|:)(?P<value>[^/;&]*)",
    re.I,
)


def prepare_experiment_url(value):
    parsed = prepare_url(value)
    decoded = unquote(unquote(parsed.path))
    # Fixed-point replacement also covers adjacent matrix-style assignments.
    changed = 0
    for _ in range(3):

        def redact(match):
            nonlocal changed
            if match["value"] and match["value"] != "REDACTED":
                changed += 1
                return match["prefix"] + match["key"] + match["separator"] + "REDACTED"
            return match[0]

        result = ASSIGNMENT.sub(redact, decoded)
        if result == decoded:
            break
        decoded = result
    path = quote(decoded, safe="/-._~!$&'()*+,;=:@")
    core = parsed.core[: -len(parsed.path)] + path
    return replace(parsed, core=core, path=path, redactions=parsed.redactions + changed)


def representation_digest(core):
    return hashlib.sha256(core.split("://", 1)[1].encode()).hexdigest()


def transform_frame(frame):
    result = frame.copy()
    cores, groups, long_url, hosting, punycode = [], [], [], [], []
    changed = 0
    for core in frame.core:
        try:
            parsed = prepare_experiment_url(core)
        except InvalidUrl:
            raise ValueError("experiment_representation_rejected_cached_row") from None
        changed += parsed.core != core
        cores.append(parsed.core)
        groups.append(parsed.group)
        long_url.append(len(parsed.core.split("://", 1)[1]) > 120)
        hosting.append(bool(EXTRACT(parsed.host).is_private))
        punycode.append("xn--" in parsed.host)
    if groups != frame.group.tolist():
        raise ValueError("experiment_changed_domain_group")
    result["core"] = cores
    result["representation_digest"] = [representation_digest(core) for core in cores]
    result["long_url"] = long_url
    result["private_hosting"] = hosting
    result["punycode"] = punycode
    return result, {"rows": len(frame), "changed_cores": int(changed)}


def assert_separated(frames):
    """Checks identities only; holdout labels never influence fitting curation."""
    seen = {key: set() for key in ("group", "digest", "representation_digest")}
    for frame in frames:
        for key, previous in seen.items():
            values = set(frame[key])
            if previous.intersection(values):
                raise ValueError("partition_overlap_" + key)
            previous.update(values)


def require_partition(frame, expected):
    if set(frame.partition) != {expected}:
        raise ValueError("unexpected_partition_for_" + expected)


def curate_fit(frame):
    require_partition(frame, "fit")
    conflicts = frame.groupby("representation_digest").label.nunique()
    conflict_keys = set(conflicts[conflicts > 1].index)
    conflict_mask = frame.representation_digest.isin(conflict_keys)
    clean = frame.loc[~conflict_mask].sort_values("digest", kind="stable")
    retained = clean.drop_duplicates("representation_digest").reset_index(drop=True)
    return retained, {
        "original_fit_rows": len(frame),
        "conflicting_fit_representations": len(conflict_keys),
        "conflicting_fit_rows_quarantined": int(conflict_mask.sum()),
        "consistent_duplicate_fit_rows_removed": len(clean) - len(retained),
        "fit_rows": len(retained),
        "automatic_relabeling": False,
        "holdout_rows_removed": 0,
    }


def fit_encoder(fit, seed, source_cap=60000, total_cap=150000):
    require_partition(fit, "fit")
    text = fit.core.str.replace(r"^https?://", "", regex=True)
    samples = []
    for source in sorted(fit.training_source.unique()):
        subset = text[fit.training_source.eq(source)]
        samples.append(subset.sample(min(source_cap, len(subset)), random_state=seed))
    sample = pd.concat(samples)
    if len(sample) > total_cap:
        sample = sample.sample(total_cap, random_state=seed)
    encoder = {
        "char": TfidfVectorizer(
            analyzer="char",
            ngram_range=(2, 5),
            max_features=100000,
            min_df=4,
            sublinear_tf=True,
            dtype=np.float32,
        ).fit(sample),
        "word": TfidfVectorizer(
            analyzer="word",
            token_pattern=r"(?u)\b[a-zA-Z]{2,}\b",
            ngram_range=(1, 2),
            max_features=20000,
            min_df=4,
            sublinear_tf=True,
            dtype=np.float32,
        ).fit(sample),
        "scaler": StandardScaler(with_mean=False).fit(numeric_values(fit.core)),
    }
    return encoder, len(sample)


def fit_weights(fit, mode):
    require_partition(fit, "fit")
    sizes = fit.training_source.value_counts()
    weights = np.sqrt(sizes.max() / fit.training_source.map(sizes).to_numpy(float))
    if mode == "source_class":
        counts = fit.groupby(["training_source", "label"]).label.transform("size")
        weights *= fit.training_source.map(sizes).to_numpy(float) / (
            2 * counts.to_numpy()
        )
    elif mode == "hard_segments":
        focus = (fit.long_url & fit.label.eq(1)) | (
            fit.private_hosting & fit.label.eq(0)
        )
        weights *= np.where(focus, 2.0, 1.0)
    elif mode != "source_sqrt":
        raise ValueError("unknown_weighting_mode")
    return weights / weights.mean()


def source_threshold(frame, scores, budget, partition):
    require_partition(frame, partition)
    if not 0 <= budget < 1:
        raise ValueError("invalid_fpr_budget")
    scores = np.asarray(scores)
    if len(scores) != len(frame) or not np.isfinite(scores).all():
        raise ValueError("invalid_scores")
    points = []
    for source in sorted(frame.training_source.unique()):
        mask = frame.training_source.eq(source).to_numpy()
        negative = np.sort(scores[mask & frame.label.eq(0).to_numpy()])
        if not len(negative) or not frame.loc[mask, "label"].eq(1).any():
            raise ValueError("source_requires_both_classes")
        allowed = int(np.floor(budget * len(negative)))
        points.append(float(np.nextafter(negative[-allowed - 1], np.inf)))
    threshold = max(points)
    rates = {}
    for source in sorted(frame.training_source.unique()):
        mask = frame.training_source.eq(source).to_numpy()
        rates[source] = metrics(frame.label.to_numpy()[mask], scores[mask], threshold)
        if rates[source]["fpr"] > budget:
            raise ValueError("fpr_budget_exceeded")
    return {
        "threshold": threshold,
        "target_fpr_per_source": budget,
        "source_rates": rates,
    }


def tune_diagnostics(frame, scores):
    point = source_threshold(frame, scores, 0.01, "tune")
    recalls = [item["recall"] for item in point["source_rates"].values()]
    return {
        **point,
        "macro_source_recall": float(np.mean(recalls)),
        "minimum_source_recall": float(min(recalls)),
        "overall": metrics(frame.label, scores, point["threshold"]),
        "diagnostic_threshold_only_not_serving_policy": True,
    }


def select_candidate(results, baseline):
    eligible = []
    for name, result in results.items():
        gain = result["macro_source_recall"] - baseline["macro_source_recall"]
        worst_delta = min(
            result["source_rates"][source]["recall"] - previous["recall"]
            for source, previous in baseline["source_rates"].items()
        )
        if gain >= 0.02 and worst_delta >= -0.05:
            eligible.append(name)
    pool = eligible or list(results)
    # Stable tie-breaking in declared candidate order; no benchmark data accepted.
    chosen = max(
        pool,
        key=lambda name: (
            results[name]["macro_source_recall"],
            results[name]["minimum_source_recall"],
            results[name]["overall"]["average_precision"],
        ),
    )
    return {
        "candidate": chosen,
        "development_improvement_gate_passed": bool(eligible),
        "eligible_candidates": eligible,
        "selected_using": "tune_only",
    }


def predict_bundle(bundle, cores, batch_size=4096):
    output = []
    cores = list(cores)
    for start in range(0, len(cores), batch_size):
        prepared = [
            prepare_experiment_url(core).core
            for core in cores[start : start + batch_size]
        ]
        matrix = feature_matrix(bundle["encoder"], prepared)
        raw = bundle["classifier"].predict_proba(matrix)[:, 1]
        probability = bundle["calibrator"].predict_proba(
            logit(np.clip(raw, 1e-7, 1 - 1e-7)).reshape(-1, 1)
        )[:, 1]
        output.append(probability)
    return np.concatenate(output) if output else np.empty(0)
