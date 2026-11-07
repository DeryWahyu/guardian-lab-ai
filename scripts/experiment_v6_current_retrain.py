"""Original v6 recipe, two prescribed fitting corpora, locked historical replay."""

import argparse
import gc
import json
import time

import joblib
import numpy as np
import pandas as pd
from scipy.special import logit
from sklearn.base import clone
from threadpoolctl import threadpool_limits

from guardian_ml.metadata import checksum
from guardian_ml.paths import ROOT
from guardian_ml.rich_artifact import RichArtifact
from evaluate_v6_indonesia_external import verify_files
from experiment_v6_development import checked_fit, matrix_batches, paired_intervals
from experiment_v6_expanded_data import now, write_json
import experiment_v6_learning as prior
from v6_current_retrain_support import (
    assert_original_recipe,
    fit_original_encoder,
    improvement_gate,
)
from v6_development_support import (
    assert_separated,
    curate_fit,
    fit_weights,
    predict_bundle,
    representation_digest,
    source_threshold,
    transform_frame,
)
from v6_indonesia_external_support import coverage, diagnostic_metrics, structure_masks
from v6_learning_support import slices
from v6_weighted_support import summarize_tune

PROTOCOL = ROOT / "ml/reports/v6-current-retrain-20261107-protocol.json"
RUN = ROOT / "ml/runs/v6-current-retrain-20261107"
REPORT = ROOT / "ml/reports/v6-current-retrain-evaluation.json"
PARTS = ("fit", "calibration", "threshold", "tune")
ARMS = ("foundation_v6_recipe", "current_v6_recipe")


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def bindings():
    files = set(prior.source_bindings()) | {
        "scripts/experiment_v6_current_retrain.py",
        "scripts/v6_current_retrain_support.py",
        "scripts/v6_learning_support.py",
        "scripts/v6_development_support.py",
        "ml/src/guardian_ml/features.py",
        "ml/policies/shadow-runtime-manifest.json",
        "ml/provenance/v6-origin.json",
        "ml/reports/v6-current-retrain-source-schema-audit.json",
        "ml/reports/v6-current-retrain-preflight-repair.json",
    }
    return {p: checksum(ROOT / p) for p in sorted(files)}


