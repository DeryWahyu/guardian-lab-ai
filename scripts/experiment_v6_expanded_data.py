"""Merge new public sources and compare three preregistered LR candidates."""

import argparse
from datetime import datetime, timezone
import gc
import json

import joblib
import numpy as np
import pandas as pd
from scipy.special import logit
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler
from threadpoolctl import threadpool_limits

from guardian_ml.metadata import checksum
from guardian_ml.paths import ROOT
from guardian_ml.rich_artifact import RichArtifact
from guardian_ml.rich_features import numeric_values

from evaluate_legitphish_v6 import collect_exposure, digest, write_sidecar
from evaluate_v6_quality import domain_intervals
from experiment_v6_development import checked_fit, matrix_batches, paired_intervals
from v6_development_support import (
    assert_separated,
    curate_fit,
    fit_weights,
    predict_bundle,
    transform_frame,
)
from v6_diagnostic_support import safe_metrics

PROTOCOL = ROOT / "ml/reports/v6-expansion-20261105-protocol.json"
INTAKE = ROOT / "ml/data/v6-expansion-20261105"
RUN = ROOT / "ml/runs/v6-expanded-data-20261105"
SOURCES = [
    "scripts/experiment_v6_expanded_data.py",
    "scripts/intake_v6_expansion.py",
    "scripts/evaluate_legitphish_v6.py",
    "scripts/v6_development_support.py",
    "scripts/v6_diagnostic_support.py",
    "scripts/experiment_v6_development.py",
    "scripts/evaluate_v6_quality.py",
]


def now():
    return datetime.now(timezone.utc).isoformat()


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes((json.dumps(value, indent=2, allow_nan=False) + "\n").encode())


def bindings():
    return {name: checksum(ROOT / name) for name in SOURCES}


def partition(group, protocol):
    bucket = int(digest(protocol["split_salt"] + group)[:16], 16) % 100
    return next(name for name, end in protocol["group_buckets"].items() if bucket < end)


def curate_new(frames, urls, domains, protocol):
    frame = pd.concat(frames, ignore_index=True)
    if not frame.label.isin([0, 1]).all():
        raise ValueError("unmapped_expansion_labels")
    conflicts = frame.groupby("representation_digest").label.nunique()
    bad = frame.representation_digest.isin(conflicts[conflicts > 1].index)
    clean = frame.loc[~bad].sort_values(["training_source", "digest"], kind="stable")
    unique = clean.drop_duplicates("representation_digest")
    old = (
        unique.digest.isin(urls)
        | unique.representation_digest.isin(urls)
        | unique.group.map(digest).isin(domains)
    )
    eligible = unique.loc[~old].sort_values("digest", kind="stable")
    capped = (
        eligible.groupby("group", sort=False)
        .head(protocol["max_rows_per_domain"])
        .copy()
    )
    capped["partition"] = capped.group.map(lambda group: partition(group, protocol))
    return capped.reset_index(drop=True), {
        "input_rows": len(frame),
        "conflict_representations": int((conflicts > 1).sum()),
        "conflicting_rows": int(bad.sum()),
        "consistent_duplicate_rows": len(clean) - len(unique),
        "prior_url_or_domain_excluded": int(old.sum()),
        "domain_cap_excluded": len(eligible) - len(capped),
        "retained_rows": len(capped),
        "new_source_class_counts": {
            str(source): {str(k): int(v) for k, v in sub.label.value_counts().items()}
            for source, sub in capped.groupby("training_source")
        },
    }


