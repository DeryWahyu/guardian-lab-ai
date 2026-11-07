"""Source ablations and predeclared policy comparisons, isolated from frozen v6."""

import argparse
import gc
import json

import joblib
import numpy as np
import pandas as pd
from scipy.special import logit
from sklearn.linear_model import LogisticRegression
from threadpoolctl import threadpool_limits

from guardian_ml.metadata import checksum
from guardian_ml.paths import ROOT
from guardian_ml.rich_artifact import RichArtifact
from evaluate_legitphish_v6 import collect_exposure, write_sidecar
from evaluate_v6_quality import domain_intervals
from experiment_v6_development import checked_fit, matrix_batches, paired_intervals
from experiment_v6_expanded_data import (
    curate_new,
    make_encoder,
    now,
    source_point,
    write_json,
)
from v6_development_support import assert_separated, fit_weights, predict_bundle
from v6_diagnostic_support import safe_metrics

PROTOCOL = ROOT / "ml/reports/v6-targeted-20261105-protocol.json"
RUN = ROOT / "ml/runs/v6-targeted-20261105"
OLD = ROOT / "ml/runs/v6-expanded-data-20261105"
INTAKE = ROOT / "ml/data/v6-targeted-20261105"
REPORT = ROOT / "ml/reports/v6-targeted-evaluation.json"
PARTS = ("fit", "tune", "calibration", "threshold", "new_test")
SOURCES = [
    "scripts/experiment_v6_targeted.py",
    "scripts/intake_v6_targeted.py",
    "scripts/experiment_v6_expanded_data.py",
    "scripts/intake_v6_expansion.py",
    "scripts/experiment_v6_development.py",
    "scripts/v6_development_support.py",
    "scripts/v6_diagnostic_support.py",
    "scripts/evaluate_legitphish_v6.py",
    "scripts/evaluate_v6_quality.py",
    "ml/src/guardian_ml/rich_features.py",
    "ml/src/guardian_ml/preprocessing.py",
    "ml/src/guardian_ml/evaluation.py",
    "ml/policies/shadow-runtime-manifest.json",
]


def bindings():
    return {name: checksum(ROOT / name) for name in SOURCES}


def prepare(protocol):
    if (RUN / "data-freeze.json").exists():
        raise ValueError("targeted_data_already_frozen")
    audit = json.loads((INTAKE / "intake.json").read_text())
    intake_path = INTAKE / "pwd2021-sanitized.parquet"
    if audit["cache_sha256"] != checksum(intake_path) or audit[
        "protocol_sha256"
    ] != checksum(PROTOCOL):
        raise ValueError("targeted_intake_changed")
    urls, domains, exposure = collect_exposure()
    full = pd.read_parquet(intake_path)
    novel, curation = curate_new([full], urls, domains, protocol)
    previous = json.loads((OLD / "data-freeze.json").read_text())
    parts, files = {}, {}
    for name in PARTS:
        new_part = novel.loc[novel.partition.eq(name)]
        if name != "new_test":
            asset = previous["partitions"][name]
            if checksum(ROOT / asset["path"]) != asset["sha256"]:
                raise ValueError("prior_development_partition_changed")
            new_part = pd.concat(
                [pd.read_parquet(ROOT / asset["path"]), new_part], ignore_index=True
            )
        parts[name] = new_part.reset_index(drop=True)
    # Identity-only audits of historical test cohorts, never fitted or selected from.
    identity_paths = [
        OLD / "new_test.parquet",
        ROOT
        / "ml/runs/notebook-tfidf-logistic-v6/data/deepurlbench-holdout-v6.parquet",
        ROOT / "ml/runs/notebook-tfidf-logistic-v6/data/phishtank-2026-v6.parquet",
        ROOT / "ml/data/legitphish-v2-v6-qa/sanitized-domain-disjoint.parquet",
    ]
    assert_separated(list(parts.values()))
    for path in identity_paths:
        identity = pd.read_parquet(path, columns=["group", "digest"])
        for frame in parts.values():
            if set(frame.group).intersection(identity.group) or set(
                frame.digest
            ).intersection(identity.digest):
                raise ValueError(
                    "targeted_development_or_new_test_overlaps_observed_test"
                )
    RUN.mkdir(parents=True, exist_ok=True)
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
        ROOT / "ml/data/exposure-sidecars/pwd2021-targeted-20261105.sqlite", full
    )
    frozen = {
        "frozen_at_utc": now(),
        "protocol_sha256": checksum(PROTOCOL),
        "source_hashes": bindings(),
        "intake": audit,
        "curation": curation,
        "partitions": files,
        "prior_exposure_hashes": exposure,
        "sidecar": sidecar,
        "observed_test_hashes": {
            p.relative_to(ROOT).as_posix(): checksum(p) for p in identity_paths
        },
        "old_data_freeze_sha256": checksum(OLD / "data-freeze.json"),
        "production_ready": False,
        "automatic_relabeling": False,
    }
    write_json(RUN / "data-freeze.json", frozen)
    write_json(
        ROOT / "ml/provenance/pwd2021-targeted-exposure.json",
        {
            "sidecar": sidecar,
            "data_freeze_sha256": checksum(RUN / "data-freeze.json"),
            "scope": "all sanitized publisher intake, including excluded and reserved holdout rows",
            "future_novelty_audits_must_include": True,
        },
    )
    print(json.dumps({"curation": curation, "partitions": files}), flush=True)


