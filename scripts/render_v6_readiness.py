"""Aggregate report of completed hardening and failed-gate model experiments."""

from guardian_ml.metadata import checksum
from guardian_ml.paths import ROOT
import experiment_v6_readiness as study


def pct(value):
    return "n/a" if value is None else f"{100 * value:.3f}%"


def main():
    report = study.parent.read(study.REPORT)
    verified = study.parent.read(ROOT / "ml/reports/v6-readiness-verification.json")
    load = study.parent.read(ROOT / "ml/reports/v6-shadow-gateway-load-test.json")
    if verified["model_report_sha256"] != checksum(study.REPORT):
        raise ValueError("readiness_report_changed_after_verification")
    expert = report["selection"]["diagnostic"]
    lines = [
        "# Perbaikan kesiapan v6: model, lisensi sumber, dan gateway",
        "",
        "**Gateway shadow telah diperkuat dan teruji. Eksperimen model belum memenuhi syarat penggantian.** "
        "Model aktif tetap frozen v6; seluruh respons tetap production_ready=false. "
        "Tidak ada server publik diluncurkan, reviewer dibuat, atau label Indonesia diisi otomatis.",
        "",
        "## Perbaikan operasional yang sudah selesai",
        "",
        "- Entry point baru `guardian_ml.shadow_gateway:create_app` memakai backend Bearer key wajib; key kosong/lemah ditolak. Primary service asli tidak diubah.",
        "- Token bucket global per proses, batas prediksi bersamaan, batas aktual body/response, deadline body dan inferensi, serta penolakan overload dengan Retry-After.",
        "- Timeout respons tidak membatalkan thread inference. Slot tetap dihitung sampai komputasi berakhir; pembatalan klien juga tidak melepaskan slot lebih awal.",
        "- Assignment path yang terdeteksi berisi credential/secret ditolak sebagai unsupported tanpa score/band. Representasi model asli tidak diubah; sanitizer tetap heuristik dan cakupan input gateway berkurang.",
        "- Monitoring hanya counters/histogram; tidak menyimpan key, IP, URL, body, atau event per request. Metrics kualitas online tetap null.",
        "- Manifest gateway mengikat dua source baru, parent runtime manifest, delapan versi dependency inferensi dan empat dependency layanan. Source manifest dan binary/metadata/threshold asli tetap utuh.",
        "",
        "## Uji beban dan parity",
        "",
        "Uji menggunakan model v6 asli dan URL sintetis melalui ASGI in-process pada workstation ini. "
        "Kuota benchmark sengaja dilonggarkan ke 10.000 request/menit dan burst 1.000; kapasitas inferensi tetap 2. "
        "Default operasional adalah 60 request/menit, burst 10, kapasitas 2, timeout inference 5 detik/body 3 detik. "
        "Hasil ini tidak membuktikan throughput jaringan, TLS, beberapa worker/replica, atau SLA deployment.",
        "",
        "| Fase | Request | Konkurensi client | HTTP 200 | HTTP 503 | p95 semua respons | p95 respons berhasil | Peak inference |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for phase in load["phases"]:
        lines.append(
            f"| {phase['name']} | {phase['requests']} | {phase['client_concurrency']} | {phase['statuses'].get('200', 0)} | {phase['statuses'].get('503', 0)} | {phase['latency_ms']['p95']:.2f} ms | {phase['successful_latency_ms']['p95']:.2f} ms | {phase['gateway_counters']['peak_inflight']} |"
        )
    lines += [
        "",
        "Status overload memiliki score/band null. Semua prediksi berhasil sama dengan prediksi langsung artifact asli (delta maksimum nol). "
        "Tes tambahan memeriksa autentikasi, kuota, body chunked/slow, output terlalu besar, exception privat, deadline threadpool nyata, pembatalan klien, "
        "manifest/dependency tampering dan abstention input sensitif.",
        "",
        "## Penyaringan sumber dan pelatihan",
        "",
        "DeepURLBench (NC menurut catatan proyek) dan ISCX replica (hak data asal belum jelas) dikeluarkan dari seluruh fitting, vocabulary, scaler, calibration, threshold dan tune. "
        "Estimator baseline dilatih dari nol; hanya constructor v6 yang di-clone. Tidak ada fitted vocabulary/IDF/scaler/koefisien lama digunakan. "
        "Sembilan sumber yang dipertahankan mendeklarasikan CC BY 4.0 pada metadata penerbit. "
        "Ini penyaringan deklarasi penerbit, bukan commercial clearance: sumber hulu PWD2021/Ebbu, PhishBD/ISCX, attribution, privasi dan linkage versi masih perlu review.",
        "",
        "| Partisi setelah filter | Total | Benign | Phishing | Private benign | Private phishing |",
        "| --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    for name, a in report["source_filter"].items():
        lines.append(
            f"| {name} | {a['rows']:,} | {a['benign']:,} | {a['phishing']:,} | {a['private_counts']['0']:,} | {a['private_counts']['1']:,} |"
        )
    lines += [
        "",
        "Ketimpangan benign private hosting masih besar. Dua expert Logistic Regression memakai encoder baseline yang hanya di-fit pada fitting, "
        "C=0,5/C=2, bobot soft kelas/sumber/domain yang dibatasi, kalibrator private terpisah, dan threshold private FPR 1%/0,1% pada threshold partition. "
        "Probabilitas tidak dipetakan ulang untuk menyamarkan threshold kelompok; Brier/ECE dihitung dari probabilitas asli, confusion/bootstrap dari keputusan routing.",
        "",
        "| Varian development | Private recall | Private FPR | Macro recall sumber | Macro Brier | Lolos gate |",
        "| --- | ---: | ---: | ---: | ---: | --- |",
    ]
    for name, row in report["development"].items():
        detail = report["selection"]["details"].get(name)
        lines.append(
            f"| {name} | {pct(row['private']['recall'])} | {pct(row['private']['fpr'])} | {pct(row['macro_recall'])} | {row['macro_brier']:.6f} | {detail['passed'] if detail else 'control'} |"
        )
    lines += [
        "",
        f"Kedua expert gagal guard development. `{expert}` dibekukan sebagai challenger diagnostik berdasarkan tune, bukan dipromosikan. "
        "Contohnya expert C=2 menambah private recall 5,28 pp dibanding baseline dengan batas private FPR yang sama, tetapi kehilangan 21,30 pp dibanding native baseline. "
        "Keputusan itu dipertahankan setelah test.",
        "",
        "## Replay historis warning",
        "",
        "Semua 11 cohort sudah pernah teramati. Source NC dapat dipakai untuk diagnostik riset historis di sini; tidak dipakai fitting/calibration/threshold/tune. "
        "Reference scores sebelumnya diikat hash ke cohort/model dan diverifikasi replay. Ini bukan final holdout independen baru atau gold Indonesia.",
        "",
        "| Cohort | Model | N benign / phishing | TP / FN / FP / TN | Accuracy | Recall | FPR | Private recall | Brier |",
        "| --- | --- | ---: | --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    for cohort, row in report["cohorts"].items():
        for role in (
            "frozen_v6",
            "previous_current",
            "baseline",
            "private_matched",
            expert,
        ):
            metrics = row["levels"]["warning"][role]
            m = metrics["overall"]
            cm = m["confusion_matrix"]
            brier = "n/a" if m["brier_score"] is None else f"{m['brier_score']:.6f}"
            lines.append(
                f"| {cohort} | {role} | {m['benign']} / {m['phishing']} | {cm['tp']} / {cm['fn']} / {cm['fp']} / {cm['tn']} | {pct(m['accuracy'])} | {pct(m['recall'])} | {pct(m['fpr'])} | {pct(metrics['private']['recall'])} | {brier} |"
            )
    lines += [
        "",
        "Dampak penting: baseline yang disaring memperoleh recall global 27,17% dibanding model riset 11 sumber sebelumnya 32,28%, "
        "dan FPR vendor 2,51% dibanding 0,79%. Expert diagnostik hanya menangkap 4,01% phishing private hosting global pada policy private yang ketat. "
        "Penyaringan hak sumber membutuhkan pengganti benign yang berkualitas; membuang sumber saja tidak menjamin perbaikan model. "
        "Seluruh regresi dipertahankan. Tidak ada kandidat percobaan ini yang menggantikan artifact layanan atau menjadi pemenang produksi.",
        "",
        "JSON lengkap memuat precision sampel, calibration bins/ECE/logloss, counts, Wilson dan 1.000 bootstrap domain berpasangan, warning/HIGH serta private hosting. "
        "Feed positif saja tidak diberi FPR/precision/accuracy. Sampel PhishBench hanya dua benign; nol FP tetap mempunyai ketidakpastian besar.",
        "",
        "## Yang masih menghalangi produksi",
        "",
        "- Input Indonesia aktual seluruhnya kosong, dan 170 kasus review development belum memiliki pasangan review manusia yang lengkap. Antrean development bukan final gold baru.",
        "- Target recall/FPR pada independent Indonesia gold, audit kampanye/waktu serta regresi private hosting belum terselesaikan.",
        "- Hak sumber hulu, attribution dan izin penggunaan produksi belum ditetapkan hanya dengan membaca metadata CC BY penerbit.",
        "- Uji jaringan/TLS/multiworker, kuota terdistribusi, resource/process supervision dan SLA di lingkungan deployment belum dilakukan. Thread yang macet memerlukan isolasi proses/supervisor; timeout respons tidak menghentikannya paksa.",
        "",
        f"**{verified['tests']['tests']} tes lulus**, nol gagal/error/skip. Parity dan confusion matrix seluruh 11 cohort diperiksa ulang. "
        "Semua sidecar/registry, holdout termasuk 169.393 Mendeley reserved, binary, metadata dan threshold asli tetap utuh. production_ready=false.",
        "",
        "[Protokol](v6-readiness-20261107-protocol.json), [evaluasi JSON](v6-readiness-model-evaluation.json), "
        "[verifikasi](v6-readiness-verification.json), [load test](v6-shadow-gateway-load-test.json), "
        "[audit sumber](../provenance/v6-readiness-license-screening.json), [panduan gateway](../../ai-agent-docs/v6-shadow-gateway.md).",
        "",
        "Reproduksi pemeriksaan: `python scripts/verify_v6_readiness.py` dan `python scripts/render_v6_readiness.py`. "
        "Run/data/model/score berada pada `ml/runs/v6-readiness-20261107/` yang diabaikan Git. Runner menolak overwrite model/evaluasi yang telah dibekukan.",
    ]
    (ROOT / "ml/reports/v6-readiness-improvements.md").write_text(
        "\n".join(lines) + "\n", encoding="utf-8", newline="\n"
    )
    print("Saved readiness improvements report")


if __name__ == "__main__":
    main()
