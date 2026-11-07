"""Aggregate diagnostics and hash-only review preparation for frozen v6."""

import csv
import hashlib
from pathlib import Path

import numpy as np
import pandas as pd

from guardian_ml.evaluation import metrics, wilson
from v6_development_support import source_threshold


def safe_metrics(frame, scores, threshold, positive_only=False):
    labels = frame.label.to_numpy()
    scores = np.asarray(scores)
    if len(scores) != len(frame) or not np.isfinite(scores).all():
        raise ValueError("invalid_diagnostic_scores")
    if positive_only and not np.all(labels == 1):
        raise ValueError("positive_only_requires_phishing_labels")
    prediction = scores >= threshold
    tn = int(((labels == 0) & ~prediction).sum())
    fp = int(((labels == 0) & prediction).sum())
    fn = int(((labels == 1) & ~prediction).sum())
    tp = int(((labels == 1) & prediction).sum())
    result = {
        "rows": len(frame),
        "groups": int(frame.group.nunique()),
        "benign": tn + fp,
        "phishing": tp + fn,
        "confusion_matrix": {"tn": tn, "fp": fp, "fn": fn, "tp": tp},
        "threshold": float(threshold),
        "accuracy": None,
        "precision": None,
        "recall": tp / (tp + fn) if tp + fn else None,
        "fpr": None,
        "balanced_accuracy": None,
        "brier_score": None,
        "log_loss": None,
        "recall_wilson95_rows_iid_assumption": wilson(tp, tp + fn),
        "fpr_wilson95_rows_iid_assumption": [None, None],
    }
    if len(frame) and not positive_only:
        computed = metrics(labels, scores, threshold)
        result.update(computed)
        result["recall"] = tp / (tp + fn) if tp + fn else None
        result["fpr"] = fp / (fp + tn) if fp + tn else None
        result["precision"] = tp / (tp + fp) if tp + fp else None
        if result["recall"] is not None and result["fpr"] is not None:
            result["balanced_accuracy"] = (result["recall"] + 1 - result["fpr"]) / 2
        result["ece_10_fixed_bins"] = sum(
            item["rows"] * abs(item["mean_probability"] - item["phishing_fraction"])
            for item in computed["reliability_bins"]
        ) / len(frame)
    return result


def threshold_diagnostics(
    threshold_frame, threshold_scores, tune, tune_scores, budgets
):
    if set(threshold_frame.partition) != {"threshold"} or set(tune.partition) != {
        "tune"
    }:
        raise ValueError("diagnostic_threshold_partition_violation")
    for key in ("group", "digest"):
        if set(threshold_frame[key]).intersection(tune[key]):
            raise ValueError("diagnostic_threshold_overlap")
    result = []
    for budget in budgets:
        policy = source_threshold(
            threshold_frame, threshold_scores, budget, "threshold"
        )
        result.append(
            {
                "budget": budget,
                "threshold": policy["threshold"],
                "threshold_partition_source_rates": policy["source_rates"],
                "tune": safe_metrics(tune, tune_scores, policy["threshold"]),
                "tune_source_rates": {
                    source: safe_metrics(
                        tune.loc[tune.training_source.eq(source)],
                        tune_scores[tune.training_source.eq(source).to_numpy()],
                        policy["threshold"],
                    )
                    for source in sorted(tune.training_source.unique())
                },
                "selected_for_serving": False,
            }
        )
    return result


