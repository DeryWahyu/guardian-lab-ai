# Pelaksanaan benchmark LegitPhish pada frozen v6

Tanggal: 5 November 2026. [Hasil](../ml/reports/legitphish-v6-evaluation.md), [angka lengkap](../ml/reports/legitphish-v6-evaluation.json), [grafik](../ml/reports/legitphish-v6-evaluation.png).

Rilis [LegitPhish V2](https://data.mendeley.com/datasets/hx4m73v2sf/2), DOI 10.17632/hx4m73v2sf.2, mencantumkan CC BY 4.0. Daftar file publik Mendeley memberikan file `url_features_extracted1.csv`, 8.963.838 byte, SHA-256 `8685e7901c3b4e73eb43c106cb166cc932dd14f76960a032c713c2c32f09dbcd`. Payload diverifikasi dan dibaca dalam memori; raw URL/CSV tidak dipersistensikan atau dikirim ke LLM.

File berisi 101.219 baris dan 18 kolom: 63.678 label phishing=0, 37.540 legitimate=1, serta satu URL tanpa label. Pemeriksaan skema pertama menolak file sebelum scoring. Protokol awal dipertahankan, dan amendemen QA sebelum prediksi mengarantina satu baris kosong-label tanpa menetapkan label baru. Mapping angka dibalik ke skema proyek benign=0/phishing=1; fitur numerik penerbit tidak digunakan untuk memprediksi.

Parser v6 asli tetap digunakan. Input unsupported atau yang memerlukan perubahan core oleh guard assignment path dikeluarkan, agar tidak menyamarkan perubahan representasi. Konflik label scheme-free dikarantina, duplikat konsisten dibuang, lalu paparan URL/domain/private tenant diperiksa terhadap registry historis, sidecar terdahulu dan cache v6. Cap lima URL per domain dipilih berdasarkan digest tanpa skor model. Cache tersanitasi dan semua hash dibekukan sebelum scoring.

Tersisa 42.716 baris: 42.688 label phishing dan 28 benign pada 26.137 domain/private tenant. Sebagian besar benign overlap dengan data yang pernah terpapar: 37.304 baris benign unik terkena filter domain. Baris pengecualian tiap tahap/class tersedia pada laporan. Tidak dilakukan penggabungan benign tambahan untuk memperbesar dukungan.

Warning asli memberi recall 66,01% (28.179 TP, 14.509 FN), dengan domain-bootstrap 95% sekitar [65,46%; 66,56%]. Benign 0/28 FP mempunyai Wilson upper 95% 12,064%; hasil ini tidak membuktikan FPR di bawah 1%. Bootstrap nol-error yang degenerat serta precision sampel 100% dijelaskan pada laporan. HIGH recall hanya 1,38%. Semua hasil bergantung pada kebenaran label sumber dan distribusi subset yang tersisa.

[Metode artikel](https://pmc.ncbi.nlm.nih.gov/articles/PMC12538017/) mencampurkan verifikasi manual dan pencocokan threat feed. Provenance URLhaus menuntut pemeriksaan phishing-vs-malware per kasus. Data global tanpa bukti Indonesia atau timestamp kasus yang cukup tidak menjadi gold Indonesia/holdout temporal 2026. Nilai lebih tinggi/rendah terhadap benchmark sumber lain tidak membuktikan model meningkat/menurun, karena v6 dan threshold tidak berubah.

## Exposure dan reproduksi

Semua 100.853 baris intake yang lolos parser/privasi dicatat sebagai exposure, termasuk yang tidak diskor. Sidecar lokal `ml/data/exposure-sidecars/legitphish-v2-20261105.sqlite` menyimpan hash URL/representasi/domain; registry historis tidak ditimpa. [Manifest sidecar](../ml/provenance/legitphish-v2-exposure.json) mengikat checksum dan scope. Audit kebaruan di masa mendatang wajib memuat gabungan seluruh sidecar, registry historis dan cache v6.

Cache lokal: `ml/data/legitphish-v2-v6-qa/sanitized-domain-disjoint.parquet`. Model/caches/registry/sidecar tidak masuk Git. Dengan artifact asli, registry/cache lokal yang cocok dan extra `quality`, replay scoring:

```powershell
ml/.venv/Scripts/python.exe scripts/evaluate_legitphish_v6.py --stage evaluate --output-stem ml/reports/legitphish-v6-replay
```

Grafik dengan interval recall domain-bootstrap dan FPR Wilson dapat dibuat langsung dari angka agregat, tanpa membaca URL atau memprediksi ulang:

```powershell
ml/.venv/Scripts/python.exe scripts/plot_legitphish_v6.py
```

Replay tetap data teramati. Intake ulang tidak boleh menghapus sidecar lama untuk membuat data tampak baru. Program menolak overwrite artifact intake/report yang sudah selesai.

## Tindak lanjut akses Indonesia

Pencarian publik lanjutan untuk dataset SABER 2.054 URL dan IndoPhis-D/Telkom belum menemukan rilis URL+label yang dapat diunduh langsung. Artikel SABER tersedia publik; dataset aslinya September 2023. Katalog tesis Telkom tersedia, sementara bab utama ditandai perlu login. Katalog KI menjelaskan dataset tetapi tidak menyertakan file/lisensi data yang dapat diperiksa. Ini hasil penelusuran akses publik, bukan pernyataan bahwa dataset tersebut tidak ada.

Tidak ada akun, formulir permohonan akses atau pesan ke penulis yang dikirim. [Catatan literatur](research/indonesia-phishing-literature-20261105.md) mempertahankan tautan sumber dan keterbatasan bukti. Dataset Indonesia historis dapat menjadi benchmark regional setelah akses, hak dan overlap diaudit; label reviewer dan hasil Indonesia tidak diisi otomatis.