def prepare():
    if RUN.exists():
        raise ValueError("current_retrain_requires_new_directory")
    p = read(PROTOCOL)
    _, _, cache, latest = prior.check()
    active = RichArtifact()
    if set(p["foundation_sources"]) != set(active.metadata["fit_source_counts"]):
        raise ValueError("foundation_source_names_do_not_match_original_v6")
    if active.manifest["bundle_sha256"] != p["original_sha256"]:
        raise ValueError("current_retrain_original_identity_changed")
    origin = read(ROOT / "ml/provenance/v6-origin.json")
    snapshot = ROOT / origin["local_frozen_training_notebook"]
    if checksum(snapshot) != origin["training_notebook_sha256"]:
        raise ValueError("original_training_source_snapshot_changed")
    sources = {a["input_path"]: a["input_sha256"] for a in cache["assets"].values()}
    stealth_path = ROOT / "ml/data/v6-segmented-new-holdout/frozen.json"
    stealth = read(stealth_path)
    verify_files(stealth["source_hashes"])
    for item in (stealth["partitions"]["fit"], latest["assets"]["fit"]):
        sources[item["path"]] = item["sha256"]
    previous_tests = read(ROOT / "ml/runs/v6-segmented-20261105/cache-frozen.json")[
        "observed_test_bindings"
    ]
    tests = {}
    for name, filename in (
        ("observed_vendor", "deepurlbench-holdout-v6.parquet"),
        ("observed_phishtank_positive", "phishtank-2026-v6.parquet"),
        ("observed_expanded", "v6-expanded-data-20261105/new_test.parquet"),
        ("observed_pwd2021", "v6-targeted-20261105/new_test.parquet"),
        ("observed_zenodo", "v6-weighted-new-holdout/holdout.parquet"),
        ("observed_legitphish", "sanitized-domain-disjoint.parquet"),
    ):
        path = next(k for k in previous_tests if k.endswith(filename))
        tests[name] = {"path": path, "sha256": previous_tests[path]}
    tests["observed_stealth"] = stealth["partitions"]["new_test"]
    phishbench_path = ROOT / "ml/data/v6-segmented-phishbench/frozen.json"
    tests["observed_phishbench"] = read(phishbench_path)["partitions"]["new_test"]
    for n, key in (
        ("observed_ebbu", "ebbu_external"),
        ("observed_iscx", "iscx_external"),
    ):
        tests[n] = latest["assets"][key]
    external_path = ROOT / "ml/data/v6-indonesia-external-20261106/frozen.json"
    external = read(external_path)
    tests["observed_global"] = external["assets"]["global"]
    for asset in tests.values():
        sources[asset["path"]] = asset["sha256"]
    reserved = external["assets"]["reserved"]
    sources[reserved["path"]] = reserved["sha256"]
    parents = [
        ROOT / p["original_artifact"],
        snapshot,
        stealth_path,
        phishbench_path,
        external_path,
        prior.DATA / "frozen.json",
        ROOT / "ml/runs/v6-learning-20261106/prepared.json",
    ]
    sources.update(
        {path.relative_to(ROOT).as_posix(): checksum(path) for path in parents}
    )
    verify_files(sources)
    initial_sources, protocol_sha = bindings(), checksum(PROTOCOL)
    frames, privacy = {}, {}
    for part in PARTS:
        frames[part], privacy[part] = transform_frame(
            pd.read_parquet(ROOT / cache["assets"][part]["input_path"])
        )
    additions = []
    for item in (stealth["partitions"]["fit"], latest["assets"]["fit"]):
        frame, _ = transform_frame(pd.read_parquet(ROOT / item["path"]))
        if set(frame.partition) != {"fit"}:
            raise ValueError("current_retrain_extra_data_not_fit_partition")
        additions.append(frame)
    assert_separated([frames["fit"], *additions, *[frames[k] for k in PARTS[1:]]])
    combined = pd.concat([frames["fit"], *additions], ignore_index=True)
    current, curation = curate_fit(combined)
    foundation = current.loc[
        current.training_source.isin(p["foundation_sources"])
    ].reset_index(drop=True)
    if len(current) != 671440 or len(foundation) != 524699:
        raise ValueError("current_retrain_predeclared_count_mismatch")
    # Audit test identities only. No test labels or predictions influence fitting.
    isolation = {}
    for key, item in {**tests, "all_mendeley_reserved": reserved}.items():
        identity = pd.read_parquet(
            ROOT / item["path"], columns=["core", "group", "digest"]
        )
        identity["representation_digest"] = identity.core.map(representation_digest)
        assert_separated(
            [
                current,
                frames["calibration"],
                frames["threshold"],
                frames["tune"],
                identity,
            ]
        )
        isolation[key] = {
            "rows": len(identity),
            "group_digest_representation_overlap": 0,
        }
    RUN.mkdir(parents=True)
    frames["foundation_v6_recipe"], frames["current_v6_recipe"] = foundation, current
    assets = {}
    for name in (*ARMS, *PARTS[1:]):
        path = RUN / (name + ".parquet")
        frames[name].to_parquet(path, index=False)
        assets[name] = {
            "path": path.relative_to(ROOT).as_posix(),
            "sha256": checksum(path),
            **coverage(frames[name]),
        }
    if bindings() != initial_sources or checksum(PROTOCOL) != protocol_sha:
        raise ValueError("current_retrain_sources_changed_during_prepare")
    write_json(
        RUN / "data-frozen.json",
        {
            "prepared_at_utc": now(),
            "protocol_sha256": protocol_sha,
            "source_hashes": initial_sources,
            "inputs": sources,
            "assets": assets,
            "tests": tests,
            "all_sidecars": prior.sidecars(),
            "registry_path": "ml/data/indonesia-gold/registry/known-exposure.sqlite",
            "registry_sha256": checksum(
                ROOT / "ml/data/indonesia-gold/registry/known-exposure.sqlite"
            ),
            "privacy": privacy,
            "curation": curation,
            "isolation": isolation,
            "actual_recipe_from_frozen_artifact": True,
            "production_ready": False,
        },
    )
    print(
        json.dumps(
            {
                "fitting": {n: assets[n]["rows"] for n in ARMS},
                "test_cohorts": len(tests),
                "test_labels_used_for_fitting": False,
            }
        ),
        flush=True,
    )


def check():
    p, data = read(PROTOCOL), read(RUN / "data-frozen.json")
    if (
        checksum(PROTOCOL) != data["protocol_sha256"]
        or bindings() != data["source_hashes"]
        or prior.sidecars() != data["all_sidecars"]
    ):
        raise ValueError("current_retrain_frozen_protocol_sources_or_exposure_changed")
    verify_files(data["inputs"])
    verify_files({a["path"]: a["sha256"] for a in data["assets"].values()})
    verify_files({data["registry_path"]: data["registry_sha256"]})
    active = RichArtifact()
    if (
        active.manifest["bundle_sha256"] != p["original_sha256"]
        or active.manifest["frozen_metadata_sha256"] != p["original_metadata_sha256"]
    ):
        raise ValueError("current_retrain_original_changed")
    return p, data


def tune_result(frame, scores, policy, protocol):
    return {
        "primary": summarize_tune(
            frame, scores, policy["warning"]["threshold"], protocol
        ),
        "slices": slices(frame, scores, policy["warning"]["threshold"]),
    }