def check_freeze():
    frozen = json.loads((RUN / "data-freeze.json").read_text())
    if (
        frozen["protocol_sha256"] != checksum(PROTOCOL)
        or frozen["source_hashes"] != bindings()
    ):
        raise ValueError("targeted_source_or_protocol_changed")
    for item in frozen["partitions"].values():
        if checksum(ROOT / item["path"]) != item["sha256"]:
            raise ValueError("targeted_partition_changed")
    for name, sha in {
        **frozen["prior_exposure_hashes"],
        **frozen["observed_test_hashes"],
    }.items():
        if checksum(ROOT / name) != sha:
            raise ValueError("targeted_exposure_or_observed_test_changed")
    sidecar = frozen["sidecar"]
    if checksum(ROOT / sidecar["path"]) != sidecar["sha256"]:
        raise ValueError("targeted_intake_exposure_sidecar_changed")
    RichArtifact()
    return frozen


def fitting_subset(frame, candidate, protocol):
    if set(frame.partition) != {"fit"}:
        raise ValueError("candidate_fitting_partition_only")
    # Historical protocol uses the display name Mendeley; cache source ID is mendeley2020.
    allowed = {
        "mendeley2020" if name == "mendeley" else name
        for name in protocol["foundation_sources"]
    }
    allowed.update(candidate["add_sources"])
    if not allowed.issubset(set(frame.training_source)):
        raise ValueError("declared_candidate_source_missing")
    result = frame.loc[frame.training_source.isin(allowed)].reset_index(drop=True)
    if set(result.label) != {0, 1}:
        raise ValueError("candidate_requires_two_classes")
    return result


def pooled_threshold(frame, scores, budget):
    if set(frame.partition) != {"threshold"}:
        raise ValueError("pooled_policy_threshold_partition_only")
    scores = np.asarray(scores)
    if (
        len(scores) != len(frame)
        or not np.isfinite(scores).all()
        or not 0 <= budget < 1
    ):
        raise ValueError("invalid_pooled_threshold_input")
    negative = np.sort(scores[frame.label.eq(0).to_numpy()])
    if not len(negative):
        raise ValueError("pooled_policy_requires_benign")
    allowed = int(np.floor(budget * len(negative)))
    return float(np.nextafter(negative[-allowed - 1], np.inf))


def policies(frame, scores, protocol):
    strict = source_point(frame, scores, 0.01, "threshold", protocol)
    return {
        "strict_source_1pct": strict,
        **{
            f"pooled_{budget:g}": {
                "threshold": pooled_threshold(frame, scores, budget),
                "development_pooled_fpr_budget": budget,
                "does_not_guarantee_source_or_test_fpr": True,
            }
            for budget in (0.001, 0.005, 0.01, 0.02)
        },
    }


def tune_diagnostics(frame, scores, threshold, protocol):
    if set(frame.partition) != {"tune"}:
        raise ValueError("selection_tune_partition_only")
    sources = {}
    for source, subset in frame.groupby("training_source"):
        sources[source] = safe_metrics(
            subset,
            scores[frame.training_source.eq(source).to_numpy()],
            threshold,
            positive_only=subset.label.eq(1).all(),
        )
    supported = [
        m["recall"]
        for m in sources.values()
        if m["phishing"] >= protocol["min_phishing_per_source_for_macro_recall"]
    ]
    return {
        "source_rates": sources,
        "macro_source_recall": float(np.mean(supported)),
        "minimum_source_recall": float(min(supported)),
        "overall": safe_metrics(frame, scores, threshold),
    }


