"""Isolated predeclared segmented-URL LR experiment; frozen service is unchanged."""

import argparse
import gc
import json

import joblib
import numpy as np
import pandas as pd
from scipy.sparse import load_npz, save_npz, vstack
from sklearn.linear_model import LogisticRegression
from threadpoolctl import threadpool_limits

from guardian_ml.metadata import checksum
from guardian_ml.paths import ROOT
from guardian_ml.rich_artifact import RichArtifact
from evaluate_v6_quality import domain_intervals
from experiment_v6_development import checked_fit, matrix_batches, paired_intervals
from experiment_v6_expanded_data import now, write_json
import experiment_v6_weighted as previous
from v6_development_support import assert_separated, representation_digest
from v6_diagnostic_support import safe_metrics
from v6_segmented_support import (
    calibrated,
    choose_candidate,
    combine_matrix,
    extra_matrix,
    fit_calibrator,
    fit_segment_encoder,
    predict_segmented,
)
from v6_weighted_support import classifier_weights, structural_audit, summarize_tune

PROTOCOL = ROOT / "ml/reports/v6-segmented-20261105-protocol.json"
AMENDMENT = ROOT / "ml/reports/v6-segmented-source-amendment.json"
RUN = ROOT / "ml/runs/v6-segmented-20261105"
REPORT = ROOT / "ml/reports/v6-segmented-evaluation.json"
PARTS = ("fit", "calibration", "threshold", "tune")
SOURCES = previous.SOURCES + [
    "scripts/experiment_v6_segmented.py",
    "scripts/v6_segmented_support.py",
    "scripts/intake_v6_segmented.py",
    "ml/src/guardian_ml/features.py",
    "scripts/intake_v6_phishbench.py",
    "scripts/v6_pinned_download.py",
]


def read(path):
    return json.loads(path.read_text())


def bindings():
    return {name: checksum(ROOT / name) for name in SOURCES}


def old_state():
    cache, selected = previous.check_selected(read(previous.PROTOCOL))
    record = selected["records"][selected["selection"]["selected"]]
    return cache, selected, record


def wrap_native(bundle):
    return {
        **bundle,
        "feature_mode": "control",
        "calibration_kind": "source_equal_sigmoid",
    }


def load_bundle(record):
    if checksum(ROOT / record["artifact"]) != record["artifact_sha256"]:
        raise ValueError("segmented_artifact_changed")
    bundle = joblib.load(ROOT / record["artifact"])
    return wrap_native(bundle) if record.get("native") else bundle


def check_intake(path):
    frozen = read(path)
    if checksum(ROOT / frozen["protocol_path"]) != frozen["protocol_sha256"]:
        raise ValueError("segmented_intake_protocol_changed")
    for name, sha in {
        **frozen["source_hashes"],
        **frozen["prior_exposure_hashes"],
    }.items():
        if checksum(ROOT / name) != sha:
            raise ValueError("segmented_intake_source_or_exposure_changed")
    for asset in [frozen["sidecar"], *frozen["partitions"].values()]:
        if checksum(ROOT / asset["path"]) != asset["sha256"]:
            raise ValueError("segmented_intake_asset_changed")
    if checksum(ROOT / frozen["supported_path"]) != frozen["supported_sha256"]:
        raise ValueError("segmented_supported_intake_changed")
    return {
        "path": path.relative_to(ROOT).as_posix(),
        "sha256": checksum(path),
        "data": frozen,
    }


def extras_batched(encoder, frame):
    return vstack(
        [
            extra_matrix(encoder, frame.core.iloc[start : start + 4096])
            for start in range(0, len(frame), 4096)
        ],
        format="csr",
    )


def observed_paths():
    return {
        "observed_zenodo_websites_v2": ROOT
        / "ml/data/v6-weighted-new-holdout/holdout.parquet",
        "observed_pwd": previous.previous.RUN / "new_test.parquet",
        "observed_expanded": previous.previous.OLD / "new_test.parquet",
        "observed_vendor": ROOT
        / "ml/runs/notebook-tfidf-logistic-v6/data/deepurlbench-holdout-v6.parquet",
        "observed_phishtank_positive": ROOT
        / "ml/runs/notebook-tfidf-logistic-v6/data/phishtank-2026-v6.parquet",
        "observed_legitphish": ROOT
        / "ml/data/legitphish-v2-v6-qa/sanitized-domain-disjoint.parquet",
    }


