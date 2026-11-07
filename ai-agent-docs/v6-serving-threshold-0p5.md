# Ambang layanan v6: warning 0,5

Pengguna meminta ambang keputusan **0,5** pada 7 November 2026 setelah melihat diagnosis `phishing_data.csv`. Kebijakan `v6-user-warning-0.5-20261107` berlaku pada primary service `guardian_ml.shadow_service:create_app` dan gateway yang membungkusnya. Perubahan ini merupakan pilihan pengguna setelah benchmark terlihat; tidak disebut seleksi threshold pada development atau validasi independen.

| Band | Skor model |
| --- | --- |
| LOW | < 0,5 |
| MEDIUM | >= 0,5 dan < 0,9884744926236343 |
| HIGH | >= 0,9884744926236343 |

Binary, encoder, classifier, kalibrator, sanitizer, PSL dan skor v6 tetap asli. Tidak ada training, calibration fitting, pencarian threshold terbaik atau promosi kandidat. Metadata training asli tetap warning `0.904713285827399` dan high `0.9884744926236343`; checksum binary dan metadata tidak berubah. `decision_policy` pada [manifest layanan](../ml/policies/shadow-serving-manifest.json) menyatakan ambang layanan secara terpisah dari `thresholds` historis. Loader menolak policy hilang/tidak sesuai; source binding dan dependency lengkap tetap diperiksa. Manifest runtime historis tetap byte-identik; manifest layanan baru mengikat hash manifest historis tersebut. Manifest gateway diperbarui untuk mengikat manifest layanan saat ini.

Respons API memakai `geek.thresholds` untuk ambang aktif, `geek.frozen_thresholds` untuk threshold historis dan `geek.decision_policy_version` untuk identitas kebijakan. Backend menggunakan `risk_band` serta threshold aktif dari respons. Proses layanan yang sudah berjalan perlu dimulai ulang agar memuat perubahan. `scripts/validate_v6.py` melaporkan kedua threshold sekaligus dan tetap menguji skor referensi training asli. Notebook utama mempertahankan tabel evaluasi historis pada threshold asli dan menandai perbedaan dengan layanan aktif.

Pada dataset lokal yang **sudah teramati**, diagnosis dari distribusi skor memberi accuracy 93,27%, precision 96,81%, recall 89,20%, dan FPR 2,83% pada 11.241 baris supported dengan warning 0,5. Counts: TN 5.571, FP 162, FN 595, TP 4.913. Pada warning historis, accuracy 74,98%, precision 99,23%, recall 49,33%, FPR 0,37%; jadi recall meningkat bersama false alarm. Hasil ini menggunakan label file yang diberikan, termasuk duplikat; semua domain sudah ada dalam exposure lokal. Sebanyak 240 baris unsupported tetap tanpa score/band. Angka tersebut bukan estimasi trafik baru atau bukti gold Indonesia. [Laporan awal](../ml/reports/local-phishing-data-v6-evaluation.json) tetap utuh; verifikasi kebijakan baru dicatat dalam laporan terpisah.

Kalibrasi tidak berubah akibat threshold: Brier pada dataset tersebut tetap 0,061419 dan ECE 0,065751. Interval dan metrik pada data teramati tidak menggantikan pengujian independen. Tabel benchmark historis serta aturan exposure tetap berlaku; data test tidak dialihkan ke fitting. LOW bukan SAFE dan layanan tetap shadow dengan `production_ready=false`.

[Verifikasi akhir](../ml/reports/v6-serving-threshold-0p5-verification.json) mencatat **290 tes lulus**, tanpa failure/error/skip; 62 skor referensi sintetis tetap identik (delta maksimum nol). Lima cell kode notebook utama berhasil dieksekusi tanpa training. Pemeriksaan meliputi batas skor tepat 0,5 dan HIGH, URL/QR, response privacy, input unsupported, policy/dependency/source tampering serta artifact parity. [Load test gateway pada policy baru](../ml/reports/v6-serving-threshold-0p5-gateway-load.json) memperoleh 100/100 sukses pada konkurensi 2; burst berlebih ditolak tanpa score/band, dan seluruh 102 prediksi sukses tetap identik. Ini bukti ASGI in-process, bukan SLA deployment. Manifest runtime historis, laporan sebelumnya dan exposure sidecar tetap utuh.
