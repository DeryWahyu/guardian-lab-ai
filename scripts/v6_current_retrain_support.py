"""Exact v6 constructor cloning and fit-only recipe, with versioned input privacy."""

import numpy as np
import pandas as pd
from sklearn.base import clone

from guardian_ml.rich_features import numeric_values
from v6_development_support import require_partition
from v6_learning_support import choose


def fit_original_encoder(original, fit, protocol):
    require_partition(fit, "fit")
    spec = protocol["recipe"]
    text = fit.core.str.replace(r"^https?://", "", regex=True).reset_index(drop=True)
    sources = fit.training_source.reset_index(drop=True)
    pieces = [
        text.loc[sources.eq(source)].sample(
            min(spec["vocabulary_source_cap"], int(sources.eq(source).sum())),
            random_state=protocol["seed"],
        )
        for source in sorted(sources.unique())
    ]
    sample = pd.concat(pieces)
    if len(sample) > spec["vocabulary_fit_limit"]:
        sample = sample.sample(
            spec["vocabulary_fit_limit"], random_state=protocol["seed"]
        )
    encoder = {
        name: clone(original["encoder"][name]) for name in ("char", "word", "scaler")
    }
    encoder["char"].fit(sample)
    encoder["word"].fit(sample)
    encoder["scaler"].fit(numeric_values(fit.core))
    return encoder, len(sample)


def assert_original_recipe(bundle, original):
    for name in ("classifier", "calibrator"):
        if bundle[name].get_params() != original[name].get_params():
            raise ValueError("retrain_estimator_recipe_changed")
    for name in ("char", "word", "scaler"):
        if (
            bundle["encoder"][name].get_params()
            != original["encoder"][name].get_params()
        ):
            raise ValueError("retrain_encoder_recipe_changed")
    if bundle["classifier"].warm_start:
        raise ValueError("retrain_must_not_warm_start")


def improvement_gate(foundation, current):
    # The predeclared gate matches the earlier explicit source/structure guards.
    result = choose({"control": foundation, "current": current}, ["current"])[
        "details"
    ]["current"]
    return {**result, "passed": result["detection_gate"], "selection_performed": False}


def check_scores(scores, rows):
    scores = np.asarray(scores)
    if (
        scores.ndim != 1
        or len(scores) != rows
        or not np.isfinite(scores).all()
        or np.any((scores < 0) | (scores > 1))
    ):
        raise ValueError("retrain_invalid_predictions")
    return scores