def policies(frame, scores, p):
    return {
        level: {
            **source_threshold(frame, scores, budget, "threshold"),
            "development_source_fpr_budget": budget,
        }
        for level, budget in p["thresholds"].items()
    }


def train():
    if (RUN / "models-frozen.json").exists():
        raise ValueError("current_retrain_models_already_frozen")
    p, data = check()
    original = joblib.load(ROOT / p["original_artifact"])
    frames = {
        part: pd.read_parquet(ROOT / data["assets"][part]["path"]) for part in PARTS[1:]
    }
    original_scores = {
        part: RichArtifact().predict_cores(frames[part].core)
        for part in ("threshold", "tune")
    }
    matched = policies(frames["threshold"], original_scores["threshold"], p)
    native = {
        k: {"threshold": v} for k, v in original["metadata"]["thresholds"].items()
    }
    records = {
        "frozen_native": {
            "artifact": p["original_artifact"],
            "sha256": p["original_sha256"],
            "policies": native,
        },
        "frozen_matched_policy": {
            "artifact": p["original_artifact"],
            "sha256": p["original_sha256"],
            "policies": matched,
        },
    }
    results = {
        name: tune_result(frames["tune"], original_scores["tune"], r["policies"], p)
        for name, r in records.items()
    }
    for name in ARMS:
        checkpoint = RUN / (name + "-completed.json")
        if checkpoint.exists():
            completed = read(checkpoint)
            if completed["data_freeze_sha256"] != checksum(RUN / "data-frozen.json"):
                raise ValueError("current_retrain_checkpoint_changed")
            verify_files(
                {completed["record"]["artifact"]: completed["record"]["sha256"]}
            )
            records[name], results[name] = completed["record"], completed["result"]
            continue
        started = time.monotonic()
        fit = pd.read_parquet(ROOT / data["assets"][name]["path"])
        print(
            json.dumps({"training": name, "rows": len(fit), "recipe": "original_v6"}),
            flush=True,
        )
        encoder, vocabulary_rows = fit_original_encoder(original, fit, p)
        matrix = matrix_batches(encoder, fit)
        classifier = clone(original["classifier"])
        checked_fit(
            classifier, matrix, fit.label, sample_weight=fit_weights(fit, "source_sqrt")
        )
        features = int(matrix.shape[1])
        del matrix
        gc.collect()
        raw = {}
        for part in PARTS[1:]:
            matrix = matrix_batches(encoder, frames[part])
            raw[part] = classifier.predict_proba(matrix)[:, 1]
            del matrix
        calibrator = clone(original["calibrator"])
        checked_fit(
            calibrator,
            logit(np.clip(raw["calibration"], 1e-7, 1 - 1e-7)).reshape(-1, 1),
            frames["calibration"].label,
        )
        if calibrator.coef_[0, 0] <= 0:
            raise ValueError("current_retrain_calibration_slope_not_positive")
        from experiment_v6_weighted import calibrated

        scores = {
            part: calibrated(raw[part], calibrator) for part in ("threshold", "tune")
        }
        policy = policies(frames["threshold"], scores["threshold"], p)
        bundle = {
            "encoder": encoder,
            "classifier": classifier,
            "calibrator": calibrator,
            "metadata": {
                "version": p["experiment"] + "-" + name,
                "policies": policy,
                "representation": "url-core-path-assignment-redacted-experiment-1",
                "protocol_sha256": checksum(PROTOCOL),
                "production_ready": False,
                "noncommercial_research_only": True,
                "original_recipe_retrained": True,
            },
        }
        assert_original_recipe(bundle, original)
        artifact = RUN / (name + ".joblib")
        joblib.dump(bundle, artifact, compress=3)
        replay = predict_bundle(joblib.load(artifact), frames["tune"].core.iloc[:128])
        delta = float(np.max(np.abs(replay - scores["tune"][: len(replay)])))
        if delta > 1e-12:
            raise ValueError("current_retrain_saved_prediction_parity_failed")
        result = tune_result(frames["tune"], scores["tune"], policy, p)
        record = {
            "artifact": artifact.relative_to(ROOT).as_posix(),
            "sha256": checksum(artifact),
            "policies": policy,
            "fit_rows": len(fit),
            "fit_sources": int(fit.training_source.nunique()),
            "vocabulary_fit_rows": vocabulary_rows,
            "features": features,
            "classifier_iterations": int(classifier.n_iter_[0]),
            "calibration_slope": float(calibrator.coef_[0, 0]),
            "parity_cases": len(replay),
            "parity_max_delta": delta,
            "parameters_match_original": True,
            "elapsed_seconds": time.monotonic() - started,
        }
        write_json(
            checkpoint,
            {
                "completed_at_utc": now(),
                "data_freeze_sha256": checksum(RUN / "data-frozen.json"),
                "record": record,
                "result": result,
            },
        )
        records[name], results[name] = record, result
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
        del fit, encoder, classifier, calibrator, bundle
        gc.collect()
    check()
    write_json(
        RUN / "models-frozen.json",
        {
            "frozen_at_utc": now(),
            "data_freeze_sha256": checksum(RUN / "data-frozen.json"),
            "records": records,
            "development": results,
            "development_gate": improvement_gate(results[ARMS[0]], results[ARMS[1]]),
            "selection_performed": False,
            "test_used_for_fitting_or_selection": False,
            "production_ready": False,
        },
    )
    print(
        "Both prescribed models and native/matched policies frozen before historical replay",
        flush=True,
    )


