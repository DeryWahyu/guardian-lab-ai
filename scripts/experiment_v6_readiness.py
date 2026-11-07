"""Publisher-license screening and private-host LR research; no runtime promotion."""

import argparse
import gc

import joblib
import numpy as np
import pandas as pd
from scipy.special import logit
from sklearn.base import clone
from threadpoolctl import threadpool_limits

from guardian_ml.metadata import checksum
from guardian_ml.paths import ROOT
from guardian_ml.rich_artifact import RichArtifact
from experiment_v6_development import checked_fit, matrix_batches, paired_intervals
from experiment_v6_expanded_data import now, write_json
import experiment_v6_current_retrain as parent
from v6_current_retrain_support import fit_original_encoder, assert_original_recipe
from v6_development_support import (
    fit_weights,
    source_threshold,
    transform_frame,
)
from v6_indonesia_external_support import coverage, structure_masks
from v6_readiness_support import (
    filtered,
    private_weights,
    private_cutoff,
    decisions,
    routed_metrics,
    development,
    choose,
)

PROTOCOL = ROOT / "ml/reports/v6-readiness-20261107-protocol.json"
RUN = ROOT / "ml/runs/v6-readiness-20261107"
REPORT = ROOT / "ml/reports/v6-readiness-model-evaluation.json"
PARTS = ("fit", "calibration", "threshold", "tune")


def bindings():
    names = set(parent.bindings()) | {
        "scripts/experiment_v6_readiness.py",
        "scripts/v6_readiness_support.py",
    }
    return {n: checksum(ROOT / n) for n in sorted(names)}


def prepare():
    if RUN.exists():
        raise ValueError("readiness_requires_new_run")
    protocol = parent.read(PROTOCOL)
    _, old = parent.check()
    initial = bindings()
    RUN.mkdir(parents=True)
    assets = {}
    for part in PARTS:
        old_name = "current_v6_recipe" if part == "fit" else part
        frame = filtered(
            pd.read_parquet(ROOT / old["assets"][old_name]["path"]), protocol
        )
        if part == "fit" and len(frame) != protocol["expected_fitting_rows"]:
            raise ValueError("license_filtered_fit_count_mismatch")
        private = structure_masks(frame)["private_hosting"].to_numpy()
        path = RUN / (part + ".parquet")
        frame.to_parquet(path, index=False)
        assets[part] = {
            "path": path.relative_to(ROOT).as_posix(),
            "sha256": checksum(path),
            **coverage(frame),
            "private_counts": {
                str(y): int((frame.label.eq(y).to_numpy() & private).sum())
                for y in (0, 1)
            },
            "source_counts": {
                str(s): int(n) for s, n in frame.training_source.value_counts().items()
            },
        }
    if bindings() != initial:
        raise ValueError("readiness_sources_changed_during_prepare")
    write_json(
        RUN / "data-frozen.json",
        {
            "prepared_at_utc": now(),
            "protocol_sha256": checksum(PROTOCOL),
            "source_hashes": initial,
            "parent_data_sha256": checksum(parent.RUN / "data-frozen.json"),
            "parent_report_sha256": checksum(parent.REPORT),
            "parent_models_sha256": checksum(parent.RUN / "models-frozen.json"),
            "assets": assets,
            "exposure": old["all_sidecars"],
            "isolation": old["isolation"],
            "production_ready": False,
        },
    )
    print(
        {
            "filtered_fit_rows": assets["fit"]["rows"],
            "private_fit_classes": assets["fit"]["private_counts"],
        },
        flush=True,
    )


def check():
    data, p = parent.read(RUN / "data-frozen.json"), parent.read(PROTOCOL)
    if (
        data["source_hashes"] != bindings()
        or data["protocol_sha256"] != checksum(PROTOCOL)
        or data["parent_data_sha256"] != checksum(parent.RUN / "data-frozen.json")
        or data["parent_report_sha256"] != checksum(parent.REPORT)
        or data["parent_models_sha256"] != checksum(parent.RUN / "models-frozen.json")
        or data["exposure"] != parent.prior.sidecars()
    ):
        raise ValueError("readiness_inputs_changed")
    parent.verify_files(data["exposure"])
    parent.verify_files(parent.read(parent.RUN / "data-frozen.json")["inputs"])
    parent.verify_files({a["path"]: a["sha256"] for a in data["assets"].values()})
    original = RichArtifact()
    return p, data, original


def score_matrix(bundle, matrix):
    raw = bundle["classifier"].predict_proba(matrix)[:, 1]
    return bundle["calibrator"].predict_proba(
        logit(np.clip(raw, 1e-7, 1 - 1e-7)).reshape(-1, 1)
    )[:, 1]


def general_policies(frame, scores, p):
    base = {
        level: source_threshold(frame, scores, budget, "threshold")["threshold"]
        for level, budget in p["thresholds"].items()
    }
    return {"general": base, "private": dict(base)}


def matched_policies(frame, scores, p, general):
    return {
        "general": general["general"],
        "private": {
            level: private_cutoff(frame, scores, budget)
            for level, budget in p["thresholds"].items()
        },
    }


