"""Audit development errors and compare weights using one verified fit-only encoder."""

import argparse
import csv
import gc
import json

import joblib
import numpy as np
import pandas as pd
from scipy.sparse import load_npz, save_npz
from scipy.special import logit
from sklearn.linear_model import LogisticRegression
from threadpoolctl import threadpool_limits

from guardian_ml.metadata import checksum
from guardian_ml.paths import ROOT
from guardian_ml.rich_artifact import RichArtifact
from evaluate_v6_quality import domain_intervals
from experiment_v6_development import checked_fit, matrix_batches, paired_intervals
from experiment_v6_expanded_data import now, source_point, write_json
import experiment_v6_targeted as previous
from v6_development_support import predict_bundle, prepare_experiment_url
from v6_diagnostic_support import safe_metrics
from v6_weighted_support import (
    calibration_weights,
    choose_research_candidate,
    classifier_weights,
    development_review_queue,
    structural_audit,
    summarize_tune,
)

PROTOCOL = ROOT / "ml/reports/v6-weighted-20261105-protocol.json"
RUN = ROOT / "ml/runs/v6-weighted-20261105"
REPORT = ROOT / "ml/reports/v6-weighted-evaluation.json"
AUDIT = ROOT / "ml/reports/v6-weighted-development-audit.json"
PARTS = ("fit", "calibration", "threshold", "tune")
SOURCES = previous.SOURCES + [
    "scripts/experiment_v6_weighted.py",
    "scripts/v6_weighted_support.py",
]


def bindings():
    return {name: checksum(ROOT / name) for name in SOURCES}


def read_json(path):
    return json.loads(path.read_text())


def current_control(protocol):
    previous.check_freeze()
    selected = read_json(previous.RUN / "selected-frozen.json")
    path = ROOT / selected["artifact"]
    if (
        checksum(path) != protocol["control_artifact_sha256"]
        or checksum(path) != selected["artifact_sha256"]
    ):
        raise ValueError("weighted_control_artifact_changed")
    return selected, path


def calibrated(raw, calibrator):
    return calibrator.predict_proba(logit(np.clip(raw, 1e-7, 1 - 1e-7)).reshape(-1, 1))[
        :, 1
    ]


def inventory():
    result = {}
    for path in sorted((ROOT / "ml/data/indonesia-gold/input").glob("*.csv")):
        with path.open(encoding="utf-8-sig", newline="") as stream:
            count = sum(1 for _ in csv.DictReader(stream))
        result[path.name] = {"rows": count, "sha256": checksum(path)}
    return {
        "files": result,
        "verified_gold_established": False,
        "note": "row counts are not proof of valid independent review; no reviewer or label is generated",
    }


def matrix_points(frame, scores, protocol):
    return {
        "strict": source_point(frame, scores, 0.01, "threshold", protocol),
        "pooled": {
            "threshold": previous.pooled_threshold(frame, scores, 0.01),
            "development_budget": 0.01,
            "per_source_or_test_fpr_guaranteed": False,
        },
    }