def select_candidate(results, baseline, protocol):
    eligible = []
    for name, row in results.items():
        rates = row["strict_source_1pct"]
        deltas = [
            m["recall"] - baseline["source_rates"][source]["recall"]
            for source, m in rates["source_rates"].items()
            if m["phishing"] >= protocol["min_phishing_per_source_for_macro_recall"]
        ]
        if (
            rates["macro_source_recall"] >= baseline["macro_source_recall"] + 0.02
            and min(deltas) >= -0.05
        ):
            eligible.append(name)
    pool = eligible or list(results)
    name = max(
        pool,
        key=lambda n: (
            results[n]["strict_source_1pct"]["macro_source_recall"],
            results[n]["strict_source_1pct"]["minimum_source_recall"],
            results[n]["strict_source_1pct"]["overall"]["average_precision"],
        ),
    )
    return {
        "candidate": name,
        "eligible": eligible,
        "development_gate_passed": bool(eligible),
        "selected_on": "tune_only",
        "policy": "strict_source_1pct",
        "production_ready": False,
    }


def train(protocol):
    frozen = check_freeze()
    if (RUN / "selected-frozen.json").exists():
        raise ValueError("targeted_selected_model_already_frozen")
    frames = {
        name: pd.read_parquet(ROOT / frozen["partitions"][name]["path"])
        for name in PARTS
        if name != "new_test"
    }
    baseline = RichArtifact()
    baseline_policies = policies(
        frames["threshold"], baseline.predict_cores(frames["threshold"].core), protocol
    )
    baseline_tune_scores = baseline.predict_cores(frames["tune"].core)
    baseline_diagnostics = tune_diagnostics(
        frames["tune"],
        baseline_tune_scores,
        baseline_policies["strict_source_1pct"]["threshold"],
        protocol,
    )
    results, fit_audits, candidate_policies = {}, {}, {}
    for candidate in protocol["candidates"]:
        name = candidate["name"]
        completed = RUN / (name + "-completed.json")
        if completed.exists():
            checkpoint = json.loads(completed.read_text())
            if (
                checkpoint["data_freeze_sha256"] != checksum(RUN / "data-freeze.json")
                or checksum(RUN / (name + ".joblib")) != checkpoint["artifact_sha256"]
            ):
                raise ValueError("candidate_checkpoint_changed")
            results[name], fit_audits[name], candidate_policies[name] = (
                checkpoint["tune"],
                checkpoint["fit"],
                checkpoint["policies"],
            )
            print("Retaining completed candidate: " + name, flush=True)
            continue
        fit = fitting_subset(frames["fit"], candidate, protocol)
        print("Fitting encoder: " + name + " rows=" + str(len(fit)), flush=True)
        encoder = make_encoder(fit, protocol)
        matrix = matrix_batches(encoder, fit)
        classifier = LogisticRegression(
            random_state=protocol["seed"], **protocol["classifier"]
        )
        checked_fit(
            classifier, matrix, fit.label, sample_weight=fit_weights(fit, "source_sqrt")
        )
        del matrix
        gc.collect()
        raw = classifier.predict_proba(matrix_batches(encoder, frames["calibration"]))[
            :, 1
        ]
        calibrator = LogisticRegression(
            C=1000, max_iter=200, random_state=protocol["seed"]
        )
        checked_fit(
            calibrator,
            logit(np.clip(raw, 1e-7, 1 - 1e-7)).reshape(-1, 1),
            frames["calibration"].label,
        )
        if calibrator.coef_[0, 0] <= 0:
            raise ValueError("calibration_must_preserve_ranking")
        bundle = {
            "encoder": encoder,
            "classifier": classifier,
            "calibrator": calibrator,
        }
        candidate_policies[name] = policies(
            frames["threshold"],
            predict_bundle(bundle, frames["threshold"].core),
            protocol,
        )
        tune_scores = predict_bundle(bundle, frames["tune"].core)
        results[name] = {
            policy: tune_diagnostics(
                frames["tune"], tune_scores, point["threshold"], protocol
            )
            for policy, point in candidate_policies[name].items()
        }
        fit_audits[name] = {
            "rows": len(fit),
            "sources": fit.training_source.value_counts().to_dict(),
            "classes": {str(k): int(v) for k, v in fit.label.value_counts().items()},
            "iterations": int(classifier.n_iter_[0]),
            "converged": True,
            "feature_count": int(classifier.n_features_in_),
            "calibration_positive_slope": float(calibrator.coef_[0, 0]),
        }
        bundle["metadata"] = {
            "version": "v6-targeted-20261105-" + name,
            "policies": candidate_policies[name],
            "representation": "url-core-path-assignment-redacted-experiment-1",
            "protocol_sha256": checksum(PROTOCOL),
            "production_ready": False,
            "research_noncommercial_only": True,
        }
        artifact = RUN / (name + ".joblib")
        joblib.dump(bundle, artifact, compress=3)
        checkpoint = {
            "completed_at_utc": now(),
            "data_freeze_sha256": checksum(RUN / "data-freeze.json"),
            "artifact_sha256": checksum(artifact),
            "fit": fit_audits[name],
            "tune": results[name],
            "policies": candidate_policies[name],
        }
        write_json(completed, checkpoint)
        print(
            json.dumps(
                {
                    "candidate": name,
                    "macro_recall": results[name]["strict_source_1pct"][
                        "macro_source_recall"
                    ],
                }
            ),
            flush=True,
        )
        del encoder, classifier, calibrator, bundle, fit, raw, tune_scores
        gc.collect()
    selection = select_candidate(results, baseline_diagnostics, protocol)
    selected = RUN / (selection["candidate"] + ".joblib")
    bundle = joblib.load(selected)
    probes = frames["threshold"].core.iloc[:128].tolist() + [
        "http://example.org/password=SHORTSECRET",
        "https://example.org/password=SHORTSECRET",
    ]
    before = predict_bundle(bundle, probes)
    reloaded = joblib.load(selected)
    delta = float(np.max(np.abs(before - predict_bundle(reloaded, probes))))
    if delta > 1e-12 or before[-1] != before[-2]:
        raise ValueError("targeted_real_artifact_reload_or_scheme_parity_failed")
    check_freeze()
    write_json(
        RUN / "selected-frozen.json",
        {
            "frozen_at_utc": now(),
            "selection": selection,
            "artifact": selected.relative_to(ROOT).as_posix(),
            "artifact_sha256": checksum(selected),
            "data_freeze_sha256": checksum(RUN / "data-freeze.json"),
            "fit_audits": fit_audits,
            "tune": results,
            "baseline_tune": baseline_diagnostics,
            "baseline_policies": baseline_policies,
            "candidate_policies": candidate_policies,
            "parity_cases": len(probes),
            "max_reload_delta": delta,
            "final_test_scoring_started": False,
            "test_results_used_for_selection": False,
        },
    )
    print(json.dumps(selection), flush=True)


