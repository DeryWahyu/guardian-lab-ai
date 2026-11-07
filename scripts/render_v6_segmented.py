"""Aggregate-only report and figure for the frozen segmented research experiment."""

import json

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from guardian_ml.paths import ROOT
from experiment_v6_segmented import REPORT


def pct(value, digits=2):
    return "Tidak tersedia" if value is None else f"{100 * value:.{digits}f}%"


def ci(values, digits=2):
    return (
        "Tidak tersedia"
        if not values or values[0] is None
        else f"[{100 * values[0]:.{digits}f}%; {100 * values[1]:.{digits}f}%]"
    )


def point_interval(values, digits=2):
    if not values or values[0] is None:
        return "Tidak tersedia"
    return f"[{100 * values[0]:+.{digits}f}; {100 * values[1]:+.{digits}f}]"


def main():
    report = json.loads(REPORT.read_text())
    frozen = report["selected_freeze"]
    cache = report["cache_freeze"]
    selection = frozen["selection"]
    intake = cache["intake"]["data"]
    review = json.loads(
        (ROOT / "ml/reports/v6-segmented-human-review-status.json").read_text()
    )
    candidate_name = frozen["evaluated_candidate"]
    lines = [
        "# Eksperimen fitur URL terpisah, kalibrasi dan data terarah",
        "",
        f"Kandidat riset yang dipertahankan: `{selection['selected']}`. Challenger yang diuji: `{candidate_name}`. Gate development lolos: **{selection['development_gate_passed']}**. Semua pilihan dan threshold dibekukan dari development sebelum final scoring. V6 aktif tidak diganti, production_ready=false.",
        "",
        "Jika control_native dipertahankan, hasil challenger berikut adalah diagnosis kandidat gagal-gate, bukan bukti model pengganti telah disetujui. Seluruh benchmark lama, termasuk Zenodo websites V2, tetap berstatus teramati.",
        "",
        "## Data dan metode",
        "",
        "Tiga ablation memakai 616.050 URL fitting yang sama dari sembilan sumber: tambahan struktur numerik, teks host/subdomain/path terpisah, dan gabungan keduanya. Encoder dasar dipakai ulang tanpa refit; vocabulary/scaler tambahan di-fit hanya pada fitting asli. Arm augmentation terpisah memakai tambahan data baru tanpa refit encoder pada holdout. Semua classifier tetap Logistic Regression C=2/liblinear, dengan source/domain weighting yang sama dan sigmoid atau beta calibration monoton pada calibration terpisah.",
        "",
        f"[StealthPhisher](https://data.mendeley.com/datasets/m2479kmybx/1), CC BY 4.0: {intake['intake']['raw_rows']:,} baris mentah, {intake['intake']['sanitized_rows']:,} didukung setelah sanitasi, {intake['curation']['retained_rows']:,} URL baru setelah konflik/duplikat/exposure/domain cap. Literal Phishing/Legitimate mengikuti penerbit; tidak ada label diganti berdasarkan model.",
        "",
        "| Alokasi StealthPhisher | URL | Benign | Phishing | Domain/tenant |",
        "| --- | ---: | ---: | ---: | ---: |",
    ]
    for name, row in intake["partitions"].items():
        lines.append(
            f"| {name} | {row['rows']:,} | {row['classes'].get('0', 0):,} | {row['classes'].get('1', 0):,} | {row['groups']:,} |"
        )
    lines += [
        "",
        "Arm augmentation memiliki 668.384 URL fitting dari sepuluh sumber. Partisi calibration, threshold dan tune tetap sama dengan control, sehingga sumber tambahan belum diwakili dalam calibration. Holdout StealthPhisher adalah domain baru dari penerbit yang juga dipakai oleh salah satu arm, bukan independent-source benchmark untuk arm tersebut. Tanggal penerbitan Januari 2025 bukan tanggal observasi tiap kasus atau bukti benign kontemporer.",
        "",
        "[Audit coverage](v6-segmented-data-coverage.json) menemukan nol benign tambahan dengan URL >120 karakter atau path sedalam empat slash, dan hanya 43 benign private hosting. Ada 9.334 phishing tambahan di luar private hosting. Data membantu cakupan domain biasa, tetapi belum menutup gap hard benign/path panjang; holdout Stealth juga tidak memiliki URL >120 karakter. Bias ini membatasi klaim generalisasi hasil sumber baru.",
        "",
        "[PhishBench-External V2](https://data.mendeley.com/datasets/2ctjcnm9kn/2), CC BY 4.0, menyediakan pengujian penerbit tambahan yang seluruhnya dicadangkan. Pemeriksaan awal mencatat kegagalan integritas; retry kemudian cocok tepat dengan pin byte/SHA penerbit. CSV memakai kolom Results, bukan label; amendemen sebelum prediksi memetakan 0=benign/1=phishing sesuai dokumentasi, setelah menghitung 500 kasus masing-masing. Setelah sanitasi/exposure tersisa 272 URL: 270 phishing dan **hanya dua benign**. Tidak ada label dibuat dari prediksi atau nama institusi.",
        "",
        "Seluruh input tersanitasi, termasuk exclusions, fitting dan holdout, terdaftar dalam sidecar. Historical registry, setiap sidecar, cache v6 dan identitas nyata seluruh partisi/benchmark lama diaudit sebelum fitting. URL target tidak dikunjungi, HTML tidak dieksekusi, raw URL tidak disimpan. Redaksi tetap heuristik, bukan anonimisasi sempurna.",
        "",
        "## Seleksi development",
        "",
        "Gate mempertahankan peningkatan recall tanpa regresi besar pada FPR dan Brier per sumber. Brier mengukur kualitas probabilitas gabungan, bukan kalibrasi murni; ECE dan reliability bins juga dilaporkan. Kalibrasi monoton sendiri tidak meningkatkan ranking. Semua kriteria ada dalam protokol sebelum fitting; hasil test tidak dipakai memilih pemenang.",
        "",
        "| Varian | Macro source recall | Minimum source recall | Macro source Brier | Lolos gate |",
        "| --- | ---: | ---: | ---: | --- |",
    ]
    names, recalls, briers = [], [], []
    for name, row in frozen["tune"].items():
        if row.get("invalid"):
            lines.append(f"| {name} | Ditolak: {row['invalid']} | | | False |")
            continue
        detail = selection["details"].get(name, {})
        gate = detail.get("detection_gate", False) or detail.get(
            "calibration_gate", False
        )
        status = "Control" if name == "control_native" else str(gate)
        lines.append(
            f"| {name} | {pct(row['macro_source_recall'])} | {pct(row['minimum_source_recall'])} | {row['macro_source_brier']:.6f} | {status} |"
        )
        names.append(name)
        recalls.append(100 * row["macro_source_recall"])
        briers.append(row["macro_source_brier"])
    lines += [
        "",
        "### Regresi development per sumber",
        "",
        "| Varian | Macro recall delta, point | Worst recall delta, point | Worst FPR increase, point | Worst Brier increase |",
        "| --- | ---: | ---: | ---: | ---: |",
    ]
    for name, row in selection["details"].items():
        lines.append(
            f"| {name} | {100 * row['recall_delta']:+.3f} | {100 * row['worst_source_recall_delta']:+.3f} | {100 * row['worst_source_fpr_increase']:+.3f} | {row['worst_source_brier_increase']:+.6f} |"
        )
    lines += [
        "",
        "## Pengujian beku",
        "",
        "Strict berarti budget development 1% per sumber yang cukup support; FPR test tiap model dapat berbeda. Active memakai threshold warning asli. Precision adalah precision sampel, bukan precision trafik Indonesia.",
        "",
        "| Cohort | URL | Recall aktif | Recall control | Recall challenger | FPR control | FPR challenger |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    cohorts = {
        name: row for name, row in report["cohorts"].items() if row.get("policies")
    }
    for name, row in cohorts.items():
        m = row["policies"]
        lines.append(
            f"| {name} | {row['rows']:,} | {pct(m['active_original']['recall'])} | {pct(m['control_strict']['recall'])} | {pct(m['candidate_strict']['recall'])} | {pct(m['control_strict']['fpr'], 4)} | {pct(m['candidate_strict']['fpr'], 4)} |"
        )
    lines += [
        "",
        "### Counts dan ketidakpastian challenger",
        "",
        "| Cohort | TP | FN | FP | TN | Precision | Recall domain 95% | FPR domain 95% | FPR Wilson 95% |",
        "| --- | ---: | ---: | ---: | ---: | ---: | --- | --- | --- |",
    ]
    for name, cohort in cohorts.items():
        row = cohort["policies"]["candidate_strict"]
        counts, interval = row["confusion_matrix"], row.get("domain_bootstrap95", {})
        lines.append(
            f"| {name} | {counts['tp']} | {counts['fn']} | {counts['fp']} | {counts['tn']} | {pct(row['precision'])} | {ci(interval.get('recall95'))} | {ci(interval.get('fpr95'), 4)} | {ci(row['fpr_wilson95_rows_iid_assumption'], 4)} |"
        )
    lines += [
        "",
        "Bootstrap 1.000 domain/private tenants bersifat kondisional pada label penerbit dan tidak membuktikan kampanye independen. Wilson row-IID mengabaikan korelasi domain. **Dua benign pada PhishBench tidak cukup untuk menilai FPR**; nol FP sekalipun memiliki upper Wilson 95% sekitar 65,76%. LegitPhish memiliki hanya 28 benign; nol FP memberi upper sekitar 12,06%. PhishTank positif saja tidak menyediakan FPR/accuracy/precision trafik.",
        "",
        "### Perbedaan berpasangan terhadap control riset",
        "",
        "| Cohort | Recall delta domain 95%, percentage point | FPR delta domain 95%, percentage point |",
        "| --- | --- | --- |",
    ]
    for name, row in cohorts.items():
        paired = row["paired_candidate_minus"].get("control", {})
        lines.append(
            f"| {name} | {point_interval(paired.get('recall_delta95'))} | {point_interval(paired.get('fpr_delta95'), 4)} |"
        )
    lines += [
        "",
        "Interval selisih yang mencakup nol tidak mendukung klaim perbedaan pasti. Angka delta di atas bersatuan percentage point dan tetap kondisional pada label penerbit.",
        "",
        "### Kualitas skor: control menuju challenger",
        "",
        "| Cohort | Brier | ECE 10 bin | ROC AUC |",
        "| --- | ---: | ---: | ---: |",
    ]
    for name, row in cohorts.items():
        old, new = (row["policies"][k] for k in ("control_strict", "candidate_strict"))
        values = [
            "Tidak tersedia"
            if old.get(k) is None or new.get(k) is None
            else f"{old[k]:.6f} → {new[k]:.6f}"
            for k in ("brier_score", "ece_10_fixed_bins", "roc_auc")
        ]
        lines.append(f"| {name} | " + " | ".join(values) + " |")
    lines += [
        "",
        "## Kebijakan pooled tambahan",
        "",
        "Seluruh threshold pooled dibekukan dari threshold partition sebelum test; tidak dipilih dari tabel ini.",
        "",
        "| Cohort | Recall control pooled | FPR control pooled | Recall challenger pooled | FPR challenger pooled |",
        "| --- | ---: | ---: | ---: | ---: |",
    ]
    for name, row in cohorts.items():
        old, new = (row["policies"][k] for k in ("control_pooled", "candidate_pooled"))
        lines.append(
            f"| {name} | {pct(old['recall'])} | {pct(old['fpr'], 4)} | {pct(new['recall'])} | {pct(new['fpr'], 4)} |"
        )
    subgroup_path = ROOT / "ml/reports/v6-segmented-subgroup-diagnostics.json"
    if subgroup_path.exists():
        groups = json.loads(subgroup_path.read_text())["structural"]
        old, new = groups["control_native"], groups[candidate_name]
        lines += [
            "",
            "## Struktur URL pada tune",
            "",
            "Diagnosis setelah seleksi dibekukan; tidak mengubah pilihan atau threshold.",
            "",
            "| Kelompok | Benign | Phishing | Recall control → challenger | FPR control → challenger | FPR challenger Wilson 95% |",
            "| --- | ---: | ---: | ---: | ---: | --- |",
        ]
        for group, values in new.items():
            row, baseline = values["True"], old[group]["True"]
            lines.append(
                f"| {group} | {row['benign']} | {row['phishing']} | {pct(baseline['recall'])} → {pct(row['recall'])} | {pct(baseline['fpr'])} → {pct(row['fpr'])} | {ci(row['fpr_wilson95_rows_iid_assumption'])} |"
            )
        row, baseline = new["private_hosting"]["False"], old["private_hosting"]["False"]
        lines.append(
            f"| non_private_hosting | {row['benign']} | {row['phishing']} | {pct(baseline['recall'])} → {pct(row['recall'])} | {pct(baseline['fpr'])} → {pct(row['fpr'])} | {ci(row['fpr_wilson95_rows_iid_assumption'])} |"
        )
    lines += [
        "",
        "## Review, privasi dan keputusan",
        "",
        f"Antrean development: {review['development_review']['cases']} kasus, {review['development_review']['complete_attested_pairs']} pasangan review lengkap. Pengguna menyatakan belum ada reviewer. Berkas Indonesia aktual tetap kosong; agent tidak membuat reviewer, adjudikasi atau label Indonesia. Pemeriksa baru menolak pack tidak blind, locator tertukar dan klaim independensi hanya dari dua file/ID.",
        "",
        f"Saved-model parity {frozen['parity_cases']} kasus: delta {frozen['max_saved_prediction_delta']}; cache/inference delta {frozen['max_cached_inference_delta']}. Kelulusan tes teknis bukan bukti kebenaran label atau kesiapan produksi. Binary, metadata, dependency dan threshold asli v6 tetap utuh. LOW bukan SAFE.",
        "",
        "[JSON lengkap](v6-segmented-evaluation.json), [protokol](v6-segmented-20261105-protocol.json), [amendemen sumber](v6-segmented-source-amendment.json), [review aktual](v6-segmented-human-review-status.json), [grafik](v6-segmented-evaluation.png).",
        "",
    ]
    REPORT.with_suffix(".md").write_bytes("\n".join(lines).encode())
    draw(
        names,
        recalls,
        briers,
        cohorts,
        candidate_name,
        selection["development_gate_passed"],
    )
    print("Aggregate segmented report and figure exported", flush=True)