def train():
    if (RUN / "models-frozen.json").exists():
        raise ValueError("readiness_models_already_frozen")
    p, data, original = check()
    frames = {
        part: pd.read_parquet(ROOT / a["path"]) for part, a in data["assets"].items()
    }
    masks = {
        part: structure_masks(f)["private_hosting"].to_numpy()
        for part, f in frames.items()
    }
    for part in ("fit", "calibration", "threshold"):
        sub = frames[part].loc[masks[part]]
        if min(int(sub.label.eq(y).sum()) for y in (0, 1)) < 100:
            raise ValueError("private_host_evidence_insufficient")
    baseline_path = RUN / "baseline.joblib"
    if baseline_path.exists():
        raise ValueError("use_new_run_for_incomplete_baseline_training")
    print(
        "Training from scratch on publisher-license-filtered fitting only", flush=True
    )
    encoder, vocab_rows = fit_original_encoder(original.bundle, frames["fit"], p)
    matrix = matrix_batches(encoder, frames["fit"])
    classifier = clone(original.bundle["classifier"])
    checked_fit(
        classifier,
        matrix,
        frames["fit"].label,
        sample_weight=fit_weights(frames["fit"], "source_sqrt"),
    )
    del matrix
    gc.collect()
    matrices = {part: matrix_batches(encoder, frames[part]) for part in PARTS[1:]}
    raw = classifier.predict_proba(matrices["calibration"])[:, 1]
    calibrator = clone(original.bundle["calibrator"])
    checked_fit(
        calibrator,
        logit(np.clip(raw, 1e-7, 1 - 1e-7)).reshape(-1, 1),
        frames["calibration"].label,
    )
    if calibrator.coef_[0, 0] <= 0:
        raise ValueError("invalid_baseline_calibration_slope")
    base = {
        "encoder": encoder,
        "classifier": classifier,
        "calibrator": calibrator,
        "metadata": {
            "version": "v6-license-screened-research-20261107",
            "production_ready": False,
            "publisher_license_filter_not_legal_clearance": True,
            "no_borrowed_fitted_state": True,
        },
    }
    assert_original_recipe(base, original.bundle)
    scores = {part: score_matrix(base, x) for part, x in matrices.items()}
    policy = general_policies(frames["threshold"], scores["threshold"], p)
    base["metadata"]["policies"] = policy
    joblib.dump(base, baseline_path, compress=3)
    records = {
        "baseline": {
            "artifact": baseline_path.relative_to(ROOT).as_posix(),
            "sha256": checksum(baseline_path),
            "policies": policy,
            "vocabulary_rows": vocab_rows,
        }
    }
    matched = matched_policies(
        frames["threshold"].loc[masks["threshold"]],
        scores["threshold"][masks["threshold"]],
        p,
        policy,
    )
    records["private_matched"] = {**records["baseline"], "policies": matched}
    results = {
        name: development(
            frames["tune"],
            scores["tune"],
            decisions(scores["tune"], masks["tune"], r["policies"]),
            masks["tune"],
            r["policies"],
            p,
        )
        for name, r in records.items()
    }
    private_fit = frames["fit"].loc[masks["fit"]].reset_index(drop=True)
    private_matrix = matrix_batches(encoder, private_fit)
    for spec in p["experts"]:
        clf = clone(original.bundle["classifier"]).set_params(C=spec["C"])
        checked_fit(
            clf,
            private_matrix,
            private_fit.label,
            sample_weight=private_weights(private_fit),
        )
        raw = clf.predict_proba(matrices["calibration"][masks["calibration"]])[:, 1]
        cal = clone(original.bundle["calibrator"])
        checked_fit(
            cal,
            logit(np.clip(raw, 1e-7, 1 - 1e-7)).reshape(-1, 1),
            frames["calibration"].label.to_numpy()[masks["calibration"]],
        )
        if cal.coef_[0, 0] <= 0:
            raise ValueError("invalid_expert_calibration_slope")
        expert = {
            "classifier": clf,
            "calibrator": cal,
            "metadata": {
                "production_ready": False,
                "baseline_sha256": checksum(baseline_path),
                "C": spec["C"],
            },
        }
        pt = score_matrix(expert, matrices["threshold"][masks["threshold"]])
        ep = matched_policies(
            frames["threshold"].loc[masks["threshold"]], pt, p, policy
        )
        combined = scores["tune"].copy()
        combined[masks["tune"]] = score_matrix(expert, matrices["tune"][masks["tune"]])
        expert["metadata"]["policies"] = ep
        path = RUN / (spec["name"] + ".joblib")
        joblib.dump(expert, path, compress=3)
        records[spec["name"]] = {
            "artifact": path.relative_to(ROOT).as_posix(),
            "sha256": checksum(path),
            "policies": ep,
            "private_fit_rows": len(private_fit),
        }
        results[spec["name"]] = development(
            frames["tune"],
            combined,
            decisions(combined, masks["tune"], ep),
            masks["tune"],
            ep,
            p,
        )
        print(
            {
                "expert": spec["name"],
                "private_recall": results[spec["name"]]["private"]["recall"],
                "private_fpr": results[spec["name"]]["private"]["fpr"],
            },
            flush=True,
        )
    selection = choose(results)
    check()
    write_json(
        RUN / "models-frozen.json",
        {
            "frozen_at_utc": now(),
            "data_sha256": checksum(RUN / "data-frozen.json"),
            "records": records,
            "development": results,
            "selection": selection,
            "production_ready": False,
        },
    )
    print({"selection": selection}, flush=True)