def prepare(protocol):
    if (RUN / "data-freeze.json").exists():
        raise ValueError("expanded_data_already_frozen")
    RUN.mkdir(parents=True, exist_ok=True)
    prior_urls, prior_domains, prior_hashes = collect_exposure()
    frames, audits = [], {}
    for name in protocol["sources"]:
        path = INTAKE / (name + "-sanitized.parquet")
        audit = json.loads((INTAKE / (name + "-intake.json")).read_text())
        if audit["label_counts"] != protocol["expected_source_label_counts"][name]:
            raise ValueError("publisher_class_totals_do_not_match_declared_mapping")
        if audit.get("cache_sha256") and checksum(path) != audit["cache_sha256"]:
            raise ValueError("expansion_intake_cache_changed")
        frame = pd.read_parquet(path)
        labels = pd.to_numeric(frame.publisher_label, errors="coerce")
        if labels.isna().any() or not labels.isin([0, 1]).all():
            raise ValueError("expansion_source_needs_explicit_label_mapping")
        # Class totals agree with documented benign/phishing totals in all three releases.
        frame["label"] = labels.astype(int)
        frame = frame.drop(columns="publisher_label")
        frames.append(frame)
        audits[name] = {
            **audit,
            "cache_sha256": checksum(path),
            "label_mapping": {"0": "benign", "1": "phishing"},
            "mapping_evidence": "release documentation and exact class-total cross-check; no case relabeling",
        }
    novel, audit = curate_new(frames, prior_urls, prior_domains, protocol)
    pooled = pd.concat(frames, ignore_index=True)
    base_path = ROOT / "ml/runs/notebook-tfidf-logistic-v6/data/development-v6.parquet"
    if (
        checksum(base_path)
        != "b0c867f9ab0c813d1498908d1cd43d731b46fffe83f8d5836e0e5f2b319097a8"
    ):
        raise ValueError("original_v6_development_changed")
    foundation, privacy = transform_frame(pd.read_parquet(base_path))
    old_fit, fit_audit = curate_fit(foundation.loc[foundation.partition.eq("fit")])
    foundation = pd.concat(
        [old_fit, foundation.loc[~foundation.partition.eq("fit")]], ignore_index=True
    )
    novel = novel.drop(
        columns=[
            name
            for name in novel
            if name not in foundation
            and name
            not in [
                "core",
                "digest",
                "group",
                "representation_digest",
                "label",
                "training_source",
                "partition",
            ]
        ]
    )
    combined = pd.concat([foundation, novel], ignore_index=True)
    parts = {
        name: combined.loc[combined.partition.eq(name)].reset_index(drop=True)
        for name in protocol["group_buckets"]
    }
    assert_separated(list(parts.values()))
    files = {}
    for name, frame in parts.items():
        path = RUN / (name + ".parquet")
        frame.to_parquet(path, index=False)
        files[name] = {
            "path": path.relative_to(ROOT).as_posix(),
            "sha256": checksum(path),
            "rows": len(frame),
            "groups": int(frame.group.nunique()),
            "classes": {str(k): int(v) for k, v in frame.label.value_counts().items()},
        }
    sidecar = write_sidecar(
        ROOT / "ml/data/exposure-sidecars/v6-expanded-sources-20261105.sqlite", pooled
    )
    frozen = {
        "frozen_at_utc": now(),
        "protocol_sha256": checksum(PROTOCOL),
        "source_hashes": bindings(),
        "source_audits": audits,
        "new_data_curation": audit,
        "foundation_curation": fit_audit,
        "foundation_privacy": privacy,
        "partitions": files,
        "prior_exposure_hashes": prior_hashes,
        "exposure_sidecar": sidecar,
        "data_labels_or_scores_sent_to_llm": False,
        "source_labels_only_not_human_gold": True,
        "candidate_training_started": False,
    }
    write_json(RUN / "data-freeze.json", frozen)
    write_json(
        ROOT / "ml/provenance/v6-expanded-data-exposure.json",
        {
            "sidecar": sidecar,
            "data_freeze": (RUN / "data-freeze.json").relative_to(ROOT).as_posix(),
            "data_freeze_sha256": checksum(RUN / "data-freeze.json"),
            "scope": "all sanitized source intake; includes reserved not-yet-scored holdout",
            "future_novelty_audits_must_include": True,
        },
    )
    print(json.dumps({"new_data": audit, "partitions": files}), flush=True)


def check_freeze():
    frozen = json.loads((RUN / "data-freeze.json").read_text())
    if (
        checksum(PROTOCOL) != frozen["protocol_sha256"]
        or bindings() != frozen["source_hashes"]
    ):
        raise ValueError("expansion_protocol_or_source_changed")
    for item in frozen["partitions"].values():
        if checksum(ROOT / item["path"]) != item["sha256"]:
            raise ValueError("expanded_partition_changed")
    for name, expected in frozen["prior_exposure_hashes"].items():
        if checksum(ROOT / name) != expected:
            raise ValueError("prior_exposure_changed")
    return frozen


