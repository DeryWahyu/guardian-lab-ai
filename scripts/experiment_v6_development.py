"""Run a predeclared, local-only LR experiment without replacing frozen v6."""

import argparse
from datetime import datetime, timezone
import gc
from importlib.metadata import version
import json
from pathlib import Path
import time
import warnings

import joblib
import numpy as np
import pandas as pd
from scipy.sparse import vstack
from scipy.special import logit
from sklearn.exceptions import ConvergenceWarning
from sklearn.linear_model import LogisticRegression
from threadpoolctl import threadpool_limits

from guardian_ml.evaluation import metrics, wilson
from guardian_ml.metadata import checksum
from guardian_ml.paths import ROOT
from guardian_ml.rich_artifact import RichArtifact
from guardian_ml.rich_features import feature_matrix

from evaluate_v6_quality import domain_intervals
from v6_development_support import (
    REPRESENTATION,
    assert_separated,
    curate_fit,
    fit_encoder,
    fit_weights,
    predict_bundle,
    select_candidate,
    source_threshold,
    transform_frame,
    tune_diagnostics,
)

SOURCES = [
    "scripts/experiment_v6_development.py",
    "scripts/v6_development_support.py",
    "scripts/evaluate_v6_quality.py",
    "ml/src/guardian_ml/preprocessing.py",
    "ml/src/guardian_ml/rich_features.py",
    "ml/src/guardian_ml/features.py",
    "ml/src/guardian_ml/evaluation.py",
]
CACHE = ROOT / "ml/runs/notebook-tfidf-logistic-v6/data"


def now():
    return datetime.now(timezone.utc).isoformat()


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes((json.dumps(value, indent=2, allow_nan=False) + "\n").encode())


def load_cache(asset, columns=None):
    path = CACHE / asset["filename"]
    if checksum(path) != asset["sha256"]:
        raise ValueError("data_checksum_mismatch")
    frame = pd.read_parquet(path, columns=columns)
    if len(frame) != asset["rows"]:
        raise ValueError("data_row_count_mismatch")
    return frame


def checked_fit(estimator, matrix, labels, **kwargs):
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always", ConvergenceWarning)
        estimator.fit(matrix, labels, **kwargs)
    if any(isinstance(item.message, ConvergenceWarning) for item in caught):
        raise ValueError("estimator_not_converged")
    return estimator


def matrix_batches(encoder, frame):
    pieces = []
    for start in range(0, len(frame), 16384):
        pieces.append(feature_matrix(encoder, frame.core.iloc[start : start + 16384]))
        if start % (16384 * 8) == 0:
            print(
                f"Feature transform: {min(start + 16384, len(frame))}/{len(frame)}",
                flush=True,
            )
    return vstack(pieces, format="csr")


def source_hashes():
    return {path: checksum(ROOT / path) for path in SOURCES}


def baseline_integrity(protocol):
    frozen = RichArtifact()
    if frozen.manifest["bundle_sha256"] != protocol["frozen_artifact_sha256"]:
        raise ValueError("baseline_artifact_changed")
    if frozen.manifest["frozen_metadata_sha256"] != protocol["frozen_metadata_sha256"]:
        raise ValueError("baseline_metadata_changed")
    if (
        checksum(ROOT / "ml/policies/shadow-runtime-manifest.json")
        != protocol["runtime_manifest_sha256"]
    ):
        raise ValueError("baseline_runtime_changed")
    return frozen