def evaluate():
    if REPORT.exists():
        raise ValueError("current_retrain_evaluation_already_saved")
    p, data = check()
    frozen = read(RUN / "models-frozen.json")
    if frozen["data_freeze_sha256"] != checksum(RUN / "data-frozen.json"):
        raise ValueError("current_retrain_model_data_binding_changed")
    started_path = RUN / "evaluation-started.json"
    frozen_sha = checksum(RUN / "models-frozen.json")
    if (
        started_path.exists()
        and read(started_path)["models_freeze_sha256"] != frozen_sha
    ):
        raise ValueError("current_retrain_policy_changed_after_replay_started")
    if not started_path.exists():
        write_json(
            started_path, {"started_at_utc": now(), "models_freeze_sha256": frozen_sha}
        )
    original = RichArtifact()
    models = {}
    for name in ARMS:
        r = frozen["records"][name]
        verify_files({r["artifact"]: r["sha256"]})
        models[name] = joblib.load(ROOT / r["artifact"])
        assert_original_recipe(models[name], original.bundle)
    results, score_bindings = {}, {}
    for cohort in p["evaluation"]:
        a = data["tests"][cohort]
        frame, _ = transform_frame(pd.read_parquet(ROOT / a["path"]))
        scores = {"frozen_native": original.predict_cores(frame.core)}
        scores["frozen_matched_policy"] = scores["frozen_native"]
        scores.update(
            {
                name: predict_bundle(bundle, frame.core)
                for name, bundle in models.items()
            }
        )
        np.savez_compressed(RUN / (cohort + "-predictions.npz"), **scores)
        score_bindings[
            (RUN / (cohort + "-predictions.npz")).relative_to(ROOT).as_posix()
        ] = checksum(RUN / (cohort + "-predictions.npz"))
        levels, paired = {}, {}
        for level in ("warning", "high"):
            thresholds = {
                n: record["policies"][level]["threshold"]
                for n, record in frozen["records"].items()
            }
            levels[level] = {
                name: diagnostic_metrics(
                    frame, values, thresholds[name], p["bootstrap_repeats"], p["seed"]
                )
                for name, values in scores.items()
            }
            paired[level] = {
                name: paired_intervals(
                    frame,
                    scores[name],
                    scores[ARMS[1]],
                    [thresholds[name], thresholds[ARMS[1]]],
                    p["bootstrap_repeats"],
                    p["seed"],
                    frame.label.eq(1).all(),
                )
                for name in (ARMS[0], "frozen_native", "frozen_matched_policy")
            }
        groups = {
            name: {
                role: diagnostic_metrics(
                    frame.loc[mask],
                    values[mask.to_numpy()],
                    frozen["records"][role]["policies"]["warning"]["threshold"],
                    p["bootstrap_repeats"],
                    p["seed"],
                )
                for role, values in scores.items()
            }
            for name, mask in structure_masks(frame).items()
            if name != "id_suffix_proxy"
        }
        results[cohort] = {
            **coverage(frame),
            "previously_observed": True,
            "levels": levels,
            "paired_current_minus_reference": paired,
            "structures_warning": groups,
        }
        print(
            json.dumps(
                {
                    "evaluated": cohort,
                    "rows": len(frame),
                    "warning": {
                        n: {k: m[k] for k in ("recall", "fpr", "brier_score")}
                        for n, m in levels["warning"].items()
                    },
                }
            ),
            flush=True,
        )
    check()
    if checksum(RUN / "models-frozen.json") != frozen_sha:
        raise ValueError("current_retrain_model_freeze_changed_during_replay")
    write_json(
        REPORT,
        {
            "completed_at_utc": now(),
            "protocol_sha256": checksum(PROTOCOL),
            "models_freeze_sha256": frozen_sha,
            "records": frozen["records"],
            "development": frozen["development"],
            "development_gate": frozen["development_gate"],
            "fitting_coverage": {n: data["assets"][n] for n in ARMS},
            "cohorts": results,
            "score_bindings": score_bindings,
            "test_used_for_fitting_or_selection": False,
            "new_independent_test": False,
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
