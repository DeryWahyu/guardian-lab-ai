"""Versioned URL-only research features and conservative development selection."""

from functools import lru_cache
import re

import numpy as np
import pandas as pd
from scipy.sparse import csr_matrix, hstack
from scipy.special import logit
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler, normalize

from guardian_ml.features import entropy
from guardian_ml.preprocessing import EXTRACT
from guardian_ml.rich_features import feature_matrix
from experiment_v6_development import checked_fit
from v6_development_support import prepare_experiment_url, require_partition
from v6_weighted_support import calibration_weights

FEATURE_VERSION = "url-core-host-subdomain-path-research-1"
STRUCTURE = (
    "host_length",
    "subdomain_length",
    "domain_length",
    "path_length",
    "path_depth",
    "max_path_segment_length",
    "mean_path_segment_length",
    "host_digit_fraction",
    "subdomain_digit_fraction",
    "path_digit_fraction",
    "host_entropy",
    "subdomain_entropy",
    "path_entropy",
    "path_dot_count",
    "host_hyphen_fraction",
    "path_punctuation_fraction",
    "numeric_path_segments",
    "hex_path_segments",
)
MODES = ("structure", "segmented_text", "segmented_text_structure")


@lru_cache(maxsize=100000)
def host_parts(host):
    result = EXTRACT(host)
    return result.subdomain, result.domain


def fraction(text, predicate):
    return sum(predicate(char) for char in text) / max(1, len(text))


def split_cores(cores):
    """Only versioned sanitized host/path enter features; scheme/query are absent."""
    hosts, subdomains, paths, values = [], [], [], []
    for core in cores:
        parsed = prepare_experiment_url(core)
        host, path = parsed.host, parsed.path
        subdomain, domain = host_parts(host)
        segments = [segment for segment in path.split("/") if segment]
        lengths = [len(segment) for segment in segments]
        hosts.append(host)
        subdomains.append(subdomain or "nosubdomain")
        paths.append(
            path.lower() if re.search(r"(?u)\b[a-zA-Z]{2,}\b", path) else "nonwordpath"
        )
        values.append(
            [
                len(host),
                len(subdomain),
                len(domain),
                len(path),
                len(segments),
                max(lengths, default=0),
                float(np.mean(lengths)) if lengths else 0,
                fraction(host, str.isdigit),
                fraction(subdomain, str.isdigit),
                fraction(path, str.isdigit),
                entropy(host),
                entropy(subdomain),
                entropy(path),
                path.count("."),
                host.count("-") / max(1, len(host)),
                fraction(path, lambda char: not char.isalnum() and char != "/"),
                sum(segment.isdigit() for segment in segments),
                sum(bool(re.fullmatch(r"[a-fA-F0-9]{8,}", s)) for s in segments),
            ]
        )
    return {
        "host": hosts,
        "subdomain": subdomains,
        "path": paths,
        "structure": np.log1p(
            np.asarray(values, dtype=np.float32).reshape(-1, len(STRUCTURE))
        ),
    }


def fit_segment_encoder(fit, specification, seed):
    require_partition(fit, "fit")
    sample = pd.concat(
        [
            part.sample(min(len(part), specification["source_cap"]), random_state=seed)
            for _, part in fit.groupby("training_source", sort=True)
        ]
    )
    sample = sample.sample(
        min(len(sample), specification["total_cap"]), random_state=seed
    )
    fields = split_cores(sample.core)
    encoder = {
        "version": FEATURE_VERSION,
        "host": TfidfVectorizer(
            analyzer="char",
            ngram_range=(3, 5),
            min_df=4,
            max_features=specification["host_features"],
            sublinear_tf=True,
            dtype=np.float32,
        ).fit(fields["host"]),
        "subdomain": TfidfVectorizer(
            analyzer="word",
            token_pattern=r"(?u)\b[a-zA-Z][a-zA-Z0-9_-]{1,}\b",
            ngram_range=(1, 2),
            min_df=4,
            max_features=specification["subdomain_features"],
            sublinear_tf=True,
            dtype=np.float32,
        ).fit(fields["subdomain"]),
        "path": TfidfVectorizer(
            analyzer="word",
            token_pattern=r"(?u)\b[a-zA-Z]{2,}\b",
            ngram_range=(1, 2),
            min_df=4,
            max_features=specification["path_features"],
            sublinear_tf=True,
            dtype=np.float32,
        ).fit(fields["path"]),
        "structure_columns": STRUCTURE,
        "fit_rows": len(fit),
        "vocabulary_sample_rows": len(sample),
    }
    # Numeric scaling is fitted on fitting rows only, independently of class labels.
    numeric = np.vstack(
        [
            split_cores(fit.core.iloc[start : start + 4096])["structure"]
            for start in range(0, len(fit), 4096)
        ]
    )
    encoder["scaler"] = StandardScaler(with_mean=False).fit(numeric)
    encoder["text_features"] = sum(
        len(encoder[k].vocabulary_) for k in ("host", "subdomain", "path")
    )
    return encoder


def extra_matrix(encoder, cores):
    if (
        encoder["version"] != FEATURE_VERSION
        or tuple(encoder["structure_columns"]) != STRUCTURE
    ):
        raise ValueError("segmented_feature_schema_mismatch")
    fields = split_cores(cores)
    numeric = np.clip(encoder["scaler"].transform(fields["structure"]), 0, 10)
    return hstack(
        [
            0.7 * encoder["host"].transform(fields["host"]),
            0.5 * encoder["subdomain"].transform(fields["subdomain"]),
            0.7 * encoder["path"].transform(fields["path"]),
            0.4 * csr_matrix(normalize(numeric)),
        ],
        format="csr",
        dtype=np.float32,
    )