def evaluate():
    if REPORT.exists():
        raise ValueError("readiness_report_already_exists")
    p, data, original = check()
    frozen = parent.read(RUN / "models-frozen.json")
    if frozen["data_sha256"] != checksum(RUN / "data-frozen.json"):
        raise ValueError("readiness_model_data_binding_changed")
    freeze_sha = checksum(RUN / "models-frozen.json")
    write_json(
        RUN / "evaluation-started.json",
        {"started_at_utc": now(), "models_sha256": freeze_sha},
    )
    old_data = parent.read(parent.RUN / "data-frozen.json")
    old_report = parent.read(parent.REPORT)
    name = frozen["selection"]["diagnostic"]
    base = joblib.load(ROOT / frozen["records"]["baseline"]["artifact"])
    expert = joblib.load(ROOT / frozen["records"][name]["artifact"])
    cohorts, saved = {}, {}
    for cohort, item in old_data["tests"].items():
        frame, _ = transform_frame(pd.read_parquet(ROOT / item["path"]))
        private = structure_masks(frame)["private_hosting"].to_numpy()
        matrix = matrix_batches(base["encoder"], frame)
        probability = score_matrix(base, matrix)
        routed = probability.copy()
        if private.any():
            routed[private] = score_matrix(expert, matrix[private])
        del matrix
        old_score_path = parent.RUN / (cohort + "-predictions.npz")
        parent.verify_files(
            {
                old_score_path.relative_to(ROOT).as_posix(): old_report[
                    "score_bindings"
                ][old_score_path.relative_to(ROOT).as_posix()]
            }
        )
        old_scores = np.load(old_score_path)
        probabilities = {
            "baseline": probability,
            "private_matched": probability,
            name: routed,
            "previous_current": old_scores["current_v6_recipe"],
            "frozen_v6": old_scores["frozen_native"],
        }
        policies = {
            role: rec["policies"]
            for role, rec in frozen["records"].items()
            if role in probabilities
        }
        for role, old_role in (
            ("previous_current", "current_v6_recipe"),
            ("frozen_v6", "frozen_native"),
        ):
            threshold = {
                lev: r["threshold"]
                for lev, r in old_report["records"][old_role]["policies"].items()
            }
            policies[role] = {"general": threshold, "private": threshold}
        np.savez_compressed(
            RUN / (cohort + "-scores.npz"), private=private, **probabilities
        )
        saved[(RUN / (cohort + "-scores.npz")).relative_to(ROOT).as_posix()] = checksum(
            RUN / (cohort + "-scores.npz")
        )
        levels, pairs = {}, {}
        for level in ("warning", "high"):
            flags = {
                role: decisions(values, private, policies[role], level)
                for role, values in probabilities.items()
            }
            levels[level] = {
                role: {
                    "overall": routed_metrics(
                        frame,
                        values,
                        flags[role],
                        policies[role],
                        p["bootstrap_repeats"],
                    ),
                    "private": routed_metrics(
                        frame.loc[private],
                        values[private],
                        flags[role][private],
                        policies[role],
                        p["bootstrap_repeats"],
                    ),
                }
                for role, values in probabilities.items()
            }
            pairs[level] = {
                ref: paired_intervals(
                    frame,
                    flags[ref].astype(float),
                    flags[name].astype(float),
                    [0.5, 0.5],
                    p["bootstrap_repeats"],
                    p["seed"],
                    frame.label.eq(1).all(),
                )
                for ref in (
                    "baseline",
                    "private_matched",
                    "previous_current",
                    "frozen_v6",
                )
            }
        cohorts[cohort] = {
            **coverage(frame),
            "previously_observed": True,
            "levels": levels,
            "paired_diagnostic_minus_reference": pairs,
        }
        print({"evaluated": cohort, "rows": len(frame)}, flush=True)
        old_scores.close()
    check()
    if checksum(RUN / "models-frozen.json") != freeze_sha:
        raise ValueError("readiness_freeze_changed_during_replay")
    write_json(
        REPORT,
        {
            "completed_at_utc": now(),
            "protocol_sha256": checksum(PROTOCOL),
            "models_freeze_sha256": freeze_sha,
            "selection": frozen["selection"],
            "development": frozen["development"],
            "records": frozen["records"],
            "cohorts": cohorts,
            "scores": saved,
            "source_filter": data["assets"],
            "test_used_for_selection": False,
            "commercial_clearance": False,
            "production_ready": False,
        },
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stage", choices=["prepare", "train", "evaluate", "check"])
    args = parser.parse_args()
    with threadpool_limits(limits=4):
        {"prepare": prepare, "train": train, "evaluate": evaluate, "check": check}[
            args.stage
        ]()