def develop(protocol, protocol_path, run):
    if run.exists():
        raise ValueError("choose_new_run_directory_to_preserve_existing_run")
    run.mkdir(parents=True)
    frozen = baseline_integrity(protocol)
    registry = ROOT / "ml/data/indonesia-gold/registry/known-exposure.sqlite"
    audit = {
        "started_at_utc": now(),
        "protocol_sha256": checksum(protocol_path),
        "source_hashes": source_hashes(),
        "registry_sha256_before": checksum(registry),
        "versions": {
            name: version(name) for name in frozen.manifest["inference_dependencies"]
        },
        "protocol": protocol,
        "production_ready": False,
    }
    write_json(run / "started.json", audit)
    development = load_cache(protocol["development"])
    expected = {"fit", "tune", "calibration", "threshold"}
    if set(development.partition) != expected:
        raise ValueError("unexpected_development_partitions")
    # Benchmark labels/cores are not loaded during development.
    identities = [
        load_cache(asset, ["group", "digest"])
        for asset in protocol["benchmarks"].values()
    ]
    raw_parts = [
        development.loc[development.partition.eq(part)] for part in sorted(expected)
    ]
    dummy = [
        part.assign(representation_digest=part.digest)
        for part in [*raw_parts, *identities]
    ]
    assert_separated(dummy)
    del identities, raw_parts, dummy
    print(
        "Verified original data hashes and domain/digest partition separation",
        flush=True,
    )
    original_tune = development.loc[development.partition.eq("tune")].copy()
    transformed, privacy = transform_frame(development)
    del development
    parts = {
        part: transformed.loc[transformed.partition.eq(part)].reset_index(drop=True)
        for part in sorted(expected)
    }
    assert_separated(list(parts.values()))
    fit, curation = curate_fit(parts["fit"])
    parts["fit"] = fit
    audit.update(
        {
            "privacy": privacy,
            "fit_curation": curation,
            "partition_counts": {
                part: {
                    "rows": len(frame),
                    "groups": int(frame.group.nunique()),
                    "classes": {
                        str(k): int(v) for k, v in frame.label.value_counts().items()
                    },
                }
                for part, frame in parts.items()
            },
            "fit_source_counts": {
                str(k): int(v) for k, v in fit.training_source.value_counts().items()
            },
            "domain_digest_and_representation_separation": True,
        }
    )
    del transformed
    print(f"Fit-only curation complete: {len(fit)} fitting rows", flush=True)
    encoder, vocabulary_rows = fit_encoder(fit, protocol["seed"])
    audit["vocabulary_fit_rows"] = vocabulary_rows
    print(
        "Vocabulary and numeric scaler fitted exclusively on fit partition", flush=True
    )
    x_fit = matrix_batches(encoder, fit)
    x_tune = matrix_batches(encoder, parts["tune"])
    audit["features"] = x_fit.shape[1]
    baseline_tune = tune_diagnostics(
        original_tune, frozen.predict_cores(original_tune.core)
    )
    results, fit_details = {}, {}
    for spec in protocol["candidates"]:
        started = time.perf_counter()
        print("Training candidate: " + spec["name"], flush=True)
        classifier = LogisticRegression(
            C=spec["C"], random_state=protocol["seed"], **protocol["classifier"]
        )
        weights = fit_weights(fit, spec["weighting"])
        checked_fit(classifier, x_fit, fit.label.to_numpy(), sample_weight=weights)
        scores = classifier.predict_proba(x_tune)[:, 1]
        results[spec["name"]] = tune_diagnostics(parts["tune"], scores)
        fit_details[spec["name"]] = {
            "iterations": int(classifier.n_iter_[0]),
            "converged": True,
            "fit_and_tune_seconds": time.perf_counter() - started,
            "weights_min": float(weights.min()),
            "weights_max": float(weights.max()),
        }
        joblib.dump(classifier, run / (spec["name"] + ".joblib"), compress=3)
        print(
            json.dumps(
                {
                    "candidate": spec["name"],
                    "tune_macro_recall": results[spec["name"]]["macro_source_recall"],
                }
            ),
            flush=True,
        )
    decision = select_candidate(results, baseline_tune)
    write_json(
        run / "selection.json",
        {
            "selected_at_utc": now(),
            "decision": decision,
            "baseline_tune": baseline_tune,
            "candidates": results,
        },
    )
    del x_fit, x_tune, weights, scores, classifier, fit, original_tune
    gc.collect()
    print("Selection fixed using tune only: " + decision["candidate"], flush=True)
    classifier = joblib.load(run / (decision["candidate"] + ".joblib"))
    calibration = parts["calibration"]
    raw = classifier.predict_proba(matrix_batches(encoder, calibration))[:, 1]
    spec = protocol["calibration"]
    calibrator = LogisticRegression(
        C=spec["C"], max_iter=spec["max_iter"], random_state=protocol["seed"]
    )
    checked_fit(
        calibrator,
        logit(np.clip(raw, 1e-7, 1 - 1e-7)).reshape(-1, 1),
        calibration.label,
    )
    if calibrator.coef_[0, 0] <= 0:
        raise ValueError("calibration_must_preserve_ranking")
    bundle = {"encoder": encoder, "classifier": classifier, "calibrator": calibrator}
    threshold_frame = parts["threshold"]
    scores = predict_bundle(bundle, threshold_frame.core)
    policies = {
        level: source_threshold(
            threshold_frame,
            scores,
            protocol["thresholds"][level + "_fpr_budget_per_source"],
            "threshold",
        )
        for level in ("warning", "high")
    }
    thresholds = {level: point["threshold"] for level, point in policies.items()}
    if (
        not 0 <= thresholds["warning"] <= thresholds["high"]
        or thresholds["warning"] > 1
    ):
        raise ValueError("unsupported_candidate_warning_policy")
    bundle["metadata"] = {
        "version": "v6-development-20261105-" + decision["candidate"],
        "representation": REPRESENTATION,
        "thresholds": thresholds,
        "high_enabled": thresholds["high"] <= 1,
        "production_ready": False,
        "noncommercial_research_only": True,
        "protocol_sha256": audit["protocol_sha256"],
        "source_hashes": audit["source_hashes"],
        "versions": audit["versions"],
        "candidate": decision,
        "fit_rows": curation["fit_rows"],
    }
    model_path = run / "selected-candidate.joblib"
    joblib.dump(bundle, model_path, compress=3)
    restored = joblib.load(model_path)
    # Real, non-persisted development rows plus synthetic privacy/parity probes.
    probes = threshold_frame.core.iloc[:128].tolist() + [
        "https://example.org/password=SHORTVALUE",
        "http://example.org/password=SHORTVALUE",
        "https://example.org/reset;token=SHORTVALUE",
        "https://example.org/login?token=SHORTVALUE",
    ]
    before, after = predict_bundle(bundle, probes), predict_bundle(restored, probes)
    delta = float(np.max(np.abs(before - after)))
    if delta > 1e-12 or after[-4] != after[-3]:
        raise ValueError("saved_candidate_prediction_parity_failure")
    audit.update(
        {
            "frozen_at_utc": now(),
            "selection": decision,
            "candidate_tune_results": results,
            "baseline_tune_control": baseline_tune,
            "candidate_fits": fit_details,
            "threshold_selection": policies,
            "calibration": {
                "rows": len(calibration),
                "iterations": int(calibrator.n_iter_[0]),
                "slope": float(calibrator.coef_[0, 0]),
                "converged": True,
            },
            "selected_bundle_sha256": checksum(model_path),
            "selection_record_sha256": checksum(run / "selection.json"),
            "saved_model_parity": {
                "cases": len(probes),
                "maximum_absolute_error": delta,
            },
            "registry_sha256_after": checksum(registry),
            "benchmark_labels_or_scores_used_for_selection": False,
        }
    )
    if (
        source_hashes() != audit["source_hashes"]
        or audit["registry_sha256_before"] != audit["registry_sha256_after"]
    ):
        raise ValueError("source_or_exposure_registry_changed_during_training")
    baseline_integrity(protocol)
    write_json(run / "frozen-experiment.json", audit)
    print(
        "Selected model calibrated, thresholds fixed and artifact saved before benchmark scoring",
        flush=True,
    )


