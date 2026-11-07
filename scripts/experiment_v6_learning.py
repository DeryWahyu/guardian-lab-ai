"""Run frozen-protocol learning curves, LR ablations and external evaluation."""

import argparse
import gc
import json
import time

import joblib
import numpy as np
import pandas as pd
from scipy.sparse import load_npz
from scipy.special import logit
from sklearn.linear_model import LogisticRegression
from threadpoolctl import threadpool_limits

from guardian_ml.metadata import checksum
from guardian_ml.paths import ROOT
from guardian_ml.rich_artifact import RichArtifact
from evaluate_v6_indonesia_external import verify_files
from experiment_v6_development import checked_fit, matrix_batches, paired_intervals
from experiment_v6_expanded_data import make_encoder, now, source_point, write_json
import experiment_v6_weighted as previous
from v6_development_support import (
    assert_separated,
    predict_bundle,
    prepare_experiment_url,
)
from v6_indonesia_external_support import coverage, diagnostic_metrics, structure_masks
from v6_diagnostic_support import safe_metrics
from v6_learning_support import choose, nested_fit, slices, weights
from v6_weighted_support import calibration_weights, summarize_tune

PROTOCOL = ROOT / "ml/reports/v6-learning-20261106-protocol.json"
RUN = ROOT / "ml/runs/v6-learning-20261106"
DATA = ROOT / "ml/data/v6-learning-20261106"
REPORT = ROOT / "ml/reports/v6-learning-evaluation.json"
PARTS = ("fit", "calibration", "threshold", "tune")


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def source_bindings():
    paths = set(previous.SOURCES) | {
        "scripts/experiment_v6_learning.py",
        "scripts/v6_learning_support.py",
        "scripts/intake_v6_learning.py",
        "scripts/v6_weighted_support.py",
        "scripts/v6_indonesia_external_support.py",
        "scripts/evaluate_v6_indonesia_external.py",
        "ml/src/guardian_ml/preprocessing.py",
        "ml/src/guardian_ml/rich_features.py",
        "ml/src/guardian_ml/evaluation.py",
        "ml/src/guardian_ml/rich_artifact.py",
    }
    return {p: checksum(ROOT / p) for p in sorted(paths)}


def sidecars():
    return {
        p.relative_to(ROOT).as_posix(): checksum(p)
        for p in sorted((ROOT / "ml/data/exposure-sidecars").glob("*.sqlite"))
    }


def prepare():
    if RUN.exists():
        raise ValueError("learning_prepare_requires_new_run")
    p = read(PROTOCOL)
    cache = previous.check_cache(read(previous.PROTOCOL))
    intake = read(DATA / "frozen.json")
    if intake["protocol_sha256"] != checksum(PROTOCOL):
        raise ValueError("learning_intake_protocol_changed")
    verify_files(intake["source_hashes"])
    verify_files(intake["prior_exposure_hashes"])
    verify_files(intake["actual_prior_identity_bindings"])
    verify_files(
        {
            intake["sidecar"]["path"]: intake["sidecar"]["sha256"],
            p["control"]: p["control_sha256"],
        }
    )
    frames = [
        pd.read_parquet(ROOT / cache["assets"][part]["input_path"]) for part in PARTS
    ]
    for asset in intake["assets"].values():
        verify_files({asset["path"]: asset["sha256"]})
        frames.append(pd.read_parquet(ROOT / asset["path"]))
    assert_separated(frames)
    if len(frames[0]) != p["fit_rows"]:
        raise ValueError("learning_fit_count_changed")
    extra = frames[4]
    masks = structure_masks(extra)
    hard = int(
        (
            (masks["long_url_over_120"] | masks["deep_path_at_least_4"])
            & extra.label.eq(0)
        ).sum()
    )
    hosted = int((masks["private_hosting"] & extra.label.eq(1)).sum())
    active = RichArtifact()
    RUN.mkdir(parents=True)
    state = {
        "prepared_at_utc": now(),
        "protocol_sha256": checksum(PROTOCOL),
        "source_hashes": source_bindings(),
        "base_cache_sha256": checksum(ROOT / p["base_cache"]),
        "intake_freeze_sha256": checksum(DATA / "frozen.json"),
        "all_sidecars": sidecars(),
        "original_bundle_sha256": active.manifest["bundle_sha256"],
        "original_metadata_sha256": active.manifest["frozen_metadata_sha256"],
        "augmentation_eligible": hard >= 100 or hosted >= 100,
        "augmentation_hard_benign": hard,
        "augmentation_private_phishing": hosted,
        "development_coverage": {
            part: coverage(frames[i]) for i, part in enumerate(PARTS)
        },
        "identity_overlap_checks": "group, digest and scheme-free representation across all development and new data; historical test identities bound by intake",
        "production_ready": False,
    }
    write_json(RUN / "prepared.json", state)
    print(
        json.dumps(
            {
                "prepared": True,
                "augmentation_eligible": state["augmentation_eligible"],
                "hard_benign": hard,
                "private_phishing": hosted,
            }
        ),
        flush=True,
    )