def bar_intervals(axis, positions, values, rows, key):
    intervals = [row.get("domain_bootstrap95", {}).get(key) for row in rows]
    lower = [
        max(value - 100 * bound[0], 0) if bound and bound[0] is not None else 0
        for value, bound in zip(values, intervals)
    ]
    upper = [
        max(100 * bound[1] - value, 0) if bound and bound[1] is not None else 0
        for value, bound in zip(values, intervals)
    ]
    axis.errorbar(
        positions,
        values,
        yerr=[lower, upper],
        fmt="none",
        ecolor="#263238",
        elinewidth=0.8,
        capsize=2,
    )


def draw(names, recalls, briers, cohorts, candidate_name, gate_passed):
    labels = [
        name.replace("__source_equal_", " / ")
        .replace("segmented_text_structure_augmented", "Text+structure+data")
        .replace("segmented_text_structure", "Text+structure")
        .replace("segmented_text", "Segmented text")
        .replace("control_native", "Previous research")
        .replace("control_beta", "Control")
        for name in names
    ]
    colors = ["#087f8c" if n == candidate_name else "#99b8bb" for n in names]
    fig, axes = plt.subplots(2, 2, figsize=(15, 11), layout="constrained")
    axes[0, 0].barh(labels, recalls, color=colors)
    axes[0, 0].set(
        xlabel="Macro source recall on common tune (%)",
        title="Predeclared feature/calibration/data variants",
    )
    axes[0, 1].barh(labels, briers, color=colors)
    axes[0, 1].set(
        xlabel="Macro source Brier (lower is better)", title="Development score quality"
    )
    labels = {
        "new_stealth_domain_holdout": "New Stealth",
        "new_phishbench_publisher_holdout": "New external*",
        "observed_zenodo_websites_v2": "Zenodo**",
        "observed_pwd": "PWD**",
        "observed_expanded": "Expanded**",
        "observed_vendor": "Vendor**",
        "observed_phishtank_positive": "PhishTank**",
        "observed_legitphish": "LegitPhish**",
    }
    roles = [
        ("active_original", "Active V6", "#a1b6ba"),
        ("control_strict", "Previous research", "#cf694c"),
        (
            "candidate_strict",
            "Research challenger" if gate_passed else "Failed-gate diagnostic",
            "#087f8c",
        ),
    ]
    positions = np.arange(len(cohorts))
    for index, (role, label, color) in enumerate(roles):
        values = [
            100 * row["policies"][role]["recall"]
            if row["policies"][role]["recall"] is not None
            else np.nan
            for row in cohorts.values()
        ]
        axes[1, 0].bar(
            positions + (index - 1) * 0.25, values, width=0.25, label=label, color=color
        )
        bar_intervals(
            axes[1, 0],
            positions + (index - 1) * 0.25,
            values,
            [row["policies"][role] for row in cohorts.values()],
            "recall95",
        )
    axes[1, 0].set(
        xticks=positions,
        xticklabels=[labels[k] for k in cohorts],
        ylabel="Phishing recall (%)",
        ylim=(0, 100),
        title="Recall with domain 95% intervals; ** observed",
    )
    axes[1, 0].tick_params(axis="x", rotation=25)
    axes[1, 0].legend(fontsize=8)
    picked = [
        name
        for name in (
            "new_stealth_domain_holdout",
            "observed_zenodo_websites_v2",
            "observed_vendor",
        )
        if name in cohorts
    ]
    positions = np.arange(len(picked))
    for index, (role, label, color) in enumerate(roles):
        values = [100 * cohorts[name]["policies"][role]["fpr"] for name in picked]
        axes[1, 1].bar(
            positions + (index - 1) * 0.25, values, width=0.25, label=label, color=color
        )
        bar_intervals(
            axes[1, 1],
            positions + (index - 1) * 0.25,
            values,
            [cohorts[name]["policies"][role] for name in picked],
            "fpr95",
        )
    axes[1, 1].set(
        xticks=positions,
        xticklabels=[labels[k] for k in picked],
        ylabel="False-positive rate (%)",
        title="False alarms at each model's frozen policy",
    )
    axes[1, 1].legend(fontsize=8)
    fig.suptitle(
        "V6 segmented URL research — publisher labels; original service unchanged\n"
        + (
            "Research candidate passed development gate. "
            if gate_passed
            else "Previous research retained; diagnostic challenger failed gate. "
        )
        + "No Indonesia gold.\n* New external has only 2 benign: no reliable FPR claim",
        fontsize=14,
    )
    fig.savefig(REPORT.with_suffix(".png"), dpi=170)
    plt.close(fig)


if __name__ == "__main__":
    main()