def paired_intervals(
    frame, original, candidate, thresholds, repeats, seed, positive_only=False
):
    y = frame.label.to_numpy()
    old, new = original >= thresholds[0], candidate >= thresholds[1]
    counts = (
        pd.DataFrame(
            {
                "group": frame.group,
                "phishing": y == 1,
                "benign": y == 0,
                "tp_delta": ((y == 1) & new).astype(int) - ((y == 1) & old).astype(int),
                "fp_delta": ((y == 0) & new).astype(int) - ((y == 0) & old).astype(int),
            }
        )
        .groupby("group", sort=True)
        .sum()
        .to_numpy(dtype=np.int64)
    )
    rng = np.random.default_rng(seed)
    draws = []
    for _ in range(repeats):
        positive, negative, tp_delta, fp_delta = counts[
            rng.integers(len(counts), size=len(counts))
        ].sum(axis=0)
        if positive and (positive_only or negative):
            draws.append(
                [tp_delta / positive]
                if positive_only
                else [tp_delta / positive, fp_delta / negative]
            )
    if not draws:
        raise ValueError("insufficient_bootstrap_classes")
    interval = np.quantile(draws, [0.025, 0.975], axis=0)
    return {
        "repeats": repeats,
        "valid_repeats": len(draws),
        "unit": "domain_or_private_tenant",
        "recall_delta95": interval[:, 0].tolist(),
        "fpr_delta95": None if positive_only else interval[:, 1].tolist(),
    }