def check():
    p, state = read(PROTOCOL), read(RUN / "prepared.json")
    if (
        state["protocol_sha256"] != checksum(PROTOCOL)
        or state["source_hashes"] != source_bindings()
        or state["all_sidecars"] != sidecars()
        or state["base_cache_sha256"] != checksum(ROOT / p["base_cache"])
        or state["intake_freeze_sha256"] != checksum(DATA / "frozen.json")
    ):
        raise ValueError("learning_frozen_inputs_changed")
    cache, intake = read(ROOT / p["base_cache"]), read(DATA / "frozen.json")
    for asset in cache["assets"].values():
        verify_files(
            {
                asset["input_path"]: asset["input_sha256"],
                asset["matrix_path"]: asset["matrix_sha256"],
            }
        )
    for asset in intake["assets"].values():
        verify_files({asset["path"]: asset["sha256"]})
    verify_files({p["control"]: p["control_sha256"]})
    verify_files(intake["prior_exposure_hashes"])
    active = RichArtifact()
    if (
        active.manifest["bundle_sha256"] != state["original_bundle_sha256"]
        or active.manifest["frozen_metadata_sha256"]
        != state["original_metadata_sha256"]
    ):
        raise ValueError("learning_active_v6_changed")
    return p, state, cache, intake


def result_for(bundle, raw, frames, p):
    scores = {
        part: previous.calibrated(values, bundle["calibrator"])
        for part, values in raw.items()
    }
    points = {
        str(b): source_point(
            frames["threshold"], scores["threshold"], b, "threshold", p
        )
        for b in p["threshold_budgets"]
    }
    policies = {
        b: summarize_tune(frames["tune"], scores["tune"], pt["threshold"], p)
        for b, pt in points.items()
    }
    threshold = points[str(p["primary_budget"])]["threshold"]
    return (
        {
            "primary": policies[str(p["primary_budget"])],
            "policies": policies,
            "slices": slices(frames["tune"], scores["tune"], threshold),
        },
        points,
        scores["tune"],
    )


