"""Verify real artifacts/scores and render aggregate evidence for v6 retraining."""

from datetime import datetime
import json
import xml.etree.ElementTree as ET

import joblib
import numpy as np
import pandas as pd

from guardian_ml.metadata import checksum
from guardian_ml.paths import ROOT
from guardian_ml.rich_artifact import RichArtifact
from experiment_v6_expanded_data import now, write_json
import experiment_v6_current_retrain as study
from v6_current_retrain_support import (
    assert_original_recipe,
    check_scores,
    improvement_gate,
)
from v6_development_support import predict_bundle, transform_frame

VERIFY = ROOT / "ml/reports/v6-current-retrain-verification.json"
MARKDOWN = ROOT / "ml/reports/v6-current-retrain-evaluation.md"


def verify():
    p, data = study.check()
    frozen = study.read(study.RUN / "models-frozen.json")
    report = study.read(study.REPORT)
    started = study.read(study.RUN / "evaluation-started.json")
    if (
        report["models_freeze_sha256"] != checksum(study.RUN / "models-frozen.json")
        or started["models_freeze_sha256"] != report["models_freeze_sha256"]
    ):
        raise ValueError("retrain_replay_model_binding_changed")
    times = [
        data["prepared_at_utc"],
        frozen["frozen_at_utc"],
        started["started_at_utc"],
        report["completed_at_utc"],
    ]
    parsed = [datetime.fromisoformat(t) for t in times]
    if parsed != sorted(parsed):
        raise ValueError("retrain_replay_chronology_invalid")
    if (
        improvement_gate(
            frozen["development"][study.ARMS[0]], frozen["development"][study.ARMS[1]]
        )
        != report["development_gate"]
    ):
        raise ValueError("retrain_development_gate_not_reproducible")
    original = RichArtifact()
    parity = {}
    for name in study.ARMS:
        r = frozen["records"][name]
        study.verify_files({r["artifact"]: r["sha256"]})
        model = joblib.load(ROOT / r["artifact"])
        assert_original_recipe(model, original.bundle)
        if (
            r["parity_max_delta"] > 1e-12
            or r["fit_rows"] != data["assets"][name]["rows"]
        ):
            raise ValueError("retrain_fitting_record_or_parity_changed")
    for cohort, item in data["tests"].items():
        frame, _ = transform_frame(pd.read_parquet(ROOT / item["path"]))
        path = study.RUN / (cohort + "-predictions.npz")
        study.verify_files(
            {
                path.relative_to(ROOT).as_posix(): report["score_bindings"][
                    path.relative_to(ROOT).as_posix()
                ]
            }
        )
        stored = np.load(path)
        if not np.array_equal(stored["frozen_native"], stored["frozen_matched_policy"]):
            raise ValueError("threshold_only_reference_changed_model_scores")
        positive = frame.label.to_numpy() == 1
        indices = np.linspace(0, len(frame) - 1, min(128, len(frame)), dtype=int)
        checks = {}
        for name, r in frozen["records"].items():
            scores = check_scores(stored[name], len(frame))
            for level in ("warning", "high"):
                flags = scores >= r["policies"][level]["threshold"]
                counts = {
                    "tp": int((flags & positive).sum()),
                    "fn": int((~flags & positive).sum()),
                    "fp": int((flags & ~positive).sum()),
                    "tn": int((~flags & ~positive).sum()),
                }
                m = report["cohorts"][cohort]["levels"][level][name]
                if counts != m["confusion_matrix"]:
                    raise ValueError("retrain_saved_score_confusion_mismatch")
                if positive.all() and any(
                    m[k] is not None
                    for k in ("fpr", "precision", "accuracy", "brier_score")
                ):
                    raise ValueError(
                        "positive_only_feed_has_unsupported_binary_metrics"
                    )
            if name.startswith("frozen_"):
                replay = original.predict_cores(frame.core.iloc[indices])
            else:
                replay = predict_bundle(
                    joblib.load(ROOT / r["artifact"]), frame.core.iloc[indices]
                )
            delta = (
                float(np.max(np.abs(replay - scores[indices]))) if len(indices) else 0.0
            )
            if delta > 1e-12:
                raise ValueError("retrain_saved_scores_do_not_match_reloaded_artifact")
            checks[name] = {
                "rows_recounted": len(frame),
                "distributed_replay_cases": len(indices),
                "max_delta": delta,
            }
        parity[cohort] = checks
        stored.close()
    xml = study.RUN / "final-tests.xml"
    suites = list(ET.parse(xml).getroot().iter("testsuite"))
    tests = {
        key: sum(int(s.get(key, 0)) for s in suites)
        for key in ("tests", "failures", "errors", "skipped")
    }
    if tests["tests"] < 237 or any(tests[k] for k in ("failures", "errors", "skipped")):
        raise ValueError("retrain_test_run_incomplete")
    test_manifest = study.read(study.RUN / "test-run-manifest.json")
    for filename, expected in test_manifest["source_reports"].items():
        if checksum(study.RUN / filename) != expected:
            raise ValueError("retrain_source_junit_report_changed")
    if test_manifest["aggregate"] != tests:
        raise ValueError("retrain_combined_test_counts_changed")
    if (
        report["test_used_for_fitting_or_selection"]
        or report["new_independent_test"]
        or report["production_ready"]
    ):
        raise ValueError("retrain_evidence_status_incorrect")
    study.check()
    result = {
        "verified_at_utc": now(),
        "report_sha256": checksum(study.REPORT),
        "verifier_sha256": checksum(__file__),
        "test_report_sha256": checksum(xml),
        "tests": tests,
        "test_run_manifest": test_manifest,
        "original_estimator_hyperparameters_preserved": True,
        "new_estimators_fitted_from_scratch": True,
        "original_v6_binary_metadata_thresholds_unchanged": True,
        "chronology_verified": True,
        "isolation": data["isolation"],
        "all_eight_exposure_sidecars_unchanged": len(data["all_sidecars"]),
        "prediction_parity_and_confusion_recounts": parity,
        "selection_performed": False,
        "production_ready": False,
    }
    write_json(VERIFY, result)
    print(
        json.dumps(
            {
                "tests": tests,
                "verified_cohorts": len(parity),
                "fitting_rows": data["assets"][study.ARMS[1]]["rows"],
                "production_ready": False,
            }
        ),
        flush=True,
    )


