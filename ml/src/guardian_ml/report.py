"""Expand reporting of the two frozen thresholds without fitting or tuning."""

import json
from pathlib import Path

import pandas as pd
from threadpoolctl import threadpool_limits

from .evaluation import apply_calibration, metrics
from .metadata import checksum, dump_json, now
from .paths import DATA, REPORTS, ARTIFACTS, ROOT
from .predictor import Predictor


def percent(value):
    return f"{100 * value:.3f}%"


def main():
    model = Predictor()
    manifest = model.manifest
    assert checksum(DATA / "curated.parquet") == manifest["data_sha256"]
    frame = pd.read_parquet(DATA / "curated.parquet")
    features = pd.read_parquet(DATA / "features.parquet")
    data = json.loads((REPORTS / "data-audit.json").read_text())
    final = json.loads((REPORTS / "final-test.json").read_text())
    validation = json.loads((REPORTS / "validation-results.json").read_text())
    frozen = json.loads((REPORTS / "frozen-selection.json").read_text())
    outputs = {}
    for partition in ("test", "external"):
        mask = frame.partition.eq(partition) & frame.novel_domain
        part = frame[mask].reset_index(drop=True)
        raw = model.bundle["candidate"].predict(part.core, features[mask].reset_index(drop=True))
        probability = apply_calibration(model.bundle["calibrator"], raw)
        outputs[partition + "_novel_domain"] = {
            name: metrics(part.label, probability, value)
            for name, value in manifest["thresholds"].items()
        }
        assert (
            outputs[partition + "_novel_domain"]["high"]["confusion_matrix"]
            == (final["results"][partition + "_novel_domain"]["confusion_matrix"])
        )
    primary = outputs["test_novel_domain"]
    hypothetical = {}
    for level, result in primary.items():
        hypothetical[level] = {}
        for prevalence in (0.001, 0.01, 0.05):
            tp = result["recall"] * prevalence
            fp = result["fpr"] * (1 - prevalence)
            hypothetical[level][str(prevalence)] = tp / (tp + fp) if tp + fp else 0
    dump_json(
        REPORTS / "operating-thresholds.json",
        {
            "reported_at_utc": now(),
            "reporter_sha256": checksum(Path(__file__)),
            "bundle_sha256": manifest["bundle_sha256"],
            "model_or_thresholds_refitted": False,
            "results": outputs,
            "hypothetical_precision_by_prevalence": hypothetical,
            "hypothesis": "Assumes measured class-conditional recall/FPR transfer; not observed traffic precision",
        },
    )
    lines = [
        "# Model Card — Guardian Lab URL Core v1",
        "",
        f"Tanggal evaluasi: {final['evaluated_at_utc']}. Model: **{manifest['model_name']}**.",
        "",
        "**Status: kandidat riset terlatih. Recall masih terbatas; belum layak menjadi satu-satunya "
        "penentu keamanan atau dipromosikan otomatis ke aplikasi.**",
        "",
        "## Tujuan dan cakupan",
        "",
        "Mendukung pilar Recognize Guardian Lab dengan indikator phishing pada URL HTTP/HTTPS. "
        "URL hasil QR memakai representasi, model, kalibrator, dan threshold yang sama. "
        "Model tidak membuka situs dan tidak menganalisis malware APK, konten halaman, redirect, atau merchant QRIS.",
        "",
        "## Data dan audit",
        "",
        "PhreshPhish dipin pada revision `" + manifest["source_revision"] + "`. "
        "PhiUSIIL dipakai hanya sebagai pembanding eksternal dengan mapping 0 sumber menjadi phishing=1.",
        "",
        "Sumber resmi: [PhreshPhish](https://huggingface.co/datasets/phreshphish/phreshphish) "
        "dan [PhiUSIIL UCI](https://archive.ics.uci.edu/dataset/967/phiusiil+phishing+url+dataset). "
        "Keduanya mencantumkan CC BY 4.0; card PhreshPhish juga menyebut riset anti-phishing. "
        "Ketentuan sumber tetap harus diperiksa sebelum penggunaan atau distribusi lain.",
        "",
        "Audit membaca 902.110 baris sumber. Pemeriksaan ulang sanitasi sempat mendeteksi pola residual; "
        "aturan diperbaiki dan ingestion diulang sebelum training. Seluruh "
        f"{len(data['independent_checks'])} pemeriksaan akhir lulus. Screening regex bukan bukti bahwa "
        "semua informasi pribadi atau seluruh kesalahan label sudah ditemukan.",
        "",
        "- Query/fragment dibuang identik pada kedua kelas untuk mengurangi artefak privasi sumber.",
        f"- {sum(data['rejected_by_reason_and_class'].values()):,} baris sumber ditolak oleh kebijakan "
        "input/privacy sebelum kurasi. Pada phishing train, 20.941 dari 221.526 baris ditolak; "
        "cakupan model tidak boleh disamakan dengan seluruh URL sumber. Rincian per kelas/alasan ada pada audit JSON.",
        "- 43 URL core memiliki label berbeda; 7.053 baris terkait dikeluarkan. Ini dapat berasal dari "
        "hilangnya konteks setelah transformasi atau perubahan status, bukan otomatis kesalahan label asli.",
        "- 51.216 duplikat canonical dalam sumber dikeluarkan, dihitung pada seluruh sumber yang diproses.",
        "- 1.379 baris train bertabrakan dengan URL core test dan 605 baris berada di hari batas test; keduanya dikeluarkan.",
        "- 69.401 baris validasi memiliki domain yang sudah muncul pada fit dan dikeluarkan dari validasi.",
        "- Label kampanye tidak tersedia; domain-disjoint tidak membuktikan campaign-disjoint.",
        "",
        "| Partisi | Baris | Benign | Phishing | Kelompok domain/tenant |",
        "| --- | ---: | ---: | ---: | ---: |",
    ]
    for name, item in data["curation"]["partitions"].items():
        lines.append(
            f"| {name} | {item['rows']:,} | {item['benign']:,} | {item['phishing']:,} | {item['groups']:,} |"
        )
    lines += [
        "",
        "Fit: 2 Juli 2024–22 Februari 2025. Validasi: 23 Februari–7 September 2025. "
        "Test: 8 September–16 Desember 2025. Tune, calibration, dan threshold dipisahkan menurut "
        "domain/tenant dalam periode validasi. Test domain baru tidak berbagi kelompok dengan seluruh pengembangan.",
        "",
        "## Perbandingan kandidat pada tune",
        "",
        "Pemenang dipilih dari recall pada FPR empiris maksimal 0,1%, lalu average precision. "
        "Pemilihan selesai sebelum test final. Ini eksperimen beranggaran terbatas, bukan pencarian optimum global.",
        "",
        "Heuristik adalah baseline penelitian Python, bukan port identik scoring TypeScript aplikasi web.",
        "",
        "| Kandidat | Recall | FPR | Average precision | Fit + tune (detik) |",
        "| --- | ---: | ---: | ---: | ---: |",
    ]
    for item in validation["candidates"]:
        value = item["tune"]
        lines.append(
            f"| {item['name']} | {percent(value['recall'])} | {percent(value['fpr'])} | "
            f"{value['average_precision']:.4f} | {item['fit_and_tune_seconds']:.1f} |"
        )
    lines += [
        "",
        "Pemenang memakai TF-IDF karakter 3–5 gram, vocabulary maksimal 40.000 yang di-fit pada "
        "100.000 contoh fit deterministik, dan logistic regression dengan optimizer SGD. Seluruh "
        "302.812 contoh fit digunakan untuk pelatihan classifier. Dua alpha dicoba, masing-masing maksimal "
        "12 epoch dengan penghentian berbasis tune. CatBoost/XGBoost membandingkan depth 6 dan 8, "
        "maksimal 800 iterasi, early stopping 60, pada 34 fitur numerik dan suffix. Tidak ada full-hostname kategori.",
        "",
        "Kalibrasi "
        + frozen["calibration"]["selected"]
        + " dipilih melalui group holdout pada partisi calibration. "
        "Probabilitas mengacu pada distribusi riset PhreshPhish, bukan prevalensi trafik pengguna Guardian Lab.",
        "",
        "## Test utama pada domain baru",
        "",
        "80.052 baris: 29.146 benign, 50.906 phishing, 59.880 domain/tenant. Kedua threshold berikut "
        "sudah dibekukan dari partisi threshold sebelum test. Baris peringatan mencakup MEDIUM dan HIGH.",
        "",
        "| Kebijakan | Threshold p | Precision benchmark | Recall | FPR | FP / benign |",
        "| --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    for level, title in (("low", "Peringatan MEDIUM + HIGH"), ("high", "Indikasi kuat HIGH")):
        item = primary[level]
        lines.append(
            f"| {title} | {item['threshold']:.9f} | {percent(item['precision'])} | "
            f"{percent(item['recall'])} | {percent(item['fpr'])} | "
            f"{item['confusion_matrix']['fp']} / {item['benign']} |"
        )
    high = final["results"]["test_novel_domain"]
    interval = high["group_bootstrap"]
    lines += [
        "",
        f"Average precision: {high['average_precision']:.4f}; ROC-AUC: {high['roc_auc']:.4f}; "
        f"Brier: {high['brier_score']:.4f}. HIGH memiliki accuracy {percent(high['accuracy'])} "
        "pada komposisi test ini; precision tinggi tidak berarti accuracy atau recall tinggi.",
        "",
        f"Bootstrap 200 kali per domain: CI95 recall HIGH {percent(interval['recall95'][0])}–"
        f"{percent(interval['recall95'][1])}; FPR {percent(interval['fpr95'][0])}–"
        f"{percent(interval['fpr95'][1])}. Interval mencerminkan sampel/domain dalam sumber ini, "
        "tidak menjamin ketahanan terhadap perubahan modus atau noise label.",
        "",
        "## Pembanding eksternal",
        "",
        "PhiUSIIL domain baru: 194.559 baris setelah mengeluarkan URL/domain yang tumpang tindih "
        "dengan pengembangan dan test PhreshPhish. Dataset berbeda sumber ini tetap memiliki bias "
        "koleksi dan tidak menggantikan data Indonesia atau holdout 2026.",
        "",
        "| Kebijakan | Precision benchmark | Recall | FPR |",
        "| --- | ---: | ---: | ---: |",
    ]
    for level in ("low", "high"):
        item = outputs["external_novel_domain"][level]
        lines.append(
            f"| {level} | {percent(item['precision'])} | {percent(item['recall'])} | {percent(item['fpr'])} |"
        )
    bench = final["inference_benchmark"]
    lines += [
        "",
        "## Artifact dan inferensi",
        "",
        f"Bundle lokal: `{(ARTIFACTS / manifest['bundle_filename']).relative_to(ROOT).as_posix()}`, "
        f"{manifest['bundle_bytes']:,} byte. "
        "Binary dan dataset diabaikan Git. Manifest, kalibrator, threshold, dependency, PSL offline, "
        "schema, hash implementasi, dan checksum menyertai model.",
        "",
        f"SHA-256 bundle: `{manifest['bundle_sha256']}`.",
        "",
        f"Inferensi CPU 4 thread, batch 1, 100 contoh: p50 {bench['latency_ms_p50']:.2f} ms; "
        f"p95 {bench['latency_ms_p95']:.2f} ms; startup {bench['startup_seconds']:.3f} detik. "
        "RAM pada final-test.json adalah proses evaluasi yang memuat dataset, bukan kebutuhan RAM inferensi saja.",
        "",
        "Parity URL/QR, query diabaikan konsisten, save/reload, checksum rusak, dan schema tidak kompatibel "
        "sudah diuji dengan artifact nyata. Loader hanya menerima artifact training yang dipercaya; "
        "checksum bukan perlindungan untuk deserialize pickle dari pihak asing.",
        "",
        "## Batas kemampuan dan keputusan",
        "",
        "Model ini dapat memberi peringatan awal, tetapi masih melewatkan sebagian besar phishing pada "
        "threshold HIGH. Jangan menggunakan LOW sebagai jaminan aman. Ketentuan input/privacy juga menolak "
        "sebagian URL; evaluasi di atas hanya berlaku untuk sampel yang lolos kebijakan tersebut.",
        "",
        "Gold set Indonesia, observasi terbaru 2026, verifikasi label manual, dan kampanye lintas domain "
        "masih perlu dikerjakan. Query-only threats dan domain sah yang disusupi dapat sulit dibedakan. "
        "Belum ada integrasi ke aplikasi web atau promosi produksi.",
        "",
        "Precision sangat dipengaruhi prevalensi. Pada asumsi hipotetis prevalensi phishing 0,1% dan "
        "recall/FPR HIGH yang sama, precision yang dihitung hanya "
        + percent(hypothetical["high"]["0.001"])
        + ". "
        "Ini simulasi matematis, bukan hasil trafik nyata.",
        "",
        "![Kurva evaluasi dan perbandingan validasi](./evaluation.png)",
        "",
        "Bukti: [data audit](./data-audit.json), [protokol](./run-protocol.json), "
        "[validasi](./validation-results.json), [pilihan beku](./frozen-selection.json), "
        "[test final](./final-test.json), [dua threshold](./operating-thresholds.json).",
        "",
    ]
    (REPORTS / "model-card.md").write_text("\n".join(lines), encoding="utf-8")
    print(
        json.dumps(
            {
                name: {
                    level: {key: item[key] for key in ("recall", "fpr", "precision")}
                    for level, item in levels.items()
                }
                for name, levels in outputs.items()
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    with threadpool_limits(limits=4):
        main()