def train():
    if (RUN / "selected-frozen.json").exists():
        raise ValueError("learning_selection_already_frozen")
    p, state, cache, intake = check()
    frames = {
        part: pd.read_parquet(ROOT / cache["assets"][part]["input_path"])
        for part in PARTS
    }
    for part in ("tune", "threshold"):
        frames[part]["core"] = [
            prepare_experiment_url(c).core for c in frames[part].core
        ]
    control = joblib.load(ROOT / p["control"])
    results, records = {}, {}
    raw = {
        part: control["classifier"].predict_proba(
            load_npz(ROOT / cache["assets"][part]["matrix_path"])
        )[:, 1]
        for part in PARTS
        if part != "fit"
    }
    results["control"], points, control_scores = result_for(control, raw, frames, p)
    fit_raw = control["classifier"].predict_proba(
        load_npz(ROOT / cache["assets"]["fit"]["matrix_path"])
    )[:, 1]
    results["control"]["fit_metrics"] = safe_metrics(
        frames["fit"],
        previous.calibrated(fit_raw, control["calibrator"]),
        points["0.01"]["threshold"],
    )
    del fit_raw
    if abs(points["0.01"]["threshold"] - p["control_threshold"]) > 1e-12:
        raise ValueError("learning_control_policy_replay_mismatch")
    direct = predict_bundle(control, frames["tune"].core.iloc[:128])
    if np.max(np.abs(direct - control_scores[:128])) > 1e-12:
        raise ValueError("learning_control_cached_real_parity_failed")
    records["control"] = {
        "artifact": p["control"],
        "sha256": p["control_sha256"],
        "thresholds": points,
        "fit_rows": len(frames["fit"]),
        "fit_groups": int(frames["fit"].group.nunique()),
        "feature_count": int(control["classifier"].n_features_in_),
        "fraction": 1.0,
        "saved_model_parity_max_delta": 0.0,
    }
    jobs = [
        {"name": "curve_" + str(int(f * 100)), "fraction": f, "C": 2, "weights": "base"}
        for f in p["learning_curve"]["fractions"]
        if f < 1
    ]
    jobs += [
        c
        for c in p["candidates"]
        if c["name"] != "plus_iscx_fit" or state["augmentation_eligible"]
    ]
    eligible_names = [c["name"] for c in jobs if "fraction" not in c]
    for spec in jobs:
        name = spec["name"]
        path = RUN / (name + "-completed.json")
        if path.exists():
            cp = read(path)
            if cp["prepared_sha256"] != checksum(RUN / "prepared.json"):
                raise ValueError("learning_checkpoint_inputs_changed")
            verify_files({cp["record"]["artifact"]: cp["record"]["sha256"]})
            results[name], records[name] = cp["result"], cp["record"]
            continue
        started = time.monotonic()
        fit = frames["fit"]
        encoder = control["encoder"]
        refit = "fraction" in spec or name == "plus_iscx_fit"
        if "fraction" in spec:
            fit = nested_fit(fit, spec["fraction"], p["learning_curve"]["salt"])
        elif name == "plus_iscx_fit":
            fit = pd.concat(
                [fit, pd.read_parquet(ROOT / intake["assets"]["fit"]["path"])],
                ignore_index=True,
            )
        print(
            json.dumps({"fitting": name, "rows": len(fit), "refit_encoder": refit}),
            flush=True,
        )
        if refit:
            encoder = make_encoder(fit, p)
            matrix = matrix_batches(encoder, fit)
        else:
            matrix = load_npz(ROOT / cache["assets"]["fit"]["matrix_path"])
        classifier = LogisticRegression(
            random_state=p["seed"], **{**p["classifier"], "C": spec["C"]}
        )
        checked_fit(
            classifier, matrix, fit.label, sample_weight=weights(fit, spec["weights"])
        )
        fit_raw = classifier.predict_proba(matrix)[:, 1]
        features = int(matrix.shape[1])
        del matrix
        gc.collect()
        raw = {}
        for part in PARTS[1:]:
            matrix = (
                matrix_batches(encoder, frames[part])
                if refit
                else load_npz(ROOT / cache["assets"][part]["matrix_path"])
            )
            raw[part] = classifier.predict_proba(matrix)[:, 1]
            del matrix
        calibrator = LogisticRegression(C=1000, max_iter=200, random_state=p["seed"])
        checked_fit(
            calibrator,
            logit(np.clip(raw["calibration"], 1e-7, 1 - 1e-7)).reshape(-1, 1),
            frames["calibration"].label,
            sample_weight=calibration_weights(
                frames["calibration"], "source_equal_sigmoid"
            ),
        )
        if calibrator.coef_[0, 0] <= 0:
            raise ValueError("learning_nonpositive_calibration_slope")
        bundle = {
            "encoder": encoder,
            "classifier": classifier,
            "calibrator": calibrator,
            "metadata": {
                "version": p["experiment"] + "-" + name,
                "protocol_sha256": checksum(PROTOCOL),
                "production_ready": False,
                "noncommercial_research_only": True,
                "representation": "url-core-path-assignment-redacted-experiment-1",
            },
        }
        result, points, scores = result_for(bundle, raw, frames, p)
        result["fit_metrics"] = safe_metrics(
            fit, previous.calibrated(fit_raw, calibrator), points["0.01"]["threshold"]
        )
        bundle["metadata"]["policies"] = points
        artifact = RUN / (name + ".joblib")
        joblib.dump(bundle, artifact, compress=3)
        probes = frames["tune"].core.iloc[:128]
        replay = predict_bundle(joblib.load(artifact), probes)
        delta = float(np.max(np.abs(replay - scores[: len(probes)])))
        if delta > 1e-12:
            raise ValueError("learning_saved_model_prediction_parity_failed")
        record = {
            "artifact": artifact.relative_to(ROOT).as_posix(),
            "sha256": checksum(artifact),
            "thresholds": points,
            "fit_rows": len(fit),
            "fit_groups": int(fit.group.nunique()),
            "fit_class_counts": {
                str(k): int(v) for k, v in fit.label.value_counts().items()
            },
            "feature_count": features,
            "fraction": spec.get("fraction"),
            "spec": spec,
            "iterations": int(classifier.n_iter_[0]),
            "calibration_slope": float(calibrator.coef_[0, 0]),
            "encoder_fit_only": True,
            "saved_model_parity_cases": len(probes),
            "saved_model_parity_max_delta": delta,
            "elapsed_seconds": time.monotonic() - started,
        }
        write_json(
            path,
            {
                "completed_at_utc": now(),
                "prepared_sha256": checksum(RUN / "prepared.json"),
                "record": record,
                "result": result,
            },
        )
        results[name], records[name] = result, record
        print(
            json.dumps(
                {
                    "completed": name,
                    "macro_recall": result["primary"]["macro_source_recall"],
                    "macro_brier": result["primary"]["macro_source_brier"],
                    "seconds": record["elapsed_seconds"],
                }
            ),
            flush=True,
        )
        del bundle, classifier, calibrator, encoder, raw, fit
        gc.collect()
    selection = choose(results, eligible_names)
    check()
    write_json(
        RUN / "selected-frozen.json",
        {
            "frozen_at_utc": now(),
            "prepared_sha256": checksum(RUN / "prepared.json"),
            "selection": selection,
            "records": records,
            "results": results,
            "production_ready": False,
        },
    )
    print(json.dumps({"selection": selection}), flush=True)