def prepare(protocol):
    if (RUN / "cache-frozen.json").exists():
        raise ValueError("segmented_cache_already_frozen")
    cache, selected, record = old_state()
    amendment = read(AMENDMENT)
    if checksum(PROTOCOL) != amendment["parent_sha256"]:
        raise ValueError("segmented_parent_changed")
    intake = check_intake(ROOT / protocol["new_holdout_freeze"])
    phishbench_path = ROOT / "ml/data/v6-segmented-phishbench/frozen.json"
    phishbench = check_intake(phishbench_path) if phishbench_path.exists() else None
    RUN.mkdir(parents=True, exist_ok=True)
    initial = {
        "started_at_utc": now(),
        "protocol_sha256": checksum(PROTOCOL),
        "amendment_sha256": checksum(AMENDMENT),
        "source_hashes": bindings(),
        "previous_selection_sha256": checksum(previous.RUN / "selected-frozen.json"),
        "intake": intake,
        "phishbench": phishbench,
        "all_current_sidecars": {
            p.relative_to(ROOT).as_posix(): checksum(p)
            for p in sorted((ROOT / "ml/data/exposure-sidecars").glob("*.sqlite"))
        },
    }
    write_json(RUN / "cache-started.json", initial)
    original = RichArtifact()
    fit = pd.read_parquet(ROOT / cache["assets"]["fit"]["input_path"])
    if len(fit) != protocol["fitting_rows"]:
        raise ValueError("segmented_original_fit_rows_changed")
    new_fit = pd.read_parquet(ROOT / intake["data"]["partitions"]["fit"]["path"])
    new_test = pd.read_parquet(ROOT / intake["data"]["partitions"]["new_test"]["path"])
    original_parts = [
        pd.read_parquet(
            ROOT / asset["input_path"],
            columns=["group", "digest", "representation_digest"],
        )
        for asset in cache["assets"].values()
    ]
    assert_separated([*original_parts, new_fit, new_test])
    new_frames = [new_fit, new_test]
    if phishbench:
        new_frames.append(
            pd.read_parquet(ROOT / phishbench["data"]["partitions"]["new_test"]["path"])
        )
        assert_separated(
            [
                *original_parts,
                new_fit,
                new_test,
                pd.read_parquet(
                    ROOT / phishbench["data"]["partitions"]["new_test"]["path"]
                ),
            ]
        )
    observed_bindings = {}
    for path in observed_paths().values():
        identities = pd.read_parquet(path, columns=["core", "group", "digest"])
        identities["representation_digest"] = identities.core.map(representation_digest)
        for fresh in new_frames:
            assert_separated([identities, fresh])
        observed_bindings[path.relative_to(ROOT).as_posix()] = checksum(path)
    del original_parts, new_frames, identities
    print(
        "Fitting host/subdomain/path vocabulary and numeric scaler on original fitting only",
        flush=True,
    )
    encoder = fit_segment_encoder(fit, protocol["new_encoder"], protocol["seed"])
    encoder_path = RUN / "segment-encoder.joblib"
    joblib.dump(encoder, encoder_path, compress=3)
    assets = {}
    for name in PARTS:
        frame = (
            fit
            if name == "fit"
            else pd.read_parquet(ROOT / cache["assets"][name]["input_path"])
        )
        print("Caching new feature views: " + name, flush=True)
        matrix = extras_batched(encoder, frame)
        path = RUN / (name + "-extra.npz")
        save_npz(path, matrix, compressed=False)
        assets[name] = {
            **cache["assets"][name],
            "extra_path": path.relative_to(ROOT).as_posix(),
            "extra_sha256": checksum(path),
            "extra_features": int(matrix.shape[1]),
            "extra_nonzero": int(matrix.nnz),
        }
        del matrix
        gc.collect()
    minimum = amendment["augmentation_arm"]["minimum_new_fit_per_class"]
    counts = new_fit.label.value_counts()
    augmentation = all(counts.get(label, 0) >= minimum for label in (0, 1))
    control = load_bundle({**record, "native": True})
    if augmentation:
        print(
            "Caching new-source fitting rows for separate augmentation arm", flush=True
        )
        # New raw intake is already sanitized with exactly the experiment representation.
        for kind, matrix in [
            ("base", matrix_batches(control["encoder"], new_fit)),
            ("extra", extras_batched(encoder, new_fit)),
        ]:
            path = RUN / ("augmentation-" + kind + ".npz")
            save_npz(path, matrix, compressed=False)
            assets["augmentation_" + kind] = {
                "path": path.relative_to(ROOT).as_posix(),
                "sha256": checksum(path),
            }
            del matrix
    matrix = load_npz(ROOT / cache["assets"]["tune"]["matrix_path"])
    tune = pd.read_parquet(ROOT / cache["assets"]["tune"]["input_path"])
    raw = control["classifier"].predict_proba(matrix)[:, 1]
    score = calibrated(raw, control["calibrator"], control["calibration_kind"])
    direct = predict_segmented(control, tune.core.iloc[:128])
    if not np.allclose(direct, score[:128], rtol=0, atol=1e-12):
        raise ValueError("segmented_native_cache_parity_failed")
    native_policies = record["policies"]
    summary = summarize_tune(
        tune, score, native_policies["strict"]["threshold"], protocol
    )
    expected = selected["tune"][selected["selection"]["selected"]]["overall"][
        "confusion_matrix"
    ]
    if summary["overall"]["confusion_matrix"] != expected:
        raise ValueError("segmented_native_full_tune_replay_changed")
    if initial["source_hashes"] != bindings():
        raise ValueError("segmented_source_changed_during_caching")
    write_json(
        RUN / "cache-frozen.json",
        {
            **initial,
            "frozen_at_utc": now(),
            "base_cache": cache,
            "assets": assets,
            "encoder_path": encoder_path.relative_to(ROOT).as_posix(),
            "encoder_sha256": checksum(encoder_path),
            "encoder_fit_rows": len(fit),
            "encoder_vocabulary_sample_rows": encoder["vocabulary_sample_rows"],
            "augmentation_available": augmentation,
            "new_fit_counts": {str(k): int(v) for k, v in counts.items()},
            "native_record": {**record, "native": True},
            "native_tune": summary,
            "max_native_cached_delta": float(np.max(np.abs(direct - score[:128]))),
            "original_v6_sha256": checksum(
                ROOT
                / "ml/runs/notebook-tfidf-logistic-v6/artifacts/url-core-logistic-v6.joblib"
            ),
            "original_v6_warning": original.metadata["thresholds"]["warning"],
            "observed_test_bindings": observed_bindings,
            "isolation": {
                "original_partitions": 4,
                "new_fit_vs_new_test": True,
                "additional_publisher_checked": bool(phishbench),
                "overlaps": 0,
            },
            "transformations_fitted_on_holdouts": False,
            "production_ready": False,
        },
    )
    print("Segmented feature/data cache frozen", flush=True)