def summarize(frame, scores, threshold, positive_only=False, bootstrap=None):
    if positive_only:
        if not frame.label.eq(1).all():
            raise ValueError("positive_only_requires_phishing_labels")
        tp = int((scores >= threshold).sum())
        result = {
            "rows": len(frame),
            "phishing": len(frame),
            "benign": 0,
            "tp": tp,
            "fn": len(frame) - tp,
            "recall": tp / len(frame),
            "recall_wilson95_rows_iid_assumption": wilson(tp, len(frame)),
            "accuracy": None,
            "fpr": None,
            "precision": None,
            "brier_score": None,
            "log_loss": None,
            "threshold": threshold,
        }
    else:
        result = metrics(frame.label, scores, threshold)
        result["balanced_accuracy"] = (result["recall"] + 1 - result["fpr"]) / 2
        result["ece_10_fixed_bins"] = sum(
            b["rows"] * abs(b["mean_probability"] - b["phishing_fraction"])
            for b in result["reliability_bins"]
        ) / len(frame)
    result["groups"] = int(frame.group.nunique())
    if bootstrap:
        result["domain_bootstrap95"] = domain_intervals(
            frame,
            scores,
            threshold,
            bootstrap["domain_bootstrap_repeats"],
            bootstrap["seed"],
            positive_only,
        )
    return result


def benchmark(protocol, protocol_path, run, output):
    if output.with_suffix(".json").exists() or output.with_suffix(".md").exists():
        raise ValueError("completed_report_already_exists")
    audit = json.loads((run / "frozen-experiment.json").read_text())
    if (
        checksum(protocol_path) != audit["protocol_sha256"]
        or source_hashes() != audit["source_hashes"]
    ):
        raise ValueError("protocol_or_source_changed_after_freeze")
    if checksum(run / "selected-candidate.joblib") != audit["selected_bundle_sha256"]:
        raise ValueError("candidate_checksum_mismatch")
    if checksum(run / "selection.json") != audit["selection_record_sha256"]:
        raise ValueError("selection_changed_after_freeze")
    frozen = baseline_integrity(protocol)
    candidate = joblib.load(run / "selected-candidate.joblib")
    benchmarks = {}
    for name, asset in protocol["benchmarks"].items():
        original = load_cache(asset)
        frame, privacy = transform_frame(original)
        scores = {
            "frozen_v6": frozen.predict_cores(original.core),
            "candidate": predict_bundle(candidate, original.core),
        }
        thresholds = {
            "frozen_v6": frozen.metadata["thresholds"],
            "candidate": candidate["metadata"]["thresholds"],
        }
        positive_only = name == "community_positive"
        result = {
            "privacy_transform": privacy,
            "already_observed": True,
            "models": {},
            "paired_delta": {},
        }
        for model in scores:
            result["models"][model] = {
                level: summarize(
                    frame,
                    scores[model],
                    thresholds[model][level],
                    positive_only,
                    protocol["uncertainty"],
                )
                for level in ("warning", "high")
            }
            segments = {}
            for segment in ("long_url", "private_hosting", "punycode"):
                mask = frame[segment].to_numpy()
                segments[segment] = (
                    summarize(
                        frame.loc[mask],
                        scores[model][mask],
                        thresholds[model]["warning"],
                        positive_only,
                    )
                    if mask.any()
                    else None
                )
            result["models"][model]["warning_segments"] = segments
        for level in ("warning", "high"):
            result["paired_delta"][level] = paired_intervals(
                frame,
                scores["frozen_v6"],
                scores["candidate"],
                [thresholds["frozen_v6"][level], thresholds["candidate"][level]],
                protocol["uncertainty"]["paired_delta_repeats"],
                protocol["seed"],
                positive_only,
            )
        benchmarks[name] = result
        print("Completed already-observed benchmark: " + name, flush=True)
    baseline_integrity(protocol)
    report = {
        "completed_at_utc": now(),
        "new_independent_test": False,
        "production_ready": False,
        "active_model_changed": False,
        "development": audit,
        "benchmarks": benchmarks,
        "limitations": protocol["limitations"],
        "decision": "retain_frozen_v6_service_candidate_is_research_only_pending_new_independent_validation",
    }
    write_json(output.with_suffix(".json"), report)
    render_report(output.with_suffix(".md"), report, run)
    render_plot(output.with_suffix(".png"), report)