def evaluate():
    if REPORT.exists():
        raise ValueError("learning_evaluation_already_saved")
    p, state, cache, intake = check()
    selected = read(RUN / "selected-frozen.json")
    if selected["prepared_sha256"] != checksum(RUN / "prepared.json"):
        raise ValueError("learning_selection_binding_changed")
    selected_sha = checksum(RUN / "selected-frozen.json")
    diagnostic = selected["selection"]["diagnostic"]
    model_names = ["control", diagnostic]
    models = {}
    for name in model_names:
        item = selected["records"][name]
        verify_files({item["artifact"]: item["sha256"]})
        models[name] = joblib.load(ROOT / item["artifact"])
    original = RichArtifact()
    assets = {k: v for k, v in intake["assets"].items() if k != "fit"}
    old_path = "ml/data/v6-indonesia-external-20261106/global.parquet"
    # Already exposed 50K benchmark: regression only, never fresh confirmation.
    old_sha = intake["actual_prior_identity_bindings"][old_path]
    assets["observed_global_50000"] = {"path": old_path, "sha256": old_sha}
    cohorts, score_bindings = {}, {}
    for cohort, asset in assets.items():
        verify_files({asset["path"]: asset["sha256"]})
        frame = pd.read_parquet(ROOT / asset["path"])
        scores = {
            "active_v6": original.predict_cores(frame.core)
            if len(frame)
            else np.array([])
        }
        scores.update(
            {
                name: predict_bundle(bundle, frame.core) if len(frame) else np.array([])
                for name, bundle in models.items()
            }
        )
        np.savez_compressed(RUN / (cohort + "-predictions.npz"), **scores)
        score_bindings[
            (RUN / (cohort + "-predictions.npz")).relative_to(ROOT).as_posix()
        ] = checksum(RUN / (cohort + "-predictions.npz"))
        thresholds = {
            "active_v6": original.manifest["thresholds"]["warning"],
            **{
                n: selected["records"][n]["thresholds"]["0.01"]["threshold"]
                for n in model_names
            },
        }
        masks = {
            "all": np.ones(len(frame), dtype=bool),
            **{k: v.to_numpy() for k, v in structure_masks(frame).items()},
        }
        evaluations = {}
        for subgroup, mask in masks.items():
            evaluations[subgroup] = {
                name: diagnostic_metrics(
                    frame.loc[mask],
                    score[mask],
                    thresholds[name],
                    p["bootstrap_repeats"],
                    p["seed"],
                )
                for name, score in scores.items()
            }
        paired = None
        if len(frame) and frame.label.eq(1).any():
            paired = paired_intervals(
                frame,
                scores["control"],
                scores[diagnostic],
                [thresholds["control"], thresholds[diagnostic]],
                p["bootstrap_repeats"],
                p["seed"],
                frame.label.eq(1).all(),
            )
        policies = {
            name: {
                b: diagnostic_metrics(
                    frame,
                    scores[name],
                    point["threshold"],
                    p["bootstrap_repeats"],
                    p["seed"],
                )
                for b, point in selected["records"][name]["thresholds"].items()
            }
            for name in model_names
        }
        parity = {}
        for name in model_names:
            if not len(frame):
                continue
            replay = predict_bundle(
                joblib.load(ROOT / selected["records"][name]["artifact"]),
                frame.core.iloc[:128],
            )
            delta = float(np.max(np.abs(replay - scores[name][: len(replay)])))
            if delta > 1e-12:
                raise ValueError("learning_external_saved_model_parity_failed")
            parity[name] = {"cases": len(replay), "max_delta": delta}
        cohorts[cohort] = {
            **coverage(frame),
            "results": evaluations,
            "policies": policies,
            "paired_diagnostic_minus_control": paired,
            "parity": parity,
            "independent_publisher_from_added_training": cohort == "ebbu_external",
            "previously_observed": cohort == "observed_global_50000",
        }
        print(
            json.dumps(
                {"evaluated": cohort, "rows": len(frame), "primary": evaluations["all"]}
            ),
            flush=True,
        )
    check()
    if checksum(RUN / "selected-frozen.json") != selected_sha:
        raise ValueError("learning_selection_changed_during_external_evaluation")
    write_json(
        REPORT,
        {
            "completed_at_utc": now(),
            "protocol_sha256": checksum(PROTOCOL),
            "selection_freeze_sha256": selected_sha,
            "selection": selected["selection"],
            "development_results": selected["results"],
            "records": selected["records"],
            "intake": intake,
            "cohorts": cohorts,
            "score_bindings": score_bindings,
            "active_v6_unchanged": True,
            "test_used_for_selection": False,
            "verified_indonesia_gold": False,
            "production_ready": False,
        },
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stage", choices=["prepare", "train", "evaluate", "check"])
    args = parser.parse_args()
    with threadpool_limits(limits=4):
        {"prepare": prepare, "train": train, "evaluate": evaluate, "check": check}[
            args.stage
        ]()


if __name__ == "__main__":
    main()
