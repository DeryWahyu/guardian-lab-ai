"""Fit-only numeric structure for the v7 notebook; frozen v6 stays untouched."""

import numpy as np
import pandas as pd
from scipy.sparse import csr_matrix, hstack
from scipy.special import logit
from sklearn.preprocessing import SplineTransformer, StandardScaler

from .features import feature_row
from .preprocessing import EXTRACT, prepare_url
from .rich_features import NUMERIC_COLUMNS

SCHEMA_VERSION = "url-core-structural-v7-1"
FLAG_NAMES = ("private_hosting", "homepage", "punycode", "long_url", "redacted")
INTERACTION_COLUMNS = (
    "url_length",
    "path_length",
    "path_depth",
    "host_entropy",
    "path_entropy",
    "keyword_count",
    "brand_in_subdomain",
    "brand_in_path",
)
SPECIFICATION = {
    "schema": SCHEMA_VERSION,
    "numeric_columns": list(NUMERIC_COLUMNS),
    "flags": list(FLAG_NAMES),
    "interaction_columns": list(INTERACTION_COLUMNS),
    "numeric_transform": "log1p_then_fit_standard_scaler_clip_minus5_plus5",
    "interaction_transform": "each_flag_times_log1p_selected_numeric_then_fit_scaler",
    "spline": {"degree": 2, "n_knots": 4, "knots": "quantile", "include_bias": False},
    "spline_column_policy": "fit_quantile_knots_must_be_strictly_increasing",
    "text_weights": {"char": 1.0, "word": 0.7},
    "structural_weight": 0.15,
    "flag_weight_inside_structural_block": 2.0,
    "row_l2_normalization": False,
    "scheme_feature": False,
    "target_network_requests": False,
}


def structural_values(cores):
    numeric, flags = [], []
    for core in cores:
        item = prepare_url(core)
        if item.core != core:
            raise ValueError("canonical_core_required")
        row = feature_row(item)
        length = len(core.split("://", 1)[1])
        row["url_length"] = length
        numeric.append([row[name] for name in NUMERIC_COLUMNS])
        flags.append(
            [
                EXTRACT(item.host).is_private,
                item.path == "/",
                "xn--" in item.host,
                length > 120,
                "REDACTED" in item.path,
            ]
        )
    values = np.log1p(np.asarray(numeric, dtype=np.float32))
    indicators = np.asarray(flags, dtype=np.float32)
    selected = values[:, [NUMERIC_COLUMNS.index(name) for name in INTERACTION_COLUMNS]]
    interactions = (indicators[:, :, None] * selected[:, None, :]).reshape(len(values), -1)
    return values, indicators, interactions


class StructuralEncoder:
    def __init__(self, kind="linear"):
        if kind not in {"linear", "spline"}:
            raise ValueError("unsupported_structural_kind")
        self.kind = kind

    def fit(self, blocks, *, partition):
        if partition != "fit":
            raise ValueError("transform_fit_requires_fitting_partition")
        numeric, _, interactions = blocks
        self.numeric_scaler = StandardScaler().fit(numeric)
        self.interaction_scaler = StandardScaler().fit(interactions)
        self.fit_rows = len(numeric)
        self.spline_columns = np.array([], dtype=int)
        self.spline = None
        if self.kind == "spline":
            quantiles = np.quantile(numeric, np.linspace(0, 1, 4), axis=0)
            self.spline_columns = np.flatnonzero((np.diff(quantiles, axis=0) > 0).all(axis=0))
            if len(self.spline_columns):
                self.spline = SplineTransformer(
                    n_knots=4,
                    degree=2,
                    knots="quantile",
                    include_bias=False,
                    extrapolation="constant",
                ).fit(numeric[:, self.spline_columns])
        return self

    def transform(self, blocks):
        numeric, flags, interactions = blocks
        parts = [
            np.clip(self.numeric_scaler.transform(numeric), -5, 5),
            2 * flags,
            np.clip(self.interaction_scaler.transform(interactions), -5, 5),
        ]
        if self.spline is not None:
            parts.append(self.spline.transform(numeric[:, self.spline_columns]))
        values = np.hstack(parts).astype(np.float32)
        if not np.isfinite(values).all():
            raise ValueError("nonfinite_structural_features")
        return csr_matrix(0.15 * values)


def text_matrix(encoder, cores):
    text = pd.Series(cores).reset_index(drop=True).str.replace(r"^https?://", "", regex=True)
    return hstack(
        [encoder["char"].transform(text), 0.7 * encoder["word"].transform(text)],
        format="csr",
        dtype=np.float32,
    )


def feature_matrix(bundle, cores):
    from .rich_features import feature_matrix as original_matrix

    if bundle["kind"] == "repeat_v6":
        return original_matrix(bundle["encoder"], cores)
    return hstack(
        [
            text_matrix(bundle["encoder"], cores),
            bundle["structure"].transform(structural_values(cores)),
        ],
        format="csr",
        dtype=np.float32,
    )


def raw_probabilities(bundle, cores, batch_size=4096):
    values = list(cores)
    parts = [
        bundle["classifier"].predict_proba(feature_matrix(bundle, values[i : i + batch_size]))[:, 1]
        for i in range(0, len(values), batch_size)
    ]
    return np.concatenate(parts) if parts else np.empty(0)


def probabilities(bundle, cores):
    raw = np.clip(raw_probabilities(bundle, cores), 1e-7, 1 - 1e-7)
    return bundle["calibrator"].predict_proba(logit(raw).reshape(-1, 1))[:, 1]