def label_conflict_audit(development):
    """Cache-derived ambiguities, never a decision about the true label."""
    frame = development.copy()
    frame["representation_digest"] = [
        hashlib.sha256(core.split("://", 1)[1].encode()).hexdigest()
        for core in frame.core
    ]
    counts = frame.groupby("representation_digest").label.nunique()
    keys = set(counts[counts > 1].index)
    conflicting = frame.loc[frame.representation_digest.isin(keys)]
    coordinator, blind, stats = [], [], []
    for index, (_, subset) in enumerate(
        conflicting.groupby("representation_digest", sort=True)
    ):
        case_id = f"v6-conflict-{index + 1:03d}"
        known_dates = pd.to_datetime(subset.date, errors="coerce", utc=True).dropna()
        entry = {
            "partition": str(subset.partition.iloc[0]),
            "rows": len(subset),
            "multiple_sources": subset.training_source.nunique() > 1,
            "within_source_label_conflict": bool(
                (subset.groupby("training_source").label.nunique() > 1).any()
            ),
            "exact_cached_core_conflict": bool(
                (subset.groupby("core").label.nunique() > 1).any()
            ),
            "redaction_placeholder_present": bool(
                subset.core.str.contains("REDACTED", regex=False).any()
            ),
            "multiple_known_dates": known_dates.nunique() > 1,
        }
        stats.append(entry)
        for _, row in subset.iterrows():
            locator = {
                "case_id": case_id,
                "cache_digest": row.digest,
                "cache_filename": "development-v6.parquet",
            }
            blind.append(locator)
            coordinator.append(
                {
                    **locator,
                    "partition": row.partition,
                    "source": row.training_source,
                    "publisher_label": int(row.label),
                    "source_split": str(row.source_split),
                }
            )
    summary = {
        "development_rows": len(frame),
        "conflicting_representations": len(keys),
        "conflicting_rows": len(conflicting),
        "partition_representations": pd.Series([item["partition"] for item in stats])
        .value_counts()
        .to_dict(),
        "cross_source_representations": sum(item["multiple_sources"] for item in stats),
        "within_source_representations": sum(
            item["within_source_label_conflict"] for item in stats
        ),
        "exact_cached_core_conflicts": sum(
            item["exact_cached_core_conflict"] for item in stats
        ),
        "with_redaction_placeholder": sum(
            item["redaction_placeholder_present"] for item in stats
        ),
        "with_multiple_known_dates": sum(
            item["multiple_known_dates"] for item in stats
        ),
        "true_labels_verified": 0,
        "labels_changed": 0,
        "possible_explanations_not_proven": [
            "publisher disagreement",
            "time-dependent status",
            "omitted query or scheme",
            "sanitizer collisions",
        ],
        "original_query_context_available": False,
    }
    return summary, pd.DataFrame(coordinator), pd.DataFrame(blind)


def export_review_queues(directory, coordinator, blind):
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=False)
    # Target URLs, model outputs and publisher labels are absent from blind packs.
    if set(blind.columns) != {"case_id", "cache_digest", "cache_filename"}:
        raise ValueError("unexpected_blind_review_fields")
    coordinator.to_csv(
        directory / "conflict-coordinator.csv", index=False, lineterminator="\n"
    )
    for suffix in ("a", "b"):
        pack = blind.copy()
        for name in (
            "reviewer_id",
            "label",
            "confidence",
            "reason_code",
            "evidence_ref",
            "human_review_confirmed",
            "reviewed_at",
        ):
            pack[name] = ""
        pack.to_csv(
            directory / f"conflict-reviewer-{suffix}.csv",
            index=False,
            lineterminator="\n",
        )


def indonesia_inventory(root):
    root = Path(root)
    names = {
        "candidates": "indonesia-candidates.csv",
        "reviewer_a": "indonesia-reviewer-a.csv",
        "reviewer_b": "indonesia-reviewer-b.csv",
        "adjudication": "indonesia-adjudication.csv",
    }
    counts = {}
    for role, filename in names.items():
        path = root / "input" / filename
        if path.exists():
            with path.open(encoding="utf-8-sig", newline="") as handle:
                counts[role] = sum(
                    1 for row in csv.DictReader(handle) if any(row.values())
                )
        else:
            counts[role] = 0
    # Presence of rows is never evidence of valid independent reviews or gold status.
    return {
        "actual_input_rows": counts,
        "verified_gold_rows": None,
        "independent_reviewer_identity_verified": False,
        "independent_final_holdout_available": False,
        "classifier_evaluation_on_indonesia": "not_run_missing_verified_locked_gold",
        "status": "needs_candidate_and_human_review_evidence",
        "required_next_evidence": [
            "fresh two-class candidates with provenance and Indonesia relevance",
            "two independent human reviews and adjudication",
            "privacy rights and evidence QA",
            "domain time campaign exposure audit and locked holdout",
        ],
    }
