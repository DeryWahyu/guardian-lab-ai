"""Present immutable aggregate results; this formatter never loads target rows."""

import json

from guardian_ml.paths import ROOT


def main():
    path = ROOT / "ml/reports/v6-expanded-data-evaluation.json"
    report = json.loads(path.read_text())
    supplement = json.loads(
        (ROOT / "ml/reports/v6-expanded-matched-control.json").read_text()
    )
    data, selected = report["data_freeze"], report["selected_freeze"]
    candidate = selected["selected"]["candidate"]
    lines = [
        "# Eksperimen penggabungan dataset turunan v6",
        "",
        "**Kesimpulan:** kandidat memperbaiki recall dan false positive pada holdout domain baru, tetapi recall menurun pada semua benchmark lama yang diperiksa. Hasilnya belum menunjukkan perbaikan menyeluruh atau memenuhi syarat produksi. Model layanan tetap frozen v6 asli.",
        "",
        f"Kandidat terpilih hanya dari tune: **{candidate}**. Tiga classifier konvergen; artifact terpilih, kalibrator dan threshold dibekukan sebelum semua prediksi test. Syarat peningkatan development terpenuhi: **{selected['selected']['development_improvement_gate_passed']}**. Ini berbeda dari syarat rilis produksi.",
        "",
        "## Data yang ditambahkan",
        "",
        "| Sumber baru | Baris rilis | Lolos sanitasi |",
        "| --- | ---: | ---: |",
    ]
    for name, audit in data["source_audits"].items():
        lines.append(
            f"| {name} | {audit['raw_rows']:,} | {audit['sanitized_rows']:,} |"
        )
    lines += [
        "",
        "Total intake 296.251 baris; 118.319 URL baru tersisa setelah penyaringan. Sepuluh representasi dengan 1.286 baris konflik dikarantina, 59.716 duplikat konsisten dibuang, 79.696 kasus paparan lama dan 20.843 kelebihan cap domain dikeluarkan. Label tidak diubah atau diisi oleh LLM.",
        "",
        "| Partisi gabungan | URL | Domain/tenant | Benign | Phishing |",
        "| --- | ---: | ---: | ---: | ---: |",
    ]
    for name, item in data["partitions"].items():
        lines.append(
            f"| {name} | {item['rows']:,} | {item['groups']:,} | {item['classes'].get('0', 0):,} | {item['classes'].get('1', 0):,} |"
        )
    lines += [
        "",
        "Fitting berisi delapan sumber. Vocabulary/scaler hanya di-fit pada fitting. Partisi fondasi v6 dipertahankan, dan domain data baru dipisah deterministik sebelum fitting. Domain, digest dan representasi antar-partisi tidak overlap. Semua sumber tetap label penerbit dengan keterbatasan scope phishing, ranking benign dan timestamp, bukan gold Indonesia.",
        "",
        "## Seleksi hanya pada development",
        "",
        "| Model | Macro recall sumber pada budget FPR tune 1% | Minimum source recall |",
        "| --- | ---: | ---: |",
    ]
    for name, row in {
        "v6 kontrol tune": selected["baseline_tune"],
        **selected["candidate_tune"],
    }.items():
        lines.append(
            f"| {name} | {row['macro_source_recall']:.3%} | {row['minimum_source_recall']:.3%} |"
        )
    lines += [
        "",
        "Sumber gabungan mengubah constraint FPR yang paling ketat. Karena itu nilai kontrol tune di sini tidak langsung dibandingkan dengan macro tune empat/lima sumber pada eksperimen lama. Threshold tune hanya diagnostik pemilihan. Policy akhir kandidat memakai partisi threshold terpisah.",
        "",
        "## Perbandingan utama: policy asli v6 versus kandidat beku",
        "",
        "| Cohort | Model | URL | Precision | Recall | FPR | TP | FN | FP | TN |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]

    def rate(value):
        return "N/A" if value is None else f"{value:.3%}"

    for name, cohort in report["cohorts"].items():
        for model, levels in cohort["models"].items():
            row = levels["warning"]
            count = row["confusion_matrix"]
            fp, tn = (
                (count["fp"], count["tn"]) if row["fpr"] is not None else ("N/A", "N/A")
            )
            lines.append(
                f"| {name} | {model} | {row['rows']:,} | {rate(row['precision'])} | {rate(row['recall'])} | {rate(row['fpr'])} | {count['tp']} | {count['fn']} | {fp} | {tn} |"
            )
    lines += [
        "",
        "Pada holdout baru, kandidat menangkap 704 phishing tambahan dan mengurangi 69 false positive: recall 29,86% menjadi 38,25%, FPR 2,53% menjadi 0,40%. Domain-bootstrap berpasangan 95%: kenaikan recall [7,44; 9,37] percentage point, perubahan FPR [-2,71; -1,60] point. Perbandingan menggunakan data yang sama dan policy yang dibekukan sebelum scoring.",
        "",
        "Namun, pada vendor lama recall turun 46,31% menjadi 31,48%; pada feed positif PhishTank 46,53% menjadi 35,92%; pada LegitPhish 66,01% menjadi 42,45%. Interval delta recall berpasangan seluruh benchmark lama berada di bawah nol. Penurunan ini tetap dilaporkan dan menjadi alasan kandidat tidak menggantikan layanan aktif.",
        "",
        "| Cohort | 95% delta recall kandidat-v6, percentage point | 95% delta FPR, percentage point |",
        "| --- | --- | --- |",
    ]
    for name, cohort in report["cohorts"].items():
        paired = cohort["paired_deltas"]["warning"]
        recall = [round(100 * number, 3) for number in paired["recall_delta95"]]
        fpr = (
            None
            if paired["fpr_delta95"] is None
            else [round(100 * number, 3) for number in paired["fpr_delta95"]]
        )
        lines.append(f"| {name} | {recall} | {fpr if fpr is not None else 'N/A'} |")
    lines += [
        "",
        "## Kontrol tambahan dengan budget FPR development yang sama",
        "",
        "Kontrol tambahan dideklarasikan setelah hasil tune kandidat pertama, sebelum final test. Ia memakai classifier/encoder/kalibrator v6 asli; hanya threshold referensi yang ditentukan pada threshold partition gabungan. Ini tambahan terlambat yang dilaporkan terpisah, tidak mengubah policy v6 atau pemilihan kandidat.",
        "",
        "| Cohort | Recall v6 kontrol | Recall kandidat | FPR v6 kontrol | FPR kandidat |",
        "| --- | ---: | ---: | ---: | ---: |",
    ]
    for name, cohort in supplement["cohorts"].items():
        old, new = (
            cohort["warning"]["v6_matched_control"],
            cohort["warning"]["candidate"],
        )
        lines.append(
            f"| {name} | {rate(old['recall'])} | {rate(new['recall'])} | {rate(old['fpr'])} | {rate(new['fpr'])} |"
        )
    lines += [
        "",
        "Budget development yang sama tidak berarti FPR test sama. Contohnya, pada holdout baru kontrol memperoleh FPR 0,031% dan kandidat 0,401%; peningkatan recall terhadap kontrol juga disertai tambahan false alarm. Jangan mengganti perbandingan terhadap v6 policy asli dengan tabel kontrol untuk menyembunyikan regresi.",
        "",
        "## Kalibrasi dan syarat rilis",
        "",
        "| Cohort | Model | Brier | Log loss | ECE 10 bins |",
        "| --- | --- | ---: | ---: | ---: |",
    ]
    for name, cohort in report["cohorts"].items():
        for model, levels in cohort["models"].items():
            row = levels["warning"]
            if row["brier_score"] is not None:
                lines.append(
                    f"| {name} | {model} | {row['brier_score']:.6f} | {row['log_loss']:.6f} | {row['ece_10_fixed_bins']:.6f} |"
                )
    new = report["cohorts"]["new_domain_holdout"]["models"]["candidate"]["warning"]
    lines += [
        "",
        f"Holdout baru memenuhi jumlah minimum diagnostik (8.393 phishing/3.243 benign), tetapi Wilson lower 95% recall {new['recall_wilson95_rows_iid_assumption'][0]:.3%} masih jauh di bawah target 85%. Wilson upper 95% FPR {new['fpr_wilson95_rows_iid_assumption'][1]:.3%} berada di bawah 1% pada label/sampel ini. Jumlah dan angka FPR tersebut tidak melengkapi bukti human review, Indonesia, hak/provenance per kasus atau audit kampanye/waktu.",
        "",
        "Pada LegitPhish hanya ada 28 benign: nol FP dan bootstrap [0;0] tetap tidak membuktikan FPR populasi nol. Precision sampel bukan precision trafik. PhishTank hanya positif sehingga FPR/traffic precision/accuracy biner tidak tersedia. Tidak ada cohort digabung untuk membuat estimasi trafik atau temporal palsu.",
        "",
        f"Save/reload parity kandidat: {selected['real_and_synthetic_reload_cases']} kasus development/sintetis, max probability delta {selected['max_reload_prediction_delta']}. Seluruh 116 tes terkait proyek dan kontrol tambahan lulus (114 suite utama + 2 guard kontrol). Runtime v6 asli dan dependency inference tetap terverifikasi.",
        "",
        "## Artifact dan reproduksi",
        "",
        f"Kandidat lokal: `ml/runs/v6-expanded-data-20261105/selected-candidate.joblib`, SHA-256 `{selected['artifact_sha256']}`. Dataset, source caches, model dan exposure sidecars diabaikan Git. Metadata pemilihan dan threshold dibekukan sebelum test; semua kasus intake tercatat sebagai exposure untuk percobaan mendatang.",
        "",
        "[Prosedur](../../ai-agent-docs/v6-expanded-data-experiment.md), [protokol utama](v6-expansion-20261105-protocol.json), [protokol kontrol tambahan](v6-expanded-matched-control-protocol.json), [hasil kontrol](v6-expanded-matched-control.json), [grafik](v6-expanded-data-evaluation.png).",
        "",
        "Kesimpulan tetap riset: ada manfaat pada distribusi tambahan dan pengurangan false alarm, tetapi target recall belum tercapai dan regresi lama signifikan secara eksplorasi. Tidak ada perubahan model layanan, promosi produksi, reviewer atau label Indonesia otomatis.",
        "",
    ]
    path.with_suffix(".md").write_bytes("\n".join(lines).encode())


if __name__ == "__main__":
    main()