def prepare(protocol):
    if (RUN / "cache-frozen.json").exists():
        raise ValueError("weighted_cache_already_frozen")
    selected, control_path = current_control(protocol)
    original_data = read_json(previous.RUN / "data-freeze.json")
    control = joblib.load(control_path)
    RUN.mkdir(parents=True, exist_ok=True)
    initial = {
        "started_at_utc": now(),
        "protocol_sha256": checksum(PROTOCOL),
        "source_hashes": bindings(),
        "previous_selection_sha256": checksum(previous.RUN / "selected-frozen.json"),
        "control_artifact": control_path.relative_to(ROOT).as_posix(),
        "control_sha256": checksum(control_path),
    }
    write_json(RUN / "cache-started.json", initial)
    assets = {}
    for name in PARTS:
        asset = original_data["partitions"][name]
        frame = pd.read_parquet(ROOT / asset["path"])
        if set(frame.partition) != {name} or (
            name == "fit" and len(frame) != protocol["fitting_rows"]
        ):
            raise ValueError("weighted_feature_partition_mismatch")
        if name in ("tune", "threshold"):
            frame["core"] = [prepare_experiment_url(core).core for core in frame.core]
        print("Caching fitting-only encoder features: " + name, flush=True)
        matrix = matrix_batches(control["encoder"], frame)
        path = RUN / (name + ".npz")
        save_npz(path, matrix, compressed=False)
        assets[name] = {
            "input_path": asset["path"],
            "input_sha256": asset["sha256"],
            "matrix_path": path.relative_to(ROOT).as_posix(),
            "matrix_sha256": checksum(path),
            "rows": len(frame),
            "features": int(matrix.shape[1]),
            "nonzero": int(matrix.nnz),
        }
        del matrix, frame
        gc.collect()
    tune = pd.read_parquet(ROOT / assets["tune"]["input_path"])
    matrix = load_npz(ROOT / assets["tune"]["matrix_path"])
    scores = calibrated(
        control["classifier"].predict_proba(matrix)[:, 1], control["calibrator"]
    )
    direct = predict_bundle(control, tune.core.iloc[:128])
    delta = float(np.max(np.abs(direct - scores[:128])))
    if delta > 1e-12:
        raise ValueError("cached_features_do_not_match_real_inference")
    warning = control["metadata"]["policies"]["strict_source_1pct"]["threshold"]
    summary = summarize_tune(tune, scores, warning, protocol)
    expected = selected["tune"][selected["selection"]["candidate"]][
        "strict_source_1pct"
    ]["overall"]["confusion_matrix"]
    if summary["overall"]["confusion_matrix"] != expected:
        raise ValueError("weighted_control_replay_changed_classification")
    conflicts = {}
    for name in PARTS:
        frame = pd.read_parquet(
            ROOT / assets[name]["input_path"],
            columns=["representation_digest", "label"],
        )
        counts = frame.groupby("representation_digest").label.nunique()
        bad = set(counts[counts > 1].index)
        conflicts[name] = {
            "representations": len(bad),
            "rows": int(frame.representation_digest.isin(bad).sum()),
        }
    reviews = development_review_queue(
        tune, scores, warning, ROOT / "ml/data/v6-weighted-review-20261105"
    )
    audit = {
        "completed_at_utc": now(),
        "tune_rows": len(tune),
        "control": summary,
        "structural": structural_audit(tune, scores, warning),
        "publisher_conflicts": conflicts,
        "review_queue": reviews,
        "Indonesia_inputs": inventory(),
        "automatic_relabeling": False,
        "human_label_truth_established": False,
        "production_ready": False,
    }
    write_json(AUDIT, audit)
    if initial["source_hashes"] != bindings() or initial["protocol_sha256"] != checksum(
        PROTOCOL
    ):
        raise ValueError("weighted_sources_changed_during_feature_caching")
    current_control(protocol)
    write_json(
        RUN / "cache-frozen.json",
        {
            **initial,
            "frozen_at_utc": now(),
            "assets": assets,
            "audit_sha256": checksum(AUDIT),
            "cached_real_inference_parity_cases": len(direct),
            "max_cached_prediction_delta": delta,
            "transformations_fitted_on_holdouts": False,
        },
    )
    print("Shared feature cache and development audit frozen", flush=True)


def check_cache(protocol):
    frozen = read_json(RUN / "cache-frozen.json")
    if (
        frozen["protocol_sha256"] != checksum(PROTOCOL)
        or frozen["source_hashes"] != bindings()
    ):
        raise ValueError("weighted_cache_source_or_protocol_changed")
    if (
        checksum(previous.RUN / "selected-frozen.json")
        != frozen["previous_selection_sha256"]
    ):
        raise ValueError("previous_selection_changed")
    current_control(protocol)
    for item in frozen["assets"].values():
        if (
            checksum(ROOT / item["input_path"]) != item["input_sha256"]
            or checksum(ROOT / item["matrix_path"]) != item["matrix_sha256"]
        ):
            raise ValueError("weighted_input_or_feature_matrix_changed")
    return frozen


def holdout_binding(protocol):
    path = ROOT / protocol["new_holdout_freeze"]
    if not path.exists():
        raise ValueError(
            "new_holdout_or_explicit_unavailability_audit_required_before_fitting"
        )
    frozen = read_json(path)
    if (
        frozen.get("protocol_path")
        and checksum(ROOT / frozen["protocol_path"]) != frozen["protocol_sha256"]
    ):
        raise ValueError("new_holdout_intake_protocol_changed")
    for name, sha in {
        **frozen.get("source_hashes", {}),
        **frozen.get("prior_exposure_hashes", {}),
    }.items():
        if checksum(ROOT / name) != sha:
            raise ValueError("new_holdout_source_or_exposure_changed")
    if frozen.get("available"):
        if checksum(ROOT / frozen["path"]) != frozen["sha256"]:
            raise ValueError("new_holdout_changed")
        sidecar = frozen["sidecar"]
        if checksum(ROOT / sidecar["path"]) != sidecar["sha256"]:
            raise ValueError("new_holdout_exposure_sidecar_changed")
    return {
        "freeze_path": path.relative_to(ROOT).as_posix(),
        "freeze_sha256": checksum(path),
        "data": frozen,
    }


