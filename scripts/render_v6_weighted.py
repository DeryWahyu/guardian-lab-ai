"""Aggregate-only audit, subgroup diagnostics and publication figures for weighted v6."""

import argparse

import joblib
import numpy as np
import pandas as pd
from scipy.sparse import load_npz

from guardian_ml.metadata import checksum
from guardian_ml.paths import ROOT
from experiment_v6_expanded_data import now, write_json
import experiment_v6_weighted as study
from v6_weighted_support import structural_audit

SUBGROUP = ROOT / "ml/reports/v6-weighted-subgroup-diagnostics.json"


def pct(value):
    return "Tidak tersedia" if value is None else f"{100 * value:.2f}%"


def ci(value):
    return (
        "Tidak tersedia"
        if not value or value[0] is None
        else f"[{100 * value[0]:.2f}%; {100 * value[1]:.2f}%]"
    )


def render_audit():
    audit = study.read_json(study.AUDIT)
    total_fn = audit["control"]["overall"]["confusion_matrix"]["fn"]
    lines = [
        "# Audit development kandidat sembilan sumber",
        "",
        "Audit relatif label penerbit, bukan penentuan kebenaran label manusia. Data tune tidak menjadi final gold sampling frame.",
        "",
        f"{audit['tune_rows']:,} URL; false negative relatif penerbit {total_fn:,}. Label tidak diubah otomatis.",
        "",
        "| Sumber | Benign | Phishing | TP | FN | FP | Recall | FPR | Porsi FN sampel |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for name, row in audit["control"]["source_rates"].items():
        c = row["confusion_matrix"]
        lines.append(
            f"| {name} | {row['benign']} | {row['phishing']} | {c['tp']} | {c['fn']} | {c['fp']} | {pct(row['recall'])} | {pct(row['fpr'])} | {pct(c['fn'] / total_fn)} |"
        )
    lines += [
        "",
        "Porsi FN hanya mengikuti komposisi sampel penelitian; bukan estimasi kontribusi pada trafik Indonesia.",
        "",
        "| Struktur | Nilai | URL | FN | Recall | FPR |",
        "| --- | --- | ---: | ---: | ---: | ---: |",
    ]
    for name, groups in audit["structural"].items():
        for flag, row in groups.items():
            lines.append(
                f"| {name} | {flag} | {row['rows']} | {row['confusion_matrix']['fn']} | {pct(row['recall'])} | {pct(row['fpr'])} |"
            )
    lines += [
        "",
        "## Konflik penerbit dan review",
        "",
        "| Partisi | Representasi konflik | Baris |",
        "| --- | ---: | ---: |",
    ]
    for name, row in audit["publisher_conflicts"].items():
        lines.append(f"| {name} | {row['representations']} | {row['rows']} |")
    queue = audit["review_queue"]
    lines += [
        "",
        f"{queue['review_cases']} kasus disiapkan dalam coordinator dan dua pack blind lokal. Selesai review manusia: **{queue['completed_human_reviews']}**. Pack blind hanya memuat case ID/locator hash dan kolom reviewer yang kosong; URL, skor model dan label penerbit tidak diberikan kepada reviewer pada tahap awal.",
        "",
        "Konflik representasi bisa disebabkan scheme/query/waktu atau label sumber; audit ini tidak menetapkan label yang benar. False negative/positive adalah ketidakcocokan terhadap label penerbit, bukan bukti target kini phishing atau aman.",
        "",
        "## Input Indonesia aktual",
        "",
        "| Berkas | Baris |",
        "| --- | ---: |",
    ]
    for name, row in audit["Indonesia_inputs"]["files"].items():
        lines.append(f"| {name} | {row['rows']} |")
    lines += [
        "",
        "Tidak ada reviewer, label Indonesia atau adjudikasi yang dibuat oleh agent. Review nyata memerlukan identitas manusia independen serta evidence reference per kasus. Data global berlabel penerbit tidak otomatis memenuhi kebutuhan itu.",
        "",
    ]
    study.AUDIT.with_suffix(".md").write_bytes("\n".join(lines).encode())


def subgroup():
    protocol = study.read_json(study.PROTOCOL)
    cache, selected = study.check_selected(protocol)
    if SUBGROUP.exists():
        raise ValueError("weighted_subgroup_diagnostics_already_completed")
    record = selected["records"][selected["selection"]["evaluated_candidate"]]
    bundle = joblib.load(ROOT / record["artifact"])
    tune = pd.read_parquet(ROOT / cache["assets"]["tune"]["input_path"])
    matrix = load_npz(ROOT / cache["assets"]["tune"]["matrix_path"])
    scores = study.calibrated(
        bundle["classifier"].predict_proba(matrix)[:, 1], bundle["calibrator"]
    )
    threshold = record["policies"]["strict"]["threshold"]
    write_json(
        SUBGROUP,
        {
            "completed_at_utc": now(),
            "selected_freeze_sha256": checksum(study.RUN / "selected-frozen.json"),
            "candidate": selected["selection"]["evaluated_candidate"],
            "partition": "tune",
            "structural": structural_audit(tune, scores, threshold),
            "after_selection_exploratory_not_used_to_change_selection": True,
            "final_test_results_used": False,
        },
    )
    print(
        "Exploratory development subgroup diagnostics saved without changing selection",
        flush=True,
    )


def render_results():
    report = study.read_json(study.REPORT)
    audit = study.read_json(study.AUDIT)
    diagnostics = study.read_json(SUBGROUP)
    selected = report["selected_freeze"]
    selection = selected["selection"]
    source = selected["holdout"]["data"]
    paired_new = report["cohorts"]["new_external_publisher_holdout"][
        "paired_candidate_minus"
    ]["control"]
    regressions = [
        name
        for name, row in report["cohorts"].items()
        if row.get("policies")
        and row["policies"]["candidate_strict"]["recall"] is not None
        and row["policies"]["candidate_strict"]["recall"]
        < row["policies"]["control_strict"]["recall"]
    ]
    lines = [
        "# Pembobotan domain/sumber dan kalibrasi v6",
        "",
        "## Keputusan",
        "",
        f"Pilihan riset: `{selection['selected']}`. Kandidat yang diperiksa: `{selection['evaluated_candidate']}`. Gate development lolos: **{selection['development_gate_passed']}**. Pemilihan hanya memakai tune; semua artifact/policy dibekukan sebelum test. Layanan/notebook tetap frozen v6 asli, production_ready=false.",
        "",
        "Control riset dipertahankan karena kandidat baru tidak lolos gate. Challenger berikut hanya diagnosis gagal-gate, bukan model pengganti."
        if selection["selected"] == "control_native"
        else "Kandidat lolos gate development untuk penelitian; ini belum persetujuan produksi, validasi Indonesia atau bukti kebenaran label.",
        "",
        "Regresi recall terhadap control pada cohort berikut tetap dilaporkan: "
        + (
            ", ".join(regressions)
            if regressions
            else "tidak ada pada angka titik yang dilaporkan; ketidakpastian dan FPR tetap perlu diperiksa"
        )
        + ".",
        "",
        "## Data, audit dan pemisahan",
        "",
        "Fitting tetap **616.050 URL dari sembilan sumber**. Encoder fit-only yang sama dipakai ulang dengan checksum dan real-score parity; tidak ada fitting vocabulary/scaler pada holdout. Tiga bobot classifier dan dua sigmoid calibration diuji sesuai [protokol](v6-weighted-20261105-protocol.json). Calibration dan threshold memakai partisi terpisah; source ID bukan fitur.",
        "",
        f"[Audit development](v6-weighted-development-audit.md) memeriksa {audit['tune_rows']:,} URL dan menyiapkan {audit['review_queue']['review_cases']} kasus review. Selesai review manusia: **0**; tidak ada relabel otomatis atau identitas reviewer yang dibuat.",
        "",
        f"Holdout tambahan dari [rilis Zenodo V2](https://zenodo.org/records/23477065), CC BY 4.0: {source['rows']:,} URL pada {source['groups']:,} domain/tenant, {source['classes'].get('0', 0):,} benign dan {source['classes'].get('1', 0):,} phishing. Semua dicadangkan, tidak masuk fitting/tune/calibration/threshold. Registry historis, seluruh sidecar dan cache v6 diperiksa; audit nyata terhadap sembilan berkas menemukan nol overlap domain/digest/representasi.",
        "",
        "Penerbit memberi label literal legitimate/phishing. Pemeriksaan skema awal menghentikan asumsi label angka; amendemen sebelum prediksi mempertahankan arti label dan jumlah kelas penerbit. Hanya tabel URL diambil lewat HTTP Range sekitar 5,1 MB dari arsip 4,5 GB; CRC dan SHA-256 CSV dipin. MD5 seluruh arsip tidak dihitung ulang. Tidak ada gambar/HTML yang diekstrak, URL target dikunjungi atau raw URL dipersistensikan.",
        "",
        "Ini holdout penerbit global dengan domain baru; tanggal publikasi 2026 bukan tanggal observasi. Tidak ada klaim temporal holdout kontemporer, independent campaigns atau gold Indonesia. Sumber PhishTank/Tranco dan label penerbit tetap memiliki keterbatasan. Semua benchmark lain sudah teramati dan hanya pemeriksaan regresi.",
        "",
        "## Seleksi development",
        "",
        "| Varian | Macro recall | Minimum source recall | Macro source Brier |",
        "| --- | ---: | ---: | ---: |",
    ]
    for name, row in selected["tune"].items():
        lines.append(
            f"| {name} | {pct(row['macro_source_recall'])} | {pct(row['minimum_source_recall'])} | {row['macro_source_brier']:.6f} |"
        )
    lines += [
        "",
        "Seluruh varian menggunakan representasi dan fitting rows yang sama. Kalibrasi monoton tidak menambah kemampuan ranking; manfaat kalibrasi dinilai terpisah melalui Brier. Gate dan tie-break ditetapkan sebelum fitting; jika semua gagal, control tetap dipertahankan.",
        "",
        "## Hasil utama pada kebijakan asli/strict yang beku",
        "",
        "FPR aktual tiap model berbeda; kebijakan strict memilih budget development per sumber, bukan menjamin FPR test yang sama.",
        "",
        "| Cohort | URL | Recall v6 aktif | Recall control riset | Recall kandidat | FPR v6 aktif | FPR control | FPR kandidat |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for name, row in report["cohorts"].items():
        m = row["policies"]
        values = [
            m[role][metric]
            for metric in ["recall", "fpr"]
            for role in ["active_original", "control_strict", "candidate_strict"]
        ]
        lines.append(
            f"| {name} | {row['rows']:,} | " + " | ".join(pct(v) for v in values) + " |"
        )
    lines += [
        "",
        "### Counts, precision sampel dan ketidakpastian kandidat",
        "",
        "| Cohort | TP | FN | FP | TN | Precision | Domain recall 95% | Domain FPR 95% | Wilson FPR 95% |",
        "| --- | ---: | ---: | ---: | ---: | ---: | --- | --- | --- |",
    ]
    for name, cohort in report["cohorts"].items():
        row = cohort["policies"]["candidate_strict"]
        c, interval = row["confusion_matrix"], row.get("domain_bootstrap95", {})
        lines.append(
            f"| {name} | {c['tp']} | {c['fn']} | {c['fp']} | {c['tn']} | {pct(row['precision'])} | {ci(interval.get('recall95'))} | {ci(interval.get('fpr95'))} | {ci(row['fpr_wilson95_rows_iid_assumption'])} |"
        )
    lines += [
        "",
        "Bootstrap 1.000 domain/private tenants bersifat kondisional pada label penerbit dan tidak mengoreksi semua perbandingan eksploratif. Wilson row-IID mengabaikan korelasi domain/kampanye. PhishTank positif saja tidak menyediakan FPR/accuracy/precision trafik. LegitPhish hanya memiliki 28 benign; nol FP dan bootstrap degenerat tetap tidak menjamin FPR rendah (Wilson upper 95% sekitar 12,06% untuk 0/28). Precision sampel bukan precision trafik Indonesia.",
        "",
        f"Pada holdout penerbit baru, interval berpasangan 95% kandidat dikurangi control riset adalah recall [{100 * paired_new['recall_delta95'][0]:+.2f}; {100 * paired_new['recall_delta95'][1]:+.2f}] percentage point dan FPR [{100 * paired_new['fpr_delta95'][0]:+.3f}; {100 * paired_new['fpr_delta95'][1]:+.3f}] percentage point. Interval recall mendukung peningkatan; interval FPR masih mencakup nol, sehingga penurunan tiga FP belum bukti kuat perbaikan FPR terhadap control.",
        "",
        "### Kalibrasi: control riset menuju kandidat",
        "",
        "| Cohort | Brier control → kandidat | ECE control → kandidat | ROC AUC control → kandidat |",
        "| --- | ---: | ---: | ---: |",
    ]
    for name, cohort in report["cohorts"].items():
        old, new = (
            cohort["policies"][role] for role in ["control_strict", "candidate_strict"]
        )
        values = [
            "Tidak tersedia"
            if old.get(k) is None or new.get(k) is None
            else f"{old[k]:.6f} → {new[k]:.6f}"
            for k in ["brier_score", "ece_10_fixed_bins", "roc_auc"]
        ]
        lines.append(f"| {name} | " + " | ".join(values) + " |")
    lines += [
        "",
        "Brier/ECE lebih kecil lebih baik; ROC AUC lebih besar lebih baik. Skor tetap terkalibrasi pada campuran penelitian, bukan probabilitas trafik Indonesia.",
        "Kalibrasi vendor memburuk dibanding control riset meskipun recall meningkat. Pada diagnosis development, FPR private hosting, URL panjang dan kelompok punycode juga naik. Karena itu keuntungan recall tidak dianggap peningkatan menyeluruh pada setiap aspek; support dan interval kelompok kecil tetap diperhatikan.",
        "",
        "## Diagnosis struktur pada tune setelah seleksi",
        "",
        "Analisis ini eksploratif setelah pilihan dibekukan, tidak dipakai mengubah pilihan atau threshold.",
        "",
        "| Struktur | Nilai | Benign | Phishing | Recall control → kandidat | FPR control → kandidat | Wilson FPR kandidat 95% |",
        "| --- | --- | ---: | ---: | ---: | ---: | --- |",
    ]
    for name, groups in diagnostics["structural"].items():
        for flag, row in groups.items():
            old = audit["structural"][name][flag]
            lines.append(
                f"| {name} | {flag} | {row['benign']} | {row['phishing']} | {pct(old['recall'])} → {pct(row['recall'])} | {pct(old['fpr'])} → {pct(row['fpr'])} | {ci(row['fpr_wilson95_rows_iid_assumption'])} |"
            )
    lines += [
        "",
        "## Kebijakan tambahan yang telah ditentukan sebelum test",
        "",
        "Pooled 1% hanya analisis trade-off; tidak mengikat FPR per sumber atau test. Tidak ada threshold dipilih dari hasil di bawah.",
        "",
    ]
    for name, cohort in report["cohorts"].items():
        lines += [
            "### " + name,
            "",
            "| Kebijakan | Recall | FPR | Precision sampel |",
            "| --- | ---: | ---: | ---: |",
        ]
        for role, row in cohort["policies"].items():
            lines.append(
                f"| {role} | {pct(row['recall'])} | {pct(row['fpr'])} | {pct(row['precision'])} |"
            )
        lines.append("")
    lines += [
        "## Keterbatasan dan bukti",
        "",
        "Tidak ada dua reviewer manusia independen, gold Indonesia atau adjudikasi baru yang selesai. Minimum 1.000 phishing/3.000 benign saja tidak memenuhi gate. Layanan tetap shadow dan LOW tidak berarti SAFE. Binary/metadata/threshold v6 asli tetap utuh; seluruh kandidat turunan mewarisi batas penelitian nonkomersial.",
        "",
        f"Save/reload {selected['parity_cases']} probe nyata/sintetis: delta maksimum {selected['max_saved_prediction_delta']}. Parity cache/inference: {selected['max_cached_inference_delta']}. Tes teknis tidak membuktikan label benar atau model siap produksi.",
        "",
        "- [JSON lengkap](v6-weighted-evaluation.json), [grafik](v6-weighted-evaluation.png), [verifikasi](v6-weighted-verification.json).",
        "- [Prosedur dan sumber](../../ai-agent-docs/v6-weighted-experiment.md), [diagnosis subgroup](v6-weighted-subgroup-diagnostics.json).",
        "- [Intake asli](v6-weighted-holdout-intake-protocol.json), [inspeksi skema](v6-weighted-holdout-schema-inspection.json), [amendemen sebelum prediksi](v6-weighted-holdout-intake-amended.json), [exposure](../provenance/zenodo-websites-v2-exposure.json).",
        "",
    ]
    study.REPORT.with_suffix(".md").write_bytes("\n".join(lines).encode())
    draw(report, audit)
    print("Aggregate weighted report and figure exported", flush=True)


def short_name(name):
    return (
        name.replace("control_native", "Control / native")
        .replace("control_equal_calibration", "Control")
        .replace("source_sqrt_domain_class_soft", "Domain+class soft")
        .replace("source_equal_domain_sqrt", "Equal source+domain")
        .replace("source_sqrt_domain_sqrt", "Domain")
        .replace("__row_sigmoid", " / row cal")
        .replace("__source_equal_sigmoid", " / equal cal")
    )


def draw(report, audit):
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, axes = plt.subplots(2, 2, figsize=(14, 10), constrained_layout=True)
    selected = report["selected_freeze"]["selection"]
    fig.suptitle(
        "V6 weighting/calibration research — publisher labels, no Indonesia gold\nSelection frozen before final scoring; original v6 service unchanged",
        fontsize=14,
    )
    ax = axes[0, 0]
    names = list(report["selected_freeze"]["tune"])
    values = [
        100 * report["selected_freeze"]["tune"][name]["macro_source_recall"]
        for name in names
    ]
    ax.barh(
        [short_name(n) for n in names],
        values,
        color=[
            "#087f8c" if n == selected["evaluated_candidate"] else "#98b6bb"
            for n in names
        ],
    )
    for index, value in enumerate(values):
        ax.text(value + 0.2, index, f"{value:.1f}%", va="center", fontsize=9)
    ax.set(
        xlim=(0, max(values) * 1.18),
        xlabel="Macro source recall on common tune (%)",
        title="Fixed encoder/data; weighting and calibration variants",
    )
    ax = axes[0, 1]
    source_rows = sorted(
        audit["control"]["source_rates"].items(),
        key=lambda item: item[1]["confusion_matrix"]["fn"],
        reverse=True,
    )
    ax.barh(
        [s for s, _ in source_rows],
        [r["confusion_matrix"]["fn"] for _, r in source_rows],
        color="#cf6a4c",
    )
    ax.invert_yaxis()
    ax.set(
        xlabel="Publisher-labeled phishing missed (development sample)",
        title="Control false negatives by source, not traffic share",
    )
    keys = list(report["cohorts"])
    labels = [
        "New external"
        if key.startswith("new_")
        else key.replace("observed_", "").replace("_positive", "")
        for key in keys
    ]
    x = np.arange(len(keys))
    for role, offset, color, label in [
        ("active_original", -0.25, "#a4b6ba", "Active v6 warning"),
        ("control_strict", 0, "#cf6a4c", "Previous research strict"),
        ("candidate_strict", 0.25, "#087f8c", "Frozen challenger strict"),
    ]:
        values, lower, upper = [], [], []
        for key in keys:
            row = report["cohorts"][key]["policies"][role]
            value = row["recall"]
            low, high = row["domain_bootstrap95"]["recall95"]
            values.append(100 * value)
            lower.append(max(0, 100 * (value - low)))
            upper.append(max(0, 100 * (high - value)))
        axes[1, 0].bar(
            x + offset,
            values,
            width=0.25,
            yerr=[lower, upper],
            capsize=2,
            color=color,
            label=label,
        )
    axes[1, 0].set(
        xticks=x,
        xticklabels=labels,
        ylabel="Phishing recall (%)",
        ylim=(0, 100),
        title="Fixed primary policies; domain 95% intervals",
    )
    axes[1, 0].tick_params(axis="x", rotation=20)
    axes[1, 0].legend(fontsize=7)
    false_keys = [
        key
        for key in keys
        if key.startswith("new_") or key in ("observed_expanded", "observed_vendor")
    ]
    x = np.arange(len(false_keys))
    for role, offset, color, label in [
        ("active_original", -0.25, "#a4b6ba", "Active v6"),
        ("control_strict", 0, "#cf6a4c", "Previous research"),
        ("candidate_strict", 0.25, "#087f8c", "Frozen challenger"),
    ]:
        values = [
            100 * report["cohorts"][key]["policies"][role]["fpr"] for key in false_keys
        ]
        axes[1, 1].bar(x + offset, values, width=0.25, color=color, label=label)
    axes[1, 1].set(
        xticks=x,
        xticklabels=[
            "New external" if key.startswith("new_") else key.replace("observed_", "")
            for key in false_keys
        ],
        ylabel="Observed false positive rate (%)",
        title="False alarms at each model's frozen policy",
    )
    axes[1, 1].legend(fontsize=8)
    fig.savefig(study.REPORT.with_suffix(".png"), dpi=160)
    plt.close(fig)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--stage", choices=["audit", "subgroup", "results"], required=True
    )
    args = parser.parse_args()
    {"audit": render_audit, "subgroup": subgroup, "results": render_results}[
        args.stage
    ]()