def make_encoder(fit, protocol):
    if set(fit.partition) != {"fit"}:
        raise ValueError("encoder_fit_partition_only")
    spec = protocol["encoder"]
    text = fit.core.str.replace(r"^https?://", "", regex=True)
    sample = pd.concat(
        [
            text.loc[fit.training_source.eq(source)].sample(
                min(
                    spec["vocabulary_source_cap"],
                    int(fit.training_source.eq(source).sum()),
                ),
                random_state=protocol["seed"],
            )
            for source in sorted(fit.training_source.unique())
        ]
    )
    sample = sample.sample(
        min(len(sample), spec["vocabulary_total_cap"]), random_state=protocol["seed"]
    )
    encoder = {
        "char": TfidfVectorizer(
            analyzer="char",
            ngram_range=tuple(spec["char_ngram"]),
            max_features=spec["char_max_features"],
            min_df=spec["min_df"],
            sublinear_tf=True,
            dtype=np.float32,
        ).fit(sample),
        "word": TfidfVectorizer(
            analyzer="word",
            token_pattern=r"(?u)\b[a-zA-Z]{2,}\b",
            ngram_range=(1, 2),
            max_features=spec["word_max_features"],
            min_df=spec["min_df"],
            sublinear_tf=True,
            dtype=np.float32,
        ).fit(sample),
        "scaler": StandardScaler(with_mean=False).fit(numeric_values(fit.core)),
    }
    return encoder


def source_point(frame, scores, budget, expected, protocol):
    if set(frame.partition) != {expected}:
        raise ValueError("source_point_partition_violation")
    scores = np.asarray(scores)
    points, omitted = [], []
    for source in sorted(frame.training_source.unique()):
        mask = (
            frame.training_source.eq(source).to_numpy() & frame.label.eq(0).to_numpy()
        )
        negative = np.sort(scores[mask])
        if len(negative) < protocol["min_benign_per_source_for_threshold"]:
            omitted.append(source)
            continue
        allowed = int(np.floor(len(negative) * budget))
        points.append(float(np.nextafter(negative[-allowed - 1], np.inf)))
    if not points:
        raise ValueError("no_supported_benign_source_for_threshold")
    threshold = max(points)
    rates = {}
    for source in sorted(frame.training_source.unique()):
        mask = frame.training_source.eq(source).to_numpy()
        subset = frame.loc[mask]
        rates[source] = safe_metrics(
            subset, scores[mask], threshold, positive_only=subset.label.eq(1).all()
        )
    return {
        "threshold": threshold,
        "source_rates": rates,
        "sources_without_sufficient_benign_for_constraint": omitted,
    }


def diagnostic(frame, scores, protocol):
    result = source_point(frame, scores, 0.01, "tune", protocol)
    included = [
        rate["recall"]
        for rate in result["source_rates"].values()
        if rate["phishing"] >= protocol["min_phishing_per_source_for_macro_recall"]
    ]
    result["macro_source_recall"] = float(np.mean(included))
    result["minimum_source_recall"] = min(included)
    result["overall"] = safe_metrics(frame, scores, result["threshold"])
    return result


def choose(results, baseline):
    eligible = []
    for name, row in results.items():
        deltas = [
            rate["recall"] - baseline["source_rates"][source]["recall"]
            for source, rate in row["source_rates"].items()
            if rate["phishing"] >= 20
        ]
        if (
            row["macro_source_recall"] >= baseline["macro_source_recall"] + 0.02
            and min(deltas) >= -0.05
        ):
            eligible.append(name)
    pool = eligible or list(results)
    name = max(
        pool,
        key=lambda name: (
            results[name]["macro_source_recall"],
            results[name]["minimum_source_recall"],
            results[name]["overall"]["average_precision"],
        ),
    )
    return {
        "candidate": name,
        "development_improvement_gate_passed": bool(eligible),
        "eligible": eligible,
        "selected_on": "tune_only",
        "automatic_production_promotion": False,
    }