def check_holdout_matches(frozen, protocol):
    actual = holdout_binding(protocol)
    if actual != frozen:
        raise ValueError("holdout_binding_changed_after_fitting_started")


def train(protocol):
    if (RUN / "selected-frozen.json").exists():
        raise ValueError("weighted_model_already_selected")
    cache = check_cache(protocol)
    holdout = holdout_binding(protocol)
    started = {
        "started_at_utc": now(),
        "cache_freeze_sha256": checksum(RUN / "cache-frozen.json"),
        "holdout": holdout,
        "source_hashes": bindings(),
    }
    write_json(RUN / "training-started.json", started)
    frames = {
        name: pd.read_parquet(
            ROOT / item["input_path"],
            columns=["partition", "group", "label", "training_source"],
        )
        for name, item in cache["assets"].items()
    }
    matrices = {
        name: load_npz(ROOT / item["matrix_path"])
        for name, item in cache["assets"].items()
    }
    control = joblib.load(ROOT / cache["control_artifact"])
    results, records = {}, {}
    raw_native = {
        name: control["classifier"].predict_proba(matrices[name])[:, 1]
        for name in ("calibration", "tune", "threshold")
    }
    native_policy = {
        "strict": control["metadata"]["policies"]["strict_source_1pct"],
        "pooled": control["metadata"]["policies"]["pooled_0.01"],
    }
    results["control_native"] = summarize_tune(
        frames["tune"],
        calibrated(raw_native["tune"], control["calibrator"]),
        native_policy["strict"]["threshold"],
        protocol,
    )
    records["control_native"] = {
        "artifact": cache["control_artifact"],
        "artifact_sha256": cache["control_sha256"],
        "policies": native_policy,
        "classifier_mode": "frozen_source_sqrt",
        "calibration_mode": "frozen_row_sigmoid",
    }
    modes = ["control_equal_calibration"] + protocol["classifier_candidates"]
    for mode in modes:
        checkpoint_path = RUN / (mode + "-completed.json")
        if checkpoint_path.exists():
            checkpoint = read_json(checkpoint_path)
            if (
                checkpoint["cache_freeze_sha256"] != started["cache_freeze_sha256"]
                or checkpoint["holdout"] != holdout
            ):
                raise ValueError("weighted_checkpoint_inputs_changed")
            for name, record in checkpoint["records"].items():
                if checksum(ROOT / record["artifact"]) != record["artifact_sha256"]:
                    raise ValueError("weighted_checkpoint_artifact_changed")
            results.update(checkpoint["results"])
            records.update(checkpoint["records"])
            continue
        if mode == "control_equal_calibration":
            classifier, raw = control["classifier"], raw_native
            cal_modes = ["source_equal_sigmoid"]
        else:
            weights = classifier_weights(frames["fit"], mode)
            classifier = LogisticRegression(
                random_state=protocol["seed"], **protocol["classifier"]
            )
            print("Training weighted classifier: " + mode, flush=True)
            checked_fit(
                classifier, matrices["fit"], frames["fit"].label, sample_weight=weights
            )
            raw = {
                part: classifier.predict_proba(matrices[part])[:, 1]
                for part in ("calibration", "tune", "threshold")
            }
            cal_modes = protocol["calibrators"]
        group_results, group_records = {}, {}
        for cal_mode in cal_modes:
            name = mode + "__" + cal_mode
            calibrator = LogisticRegression(
                C=1000, max_iter=200, random_state=protocol["seed"]
            )
            checked_fit(
                calibrator,
                logit(np.clip(raw["calibration"], 1e-7, 1 - 1e-7)).reshape(-1, 1),
                frames["calibration"].label,
                sample_weight=calibration_weights(frames["calibration"], cal_mode),
            )
            if calibrator.coef_[0, 0] <= 0:
                raise ValueError("weighted_calibration_must_preserve_ranking")
            scores = calibrated(raw["threshold"], calibrator)
            points = matrix_points(frames["threshold"], scores, protocol)
            tune_scores = calibrated(raw["tune"], calibrator)
            metrics = summarize_tune(
                frames["tune"], tune_scores, points["strict"]["threshold"], protocol
            )
            bundle = {
                "encoder": control["encoder"],
                "classifier": classifier,
                "calibrator": calibrator,
                "metadata": {
                    "version": "v6-weighted-20261105-" + name,
                    "representation": "url-core-path-assignment-redacted-experiment-1",
                    "protocol_sha256": checksum(PROTOCOL),
                    "policies": points,
                    "encoder_provenance_artifact_sha256": cache["control_sha256"],
                    "production_ready": False,
                    "research_noncommercial_only": True,
                },
            }
            artifact = RUN / (name + ".joblib")
            joblib.dump(bundle, artifact, compress=3)
            group_records[name] = {
                "artifact": artifact.relative_to(ROOT).as_posix(),
                "artifact_sha256": checksum(artifact),
                "policies": points,
                "classifier_mode": mode,
                "calibration_mode": cal_mode,
                "iterations": int(classifier.n_iter_[0]),
                "converged": True,
                "positive_calibration_slope": float(calibrator.coef_[0, 0]),
            }
            group_results[name] = metrics
            print(
                json.dumps(
                    {
                        "candidate": name,
                        "macro_recall": metrics["macro_source_recall"],
                        "macro_brier": metrics["macro_source_brier"],
                    }
                ),
                flush=True,
            )
        results.update(group_results)
        records.update(group_records)
        write_json(
            checkpoint_path,
            {
                "cache_freeze_sha256": started["cache_freeze_sha256"],
                "holdout": holdout,
                "results": group_results,
                "records": group_records,
            },
        )
    selection = choose_research_candidate(results, results["control_native"])
    candidate = records[selection["evaluated_candidate"]]
    bundle = joblib.load(ROOT / candidate["artifact"])
    tune_cores = (
        pd.read_parquet(ROOT / cache["assets"]["tune"]["input_path"], columns=["core"])
        .core.iloc[:128]
        .tolist()
    )
    probes = tune_cores + [
        "http://example.org/password=SHORTSECRET",
        "https://example.org/password=SHORTSECRET",
    ]
    original_scores = predict_bundle(bundle, probes)
    restored = joblib.load(ROOT / candidate["artifact"])
    delta = float(np.max(np.abs(original_scores - predict_bundle(restored, probes))))
    matrix_probe = calibrated(
        bundle["classifier"].predict_proba(matrices["tune"][:128])[:, 1],
        bundle["calibrator"],
    )
    if (
        delta != 0
        or not np.allclose(matrix_probe, original_scores[:128], rtol=0, atol=1e-12)
        or original_scores[-1] != original_scores[-2]
    ):
        raise ValueError("weighted_artifact_cached_inference_or_scheme_parity_failed")
    check_cache(protocol)
    check_holdout_matches(holdout, protocol)
    write_json(
        RUN / "selected-frozen.json",
        {
            "frozen_at_utc": now(),
            "selection": selection,
            "records": records,
            "tune": results,
            "cache_freeze_sha256": started["cache_freeze_sha256"],
            "holdout": holdout,
            "training_started_at_utc": started["started_at_utc"],
            "parity_cases": len(probes),
            "max_saved_prediction_delta": delta,
            "max_cached_inference_delta": float(
                np.max(np.abs(matrix_probe - original_scores[:128]))
            ),
            "test_used_for_selection": False,
            "production_ready": False,
        },
    )
    print(json.dumps(selection), flush=True)


