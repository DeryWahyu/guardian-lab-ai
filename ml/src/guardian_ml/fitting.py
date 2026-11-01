"""Bounded CPU experiment budget, early stopping uses tune partition only."""

import copy
import numpy as np
from catboost import CatBoostClassifier
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import SGDClassifier
from sklearn.metrics import average_precision_score
from sklearn.preprocessing import OneHotEncoder
from xgboost import XGBClassifier

from .features import CATEGORICAL
from .models import Candidate
from .paths import SEED
from .evaluation import operating_point


def fit_linear(frame, features, fit_mask, tune_mask):
    fit = frame.loc[fit_mask, "core"].reset_index(drop=True)
    tune = frame.loc[tune_mask, "core"].reset_index(drop=True)
    y = frame.loc[fit_mask, "label"].to_numpy()
    yt = frame.loc[tune_mask, "label"].to_numpy()
    vectorizer = TfidfVectorizer(
        analyzer="char",
        ngram_range=(3, 5),
        max_features=40000,
        min_df=4,
        sublinear_tf=True,
        dtype=np.float32,
    )
    vocabulary_sample = fit.sample(min(100000, len(fit)), random_state=SEED)
    vectorizer.fit(vocabulary_sample)
    matrix = vectorizer.transform(fit)
    validation = vectorizer.transform(tune)
    winner, best = None, (-1, -1)
    trials = []
    rng = np.random.default_rng(SEED)
    for alpha in (1e-5, 1e-6):
        model = SGDClassifier(loss="log_loss", alpha=alpha, average=True, random_state=SEED)
        local_best, stale = -1, 0
        for epoch in range(12):
            ordering = rng.permutation(len(y))
            for start in range(0, len(y), 16384):
                rows = ordering[start : start + 16384]
                model.partial_fit(matrix[rows], y[rows], classes=np.array([0, 1]))
            probabilities = model.predict_proba(validation)[:, 1]
            score = average_precision_score(yt, probabilities)
            comparison = (operating_point(yt, probabilities)["recall"], float(score))
            if comparison > best:
                best = comparison
                winner = copy.deepcopy(model)
            if score > local_best + 0.0001:
                local_best, stale = score, 0
            else:
                stale += 1
            if stale >= 3:
                break
        trials.append(
            {"alpha": alpha, "epochs": epoch + 1, "best_tune_average_precision": float(local_best)}
        )
        print(
            f"Linear baseline: alpha={alpha}, epochs={epoch + 1}, tune AP={local_best:.4f}",
            flush=True,
        )
    return Candidate("tfidf_logistic_sgd", "linear", winner, vectorizer), {
        "optimizer": "SGD logistic regression",
        "trials": trials,
        "max_epochs_per_trial": 12,
        "vocabulary_fit_rows": len(vocabulary_sample),
        "vocabulary_features": len(vectorizer.vocabulary_),
        "vocabulary_source": "deterministic fit-only sample for memory budget",
    }


def fit_tree(kind, frame, features, fit_mask, tune_mask, depth=6):
    train = features.loc[fit_mask].reset_index(drop=True)
    tune = features.loc[tune_mask].reset_index(drop=True)
    y = frame.loc[fit_mask, "label"].to_numpy()
    yt = frame.loc[tune_mask, "label"].to_numpy()
    if kind == "catboost":
        model = CatBoostClassifier(
            iterations=800,
            depth=depth,
            learning_rate=0.06,
            l2_leaf_reg=5,
            loss_function="Logloss",
            eval_metric="Logloss",
            random_seed=SEED,
            thread_count=4,
            allow_writing_files=False,
            verbose=200,
        )
        model.fit(
            train, y, cat_features=list(CATEGORICAL), eval_set=(tune, yt), early_stopping_rounds=60
        )
        return Candidate(f"catboost_d{depth}", "catboost", model), {
            "parameters": model.get_params(),
            "best_iteration": model.get_best_iteration(),
            "tuning_budget": "one predeclared configuration, up to 800 iterations",
        }
    encoder = OneHotEncoder(
        handle_unknown="ignore",
        min_frequency=10,
        max_categories=100,
        sparse_output=True,
        dtype=np.float32,
    ).fit(train[list(CATEGORICAL)])
    model = XGBClassifier(
        n_estimators=800,
        max_depth=depth,
        learning_rate=0.06,
        min_child_weight=10,
        reg_lambda=5,
        subsample=0.9,
        colsample_bytree=0.9,
        objective="binary:logistic",
        eval_metric="logloss",
        tree_method="hist",
        max_bin=128,
        n_jobs=4,
        random_state=SEED,
        early_stopping_rounds=60,
    )
    candidate = Candidate(f"xgboost_d{depth}", "xgboost", model, encoder)
    model.fit(
        candidate.xgb_matrix(train), y, eval_set=[(candidate.xgb_matrix(tune), yt)], verbose=200
    )
    return candidate, {
        "parameters": model.get_params(),
        "best_iteration": int(model.best_iteration),
        "tuning_budget": "one predeclared configuration, up to 800 iterations",
    }