def train(protocol):
    frozen = check_freeze()
    if (RUN / "selected-frozen.json").exists():
        raise ValueError("selected_expansion_model_already_frozen")
    fit = pd.read_parquet(ROOT / frozen["partitions"]["fit"]["path"])
    tune = pd.read_parquet(ROOT / frozen["partitions"]["tune"]["path"])
    print("Fitting expanded encoder on " + str(len(fit)) + " fit rows only", flush=True)
    encoder = make_encoder(fit, protocol)
    x_fit = matrix_batches(encoder, fit)
    x_tune = matrix_batches(encoder, tune)
    baseline = diagnostic(tune, RichArtifact().predict_cores(tune.core), protocol)
    results, details = {}, {}
    for candidate in protocol["training_candidates"]:
        print("Training " + candidate["name"], flush=True)
        weights = fit_weights(fit, "source_sqrt")
        if candidate["weights"] == "source_domain":
            weights /= np.sqrt(fit.groupby("group").group.transform("size").to_numpy())
            weights /= weights.mean()
        model = LogisticRegression(
            C=candidate["C"], random_state=protocol["seed"], **protocol["classifier"]
        )
        checked_fit(model, x_fit, fit.label, sample_weight=weights)
        results[candidate["name"]] = diagnostic(
            tune, model.predict_proba(x_tune)[:, 1], protocol
        )
        details[candidate["name"]] = {
            "iterations": int(model.n_iter_[0]),
            "converged": True,
            "fit_rows": len(fit),
            "features": x_fit.shape[1],
        }
        joblib.dump(model, RUN / (candidate["name"] + ".joblib"), compress=3)
        write_json(
            RUN / "tune-progress.json", {"baseline": baseline, "candidates": results}
        )
        print(
            json.dumps(
                {
                    "candidate": candidate["name"],
                    "macro_recall": results[candidate["name"]]["macro_source_recall"],
                }
            ),
            flush=True,
        )
    selected = choose(results, baseline)
    write_json(
        RUN / "selection.json",
        {
            "selected_at_utc": now(),
            "selection": selected,
            "baseline": baseline,
            "results": results,
        },
    )
    del x_fit, x_tune, fit, tune, weights, model
    gc.collect()
    calibration = pd.read_parquet(ROOT / frozen["partitions"]["calibration"]["path"])
    classifier = joblib.load(RUN / (selected["candidate"] + ".joblib"))
    raw = classifier.predict_proba(matrix_batches(encoder, calibration))[:, 1]
    calibrator = LogisticRegression(C=1000, max_iter=200, random_state=protocol["seed"])
    checked_fit(
        calibrator,
        logit(np.clip(raw, 1e-7, 1 - 1e-7)).reshape(-1, 1),
        calibration.label,
    )
    if calibrator.coef_[0, 0] <= 0:
        raise ValueError("expanded_calibrator_must_preserve_ranking")
    bundle = {"encoder": encoder, "classifier": classifier, "calibrator": calibrator}
    thresholds = pd.read_parquet(ROOT / frozen["partitions"]["threshold"]["path"])
    scores = predict_bundle(bundle, thresholds.core)
    policies = {
        name: source_point(thresholds, scores, budget, "threshold", protocol)
        for name, budget in [("warning", 0.01), ("high", 0.001)]
    }
    bundle["metadata"] = {
        "version": "v6-expanded-data-20261105-" + selected["candidate"],
        "thresholds": {name: row["threshold"] for name, row in policies.items()},
        "representation": "url-core-path-assignment-redacted-experiment-1",
        "source_hashes": frozen["source_hashes"],
        "protocol_sha256": frozen["protocol_sha256"],
        "production_ready": False,
        "research_noncommercial_only": True,
    }
    path = RUN / "selected-candidate.joblib"
    joblib.dump(bundle, path, compress=3)
    restored = joblib.load(path)
    probes = thresholds.core.iloc[:128].tolist() + [
        "http://example.org/password=SHORTSECRET",
        "https://example.org/password=SHORTSECRET",
    ]
    before, after = predict_bundle(bundle, probes), predict_bundle(restored, probes)
    delta = float(np.max(np.abs(before - after)))
    if delta > 1e-12 or before[-1] != before[-2]:
        raise ValueError("expanded_saved_artifact_parity_failed")
    check_freeze()
    write_json(
        RUN / "selected-frozen.json",
        {
            "frozen_at_utc": now(),
            "selected": selected,
            "candidate_fits": details,
            "candidate_tune": results,
            "baseline_tune": baseline,
            "threshold_selection": policies,
            "artifact_sha256": checksum(path),
            "selection_sha256": checksum(RUN / "selection.json"),
            "data_freeze_sha256": checksum(RUN / "data-freeze.json"),
            "real_and_synthetic_reload_cases": len(probes),
            "max_reload_prediction_delta": delta,
            "calibration_positive_slope": float(calibrator.coef_[0, 0]),
            "test_scores_seen_before_freezing": False,
        },
    )
    print(
        "Selected expanded artifact calibrated and frozen before all test scoring",
        flush=True,
    )


