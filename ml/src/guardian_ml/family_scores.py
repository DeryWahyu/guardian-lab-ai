"""Offline scoring of trusted v9 comparison artifacts, never the shadow runtime."""

import numpy as np
from scipy.special import logit

from .family_features import shared_matrix
from .rich_features import feature_matrix as rich_matrix
from .structural_features import feature_matrix as structural_matrix


def matrix_raw(bundle, matrix):
    if bundle["family"] == "shared_lr":
        matrix = bundle["scaler"].transform(matrix)
    if bundle["family"] == "shared_catboost":
        return bundle["classifier"].predict_proba(matrix, thread_count=4)[:, 1]
    return bundle["classifier"].predict_proba(matrix)[:, 1]


def raw_scores(bundle, cores, batch_size=2048):
    cores = list(cores)
    result = []
    for start in range(0, len(cores), batch_size):
        batch = cores[start : start + batch_size]
        if bundle["family"].startswith("shared_"):
            matrix = shared_matrix(bundle["shared_encoder"], batch)
        elif bundle["family"] == "full_v8":
            matrix = structural_matrix(bundle, batch)
        elif bundle["family"] == "full_v6":
            matrix = rich_matrix(bundle["encoder"], batch)
        else:
            raise ValueError("unsupported_comparison_family")
        result.append(matrix_raw(bundle, matrix))
    return np.concatenate(result) if result else np.empty(0)


def calibrated(bundle, raw):
    raw = np.clip(raw, 1e-7, 1 - 1e-7)
    return bundle["calibrator"].predict_proba(logit(raw).reshape(-1, 1))[:, 1]


def probabilities(bundle, cores):
    return calibrated(bundle, raw_scores(bundle, cores))