def render_report(path, report, run):
    audit = report["development"]
    lines = [
        "# Eksperimen pengembangan v6",
        "",
        "Tiga kandidat Logistic Regression dilatih terpisah. Layanan tetap menggunakan frozen v6 asli. Kandidat dipilih hanya dari tune; hasil di bawah adalah pemeriksaan benchmark yang sudah pernah teramati, bukan validasi independen baru.",
        "",
        f"Kandidat terpilih: **{audit['selection']['candidate']}**. Lolos syarat peningkatan development: **{audit['selection']['development_improvement_gate_passed']}**. Tidak ada promosi produksi.",
        "",
        "## Pemilihan development",
        "",
        "| Kandidat | Macro recall per sumber pada FPR tune <=1% | Recall sumber terendah |",
        "| --- | ---: | ---: |",
    ]
    for name, item in {
        "v6 kontrol tune": audit["baseline_tune_control"],
        **audit["candidate_tune_results"],
    }.items():
        lines.append(
            f"| {name} | {item['macro_source_recall']:.2%} | {item['minimum_source_recall']:.2%} |"
        )
    lines += [
        "",
        "Threshold tune di tabel hanya diagnostik pemilihan. Threshold kandidat akhir ditentukan pada partisi threshold setelah kalibrasi terpisah.",
        "",
        "## Benchmark teramati, warning",
        "",
        "| Data | Model | URL | Accuracy | Precision | Recall | FPR |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    for name, benchmark_result in report["benchmarks"].items():
        for model, results in benchmark_result["models"].items():
            row = results["warning"]
            values = [
                "N/A" if row[key] is None else f"{100 * row[key]:.3f}%"
                for key in ("accuracy", "precision", "recall", "fpr")
            ]
            lines.append(
                f"| {name} | {model} | {row['rows']:,} | " + " | ".join(values) + " |"
            )
    lines += [
        "",
        "Interval bootstrap berpasangan 95% untuk delta kandidat terhadap v6 (percentage point):",
        "",
    ]
    for name, result in report["benchmarks"].items():
        paired = result["paired_delta"]["warning"]
        recall = [round(100 * value, 3) for value in paired["recall_delta95"]]
        fpr = (
            None
            if paired["fpr_delta95"] is None
            else [round(100 * value, 3) for value in paired["fpr_delta95"]]
        )
        lines.append(
            f"- {name}: delta recall {recall}; delta FPR {fpr if fpr is not None else 'N/A'}."
        )
    curation = audit["fit_curation"]
    lines += [
        "",
        "## Data, privasi dan reproduksi",
        "",
        f"Fitting memakai {curation['fit_rows']:,} baris setelah {curation['conflicting_fit_rows_quarantined']} baris konflik ({curation['conflicting_fit_representations']} representasi) dikarantina dan {curation['consistent_duplicate_fit_rows_removed']:,} duplikat konsisten dibuang. Label tidak diubah. Tune/calibration/threshold dan benchmark tidak dikurangi berdasarkan label atau kesalahan model.",
        "",
        f"Sanitizer eksperimen mengubah {audit['privacy']['changed_cores']} dari {audit['privacy']['rows']:,} core development. Ini menutup pola assignment path yang diuji, bukan jaminan anonimisasi lengkap. Parser v6 asli tetap beku.",
        "",
        f"Partisi: `{json.dumps(audit['partition_counts'], sort_keys=True)}`.",
        "",
        f"Artifact eksperimen lokal: `{run.relative_to(ROOT).as_posix()}/selected-candidate.joblib`, SHA-256 `{audit['selected_bundle_sha256']}`. Artifact/data tidak masuk Git dan tidak diterima otomatis oleh loader layanan v6. Save/reload parity {audit['saved_model_parity']['cases']} kasus: max delta {audit['saved_model_parity']['maximum_absolute_error']}.",
        "",
        "Sumber runtime, metadata, binary, threshold v6 dan registry exposure tetap utuh. Detail kalibrasi, counts, interval Wilson/domain, segment URL panjang/private hosting/punycode dan kebijakan HIGH ada dalam JSON pendamping.",
        "",
        "Jalankan ulang menggunakan direktori/output baru:",
        "",
        "```powershell",
        "ml/.venv/Scripts/python.exe scripts/experiment_v6_development.py --run-dir ml/runs/v6-development-replay --output-stem ml/reports/v6-development-replay",
        "```",
        "",
        "Memerlukan environment proyek dengan extra `quality` dan cache v6 lokal. Protokol disimpan sebelum training; konfigurasi tidak diubah setelah melihat benchmark.",
        "",
        "## Batas kesimpulan",
        "",
    ]
    lines += ["- " + limitation for limitation in report["limitations"]]
    lines += [
        "",
        "Pedoman metode: [pencegahan leakage](https://scikit-learn.org/stable/common_pitfalls.html#data-leakage), [pemilihan threshold](https://scikit-learn.org/stable/modules/classification_threshold.html), [kalibrasi](https://scikit-learn.org/stable/modules/calibration.html). Dependency proyek tetap pada versi training asli.",
        "",
    ]
    path.write_bytes("\n".join(lines).encode())


def render_plot(path, report):
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, axes = plt.subplots(1, 3, figsize=(14, 4.5), constrained_layout=True)
    for ax, dataset, key, title in [
        (axes[0], "vendor", "recall", "Vendor phishing recall"),
        (axes[1], "vendor", "fpr", "Vendor false-positive rate"),
        (axes[2], "community_positive", "recall", "Community positive-only recall"),
    ]:
        models = report["benchmarks"][dataset]["models"]
        values = [
            models[name]["warning"][key] * 100 for name in ("frozen_v6", "candidate")
        ]
        interval = [
            np.array(models[name]["warning"]["domain_bootstrap95"][key + "95"]) * 100
            for name in ("frozen_v6", "candidate")
        ]
        ax.bar([0, 1], values, color=["#176b87", "#db8f38"])
        for i, (value, ci) in enumerate(zip(values, interval)):
            ax.plot([i, i], ci, color="black")
            ax.text(
                i,
                ci[1] + (1 if key == "recall" else 0.02),
                f"{value:.2f}%",
                ha="center",
            )
        ax.set(
            xticks=[0, 1],
            xticklabels=["Frozen v6", "Candidate"],
            title=title,
            ylabel="Percent",
            ylim=(0, max(100 if key == "recall" else 1.3, max(values) * 1.3)),
        )
    fig.suptitle(
        "Already-observed benchmarks; selected on development only\nWarning policies, 95% domain bootstrap intervals; no production promotion"
    )
    fig.savefig(path, dpi=160)
    plt.close(fig)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--protocol",
        type=Path,
        default=ROOT / "ml/reports/v6-development-experiment-protocol.json",
    )
    parser.add_argument(
        "--run-dir", type=Path, default=ROOT / "ml/runs/v6-development-20261105"
    )
    parser.add_argument(
        "--output-stem",
        type=Path,
        default=ROOT / "ml/reports/v6-development-experiment",
    )
    parser.add_argument(
        "--stage", choices=["all", "develop", "benchmark"], default="all"
    )
    args = parser.parse_args()
    args.run_dir, args.output_stem = args.run_dir.resolve(), args.output_stem.resolve()
    if not args.run_dir.is_relative_to(
        ROOT / "ml/runs"
    ) or not args.output_stem.is_relative_to(ROOT / "ml/reports"):
        raise ValueError("experiment_output_outside_allowed_directories")
    protocol = json.loads(args.protocol.read_text(encoding="utf-8"))
    with threadpool_limits(limits=4):
        if args.stage in ("all", "develop"):
            develop(protocol, args.protocol, args.run_dir)
        if args.stage in ("all", "benchmark"):
            benchmark(protocol, args.protocol, args.run_dir, args.output_stem)


if __name__ == "__main__":
    main()