def check_cache():
    frozen = read(RUN / "cache-frozen.json")
    if (
        frozen["protocol_sha256"] != checksum(PROTOCOL)
        or frozen["amendment_sha256"] != checksum(AMENDMENT)
        or frozen["source_hashes"] != bindings()
    ):
        raise ValueError("segmented_frozen_source_or_protocol_changed")
    old_state()
    if (
        checksum(previous.RUN / "selected-frozen.json")
        != frozen["previous_selection_sha256"]
    ):
        raise ValueError("segmented_previous_selection_changed")
    for item in frozen["assets"].values():
        for path_key, sha_key in (("path", "sha256"), ("extra_path", "extra_sha256")):
            if path_key in item and checksum(ROOT / item[path_key]) != item[sha_key]:
                raise ValueError("segmented_cached_matrix_changed")
    if checksum(ROOT / frozen["encoder_path"]) != frozen["encoder_sha256"]:
        raise ValueError("segmented_encoder_changed")
    for item in (frozen["intake"], frozen["phishbench"]):
        if item and check_intake(ROOT / item["path"]) != item:
            raise ValueError("segmented_intake_binding_changed")
    for name, sha in frozen["observed_test_bindings"].items():
        if checksum(ROOT / name) != sha:
            raise ValueError("segmented_observed_test_changed")
    sidecars = {
        p.relative_to(ROOT).as_posix(): checksum(p)
        for p in sorted((ROOT / "ml/data/exposure-sidecars").glob("*.sqlite"))
    }
    if sidecars != frozen["all_current_sidecars"]:
        raise ValueError("segmented_sidecar_inventory_changed")
    return frozen


def stage_matrices(cache, encoder, mode, parts):
    return {
        name: combine_matrix(
            load_npz(ROOT / cache["assets"][name]["matrix_path"]),
            load_npz(ROOT / cache["assets"][name]["extra_path"]),
            encoder,
            mode,
        )
        for name in parts
    }