def pct(value):
    return "n/a" if value is None else f"{100 * value:.3f}%"


def val(value):
    return "n/a" if value is None else f"{value:.6f}"


def ci(values):
    return (
        "n/a" if values is None else f"[{100 * values[0]:+.3f}, {100 * values[1]:+.3f}]"
    )


def render():
    r, verification = study.read(study.REPORT), study.read(VERIFY)
    if checksum(study.REPORT) != verification["report_sha256"]:
        raise ValueError("retrain_report_changed_after_verification")
    data = study.read(study.RUN / "data-frozen.json")
    foundation, current = study.ARMS
    names = {
        "frozen_native": "v6 asli / threshold asli",
        "frozen_matched_policy": "v6 asli / threshold development sama",
        foundation: "Recipe v6 / lima sumber terkurasi",
        current: "Recipe v6 / seluruh fitting terbaru",
    }
    lines = [
        "# Pelatihan recipe v6 dengan data saat ini",
        "",
        f"Selesai: {r['completed_at_utc']}. Dua model baru dilatih dari nol menggunakan constructor/hyperparameter asli v6. "
        "Keduanya menggunakan Logistic Regression C=2, TF-IDF karakter 100k/kata 20k, fitur numerik, bobot sumber akar kuadrat, "
        "serta sigmoid calibration tanpa bobot. Tidak ada pencarian hyperparameter atau pemilihan pemenang dari test.",
        "",
        "## Perbandingan yang diuji",
        "",
        "| Model | URL fitting | Sumber | Keterangan |",
        "| --- | ---: | ---: | --- |",
        "| Frozen v6 asli | 532.793 | 5 | Binary, calibration dan threshold layanan tetap asli |",
    ]
    for name in study.ARMS:
        a = r["fitting_coverage"][name]
        lines.append(
            f"| {names[name]} | {a['rows']:,} | {r['records'][name]['fit_sources']} | Encoder/classifier/calibrator baru; semua constructor cocok dengan v6 |"
        )
    lines += [
        "",
        "Jumlah sumber kelima dicocokkan langsung dengan metadata asli: `mendeley2020`. "
        "[Audit schema sebelum fitting](v6-current-retrain-source-schema-audit.json) mencatat koreksi alias deskriptif `mendeley`; "
        "belum ada model atau prediksi test saat koreksi dilakukan.",
        "",
        "Perbedaan **seluruh fitting terbaru vs lima sumber terkurasi** mengukur pengaruh tambahan data dengan recipe, "
        "sanitasi, calibration, threshold dan tune yang sama. Perbandingan langsung terhadap binary frozen v6 juga mencakup perubahan "
        "kurasi privasi serta komposisi development, sehingga tidak boleh seluruhnya diatribusikan pada jumlah data. "
        "Sanitizer eksperimen melakukan redaksi assignment secret pendek; preprocessing v6 asli tidak diam-diam diubah.",
        "",
        "## Development sebelum replay",
        "",
        "Calibration 50.749, threshold 58.840 dan tune 107.094 dipisahkan berdasarkan domain/private tenant. "
        "Vocabulary/IDF/scaler hanya di-fit pada fitting. Threshold warning/HIGH mengikuti recipe asli: batas FPR empiris per sumber 1%/0,1%. "
        "Batas ini tidak menjamin FPR pada test atau trafik nyata.",
        "",
        "| Model | Macro recall tune | FPR tune | Macro Brier tune | Warning | HIGH |",
        "| --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    for name, result in r["development"].items():
        m, record = result["primary"], r["records"][name]
        lines.append(
            f"| {names[name]} | {pct(m['macro_source_recall'])} | {pct(m['overall']['fpr'])} | {val(m['macro_source_brier'])} | {record['policies']['warning']['threshold']:.9f} | {record['policies']['high']['threshold']:.9f} |"
        )
    g = r["development_gate"]
    lines += [
        "",
        f"Gate peningkatan current vs foundation: **{g['passed']}**. Delta macro recall {100 * g['macro_recall_delta']:+.3f} pp, "
        f"delta recall sumber terburuk {100 * g['worst_source_recall_delta']:+.3f} pp, delta macro Brier {g['macro_brier_delta']:+.6f}. "
        "Gate ditetapkan sebelum fitting. Semua model dan threshold dibekukan sebelum replay; tidak ada promosi otomatis.",
        "",
        "## Replay pada benchmark yang telah teramati",
        "",
        "Seluruh cohort berikut sudah pernah teramati dalam eksperimen terdahulu. Pembekuan baru melindungi pemisahan prosedur "
        "training/test dalam percobaan ini; tidak mengubah benchmark lama menjadi test independen baru atau gold Indonesia.",
        "",
        "| Cohort | Model | Benign / phishing | TP / FN / FP / TN | Accuracy | Recall | Precision sampel | FPR | Brier | ECE |",
        "| --- | --- | ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for cohort, row in r["cohorts"].items():
        for name, m in row["levels"]["warning"].items():
            cm = m["confusion_matrix"]
            lines.append(
                f"| {cohort} | {names[name]} | {m['benign']} / {m['phishing']} | {cm['tp']} / {cm['fn']} / {cm['fp']} / {cm['tn']} | {pct(m['accuracy'])} | {pct(m['recall'])} | {pct(m['precision'])} | {pct(m['fpr'])} | {val(m['brier_score'])} | {val(m.get('ece_10_fixed_bins'))} |"
            )
    lines += [
        "",
        "Precision mengikuti prevalensi sampel; bukan estimasi precision trafik. Feed positif saja tidak memiliki accuracy biner, FPR, precision atau Brier.",
        "",
        "| Cohort | Current − foundation recall 95% (pp) | Current − foundation FPR 95% (pp) | Current − v6 asli recall 95% (pp) |",
        "| --- | --- | --- | --- |",
    ]
    for cohort, row in r["cohorts"].items():
        pairs = row["paired_current_minus_reference"]["warning"]
        lines.append(
            f"| {cohort} | {ci(pairs[foundation]['recall_delta95'])} | {ci(pairs[foundation]['fpr_delta95'])} | {ci(pairs['frozen_native']['recall_delta95'])} |"
        )
    lines += [
        "",
        "Interval memakai 1.000 bootstrap domain/private tenant berpasangan. Wilson, reliability bins, metrik HIGH, "
        "perbandingan threshold-matched dan subgroup panjang/path dalam/private/non-private tersedia di JSON. "
        "Nol FP pada sedikit benign tetap memiliki ketidakpastian; PhishBench hanya dua benign dan ISCX hanya 70 benign.",
        "",
        "![Perbandingan retraining v6](v6-current-retrain-evaluation.png)",
        "",
        "## Data dan batas kesimpulan",
        "",
        "| Sumber fitting terbaru | Jumlah |",
        "| --- | ---: |",
    ]
    fit = pd.read_parquet(
        ROOT / data["assets"][current]["path"], columns=["training_source"]
    )
    for source, count in fit.training_source.value_counts().items():
        lines.append(f"| {source} | {count:,} |")
    lines += [
        "",
        "- Hanya partisi fitting yang diizinkan digabungkan: base 616.050, Stealth 52.334, ISCX 3.056. Semua 169.393 Mendeley reserved dan semua holdout historis tetap terpisah.",
        "- Kedua encoder memakai batas vocabulary 150.000, source cap 60.000 dan seed asli 20261101. Source ID tidak menjadi fitur classifier.",
        "- Label penerbit bisa salah dan pemisahan domain tidak menjamin independensi kampanye. Tidak dibuat reviewer, label manusia atau validasi Indonesia baru.",
        "- Sanitasi tetap heuristik. Tidak ada target URL yang dikunjungi, HTML dijalankan, atau baris dataset dikirim ke LLM.",
        "- Foundation DeepURLBench membatasi penggunaan nonkomersial. Hak data Ebbu dan data asli replika ISCX belum memiliki clearance redistribusi/komersial. Artifact tambahan disimpan lokal untuk riset.",
        "- Model layanan/notebook tetap v6 asli dan production_ready=false. LOW tidak berarti aman.",
        "",
        "## Verifikasi dan lokasi hasil",
        "",
        f"**{verification['tests']['tests']} tes lulus**, nol gagal/error/skip. Constructor seluruh estimator dibandingkan dengan artifact v6 asli; "
        "seluruh confusion matrix warning/HIGH dihitung ulang dari skor tersimpan. Prediksi diperiksa ulang setelah reload pada probe tersebar di setiap cohort; delta <=1e-12. "
        "Binary, metadata dan threshold layanan asli, registry dan seluruh delapan sidecar tetap utuh.",
        "",
        "[Protokol](v6-current-retrain-20261107-protocol.json), [JSON lengkap](v6-current-retrain-evaluation.json), "
        "[verifikasi](v6-current-retrain-verification.json). Data gabungan, model, checkpoint dan skor tersimpan di `ml/runs/v6-current-retrain-20261107/`, yang diabaikan Git.",
        "",
        "Pemeriksaan lokal: `python scripts/experiment_v6_current_retrain.py check` dan `python scripts/report_v6_current_retrain.py`. "
        "Runner memiliki tahap prepare/train/evaluate, menolak overwrite freeze/evaluasi dan memeriksa hash sebelum melanjutkan checkpoint. "
        "Pengulangan training membutuhkan run baru dengan input/protokol terpin; jangan menghapus registry exposure.",
    ]
    MARKDOWN.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    plot(r)
    print("Saved aggregate Markdown, PNG and SVG retraining reports")


def plot(report):
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    names = list(report["cohorts"])
    labels = [n.removeprefix("observed_") for n in names]
    fig, axes = plt.subplots(1, 3, figsize=(16, 7), constrained_layout=True)
    references = ["frozen_native", study.ARMS[0], study.ARMS[1]]
    titles = [
        "Frozen v6 native",
        "V6 recipe / five sources",
        "V6 recipe / current data",
    ]
    colors = ["#888888", "#1768ac", "#408753"]
    y = np.arange(len(names))
    for i, (role, title, color) in enumerate(zip(references, titles, colors)):
        metrics = [report["cohorts"][n]["levels"]["warning"][role] for n in names]
        axes[0].barh(
            y + (i - 1) * 0.25,
            [100 * m["recall"] for m in metrics],
            height=0.23,
            label=title,
            color=color,
        )
        axes[1].scatter(
            [np.nan if m["fpr"] is None else 100 * m["fpr"] for m in metrics],
            y + (i - 1) * 0.15,
            label=title,
            color=color,
            s=30,
        )
        axes[2].scatter(
            [np.nan if m["brier_score"] is None else m["brier_score"] for m in metrics],
            y + (i - 1) * 0.15,
            color=color,
            s=30,
        )
    for ax in axes:
        ax.set_yticks(y, labels)
        ax.invert_yaxis()
        ax.grid(axis="x", alpha=0.2)
        ax.spines[["top", "right"]].set_visible(False)
    axes[0].set(title="Phishing recall", xlabel="Recall (%)", xlim=(0, 100))
    axes[1].set(title="False positive rate", xlabel="FPR (%)")
    axes[2].set(
        title="Calibration / discrimination error", xlabel="Brier (lower is better)"
    )
    axes[0].legend(loc="lower right", fontsize=8, frameon=False)
    fig.suptitle(
        "Original v6 recipe retrained on current authorized fitting data\nHistorical observed benchmarks; warning policies fixed on separate development; positive-only FPR/Brier unavailable",
        fontsize=12,
    )
    fig.savefig(ROOT / "ml/reports/v6-current-retrain-evaluation.png", dpi=180)
    fig.savefig(ROOT / "ml/reports/v6-current-retrain-evaluation.svg")
    plt.close(fig)


if __name__ == "__main__":
    verify()
    render()