def evaluate(protocol):
    data_freeze = check_freeze()
    frozen = json.loads((RUN / "selected-frozen.json").read_text())
    if (
        checksum(RUN / "selected-candidate.joblib") != frozen["artifact_sha256"]
        or checksum(RUN / "selection.json") != frozen["selection_sha256"]
    ):
        raise ValueError("selected_expansion_artifact_changed")
    output = ROOT / "ml/reports/v6-expanded-data-evaluation.json"
    if output.exists():
        raise ValueError("expanded_final_report_already_exists")
    bundle = joblib.load(RUN / "selected-candidate.joblib")
    baseline = RichArtifact()
    datasets = {
        "new_domain_holdout": ROOT / data_freeze["partitions"]["new_test"]["path"],
        "observed_vendor": ROOT
        / "ml/runs/notebook-tfidf-logistic-v6/data/deepurlbench-holdout-v6.parquet",
        "observed_phishtank_positive": ROOT
        / "ml/runs/notebook-tfidf-logistic-v6/data/phishtank-2026-v6.parquet",
        "observed_legitphish": ROOT
        / "ml/data/legitphish-v2-v6-qa/sanitized-domain-disjoint.parquet",
    }
    results = {}
    for name, path in datasets.items():
        frame = pd.read_parquet(path)
        if frame.empty:
            results[name] = {"not_evaluated": "empty_after_novelty_filter"}
            continue
        positive_only = frame.label.eq(1).all()
        scores = {
            "v6": baseline.predict_cores(frame.core),
            "candidate": predict_bundle(bundle, frame.core),
        }
        thresholds = {
            "v6": baseline.metadata["thresholds"],
            "candidate": bundle["metadata"]["thresholds"],
        }
        cohort = {
            "rows": len(frame),
            "groups": int(frame.group.nunique()),
            "previously_observed": name != "new_domain_holdout",
            "models": {},
            "paired_deltas": {},
        }
        for model in scores:
            cohort["models"][model] = {}
            for level, threshold in thresholds[model].items():
                row = safe_metrics(frame, scores[model], threshold, positive_only)
                if positive_only or set(frame.label) == {0, 1}:
                    row["domain_bootstrap95"] = domain_intervals(
                        frame,
                        scores[model],
                        threshold,
                        protocol["domain_bootstrap_repeats"],
                        protocol["seed"],
                        positive_only,
                    )
                cohort["models"][model][level] = row
        for level in ("warning", "high"):
            if positive_only or set(frame.label) == {0, 1}:
                cohort["paired_deltas"][level] = paired_intervals(
                    frame,
                    scores["v6"],
                    scores["candidate"],
                    [thresholds["v6"][level], thresholds["candidate"][level]],
                    protocol["domain_bootstrap_repeats"],
                    protocol["seed"],
                    positive_only,
                )
        if "training_source" in frame:
            cohort["source_warning_metrics"] = {
                model: {
                    source: safe_metrics(
                        frame.loc[frame.training_source.eq(source)],
                        scores[model][frame.training_source.eq(source).to_numpy()],
                        thresholds[model]["warning"],
                        positive_only=frame.loc[
                            frame.training_source.eq(source), "label"
                        ]
                        .eq(1)
                        .all(),
                    )
                    for source in sorted(frame.training_source.unique())
                }
                for model in scores
            }
        results[name] = cohort
        print("Evaluated: " + name, flush=True)
    check_freeze()
    RichArtifact()
    report = {
        "completed_at_utc": now(),
        "protocol_sha256": checksum(PROTOCOL),
        "data_freeze": data_freeze,
        "selected_freeze": frozen,
        "cohorts": results,
        "production_ready": False,
        "original_v6_runtime_unchanged": True,
        "independent_campaigns_or_Indonesia_gold_established": False,
        "selection_used_test_results": False,
        "source_label_limitations": protocol["limits"],
        "decision": "research_candidate_only_keep_original_v6_service_pending_release_gate_evidence",
    }
    write_json(output, report)
    render_report(output.with_suffix(".md"), report)