def combine_matrix(base, extra, encoder, mode):
    if mode not in MODES or base.shape[0] != extra.shape[0]:
        raise ValueError("invalid_segmented_feature_mode_or_rows")
    text = encoder["text_features"]
    if extra.shape[1] != text + len(STRUCTURE):
        raise ValueError("invalid_segmented_feature_dimension")
    selected = (
        extra[:, text:]
        if mode == "structure"
        else (extra[:, :text] if mode == "segmented_text" else extra)
    )
    return hstack([base, selected], format="csr", dtype=np.float32)


def calibration_design(raw, kind):
    values = np.asarray(raw, dtype=float)
    if (
        values.ndim != 1
        or not np.isfinite(values).all()
        or ((values < 0) | (values > 1)).any()
    ):
        raise ValueError("invalid_raw_calibration_probabilities")
    values = np.clip(values, 1e-7, 1 - 1e-7)
    if kind == "source_equal_sigmoid":
        return logit(values).reshape(-1, 1)
    if kind == "source_equal_beta":
        return np.column_stack([np.log(values), -np.log1p(-values)])
    raise ValueError("unknown_segmented_calibration")


def fit_calibrator(frame, raw, kind, seed):
    require_partition(frame, "calibration")
    model = LogisticRegression(
        C=1000 if kind == "source_equal_sigmoid" else 10,
        max_iter=300,
        random_state=seed,
    )
    checked_fit(
        model,
        calibration_design(raw, kind),
        frame.label,
        sample_weight=calibration_weights(frame, "source_equal_sigmoid"),
    )
    if (model.coef_[0] <= 0).any():
        raise ValueError("calibration_not_strictly_monotone")
    return model


def calibrated(raw, model, kind):
    if (model.coef_[0] <= 0).any():
        raise ValueError("calibration_not_strictly_monotone")
    return model.predict_proba(calibration_design(raw, kind))[:, 1]


def predict_segmented(bundle, cores, batch_size=4096):
    output = []
    cores = list(cores)
    for start in range(0, len(cores), batch_size):
        prepared = [
            prepare_experiment_url(core).core
            for core in cores[start : start + batch_size]
        ]
        base = feature_matrix(bundle["encoder"], prepared)
        if bundle["feature_mode"] != "control":
            base = combine_matrix(
                base,
                extra_matrix(bundle["segment_encoder"], prepared),
                bundle["segment_encoder"],
                bundle["feature_mode"],
            )
        raw = bundle["classifier"].predict_proba(base)[:, 1]
        output.append(calibrated(raw, bundle["calibrator"], bundle["calibration_kind"]))
    return np.concatenate(output) if output else np.empty(0)


def choose_candidate(results, baseline, rules):
    """Takes development summaries only; final cohorts are never inputs."""
    details, eligible = {}, []
    for name, result in results.items():
        if name == "control_native" or result.get("invalid"):
            continue
        sources = [
            s for s, row in baseline["source_rates"].items() if row["phishing"] >= 20
        ]
        benign_sources = [
            s for s, row in baseline["source_rates"].items() if row["benign"] >= 100
        ]
        gain = result["macro_source_recall"] - baseline["macro_source_recall"]
        brier_gain = baseline["macro_source_brier"] - result["macro_source_brier"]
        worst_recall = min(
            result["source_rates"][s]["recall"] - baseline["source_rates"][s]["recall"]
            for s in sources
        )
        worst_brier = max(
            result["source_rates"][s]["brier_score"]
            - baseline["source_rates"][s]["brier_score"]
            for s in sources
        )
        worst_fpr = max(
            result["source_rates"][s]["fpr"] - baseline["source_rates"][s]["fpr"]
            for s in benign_sources
        )
        detection = (
            gain >= rules["minimum_recall_gain"]
            and worst_recall >= -rules["maximum_source_recall_loss"]
            and brier_gain >= -rules["maximum_macro_brier_increase"]
            and worst_brier <= rules["maximum_source_brier_increase"]
            and worst_fpr <= rules["maximum_source_fpr_increase"]
        )
        calibration = (
            gain >= -rules["calibration_maximum_recall_loss"]
            and worst_recall >= -rules["calibration_maximum_recall_loss"]
            and brier_gain >= rules["minimum_macro_brier_reduction"]
            and worst_brier <= rules["maximum_source_brier_increase"]
            and worst_fpr <= rules["calibration_maximum_fpr_increase"]
        )
        details[name] = {
            "recall_delta": gain,
            "macro_brier_reduction": brier_gain,
            "worst_source_recall_delta": worst_recall,
            "worst_source_brier_increase": worst_brier,
            "worst_source_fpr_increase": worst_fpr,
            "detection_gate": detection,
            "calibration_gate": calibration,
        }
        if detection or calibration:
            eligible.append(name)

    def rank(name):
        return (
            results[name]["macro_source_recall"],
            -results[name]["macro_source_brier"],
            results[name]["minimum_source_recall"],
        )

    detection = [n for n in eligible if details[n]["detection_gate"]]
    pool = detection or eligible
    selected = max(pool, key=rank) if pool else "control_native"
    challengers = list(details)
    diagnostic = (
        selected
        if selected != "control_native"
        else (max(challengers, key=rank) if challengers else None)
    )
    return {
        "selected": selected,
        "diagnostic": diagnostic,
        "details": details,
        "development_gate_passed": bool(pool),
        "selection_data": "tune_only",
        "production_ready": False,
    }