def train(protocol):
    if (RUN / "selected-frozen.json").exists():
        raise ValueError("segmented_selection_already_frozen")
    cache = check_cache()
    write_json(
        RUN / "training-started.json",
        {"started_at_utc": now(), "cache_sha256": checksum(RUN / "cache-frozen.json")},
    )
    frames = {
        name: pd.read_parquet(
            ROOT / cache["assets"][name]["input_path"],
            columns=["partition", "label", "group", "training_source"],
        )
        for name in PARTS
    }
    native = load_bundle(cache["native_record"])
    encoder = joblib.load(ROOT / cache["encoder_path"])
    results = {"control_native": cache["native_tune"]}
    records = {"control_native": cache["native_record"]}
    modes = ["control_beta", *protocol["feature_modes"]]
    if cache["augmentation_available"]:
        modes.append("segmented_text_structure_augmented")
    for name in modes:
        completed = RUN / (name + "-completed.json")
        if completed.exists():
            checkpoint = read(completed)
            if checkpoint["cache_sha256"] != checksum(RUN / "cache-frozen.json"):
                raise ValueError("segmented_checkpoint_changed")
            for record in checkpoint["records"].values():
                load_bundle(record)
            records.update(checkpoint["records"])
            results.update(checkpoint["results"])
            continue
        feature_mode = (
            "control" if name == "control_beta" else name.removesuffix("_augmented")
        )
        if name == "control_beta":
            classifier = native["classifier"]
            matrices = {
                part: load_npz(ROOT / cache["assets"][part]["matrix_path"])
                for part in PARTS
                if part != "fit"
            }
        else:
            print("Training Logistic Regression: " + name, flush=True)
            matrices = stage_matrices(cache, encoder, feature_mode, ["fit"])
            fitting = frames["fit"]
            if name.endswith("_augmented"):
                new_fit = pd.read_parquet(
                    ROOT / cache["intake"]["data"]["partitions"]["fit"]["path"]
                )
                fitting = pd.concat([fitting, new_fit], ignore_index=True)
                extra_fit = combine_matrix(
                    load_npz(ROOT / cache["assets"]["augmentation_base"]["path"]),
                    load_npz(ROOT / cache["assets"]["augmentation_extra"]["path"]),
                    encoder,
                    feature_mode,
                )
                matrices["fit"] = vstack([matrices["fit"], extra_fit], format="csr")
                del extra_fit, new_fit
            classifier = LogisticRegression(
                random_state=protocol["seed"], **protocol["classifier"]
            )
            checked_fit(
                classifier,
                matrices["fit"],
                fitting.label,
                sample_weight=classifier_weights(fitting, "source_equal_domain_sqrt"),
            )
            fit_rows = len(fitting)
            del matrices, fitting
            gc.collect()
            matrices = stage_matrices(
                cache, encoder, feature_mode, ["calibration", "threshold", "tune"]
            )
        raw = {
            part: classifier.predict_proba(matrix)[:, 1]
            for part, matrix in matrices.items()
        }
        del matrices
        gc.collect()
        group_results, group_records = {}, {}
        for kind in (
            ["source_equal_beta"] if name == "control_beta" else protocol["calibrators"]
        ):
            identity = name + "__" + kind
            try:
                calibrator = fit_calibrator(
                    frames["calibration"], raw["calibration"], kind, protocol["seed"]
                )
            except ValueError as error:
                if str(error) != "calibration_not_strictly_monotone":
                    raise
                group_results[identity] = {"invalid": "nonmonotone_calibrator_rejected"}
                continue
            points = previous.matrix_points(
                frames["threshold"],
                calibrated(raw["threshold"], calibrator, kind),
                protocol,
            )
            score = calibrated(raw["tune"], calibrator, kind)
            summary = summarize_tune(
                frames["tune"], score, points["strict"]["threshold"], protocol
            )
            bundle = {
                "encoder": native["encoder"],
                "segment_encoder": encoder,
                "feature_mode": feature_mode,
                "classifier": classifier,
                "calibrator": calibrator,
                "calibration_kind": kind,
                "metadata": {
                    "version": "v6-segmented-20261105-" + identity,
                    "policies": points,
                    "protocol_sha256": checksum(PROTOCOL),
                    "amendment_sha256": checksum(AMENDMENT),
                    "fit_rows": protocol["fitting_rows"]
                    if name == "control_beta"
                    else fit_rows,
                    "production_ready": False,
                    "research_noncommercial_only": True,
                },
            }
            path = RUN / (identity + ".joblib")
            joblib.dump(bundle, path, compress=3)
            group_records[identity] = {
                "artifact": path.relative_to(ROOT).as_posix(),
                "artifact_sha256": checksum(path),
                "policies": points,
                "fit_rows": bundle["metadata"]["fit_rows"],
                "iterations": int(classifier.n_iter_[0]),
                "converged": True,
            }
            group_results[identity] = summary
            print(
                json.dumps(
                    {
                        "candidate": identity,
                        "macro_recall": summary["macro_source_recall"],
                        "macro_brier": summary["macro_source_brier"],
                    }
                ),
                flush=True,
            )
        write_json(
            completed,
            {
                "cache_sha256": checksum(RUN / "cache-frozen.json"),
                "results": group_results,
                "records": group_records,
            },
        )
        records.update(group_records)
        results.update(group_results)
        del classifier, raw
        gc.collect()
    selection = choose_candidate(
        results, results["control_native"], protocol["selection"]
    )
    candidate_name = selection["diagnostic"] or "control_native"
    candidate = load_bundle(records[candidate_name])
    cores = (
        pd.read_parquet(ROOT / cache["assets"]["tune"]["input_path"], columns=["core"])
        .core.iloc[:128]
        .tolist()
    )
    probes = cores + [
        "http://example.org/password=SHORTSECRET",
        "https://example.org/password=SHORTSECRET",
    ]
    scores = predict_segmented(candidate, probes)
    restored = load_bundle(records[candidate_name])
    delta = float(np.max(np.abs(scores - predict_segmented(restored, probes))))
    if delta != 0 or scores[-1] != scores[-2]:
        raise ValueError("segmented_saved_or_scheme_parity_failed")
    if candidate["feature_mode"] == "control":
        probe_matrix = load_npz(ROOT / cache["assets"]["tune"]["matrix_path"])[:128]
    else:
        probe_matrix = stage_matrices(
            cache, encoder, candidate["feature_mode"], ["tune"]
        )["tune"][:128]
    cached = calibrated(
        candidate["classifier"].predict_proba(probe_matrix)[:, 1],
        candidate["calibrator"],
        candidate["calibration_kind"],
    )
    cache_delta = float(np.max(np.abs(cached - scores[:128])))
    if cache_delta > 1e-12:
        raise ValueError("segmented_real_cached_inference_parity_failed")
    check_cache()
    write_json(
        RUN / "selected-frozen.json",
        {
            "frozen_at_utc": now(),
            "cache_sha256": checksum(RUN / "cache-frozen.json"),
            "selection": selection,
            "records": records,
            "tune": results,
            "parity_cases": len(probes),
            "max_saved_prediction_delta": delta,
            "max_cached_inference_delta": cache_delta,
            "evaluated_candidate": candidate_name,
            "test_used_for_selection": False,
            "production_ready": False,
        },
    )
    print(json.dumps(selection), flush=True)


