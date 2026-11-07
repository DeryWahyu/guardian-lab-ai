"""Render aggregate-only experiment tables and a standalone learning-curve plot."""

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Patch
import numpy as np

from guardian_ml.paths import ROOT
import experiment_v6_learning as study


def pct(value):
    return "n/a" if value is None else f"{100 * value:.3f}%"


def number(value):
    return "n/a" if value is None else f"{value:.6f}"


def interval(values, scale=100):
    if values is None or any(v is None for v in values):
        return "n/a"
    return f"[{scale * values[0]:.3f}, {scale * values[1]:.3f}]"


def main():
    report = study.read(study.REPORT)
    selected = study.read(study.RUN / "selected-frozen.json")
    verified = study.read(ROOT / "ml/reports/v6-learning-verification.json")
    decision = report["selection"]
    challenger = decision["diagnostic"]
    results, records = report["development_results"], report["records"]
    curve = ["curve_25", "curve_50", "curve_75", "control"]
    candidates = [n for n in results if not n.startswith("curve_")]
    lines = [
        "# Learning curve, regularisasi, pembobotan dan data tambahan v6",
        "",
        f"Selesai: {report['completed_at_utc']}. Model riset yang dipertahankan: **{decision['selected']}**. "
        f"Gate development {'terpenuhi' if decision['gate_passed'] else 'belum terpenuhi oleh kandidat baru'}. "
        f"Challenger yang dibekukan untuk evaluasi: `{challenger}`. "
        "Model layanan dan notebook utama tetap v6 asli; `production_ready=false`.",
        "",
        "Delapan classifier Logistic Regression baru dilatih: tiga titik learning curve dan lima ablation. "
        "Model control yang sudah dibekukan menjadi titik 100%. Semua kalibrator baru memakai calibration terpisah. "
        "Seleksi hanya menggunakan tune; learning curve tidak ikut menjadi calon pemenang.",
        "",
        "## Learning curve",
        "",
        "Persentase adalah proporsi domain/private tenant, bukan jumlah baris persis. Subset saling bersarang; "
        "vocabulary, IDF dan scaler dilatih ulang pada setiap subset. Satu seed tidak mengukur variasi antartraining.",
        "",
        "| Fraksi domain | URL fitting | Domain/tenant | Fitur | Macro recall tune | FPR tune | Macro Brier tune |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for name in curve:
        r, m = records[name], results[name]["primary"]
        lines.append(
            f"| {r['fraction']:.0%} | {r['fit_rows']:,} | {r['fit_groups']:,} | {r['feature_count']:,} | {pct(m['macro_source_recall'])} | {pct(m['overall']['fpr'])} | {number(m['macro_source_brier'])} |"
        )
    gain = (
        results["control"]["primary"]["macro_source_recall"]
        - results["curve_75"]["primary"]["macro_source_recall"]
    )
    lines += [
        "",
        f"Perubahan macro recall dari 75% ke 100%: **{100 * gain:+.3f} percentage point**. "
        "Ini diagnosis terhadap komposisi data dan recipe saat ini, bukan bukti bahwa penambahan data apa pun akan memperbaiki model.",
        "",
        "![Learning curve dan ablation](v6-learning-evaluation.png)",
        "",
        "## Kandidat development",
        "",
        "Threshold utama ditentukan pada threshold partition dengan batas FPR empiris 1% per sumber yang memiliki >=100 benign. "
        "Batas itu tidak menjamin FPR tune, test, kelompok kecil, atau trafik nyata. Private/non-private hosting diperiksa tersendiri.",
        "",
        "| Kandidat | URL fitting | Macro recall | Recall private hosting | FPR tune | Macro Brier | Gate |",
        "| --- | ---: | ---: | ---: | ---: | ---: | --- |",
    ]
    for name in candidates:
        row = results[name]
        detail = decision["details"].get(name)
        gate = (
            "control"
            if detail is None
            else str(detail["detection_gate"] or detail["calibration_gate"])
        )
        lines.append(
            f"| {name} | {records[name]['fit_rows']:,} | {pct(row['primary']['macro_source_recall'])} | {pct(row['slices']['private_hosting']['recall'])} | {pct(row['primary']['overall']['fpr'])} | {number(row['primary']['macro_source_brier'])} | {gate} |"
        )
    lines += [
        "",
        "| Kandidat | Delta macro recall (pp) | Delta recall sumber terburuk (pp) | Delta Brier | Guard private/non-private |",
        "| --- | ---: | ---: | ---: | --- |",
    ]
    for name, detail in decision["details"].items():
        lines.append(
            f"| {name} | {100 * detail['macro_recall_delta']:+.3f} | {100 * detail['worst_source_recall_delta']:+.3f} | {detail['macro_brier_delta']:+.6f} | {detail['structure_guard']} |"
        )
    lines += [
        "",
        "## Pengujian setelah model dan threshold dibekukan",
        "",
        "Ebbu tidak digunakan sebagai sumber tambahan fitting dalam eksperimen ini. PWD2021 sebelumnya memakai sebagian data asal Ebbu: "
        "pemisahan domain/URL menutup overlap identitas, tetapi tidak membuktikan independensi penuh dari proses pengumpulan. "
        "ISCX adalah holdout domain dari sumber yang juga memasok 3.056 baris fitting. Global 50.000 adalah benchmark yang sudah teramati.",
        "",
        "| Cohort | Model | N benign / phishing | TP / FN / FP / TN | Recall | Precision sampel | FPR | Brier | ECE |",
        "| --- | --- | ---: | --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    for cohort, data in report["cohorts"].items():
        for name, m in data["results"]["all"].items():
            cm = m["confusion_matrix"]
            lines.append(
                f"| {cohort} | {name} | {m['benign']} / {m['phishing']} | {cm['tp']} / {cm['fn']} / {cm['fp']} / {cm['tn']} | {pct(m['recall'])} | {pct(m['precision'])} | {pct(m['fpr'])} | {number(m['brier_score'])} | {number(m.get('ece_10_fixed_bins'))} |"
            )
    lines += [
        "",
        "Precision di tabel mengikuti prevalensi sampel; bukan estimasi precision trafik. "
        "Domain bootstrap berpasangan memakai 1.000 replikasi. Wilson mengasumsikan baris independen dan ditampilkan bersama bootstrap dalam JSON.",
        "",
        "| Cohort | Delta recall challenger−control, 95% (pp) | Delta FPR, 95% (pp) | FPR challenger Wilson 95% |",
        "| --- | --- | --- | --- |",
    ]
    for cohort, data in report["cohorts"].items():
        paired = data["paired_diagnostic_minus_control"]
        lines.append(
            f"| {cohort} | {interval(paired['recall_delta95']) if paired else 'n/a'} | {interval(paired['fpr_delta95']) if paired else 'n/a'} | {interval(data['results']['all'][challenger]['fpr_wilson95_rows_iid_assumption'])} |"
        )
    lines += [
        "",
        "## Kebijakan threshold yang telah ditetapkan sebelum test",
        "",
        "Semua kebijakan dilaporkan; hasil test tidak digunakan memilih kebijakan baru. Angka budget berikut adalah batas empiris development per sumber.",
        "",
        "| Cohort | Model | Budget development | Threshold | Recall test | FPR test |",
        "| --- | --- | ---: | ---: | ---: | ---: |",
    ]
    for cohort, data in report["cohorts"].items():
        for name, policies in data["policies"].items():
            for budget, metrics in policies.items():
                lines.append(
                    f"| {cohort} | {name} | {pct(float(budget))} | {metrics['threshold']:.9f} | {pct(metrics['recall'])} | {pct(metrics['fpr'])} |"
                )
    lines += [
        "",
        "## Cakupan dan keterbatasan",
        "",
        "- Intake 118.918 URL menghasilkan 118.038 representasi tersanitasi. Setelah novelty audit: fitting 3.056, Ebbu test 8.849, ISCX test 2.066. Semua input supported dicatat dalam sidecar exposure, termasuk yang dikeluarkan.",
        "- Fitting tambahan hanya mencakup 108 benign dan 40 hard benign unik. Phishing private hosting bertambah 104. Tidak ada asumsi bahwa banyak data otomatis memperbaiki model.",
        "- ISCX test hanya mempunyai 70 benign; angka FPR dan subgroup kecil perlu dibaca bersama intervalnya. Kesamaan byte replika ISCX dengan sumber asli belum dapat dibuktikan.",
        "- Sumber historis dan label penerbit dapat salah. Tidak ada reviewer, label gold Indonesia, atau holdout temporal Indonesia baru yang dibuat.",
        "- Sanitizer tetap heuristik. Tidak ada URL target dikunjungi, HTML dieksekusi, atau data mentah dikirim ke LLM.",
        "- Lisensi eksplisit Ebbu dan hak data asli ISCX belum jelas; artifact tambahan tetap lokal riset. Foundation juga memiliki batas nonkomersial. Ini tidak memberi izin penggunaan komersial atau redistribusi data.",
        "- Seluruh 169.393 kasus Mendeley yang sudah dicadangkan tetap tidak digunakan untuk fitting, calibration, threshold atau pemilihan model.",
        "",
        "Penyaringan input per kelas (0=benign, 1=phishing):",
        "",
        "| Sumber | Raw 0 / 1 | Supported 0 / 1 | Unsupported 0 / 1 |",
        "| --- | ---: | ---: | ---: |",
        *[
            f"| {name} | {a['raw_label_counts']['0']} / {a['raw_label_counts']['1']} | "
            f"{a['supported_label_counts']['0']} / {a['supported_label_counts']['1']} | "
            f"{a['unsupported_by_label']['0']} / {a['unsupported_by_label']['1']} |"
            for name, a in verified["publisher_sanitization_counts"].items()
        ],
        "",
        "## Verifikasi dan reproduksi",
        "",
        f"{verified['tests']['tests']} tes lulus; nol gagal/error/skip. {len(verified['saved_model_parity'])} artifact diperiksa ulang pada masing-masing 128 probe; delta nol. "
        f"Audit mencakup {len(verified['novelty_audit'])} sumber exposure/cache/identitas. Hash binary, metadata dan threshold v6 aktif tetap sama.",
        "",
        "Protokol: [JSON](v6-learning-20261106-protocol.json). Hasil lengkap, interval, calibration bins dan subgroup: "
        "[JSON evaluasi](v6-learning-evaluation.json). [Verifikasi](v6-learning-verification.json). "
        "[Audit sumber](../../ai-agent-docs/research/v6-learning-source-audit-20261106.md). "
        "Artifact dan predictions berada di `ml/runs/v6-learning-20261106/` yang diabaikan Git.",
        "",
        "Untuk memeriksa hasil lokal: `python scripts/experiment_v6_learning.py check`, "
        "`python scripts/verify_v6_learning.py`, `python scripts/render_v6_learning.py`. "
        "Runner menolak menimpa intake/seleksi/evaluasi yang telah dibekukan. Replay training memerlukan run/protokol baru dan hash input yang sama; "
        "menghapus registry exposure bukan prosedur replay yang sah.",
    ]
    (ROOT / "ml/reports/v6-learning-evaluation.md").write_text(
        "\n".join(lines) + "\n", encoding="utf-8", newline="\n"
    )
    plt.rcParams.update(
        {"font.size": 10, "axes.spines.top": False, "axes.spines.right": False}
    )
    fig, axes = plt.subplots(2, 2, figsize=(13, 9), constrained_layout=True)
    x = [records[n]["fit_rows"] / 1000 for n in curve]
    axes[0, 0].plot(
        x,
        [100 * results[n]["primary"]["macro_source_recall"] for n in curve],
        "o-",
        color="#1768ac",
    )
    axes[0, 0].set(
        title="Learning curve: macro source recall (tune)",
        xlabel="Fitting URLs (thousands)",
        ylabel="Recall (%)",
    )
    axes[0, 1].plot(
        x,
        [100 * results[n]["primary"]["overall"]["fpr"] for n in curve],
        "o-",
        color="#b64926",
    )
    axes[0, 1].set(
        title="False positives on unchanged tune",
        xlabel="Fitting URLs (thousands)",
        ylabel="FPR (%)",
    )
    for label, key, color in [
        ("Fitting", "fit_metrics", "#438551"),
        ("Tune", "primary", "#1768ac"),
    ]:
        values = [
            results[n][key]["brier_score"]
            if key == "fit_metrics"
            else results[n][key]["overall"]["brier_score"]
            for n in curve
        ]
        axes[1, 0].plot(x, values, "o-", label=label, color=color)
    axes[1, 0].set(
        title="Calibration error (row-weighted Brier)",
        xlabel="Fitting URLs (thousands)",
        ylabel="Brier (lower is better)",
    )
    axes[1, 0].legend(frameon=False)
    names = list(decision["details"])
    values = [100 * decision["details"][n]["macro_recall_delta"] for n in names]
    axes[1, 1].barh(
        np.arange(len(names)),
        values,
        color=[
            "#438551"
            if decision["details"][n]["detection_gate"]
            or decision["details"][n]["calibration_gate"]
            else "#b64926"
            for n in names
        ],
    )
    axes[1, 1].set_yticks(np.arange(len(names)), names)
    axes[1, 1].axvline(0, color="#777", linewidth=0.7)
    axes[1, 1].legend(
        handles=[
            Patch(color="#438551", label="Gate passed"),
            Patch(color="#b64926", label="Gate not met"),
        ],
        frameon=False,
        fontsize=8,
        loc="best",
    )
    axes[1, 1].set(
        title="Candidate change vs retained control",
        xlabel="Macro recall change (percentage points)",
    )
    for ax in axes.flat:
        ax.grid(axis="y", alpha=0.18)
    fig.suptitle(
        "v6 research: nested learning curve and separate LR ablations\nPrimary policy: empirical source FPR budget 1%; one training seed; no production promotion",
        fontsize=13,
    )
    fig.savefig(ROOT / "ml/reports/v6-learning-evaluation.png", dpi=180)
    fig.savefig(ROOT / "ml/reports/v6-learning-evaluation.svg")
    plt.close(fig)
    del selected
    print("Saved aggregate report, PNG and SVG learning-curve plots")


if __name__ == "__main__":
    main()