def render_report(path, report):
    selection = report["selected_freeze"]["selected"]
    lines = [
        "# Eksperimen gabungan dataset untuk turunan v6",
        "",
        f"Kandidat dipilih dari tune: **{selection['candidate']}**. Syarat peningkatan development terpenuhi: **{selection['development_improvement_gate_passed']}**. Model layanan tetap frozen v6 asli; belum ada gold Indonesia atau promosi produksi.",
        "",
        "## Data yang digabung",
        "",
        "| Sumber baru | Baris rilis | Lolos sanitasi |",
        "| --- | ---: | ---: |",
    ]
    for name, audit in report["data_freeze"]["source_audits"].items():
        lines.append(
            f"| {name} | {audit['raw_rows']:,} | {audit['sanitized_rows']:,} |"
        )
    lines += [
        "",
        f"Kurasi data baru: `{json.dumps(report['data_freeze']['new_data_curation'], sort_keys=True)}`.",
        "",
        "| Partisi | URL | Domain/tenant | Kelas |",
        "| --- | ---: | ---: | --- |",
    ]
    for name, item in report["data_freeze"]["partitions"].items():
        lines.append(
            f"| {name} | {item['rows']:,} | {item['groups']:,} | {json.dumps(item['classes'], sort_keys=True)} |"
        )
    lines += [
        "",
        "Encoder hanya di-fit pada fitting; tiga kandidat memakai encoder baru yang sama. Seleksi hanya tune, kalibrator hanya calibration, dan policy akhir hanya threshold. Seluruh sumber memakai label penerbit; rasio sumber dan hasil sampling bukan prevalensi trafik.",
        "",
        "## Seleksi development",
        "",
        "| Model | Macro recall sumber pada cap FPR tune 1% | Recall sumber terendah |",
        "| --- | ---: | ---: |",
    ]
    for name, row in {
        "v6 kontrol": report["selected_freeze"]["baseline_tune"],
        **report["selected_freeze"]["candidate_tune"],
    }.items():
        lines.append(
            f"| {name} | {row['macro_source_recall']:.3%} | {row['minimum_source_recall']:.3%} |"
        )
    lines += [
        "",
        "## Hasil warning pada cohort yang sama",
        "",
        "| Cohort | Model | URL | Precision | Recall | FPR | FP | FN |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for name, cohort in report["cohorts"].items():
        if "models" not in cohort:
            continue
        for model, levels in cohort["models"].items():
            row = levels["warning"]
            rates = [
                "N/A" if row[key] is None else f"{row[key]:.3%}"
                for key in ("precision", "recall", "fpr")
            ]
            lines.append(
                f"| {name} | {model} | {row['rows']:,} | "
                + " | ".join(rates)
                + f" | {row['confusion_matrix']['fp'] if row['fpr'] is not None else 'N/A'} | {row['confusion_matrix']['fn']} |"
            )
        paired = cohort["paired_deltas"].get("warning")
        if paired:
            lines += [
                "",
                f"{name}: 95% paired domain bootstrap delta recall `{paired['recall_delta95']}`; delta FPR `{paired['fpr_delta95']}` (rasio 0–1).",
                "",
            ]
    lines += [
        "",
        "## Bukti dan batas",
        "",
        "New domain holdout berasal dari sumber baru yang juga masuk development; bukan independent-source atau temporal/Indonesia gold. Domain/digest/representasi tidak overlap antar-partisi dan tidak overlap exposure lama. Ketergantungan kampanye belum diketahui. Benchmark teramati tidak digunakan melatih/memilih/menyetel model.",
        "",
        "Per-source rates, counts, calibration/Brier/log loss/ECE, Wilson dan domain bootstrap tersedia di JSON. Sumber dengan <100 benign tidak mengatur batas FPR tersendiri. Pada cohort yang hanya positif, accuracy/FPR/precision trafik tidak tersedia. Pada LegitPhish, 28 benign dan bootstrap nol-error tidak membuktikan FPR rendah; gunakan batas Wilson dan dukungan domain.",
        "",
        "Semua model/dataset/registry/sidecar tetap lokal dan diabaikan Git. Manifest data dan kandidat dibekukan sebelum scoring. Binary/metadata/threshold v6 aktif serta notebook utamanya tetap utuh. Kandidat hanya riset nonkomersial mengikuti provenance fondasi.",
        "",
        "Dataset yang memerlukan akun, formulir akses atau DUA tidak diambil. Tidak ada reviewer/label Indonesia yang dibuat. Lebih banyak data tidak otomatis memperbaiki seluruh sumber; semua regresi tetap dilaporkan.",
        "",
    ]
    lines += ["- " + item for item in report["source_label_limitations"]]
    path.write_bytes(("\n".join(lines) + "\n").encode())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--stage", choices=["prepare", "train", "evaluate", "all"], default="all"
    )
    args = parser.parse_args()
    protocol = json.loads(PROTOCOL.read_text())
    with threadpool_limits(limits=4):
        if args.stage in ("prepare", "all"):
            prepare(protocol)
        if args.stage in ("train", "all"):
            train(protocol)
        if args.stage in ("evaluate", "all"):
            evaluate(protocol)


if __name__ == "__main__":
    main()