def evaluate(protocol):
    data = check_freeze()
    selected = json.loads((RUN / "selected-frozen.json").read_text())
    if selected["artifact_sha256"] != checksum(ROOT / selected["artifact"]) or selected[
        "data_freeze_sha256"
    ] != checksum(RUN / "data-freeze.json"):
        raise ValueError("selected_targeted_artifact_changed")
    if REPORT.exists():
        raise ValueError("targeted_final_report_already_exists")
    write_json(
        RUN / "evaluation-started.json",
        {
            "started_at_utc": now(),
            "selected_freeze_sha256": checksum(RUN / "selected-frozen.json"),
        },
    )
    bundle, baseline = joblib.load(ROOT / selected["artifact"]), RichArtifact()
    cohorts = {
        "new_pwd_domain_holdout": ROOT / data["partitions"]["new_test"]["path"],
        "observed_expanded_domain_holdout": OLD / "new_test.parquet",
        "observed_vendor": ROOT
        / "ml/runs/notebook-tfidf-logistic-v6/data/deepurlbench-holdout-v6.parquet",
        "observed_phishtank_positive": ROOT
        / "ml/runs/notebook-tfidf-logistic-v6/data/phishtank-2026-v6.parquet",
        "observed_legitphish": ROOT
        / "ml/data/legitphish-v2-v6-qa/sanitized-domain-disjoint.parquet",
    }
    candidate_name = selected["selection"]["candidate"]
    thresholds = {
        "v6_original": baseline.metadata["thresholds"]["warning"],
        "v6_matched_source_1pct": selected["baseline_policies"]["strict_source_1pct"][
            "threshold"
        ],
        **{
            "candidate_" + name: policy["threshold"]
            for name, policy in selected["candidate_policies"][candidate_name].items()
        },
        **{
            "v6_" + name: point["threshold"]
            for name, point in selected["baseline_policies"].items()
            if name.startswith("pooled_")
        },
    }
    results = {}
    for name, path in cohorts.items():
        frame = pd.read_parquet(path)
        if frame.empty:
            results[name] = {"rows": 0, "not_evaluated": "empty_after_novelty_filter"}
            continue
        positive_only = frame.label.eq(1).all()
        scores = {
            "v6": baseline.predict_cores(frame.core),
            "candidate": predict_bundle(bundle, frame.core),
        }
        metrics = {}
        for policy, threshold in thresholds.items():
            score = scores["candidate" if policy.startswith("candidate_") else "v6"]
            row = safe_metrics(frame, score, threshold, positive_only)
            if positive_only or set(frame.label) == {0, 1}:
                row["domain_bootstrap95"] = domain_intervals(
                    frame,
                    score,
                    threshold,
                    protocol["domain_bootstrap_repeats"],
                    protocol["seed"],
                    positive_only,
                )
            metrics[policy] = row
        paired = (
            paired_intervals(
                frame,
                scores["v6"],
                scores["candidate"],
                [thresholds["v6_original"], thresholds["candidate_strict_source_1pct"]],
                protocol["domain_bootstrap_repeats"],
                protocol["seed"],
                positive_only,
            )
            if positive_only or set(frame.label) == {0, 1}
            else None
        )
        results[name] = {
            "rows": len(frame),
            "groups": int(frame.group.nunique()),
            "previously_observed": name != "new_pwd_domain_holdout",
            "policies": metrics,
            "paired_delta_candidate_strict_minus_v6_original": paired,
        }
        print("Evaluated: " + name, flush=True)
    check_freeze()
    report = {
        "completed_at_utc": now(),
        "protocol_sha256": checksum(PROTOCOL),
        "data_freeze": data,
        "selected_freeze": selected,
        "cohorts": results,
        "production_ready": False,
        "Indonesia_gold_established": False,
        "original_v6_runtime_unchanged": True,
        "test_used_for_selection": False,
        "limits": protocol["limits"],
        "decision": "keep_frozen_v6_active; all new artifacts research only",
    }
    write_json(REPORT, report)
    render_report(report)


