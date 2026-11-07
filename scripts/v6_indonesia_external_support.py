"""Offline diagnostic helpers; suffixes and publisher labels never establish human gold."""

import csv
from collections import Counter
from urllib.parse import urlsplit

import numpy as np

from guardian_ml.evaluation import wilson
from guardian_ml.metadata import checksum
from guardian_ml.preprocessing import EXTRACT
from audit_v6_human_review import completed_review
from evaluate_v6_quality import domain_intervals
from v6_diagnostic_support import safe_metrics


def structure_masks(frame):
    hosts = frame.core.map(lambda core: urlsplit(core).hostname or "")
    paths = frame.core.map(lambda core: urlsplit(core).path)
    private = hosts.map(lambda host: bool(EXTRACT(host).is_private))
    return {
        "id_suffix_proxy": hosts.str.lower().str.endswith(".id"),
        "long_url_over_120": frame.core.str.replace(r"^https?://", "", regex=True)
        .str.len()
        .gt(120),
        "deep_path_at_least_4": paths.str.count("/").ge(4),
        "private_hosting": private,
        "non_private_hosting": ~private,
    }


def coverage(frame):
    return {
        "rows": len(frame),
        "groups": int(frame.group.nunique()),
        "benign": int(frame.label.eq(0).sum()),
        "phishing": int(frame.label.eq(1).sum()),
        "structures": {
            name: {
                "benign": int((mask & frame.label.eq(0)).sum()),
                "phishing": int((mask & frame.label.eq(1)).sum()),
            }
            for name, mask in structure_masks(frame).items()
        },
    }


def diagnostic_metrics(frame, scores, threshold, repeats=1000, seed=20261106):
    scores = np.asarray(scores, dtype=float)
    if (
        scores.ndim != 1
        or len(scores) != len(frame)
        or not np.isfinite(scores).all()
        or np.any((scores < 0) | (scores > 1))
        or not np.isfinite(threshold)
        or not frame.label.isin([0, 1]).all()
    ):
        raise ValueError("invalid_external_diagnostic_input")
    # Do not invent accuracy/precision/calibration for empty or single-class cohorts.
    if len(frame) and frame.label.eq(0).all():
        fp = int((scores >= threshold).sum())
        return {
            "rows": len(frame),
            "groups": int(frame.group.nunique()),
            "benign": len(frame),
            "phishing": 0,
            "confusion_matrix": {"tn": len(frame) - fp, "fp": fp, "fn": 0, "tp": 0},
            "fpr": fp / len(frame),
            "fpr_wilson95_rows_iid_assumption": wilson(fp, len(frame)),
            "recall": None,
            "precision": None,
            "accuracy": None,
            "brier_score": None,
            "log_loss": None,
            "balanced_accuracy": None,
            "recall_wilson95_rows_iid_assumption": [None, None],
            "threshold": threshold,
            "domain_bootstrap95": None,
        }
    result = safe_metrics(
        frame,
        scores,
        threshold,
        positive_only=bool(len(frame)) and frame.label.eq(1).all(),
    )
    result["domain_bootstrap95"] = (
        domain_intervals(
            frame, scores, threshold, repeats, seed, frame.label.eq(1).all()
        )
        if len(frame)
        else None
    )
    return result


def audit_human_inputs(directory):
    """Audit actual CSV contents. Syntax checks cannot attest real human independence."""
    files, tables = {}, {}
    for name in (
        "candidates",
        "reviewer-a",
        "reviewer-b",
        "adjudication",
        "error-review",
    ):
        path = directory / (name + ".csv")
        if not path.exists():
            files[name] = {"exists": False, "rows": 0}
            tables[name] = []
            continue
        with path.open(encoding="utf-8-sig", newline="") as stream:
            rows = list(csv.DictReader(stream))
        files[name] = {"exists": True, "rows": len(rows), "sha256": checksum(path)}
        tables[name] = rows
    problems = Counter()
    candidates = tables["candidates"]
    candidate_ids = [row.get("sample_id", "") for row in candidates]
    if len(set(candidate_ids)) != len(candidate_ids) or any(
        not x for x in candidate_ids
    ):
        problems["invalid_or_duplicate_candidate_ids"] += 1
    reviews = []
    for name in ("reviewer-a", "reviewer-b"):
        by_id = {}
        for row in tables[name]:
            identity = row.get("sample_id", "")
            if not identity or identity in by_id:
                problems["invalid_or_duplicate_review_ids"] += 1
            if identity not in candidate_ids:
                problems["orphan_reviews"] += 1
            by_id[identity] = row
        reviews.append(by_id)
    distinct_complete_pairs, agreements = 0, 0
    for identity in set(candidate_ids):
        a, b = reviews[0].get(identity, {}), reviews[1].get(identity, {})
        if not (completed_review(a) and completed_review(b)):
            problems["missing_complete_review_pair"] += 1
            continue
        if a["reviewer_id"].strip().casefold() == b["reviewer_id"].strip().casefold():
            problems["same_reviewer_pair"] += 1
            continue
        distinct_complete_pairs += 1
        if a["label"] == b["label"] and a["label"] in ("benign", "phishing"):
            agreements += 1
        else:
            problems["requires_adjudication_or_scope_exclusion"] += 1
    return {
        "files": files,
        "syntactically_complete_distinct_id_pairs": distinct_complete_pairs,
        "binary_agreements_before_evidence_and_independence_review": agreements,
        "issues": dict(problems),
        "independent_human_identity_established": False,
        "indonesia_gold_established": False,
        "indonesia_gold_metrics": None,
        "production_ready": False,
        "pending": [
            "eligible two-class Indonesia cases with per-case source, rights, observation time and relevance evidence",
            "real independent human identity and annotation evidence; two CSVs or IDs are insufficient",
            "privacy, adjudication, domain/time/campaign audits and immutable final holdout manifest",
            "evaluation of locked models on that holdout; sample counts alone do not pass release gates",
        ],
    }