def check_selected(protocol):
    cache = check_cache(protocol)
    selected = read_json(RUN / "selected-frozen.json")
    if selected["cache_freeze_sha256"] != checksum(RUN / "cache-frozen.json"):
        raise ValueError("weighted_selected_cache_changed")
    check_holdout_matches(selected["holdout"], protocol)
    for record in selected["records"].values():
        if checksum(ROOT / record["artifact"]) != record["artifact_sha256"]:
            raise ValueError("weighted_saved_artifact_changed")
    return cache, selected


def evaluate(protocol):
    if REPORT.exists():
        raise ValueError("weighted_evaluation_already_completed")
    cache, selected = check_selected(protocol)
    write_json(
        RUN / "evaluation-started.json",
        {
            "started_at_utc": now(),
            "selected_sha256": checksum(RUN / "selected-frozen.json"),
        },
    )
    control, active = joblib.load(ROOT / cache["control_artifact"]), RichArtifact()
    chosen = selected["records"][selected["selection"]["evaluated_candidate"]]
    candidate = joblib.load(ROOT / chosen["artifact"])
    prior = read_json(previous.RUN / "selected-frozen.json")
    control_record = selected["records"]["control_native"]
    thresholds = {
        "active_original": active.metadata["thresholds"]["warning"],
        "active_matched": prior["baseline_policies"]["strict_source_1pct"]["threshold"],
        "control_strict": control_record["policies"]["strict"]["threshold"],
        "candidate_strict": chosen["policies"]["strict"]["threshold"],
        "control_pooled": control_record["policies"]["pooled"]["threshold"],
        "candidate_pooled": chosen["policies"]["pooled"]["threshold"],
    }
    paths = {
        "observed_pwd": previous.RUN / "new_test.parquet",
        "observed_expanded": previous.OLD / "new_test.parquet",
        "observed_vendor": ROOT
        / "ml/runs/notebook-tfidf-logistic-v6/data/deepurlbench-holdout-v6.parquet",
        "observed_phishtank_positive": ROOT
        / "ml/runs/notebook-tfidf-logistic-v6/data/phishtank-2026-v6.parquet",
        "observed_legitphish": ROOT
        / "ml/data/legitphish-v2-v6-qa/sanitized-domain-disjoint.parquet",
    }
    if selected["holdout"]["data"].get("available"):
        paths = {
            "new_external_publisher_holdout": ROOT
            / selected["holdout"]["data"]["path"],
            **paths,
        }
    cohorts = {}
    for name, path in paths.items():
        frame = pd.read_parquet(path)
        if frame.empty:
            cohorts[name] = {"rows": 0, "not_evaluated": "no_novel_rows"}
            continue
        positive = frame.label.eq(1).all()
        supported = positive or set(frame.label) == {0, 1}
        scores = {
            "active": active.predict_cores(frame.core),
            "control": predict_bundle(control, frame.core),
            "candidate": predict_bundle(candidate, frame.core),
        }
        metrics = {}
        for role, threshold in thresholds.items():
            probability = scores[role.split("_", 1)[0]]
            row = safe_metrics(frame, probability, threshold, positive_only=positive)
            if supported:
                row["domain_bootstrap95"] = domain_intervals(
                    frame,
                    probability,
                    threshold,
                    protocol["bootstrap_repeats"],
                    protocol["seed"],
                    positive,
                )
            metrics[role] = row
        paired = (
            {
                role: paired_intervals(
                    frame,
                    scores[role],
                    scores["candidate"],
                    [
                        thresholds[
                            "active_original" if role == "active" else "control_strict"
                        ],
                        thresholds["candidate_strict"],
                    ],
                    protocol["bootstrap_repeats"],
                    protocol["seed"],
                    positive,
                )
                for role in ["active", "control"]
            }
            if supported
            else {}
        )
        cohorts[name] = {
            "rows": len(frame),
            "groups": int(frame.group.nunique()),
            "previously_observed": name != "new_external_publisher_holdout",
            "class_counts": {
                str(k): int(v) for k, v in frame.label.value_counts().items()
            },
            "policies": metrics,
            "paired_candidate_minus": paired,
        }
        print("Evaluated weighted study: " + name, flush=True)
    check_selected(protocol)
    write_json(
        REPORT,
        {
            "completed_at_utc": now(),
            "protocol_sha256": checksum(PROTOCOL),
            "cache_freeze": cache,
            "selected_freeze": selected,
            "cohorts": cohorts,
            "development_audit_sha256": checksum(AUDIT),
            "Indonesia_inputs": inventory(),
            "production_ready": False,
            "original_v6_unchanged": True,
            "human_labels_fabricated": False,
            "test_results_used_for_selection": False,
            "decision": "keep_frozen_v6_service; research selection does not authorize promotion",
        },
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--stage", choices=["prepare", "train", "evaluate"], required=True
    )
    args = parser.parse_args()
    protocol = read_json(PROTOCOL)
    with threadpool_limits(limits=2):
        {"prepare": prepare, "train": train, "evaluate": evaluate}[args.stage](protocol)


if __name__ == "__main__":
    main()
