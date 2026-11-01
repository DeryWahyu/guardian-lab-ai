"""Fit candidates, select on tune data, calibrate, and freeze before final test."""

from __future__ import annotations

import gc
import json
import time

import joblib
import pandas as pd
from threadpoolctl import threadpool_limits

from .evaluation import calibrate, apply_calibration, metrics, operating_point
from .features import feature_frame, VERSION, SCHEMA, BRANDS
from .fitting import fit_linear, fit_tree
from .metadata import checksum, dump_json, environment, source_hashes, now
from .models import Candidate
from .paths import DATA, REPORTS, ARTIFACTS, SEED, REVISION, REPRESENTATION, ensure_directories


def prepare_features(frame, data_checksum):
    cache = DATA / "features.parquet"
    marker = DATA / "features-manifest.json"
    if cache.exists() and marker.exists():
        manifest = json.loads(marker.read_text())
        if manifest.get("data_sha256") == data_checksum and manifest.get("version") == VERSION:
            assert checksum(cache) == manifest["feature_sha256"]
            return pd.read_parquet(cache)
    chunks = []
    for start in range(0, len(frame), 50000):
        chunks.append(feature_frame(frame.core.iloc[start : start + 50000]))
        print(f"Features: {min(start + 50000, len(frame))}/{len(frame)}", flush=True)
    features = pd.concat(chunks, ignore_index=True)
    assert len(features) == len(frame) and list(features.columns) == SCHEMA
    features.to_parquet(cache, index=False, compression="zstd")
    dump_json(
        marker,
        {
            "data_sha256": data_checksum,
            "version": VERSION,
            "feature_sha256": checksum(cache),
            "schema": SCHEMA,
        },
    )
    return features


