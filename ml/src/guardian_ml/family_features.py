"""Fit-only shared text/structure representation for the v9 family comparison."""

import numpy as np
import pandas as pd
from sklearn.decomposition import TruncatedSVD

from .structural_features import structural_values, text_matrix

SEED = 20261101
SCHEMA = "url-core-shared-svd64-structure38-v9"


def fit_shared_encoder(text_encoder, cores, sources, *, partition, components=64):
    if partition != "fit":
        raise ValueError("shared_encoder_requires_fitting_partition")
    cores = pd.Series(cores).reset_index(drop=True)
    sources = pd.Series(sources).reset_index(drop=True)
    indices = pd.concat(
        [s.sample(min(12000, len(s)), random_state=SEED) for _, s in sources.groupby(sources)]
    ).index
    if len(indices) > 60000:
        indices = pd.Series(indices).sample(60000, random_state=SEED).to_numpy()
    svd = TruncatedSVD(n_components=components, n_iter=5, random_state=SEED)
    svd.fit(text_matrix(text_encoder, cores.iloc[indices]))
    return {
        "schema": SCHEMA,
        "text": text_encoder,
        "svd": svd,
        "fit_rows": len(cores),
        "svd_sample_rows": len(indices),
        "fit_partition": partition,
    }


def shared_matrix(encoder, cores, batch_size=2048):
    cores = list(cores)
    result = np.empty((len(cores), encoder["svd"].n_components + 38), dtype=np.float32)
    for start in range(0, len(cores), batch_size):
        batch = cores[start : start + batch_size]
        numeric, flags, _ = structural_values(batch)
        text = encoder["svd"].transform(text_matrix(encoder["text"], batch))
        result[start : start + len(batch)] = np.hstack([text, numeric, flags])
    if not np.isfinite(result).all():
        raise ValueError("nonfinite_shared_features")
    return result


def source_weights(sources):
    sources = pd.Series(sources).reset_index(drop=True)
    values = (1 / sources.map(sources.value_counts())).to_numpy(dtype=np.float64)
    return values / values.mean()