def check_selected():
    cache = check_cache()
    selected = read(RUN / "selected-frozen.json")
    if checksum(RUN / "cache-frozen.json") != selected["cache_sha256"]:
        raise ValueError("segmented_selection_inputs_changed")
    for record in selected["records"].values():
        if checksum(ROOT / record["artifact"]) != record["artifact_sha256"]:
            raise ValueError("segmented_selected_artifact_changed")
    return cache, selected


def evaluate(protocol):
    if REPORT.exists():
        raise ValueError("segmented_final_evaluation_already_completed")
    cache, selected = check_selected()
    write_json(
        RUN / "evaluation-started.json",
        {
            "started_at_utc": now(),
            "selection_sha256": checksum(RUN / "selected-frozen.json"),
        },
    )
    control_record = selected["records"]["control_native"]
    candidate_record = selected["records"][selected["evaluated_candidate"]]
    control, candidate, active = (
        load_bundle(control_record),
        load_bundle(candidate_record),
        RichArtifact(),
    )
    paths = {
        "new_stealth_domain_holdout": ROOT
        / cache["intake"]["data"]["partitions"]["new_test"]["path"],
        "observed_zenodo_websites_v2": ROOT
        / "ml/data/v6-weighted-new-holdout/holdout.parquet",
        "observed_pwd": previous.previous.RUN / "new_test.parquet",
        "observed_expanded": previous.previous.OLD / "new_test.parquet",
        "observed_vendor": ROOT
        / "ml/runs/notebook-tfidf-logistic-v6/data/deepurlbench-holdout-v6.parquet",
        "observed_phishtank_positive": ROOT
        / "ml/runs/notebook-tfidf-logistic-v6/data/phishtank-2026-v6.parquet",
        "observed_legitphish": ROOT
        / "ml/data/legitphish-v2-v6-qa/sanitized-domain-disjoint.parquet",
    }
    if cache["phishbench"]:
        paths = {
            "new_phishbench_publisher_holdout": ROOT
            / cache["phishbench"]["data"]["partitions"]["new_test"]["path"],
            **paths,
        }
    policies = {
        "active_original": ("active", active.metadata["thresholds"]["warning"]),
        "control_strict": (
            "control",
            control_record["policies"]["strict"]["threshold"],
        ),
        "candidate_strict": (
            "candidate",
            candidate_record["policies"]["strict"]["threshold"],
        ),
        "control_pooled": (
            "control",
            control_record["policies"]["pooled"]["threshold"],
        ),
        "candidate_pooled": (
            "candidate",
            candidate_record["policies"]["pooled"]["threshold"],
        ),
    }
    cohorts = {}
    for name, path in paths.items():
        frame = pd.read_parquet(path)
        if frame.empty:
            cohorts[name] = {"rows": 0, "not_evaluated": "no_novel_supported_rows"}
            continue
        positive, both = frame.label.eq(1).all(), set(frame.label) == {0, 1}
        scores = {
            "active": active.predict_cores(frame.core),
            "control": predict_segmented(control, frame.core),
            "candidate": predict_segmented(candidate, frame.core),
        }
        np.savez_compressed(RUN / (name + "-predictions.npz"), **scores)
        metrics = {}
        for role, (model, threshold) in policies.items():
            row = safe_metrics(frame, scores[model], threshold, positive_only=positive)
            if positive or both:
                row["domain_bootstrap95"] = domain_intervals(
                    frame,
                    scores[model],
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
                        policies[
                            "active_original" if role == "active" else "control_strict"
                        ][1],
                        policies["candidate_strict"][1],
                    ],
                    protocol["bootstrap_repeats"],
                    protocol["seed"],
                    positive,
                )
                for role in ("active", "control")
            }
            if positive or both
            else {}
        )
        cohorts[name] = {
            "path": path.relative_to(ROOT).as_posix(),
            "sha256": checksum(path),
            "rows": len(frame),
            "groups": int(frame.group.nunique()),
            "previously_observed": name.startswith("observed_"),
            "classes": {str(k): int(v) for k, v in frame.label.value_counts().items()},
            "policies": metrics,
            "paired_candidate_minus": paired,
        }
        print("Evaluated segmented study: " + name, flush=True)
    check_selected()
    write_json(
        REPORT,
        {
            "completed_at_utc": now(),
            "cache_freeze": cache,
            "selected_freeze": selected,
            "cohorts": cohorts,
            "Indonesia_inputs": previous.inventory(),
            "original_v6_unchanged": True,
            "test_results_used_for_selection": False,
            "production_ready": False,
            "human_labels_fabricated": False,
        },
    )


def diagnose(protocol):
    cache, selected = check_selected()
    tune = pd.read_parquet(ROOT / cache["assets"]["tune"]["input_path"])
    results = {}
    for name in ("control_native", selected["evaluated_candidate"]):
        record = selected["records"][name]
        scores = predict_segmented(load_bundle(record), tune.core)
        results[name] = structural_audit(
            tune, scores, record["policies"]["strict"]["threshold"]
        )
    write_json(
        ROOT / "ml/reports/v6-segmented-subgroup-diagnostics.json",
        {
            "completed_at_utc": now(),
            "selected_freeze_sha256": checksum(RUN / "selected-frozen.json"),
            "selection_already_frozen": True,
            "used_to_change_selection": False,
            "structural": results,
        },
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--stage", choices=["prepare", "train", "diagnose", "evaluate"], required=True
    )
    args = parser.parse_args()
    with threadpool_limits(limits=2):
        {
            "prepare": prepare,
            "train": train,
            "diagnose": diagnose,
            "evaluate": evaluate,
        }[args.stage](read(PROTOCOL))


if __name__ == "__main__":
    main()