def main():
    ensure_directories()
    if (REPORTS / "frozen-selection.json").exists():
        raise RuntimeError("Selection already frozen; do not overwrite after test exposure")
    audit = json.loads((REPORTS / "data-audit.json").read_text())
    assert all(audit["independent_checks"].values())
    assert checksum(DATA / "curated.parquet") == audit["curated_sha256"]
    dump_json(
        REPORTS / "run-protocol.json",
        {
            "declared_at_utc": now(),
            "source_revision": REVISION,
            "data_sha256": audit["curated_sha256"],
            "seed": SEED,
            "threads": 4,
            "model_families": ["research_heuristic", "tfidf_logistic_sgd", "catboost", "xgboost"],
            "search": {
                "linear_alpha": [1e-5, 1e-6],
                "linear_max_epochs": 12,
                "tree_depth": [6, 8],
                "tree_max_iterations": 800,
                "tree_early_stopping_rounds": 60,
            },
            "selection": "tune recall at empirical FPR <= 0.001, then tune average precision",
            "calibration": "sigmoid versus isotonic, group holdout within calibration partition",
            "threshold_source": "threshold partition only",
            "high_risk_target_fpr": 0.001,
            "medium_risk_target_fpr": 0.01,
            "primary_final_test": "temporal novel-domain test",
            "final_test_not_for_tuning": True,
            "source_hashes": source_hashes(),
        },
    )
    frame = pd.read_parquet(DATA / "curated.parquet")
    features = prepare_features(frame, audit["curated_sha256"])
    fit_mask, tune_mask = frame.partition == "fit", frame.partition == "tune"
    tuning = frame[tune_mask].reset_index(drop=True)
    tune_features = features[tune_mask].reset_index(drop=True)
    y_tune = tuning.label.to_numpy()
    results = []
    experiments = ["heuristic", "linear", "catboost_d6", "catboost_d8", "xgboost_d6", "xgboost_d8"]
    for experiment in experiments:
        start = time.perf_counter()
        print(f"Training candidate: {experiment}", flush=True)
        if experiment == "heuristic":
            candidate, parameters = Candidate("heuristic", "heuristic"), {"fitted": False}
        elif experiment == "linear":
            candidate, parameters = fit_linear(frame, features, fit_mask, tune_mask)
        else:
            kind, depth = experiment.split("_d")
            candidate, parameters = fit_tree(kind, frame, features, fit_mask, tune_mask, int(depth))
        probability = candidate.predict(tuning.core, tune_features)
        operating = {
            str(budget): operating_point(y_tune, probability, budget)
            for budget in (0.01, 0.001, 0.0001)
        }
        score = metrics(y_tune, probability, operating["0.001"]["threshold"])
        elapsed = time.perf_counter() - start
        artifact = ARTIFACTS / f"candidate-{candidate.name}.joblib"
        joblib.dump(candidate, artifact, compress=3)
        results.append(
            {
                "name": candidate.name,
                "parameters": parameters,
                "tune": score,
                "operating_points": operating,
                "fit_and_tune_seconds": elapsed,
                "artifact_bytes": artifact.stat().st_size,
                "artifact_sha256": checksum(artifact),
            }
        )
        dump_json(
            REPORTS / "validation-results.json",
            {
                "candidates": results,
                "selection_rule": "max tune recall at empirical FPR <= 0.1%, then average precision",
                "test_used_for_selection": False,
                "data_sha256": audit["curated_sha256"],
            },
        )
        print(
            f"{candidate.name}: tune recall={score['recall']:.4f}, FPR={score['fpr']:.5f}, AP={score['average_precision']:.4f}",
            flush=True,
        )
        del candidate
        gc.collect()
    chosen = max(results, key=lambda row: (row["tune"]["recall"], row["tune"]["average_precision"]))
    candidate = joblib.load(ARTIFACTS / f"candidate-{chosen['name']}.joblib")
    calibration_mask = frame.partition == "calibration"
    part = frame[calibration_mask].reset_index(drop=True)
    raw = candidate.predict(part.core, features[calibration_mask].reset_index(drop=True))
    calibrator, calibration_report = calibrate(part.label.to_numpy(), raw, part.group.to_numpy())
    threshold_mask = frame.partition == "threshold"
    part = frame[threshold_mask].reset_index(drop=True)
    raw = candidate.predict(part.core, features[threshold_mask].reset_index(drop=True))
    calibrated = apply_calibration(calibrator, raw)
    points = {
        str(budget): operating_point(part.label.to_numpy(), calibrated, budget)
        for budget in (0.01, 0.001, 0.0001)
    }
    thresholds = {"low": points["0.01"]["threshold"], "high": points["0.001"]["threshold"]}
    assert thresholds["low"] <= thresholds["high"]
    metadata = {
        "model_version": "url-core-v1",
        "model_name": candidate.name,
        "created_at_utc": now(),
        "representation_version": REPRESENTATION,
        "feature_schema_version": VERSION,
        "feature_schema": SCHEMA,
        "brands": list(BRANDS),
        "label_mapping": {"benign": 0, "phishing": 1},
        "source_revision": REVISION,
        "data_sha256": audit["curated_sha256"],
        "seed": SEED,
        "threads": 4,
        "environment": environment(),
        "source_hashes": source_hashes(),
        "thresholds": thresholds,
        "probability_reference": "curated PhreshPhish; not calibrated to live Guardian Lab prevalence",
        "deployment_status": "research_candidate_not_production_approved",
    }
    bundle = {"candidate": candidate, "calibrator": calibrator, "metadata": metadata}
    bundle_path = ARTIFACTS / "url-core-v1.joblib"
    joblib.dump(bundle, bundle_path, compress=3)
    manifest = {
        **metadata,
        "bundle_filename": bundle_path.name,
        "bundle_sha256": checksum(bundle_path),
        "bundle_bytes": bundle_path.stat().st_size,
    }
    dump_json(ARTIFACTS / "manifest.json", manifest)
    selection = {
        "frozen_at_utc": now(),
        "selection": chosen,
        "manifest": manifest,
        "calibration": calibration_report,
        "threshold_operating_points": points,
        "threshold_metrics": metrics(part.label, calibrated, thresholds["high"]),
        "final_test_opened": False,
    }
    # This file is the gate: final evaluation is a separate command.
    dump_json(REPORTS / "frozen-selection.json", selection)
    print(f"Frozen winner: {candidate.name}. Final test has not been evaluated.", flush=True)


if __name__ == "__main__":
    with threadpool_limits(limits=4):
        main()
