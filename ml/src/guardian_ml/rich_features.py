"""Offline feature parity with the frozen v3/v6 research notebooks."""

import numpy as np
import pandas as pd
from scipy.sparse import csr_matrix, hstack
from sklearn.preprocessing import normalize

from .features import NUMERIC, feature_row
from .preprocessing import prepare_url

SCHEMA_VERSION = "url-core-rich-offline-v6-1"
NUMERIC_COLUMNS = tuple(name for name in NUMERIC if name != "https")


def numeric_values(cores):
    records = []
    for core in cores:
        parsed = prepare_url(core)
        if parsed.core != core:
            raise ValueError("canonical_core_required")
        row = feature_row(parsed)
        row["url_length"] = len(core.split("://", 1)[1])
        records.append(row)
    frame = pd.DataFrame.from_records(records)
    return np.log1p(np.clip(frame[list(NUMERIC_COLUMNS)].to_numpy(dtype=np.float32), 0, None))


def feature_matrix(encoder, cores):
    cores = pd.Series(cores).reset_index(drop=True)
    text = cores.str.replace(r"^https?://", "", regex=True)
    values = np.clip(encoder["scaler"].transform(numeric_values(cores)), 0, 10)
    return hstack(
        [
            encoder["char"].transform(text),
            0.7 * encoder["word"].transform(text),
            0.2 * csr_matrix(normalize(values)),
        ],
        format="csr",
        dtype=np.float32,
    )


def probabilities(bundle, cores, batch_size=4096):
    from scipy.special import logit

    result = []
    for start in range(0, len(cores), batch_size):
        matrix = feature_matrix(bundle["encoder"], cores[start : start + batch_size])
        raw = np.clip(bundle["classifier"].predict_proba(matrix)[:, 1], 1e-7, 1 - 1e-7)
        result.append(bundle["calibrator"].predict_proba(logit(raw).reshape(-1, 1))[:, 1])
    return np.concatenate(result) if result else np.empty(0, dtype=float)
