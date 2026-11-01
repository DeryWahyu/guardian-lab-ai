"""Predeclared source guard and worst-source-first development selection."""

import numpy as np
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.preprocessing import StandardScaler

from .structural_evaluation import selection_diagnostics


def fit_text_encoder(cores, sources, numeric, *, partition):
    if partition != "fit":
        raise ValueError("vocabulary_fit_requires_fitting_partition")
    text = pd.Series(cores).reset_index(drop=True).str.replace(r"^https?://", "", regex=True)
    sources = pd.Series(sources).reset_index(drop=True)
    samples = [
        text[sources.eq(s)].sample(min(60000, int(sources.eq(s).sum())), random_state=20261101)
        for s in sorted(sources.unique())
    ]
    sample = pd.concat(samples)
    if len(sample) > 150000:
        sample = sample.sample(150000, random_state=20261101)
    return {
        "view": "char_word_numeric_v8",
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
        "scaler": StandardScaler(with_mean=False).fit(numeric),
        "vocabulary_fit_rows": len(cores),
        "vocabulary_sample_rows": len(sample),
    }


def guarded_diagnostics(frame, raw, reference, margin=0.01):
    diagnostic = selection_diagnostics(frame, raw)
    deltas = {
        source: rates["recall"] - reference["point"]["source_rates"][source]["recall"]
        for source, rates in diagnostic["point"]["source_rates"].items()
    }
    diagnostic.update(
        {
            "guard_margin": margin,
            "source_recall_deltas_from_v6": deltas,
            "source_guard_passed": all(value >= -margin for value in deltas.values()),
            "worst_first_score": [
                diagnostic["min_source_recall"],
                diagnostic["macro_source_recall"],
                diagnostic["average_precision"],
            ],
            "guard_scope": "empirical_development_screen_not_statistical_noninferiority",
        }
    )
    return diagnostic


def choose_candidate(results):
    eligible = [r for r in results if r["source_guard_passed"]]
    challenger = max(eligible or results, key=lambda r: tuple(r["worst_first_score"]))
    return challenger, {
        "eligible_candidates": [r["name"] for r in eligible],
        "development_selection": challenger["name"] if eligible else "retain_frozen_v6",
        "diagnostic_challenger": challenger["name"],
        "challenger_passed_source_guard": bool(eligible),
        "production_promotion": False,
    }
