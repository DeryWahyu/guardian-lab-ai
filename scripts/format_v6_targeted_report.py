"""Write the complete human-readable report from aggregate evidence only."""

import json

from guardian_ml.paths import ROOT


def percent(value):
    return "Tidak tersedia" if value is None else f"{100 * value:.2f}%"


def interval(value):
    return (
        "Tidak tersedia"
        if not value or value[0] is None
        else f"[{100 * value[0]:.2f}%; {100 * value[1]:.2f}%]"
    )


def main():
    path = ROOT / "ml/reports/v6-targeted-evaluation.json"
    report = json.loads(path.read_text())
    previous = json.loads(
        (ROOT / "ml/reports/v6-targeted-previous-control.json").read_text()
    )
    selected = report["selected_freeze"]
    selection = selected["selection"]
    chosen = selection["candidate"]
    fit = selected["fit_audits"][chosen]
    curation = report["data_freeze"]["curation"]
    regressions = [
        name
        for name, cohort in report["cohorts"].items()
        if cohort.get("previously_observed")
        and cohort["policies"]["candidate_strict_source_1pct"]["recall"]
        < cohort["policies"]["v6_original"]["recall"]
    ]
    lines = [
        "# Eksperimen terarah v6: sumber data dan batas peringatan",
        "",
        "## Keputusan",
        "",
        f"Kandidat `{chosen}` dipilih hanya pada tune; fitting {fit['rows']:,} URL. Gate peningkatan development: **{selection['development_gate_passed']}**. "
        "Artifact baru tetap riset nonkomersial, production_ready=false. Layanan dan notebook utama tetap frozen v6 asli.",
        "",
        "".join(
            [
                "Recall kebijakan utama menurun terhadap v6 aktif pada benchmark teramati berikut: ",
                ", ".join(regressions),
                ". Karena itu belum ada peningkatan menyeluruh.",
            ]
        )
        if regressions
        else "Tidak ada penurunan recall pada benchmark teramati yang dilaporkan; ini tetap belum membuktikan kesiapan produksi atau validasi Indonesia.",
        "",
        "## Data dan provenance",
        "",
        "PWD2021 dari [rilis peneliti Mendeley V1](https://data.mendeley.com/datasets/n96ncsr5g4/1) menyediakan 80.000 URL (50.000 benign/30.000 phishing), CC BY 4.0. SQL diparse sebagai literal tanpa dieksekusi; HTML tidak diambil. Ini label penerbit global historis 2020–2021, bukan gold Indonesia atau review manusia independen per kasus. "
        "[Audit sumber tambahan](../../ai-agent-docs/research/v6-targeted-source-audit-20261105.md) menjelaskan sumber jurnal lain yang diperiksa dan alasan tidak digunakan.",
        "",
        f"78.102 URL lolos sanitasi; {curation['conflicting_rows']} baris berlabel konflik dikarantina, {curation['consistent_duplicate_rows']} duplikat konsisten dikeluarkan, "
        f"{curation['prior_url_or_domain_excluded']} URL/domain terpapar sebelumnya dikeluarkan, {curation['domain_cap_excluded']} melewati cap lima/domain. Tersisa **{curation['retained_rows']:,} URL baru**. Tidak ada relabel otomatis.",
        "",
        "| Partisi | URL | Benign | Phishing | Domain/tenant |",
        "| --- | ---: | ---: | ---: | ---: |",
    ]
    for name, part in report["data_freeze"]["partitions"].items():
        lines.append(
            f"| {name} | {part['rows']:,} | {part['classes'].get('0', 0):,} | {part['classes'].get('1', 0):,} | {part['groups']:,} |"
        )
    lines += [
        "",
        "Registry historis, seluruh sidecar dan cache v6 masuk audit novelty. Sidecar PWD2021 mencatat seluruh intake tersanitasi, termasuk baris yang dikeluarkan dan holdout cadangan. Domain, digest dan representasi tidak melintasi partisi; kemerdekaan kampanye belum dibuktikan. Raw URL tidak dipersistensikan; cache tersanitasi, registry dan binary tetap diabaikan Git. Pada PWD semua model dinilai atas core tersanitasi versi eksperimen, termasuk kontrol v6; ini bukan scoring atas seluruh raw URL penerbit dan tidak mengubah parser layanan aktif.",
        "",
        "## Ablasi sumber pada development",
        "",
        "Semua kandidat memakai LR C=2/liblinear, resep TF-IDF dan source_sqrt yang sama. Encoder di-fit ulang pada fitting subset setiap kandidat. Tune/calibration/threshold sama untuk seluruh kandidat. Pemilihan memakai macro recall dengan budget FPR 1% per sumber yang cukup didukung; tie-break minimum source recall lalu AP. Test tidak dipakai memilih kandidat.",
        "",
        "| Kandidat | Fit | Macro recall tune strict | Minimum source recall |",
        "| --- | ---: | ---: | ---: |",
    ]
    for name, audit in selected["fit_audits"].items():
        diagnostic = selected["tune"][name]["strict_source_1pct"]
        lines.append(
            f"| {name} | {audit['rows']:,} | {percent(diagnostic['macro_source_recall'])} | {percent(diagnostic['minimum_source_recall'])} |"
        )
    lines += [
        "",
        "Ini uji pengaruh sumber dalam resep yang tetap; bukan bukti bahwa satu penerbit menyebabkan perubahan pada setiap jenis phishing. Source ID tidak menjadi fitur. Kalibrasi sigmoid di-fit hanya pada calibration dengan slope positif; threshold dipilih hanya pada threshold partition.",
        "",
        "## Hasil utama setelah pembekuan",
        "",
        "Ketiga model di bawah memakai kebijakan warning/strict masing-masing yang dibekukan sebelum scoring baru. Kebijakan dan jumlah sumber development berbeda; tabel ini tidak mengasumsikan FPR test yang sama.",
        "",
        "| Cohort | URL | Recall v6 aktif | Recall kandidat sebelumnya | Recall kandidat baru | FPR v6 aktif | FPR sebelumnya | FPR baru |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for name, cohort in report["cohorts"].items():
        active = cohort["policies"]["v6_original"]
        new = cohort["policies"]["candidate_strict_source_1pct"]
        old = previous["cohorts"][name]["previous_candidate"]
        lines.append(
            f"| {name} | {cohort['rows']:,} | {percent(active['recall'])} | {percent(old['recall'])} | {percent(new['recall'])} | {percent(active['fpr'])} | {percent(old['fpr'])} | {percent(new['fpr'])} |"
        )
    lines += [
        "",
        "PWD holdout adalah domain baru dari sumber historis yang juga digunakan development. Empat cohort lain sudah teramati sebelum eksperimen ini dan hanya pemeriksaan regresi. Protokol didorong temuan test terdahulu; hasil baru tidak menghapus adaptasi tersebut.",
        "",
        "### Counts dan ketidakpastian kandidat baru",
        "",
        "| Cohort | TP | FN | FP | TN | Precision sampel | Domain recall 95% | Domain FPR 95% | Wilson FPR 95% (row IID) |",
        "| --- | ---: | ---: | ---: | ---: | ---: | --- | --- | --- |",
    ]
    for name, cohort in report["cohorts"].items():
        row = cohort["policies"]["candidate_strict_source_1pct"]
        counts, ci = row["confusion_matrix"], row["domain_bootstrap95"]
        lines.append(
            f"| {name} | {counts['tp']} | {counts['fn']} | {counts['fp']} | {counts['tn']} | {percent(row['precision'])} | {interval(ci['recall95'])} | {interval(ci.get('fpr95'))} | {interval(row['fpr_wilson95_rows_iid_assumption'])} |"
        )
    lines += [
        "",
        "Bootstrap memakai 1.000 pengambilan ulang domain/private tenant. Interval kondisional pada label penerbit dan tidak mengoreksi semua perbandingan eksploratif. Wilson row-IID mengabaikan korelasi domain/kampanye. LegitPhish hanya memiliki 28 benign: 0/28 FP, bila terjadi, tetap memiliki Wilson upper 95% sekitar 12,06%; bootstrap nol yang degenerat bukan jaminan FPR. PhishTank positif saja tidak menyediakan FPR, binary accuracy atau precision trafik.",
        "",
        "### Kalibrasi dan pemisahan risiko: v6 aktif menuju kandidat baru",
        "",
        "| Cohort | Brier v6 → baru | ECE v6 → baru | ROC AUC v6 → baru | AP v6 → baru |",
        "| --- | ---: | ---: | ---: | ---: |",
    ]
    for name, cohort in report["cohorts"].items():
        row = cohort["policies"]["candidate_strict_source_1pct"]
        active = cohort["policies"]["v6_original"]
        values = [
            "Tidak tersedia"
            if row.get(key) is None or active.get(key) is None
            else f"{active[key]:.6f} → {row[key]:.6f}"
            for key in [
                "brier_score",
                "ece_10_fixed_bins",
                "roc_auc",
                "average_precision",
            ]
        ]
        lines.append(f"| {name} | " + " | ".join(values) + " |")
    lines += [
        "",
        "Brier/ECE lebih kecil lebih baik; ROC AUC/AP lebih besar lebih baik dengan keterbatasan distribusi kelas. Pada vendor, Brier dan ECE justru memburuk walaupun ROC AUC sedikit meningkat secara angka. Skor terkalibrasi pada distribusi riset. Precision dan kalibrasi sampel tidak menjadi estimasi probabilitas/precision trafik Indonesia.",
        "",
        "## Perbandingan kebijakan tambahan yang ditetapkan sebelum test",
        "",
        "Pooled budget 0,1%, 0,5%, 1%, 2% ditentukan pada threshold partition untuk kedua model. Pooled budget tidak mengikat FPR tiap sumber dan tidak menjamin FPR test. Tidak ada kebijakan yang dipromosikan atau dipilih dari hasil test.",
        "",
    ]
    for name, cohort in report["cohorts"].items():
        lines += [
            "### " + name,
            "",
            "| Kebijakan | Recall | FPR | Precision sampel |",
            "| --- | ---: | ---: | ---: |",
        ]
        for policy, row in cohort["policies"].items():
            lines.append(
                f"| {policy} | {percent(row['recall'])} | {percent(row['fpr'])} | {percent(row['precision'])} |"
            )
        lines.append("")
    lines += [
        "## Pemeriksaan dan batas penggunaan",
        "",
        f"Semua classifier konvergen. Save/reload {selected['parity_cases']} probe nyata/sintetis, delta maksimum {selected['max_reload_delta']}. Model aktif v6, metadata, dependensi inference, PSL offline dan threshold aslinya tetap sama. Verifikasi teknis tidak membuktikan label benar atau detection recall tinggi.",
        "",
        "Tidak ada gold Indonesia, dua reviewer independen atau two-class temporal holdout terkini. Holdout PWD mempunyai 1.654 benign, di bawah minimum 3.000 pada gate proyek; jumlah sampel saja juga tidak cukup. LOW tidak berarti SAFE. Model tetap research/internal shadow.",
        "",
        "## Bukti dan reproduksi",
        "",
        "- [Protokol utama](v6-targeted-20261105-protocol.json), [hasil numerik lengkap](v6-targeted-evaluation.json), [grafik](v6-targeted-evaluation.png).",
        "- [Kontrol kandidat sebelumnya](v6-targeted-previous-control.json), [protokol kontrol](v6-targeted-previous-control-protocol.json); tambahan dinyatakan selama training, sebelum test, tanpa mengubah seleksi.",
        "- [Manifest exposure](../provenance/pwd2021-targeted-exposure.json), [verifikasi akhir](v6-targeted-verification.json).",
        "- Jalankan intake_v6_targeted.py, experiment_v6_targeted.py --stage prepare/train/evaluate, lalu v6_targeted_previous_control.py sesuai urutan freeze sebelum scoring/evaluate sesudahnya. Run beku tidak boleh ditimpa atau sidecar dihapus demi mengklaim novelty.",
        "",
    ]
    path.with_suffix(".md").write_bytes("\n".join(lines).encode())
    print("Wrote full aggregate report")


if __name__ == "__main__":
    main()