def render_report(report):
    lines = [
        "# Evaluasi sumber data dan kebijakan peringatan v6",
        "",
        "Semua kandidat hanya riset; layanan dan notebook utama tetap frozen v6. Label penerbit tidak menjadi gold Indonesia.",
        "",
        "## Intake dan seleksi development",
        "",
        f"Kurasi sumber PWD2021: `{json.dumps(report['data_freeze']['curation'])}`",
        "",
        f"Seleksi tune saja: `{json.dumps(report['selected_freeze']['selection'])}`",
        "",
        "| Kandidat | Fit | Macro recall tune, strict 1%/sumber |",
        "| --- | ---: | ---: |",
    ]
    for name, audit in report["selected_freeze"]["fit_audits"].items():
        recall = report["selected_freeze"]["tune"][name]["strict_source_1pct"][
            "macro_source_recall"
        ]
        lines.append(f"| {name} | {audit['rows']} | {100 * recall:.2f}% |")
    lines += [
        "",
        "## Pengujian setelah artifact dibekukan",
        "",
        "Pooled dan per-source adalah kebijakan berbeda. Budget development yang sama tidak menjamin FPR test sama. Semua alternatif telah ditetapkan sebelum scoring; tidak memilih threshold dari tabel test.",
        "",
    ]

    def pct(value):
        return "Tidak tersedia" if value is None else f"{100 * value:.2f}%"

    for name, cohort in report["cohorts"].items():
        lines += [
            "### " + name,
            "",
            f"{cohort['rows']} URL; previously_observed={cohort.get('previously_observed')}. "
            "Sumber historis dan kemerdekaan domain belum membuktikan kemerdekaan kampanye/waktu.",
            "",
            "| Kebijakan | Precision sampel | Recall | FPR |",
            "| --- | ---: | ---: | ---: |",
        ]
        for name, row in cohort.get("policies", {}).items():
            lines.append(
                f"| {name} | {pct(row['precision'])} | {pct(row['recall'])} | {pct(row['fpr'])} |"
            )
        lines += [
            "",
            "Counts, interval Wilson/domain-bootstrap, Brier, ECE, AP dan AUC tersedia di JSON. Precision sampel tidak sama dengan precision trafik. Feed positif tidak menyediakan FPR/accuracy/precision trafik.",
            "",
        ]
    lines += ["## Batas dan keputusan", ""] + [
        "- " + limit for limit in report["limits"]
    ]
    lines += [
        "",
        "Tidak ada promosi model atau perubahan threshold layanan. Hasil test yang telah dibaca menjadi benchmark teramati untuk penelitian berikutnya.",
        "",
    ]
    REPORT.with_suffix(".md").write_bytes("\n".join(lines).encode())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--stage", choices=["prepare", "train", "evaluate"], required=True
    )
    args = parser.parse_args()
    protocol = json.loads(PROTOCOL.read_text())
    with threadpool_limits(limits=2):
        {"prepare": prepare, "train": train, "evaluate": evaluate}[args.stage](protocol)


if __name__ == "__main__":
    main()
