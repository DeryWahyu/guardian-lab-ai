# Hasil Perbandingan CatBoost dan Logistic Regression v9

> Selesai 1 November 2026. [Protokol sebelum fitting](./model-family-comparison-v9-plan.md), [notebook terlatih](../guardian_lab_url_qr_comparison_v9.ipynb), [laporan lengkap](../ml/reports/model-comparison-v9.json).

## Keputusan

**CatBoost belum mengungguli Logistic Regression lengkap pada eksperimen ini.** CatBoost depth 8 lebih baik daripada Logistic Regression dengan representasi ringkas yang sama, tetapi recall lebih rendah daripada LR lengkap v8 pada seluruh tujuh benchmark. Seluruh kandidat baru gagal guard per sumber development. Keputusan tetap mempertahankan frozen v6 untuk shadow internal; tidak ada promosi model publik.

Perbandingan ini tidak membuktikan seluruh keluarga CatBoost lebih buruk. Teks diringkas menjadi 64 komponen SVD sebelum classifier; hasil berlaku untuk representasi dan anggaran yang diuji. CNN belum dilatih.

## Data dan fitur yang benar-benar dipakai

Seluruh classifier baru memakai **535.504 URL fitting** yang sama: **201.161 phishing dan 334.343 benign**. Tune 84.545, calibration 40.635, threshold 47.219; total development 707.903. Data persis cache v8, tanpa intake baru atau relabel. Canonical core/digest/domain diverifikasi seluruh development; role dipisah berdasarkan domain/tenant dan input cocok checksum parent v8 yang dibekukan.

Representasi bersama memiliki 102 fitur: 64 komponen teks dan 38 fitur struktur. Vocabulary frozen v8 hanya berasal dari fit; SVD benar-benar di-fit pada **52.636 contoh fitting**, sesuai cap per sumber 12.000 dan total maksimal 60.000. Explained variance SVD sekitar **21,98%**; ini ukuran variasi proyeksi teks, bukan persentase informasi label atau accuracy. LR bersama memakai scaler fit-only; CatBoost memakai nilai fitur bersama langsung. Bobot inverse source count mean satu identik pada kedua keluarga.

Kontrol LR lengkap v8 memakai seluruh TF-IDF/struktur dan fitting v8 yang sama. Kontrol v6 mempunyai fitting lebih lama/lebih kecil (532.793), sehingga berperan sebagai referensi guard/runtime, bukan pembanding classifier dengan fitting identik. Notebook/model v3/v6/v7/v8 serta manifest shadow tetap identik menurut checksum.

## Seleksi hanya dari development

| Kandidat               |   Durasi fit | Iterasi/pohon tersimpan | Macro recall tune | Minimum recall sumber | Guard |
| ---------------------- | -----------: | ----------------------: | ----------------: | --------------------: | ----- |
| lr_shared_c05          |  32.40 detik |                       8 |            22.20% |                 3.22% | Gagal |
| lr_shared_c2           |  34.64 detik |                       8 |            22.15% |                 3.22% | Gagal |
| catboost_shared_depth6 |  84.11 detik |                     600 |            32.59% |                18.50% | Gagal |
| catboost_shared_depth8 | 117.20 detik |                     575 |            35.78% |                25.47% | Gagal |

Finalist diagnosis: **LR C=0,5** dan **CatBoost depth=8, 575 pohon**. Pada representasi bersama, CatBoost menaikkan macro recall tune dari 22,20% menjadi 35,78%, tetapi minimum recall 25,47% masih di bawah kontrol v6 sekitar 40,75%. LR lengkap v8 memiliki macro recall sekitar 47,76% pada audit tune yang sama.

CatBoost depth 8 menyimpan best iteration 574 dari maksimum 600; logloss akhir teramati train sekitar 0,206 dan tune 0,359. CatBoost depth 6 menyentuh cap 600. Anggaran ini tidak membuktikan konfigurasi optimal global. Tidak ada trial tambahan setelah hasil benchmark.

Setiap finalist dan kontrol dikalibrasi pada calibration saja. Threshold dipilih dari threshold partition dengan aturan upper Wilson per sumber 1% (warning) / 0,1% (high) bila dukungan cukup, serta fallback empiris sumber kecil yang dicatat. **Anggaran FPR development sama; FPR terukur pada benchmark tidak harus sama.** Tidak ada pencarian threshold dari test.

**Kontrol v6 pada laporan ini memakai threshold pembanding v9, bukan kebijakan runtime v6 asli.** Warning kontrol 0,9286581321406272; runtime tetap warning asli 0,904713285827399. Perubahan angka kontrol tidak berasal dari refit classifier atau perubahan API. LR lengkap v8 mempertahankan warning 0,9103663235299849.

## Hasil warning pada benchmark yang sama

Semua dataset berikut sudah teramati sebelum eksperimen v9 dan tidak disebut test independen baru. TR-OP domain-disjoint berasal dari sumber yang juga masuk fitting v8/v9. Sampel audit manusia PhishVN adalah 33 kasus global/Vietnam yang kecil, bukan gold Indonesia.

| Benchmark                           | Model                   |       Accuracy | Recall phishing |            FPR |
| ----------------------------------- | ----------------------- | -------------: | --------------: | -------------: |
| observed_phish360 (7,516)           | LR fitur bersama        |         64.72% |          17.43% |          0.21% |
| observed_phish360 (7,516)           | CatBoost fitur bersama  |         73.92% |          38.99% |          0.16% |
| observed_phish360 (7,516)           | LR lengkap v8           |         78.06% |          48.89% |          0.30% |
| observed_phish360 (7,516)           | v6 kontrol threshold v9 |         72.94% |          36.61% |          0.12% |
| observed_tr_op (1,097)              | LR fitur bersama        |         52.96% |          27.77% |          0.26% |
| observed_tr_op (1,097)              | CatBoost fitur bersama  |         65.72% |          47.27% |          0.00% |
| observed_tr_op (1,097)              | LR lengkap v8           |         73.29% |          58.91% |          0.00% |
| observed_tr_op (1,097)              | v6 kontrol threshold v9 |         60.44% |          39.13% |          0.00% |
| observed_vendor (20,000)            | LR fitur bersama        |         90.78% |          21.85% |          0.65% |
| observed_vendor (20,000)            | CatBoost fitur bersama  |         91.88% |          31.48% |          0.62% |
| observed_vendor (20,000)            | LR lengkap v8           |         93.25% |          45.73% |          0.84% |
| observed_vendor (20,000)            | v6 kontrol threshold v9 |         92.72% |          39.35% |          0.65% |
| observed_human_phishvn (33)         | LR fitur bersama        |         33.33% |           0.00% |          0.00% |
| observed_human_phishvn (33)         | CatBoost fitur bersama  |         33.33% |           0.00% |          0.00% |
| observed_human_phishvn (33)         | LR lengkap v8           |         39.39% |           9.09% |          0.00% |
| observed_human_phishvn (33)         | v6 kontrol threshold v9 |         42.42% |          13.64% |          0.00% |
| observed_phishtank_positive (9,269) | LR fitur bersama        | Tidak tersedia |          22.35% | Tidak tersedia |
| observed_phishtank_positive (9,269) | CatBoost fitur bersama  | Tidak tersedia |          29.29% | Tidak tersedia |
| observed_phishtank_positive (9,269) | LR lengkap v8           | Tidak tersedia |          47.20% | Tidak tersedia |
| observed_phishtank_positive (9,269) | v6 kontrol threshold v9 | Tidak tersedia |          42.04% | Tidak tersedia |
| observed_phresh (80,052)            | LR fitur bersama        |         50.87% |          22.95% |          0.36% |
| observed_phresh (80,052)            | CatBoost fitur bersama  |         54.41% |          28.48% |          0.29% |
| observed_phresh (80,052)            | LR lengkap v8           |         59.63% |          36.68% |          0.30% |
| observed_phresh (80,052)            | v6 kontrol threshold v9 |         60.18% |          37.44% |          0.10% |
| observed_urlphish (85,824)          | LR fitur bersama        |         95.45% |          34.86% |          0.03% |
| observed_urlphish (85,824)          | CatBoost fitur bersama  |         96.16% |          45.47% |          0.06% |
| observed_urlphish (85,824)          | LR lengkap v8           |         97.10% |          60.44% |          0.17% |
| observed_urlphish (85,824)          | v6 kontrol threshold v9 |         96.59% |          51.51% |          0.05% |

Pada Phish360, CatBoost menangkap 1.248/3.201 phishing dan salah menandai 7/4.315 benign. LR bersama menangkap 558 dan menghasilkan 9 FP; LR lengkap v8 menangkap 1.565 dengan 13 FP. CatBoost menangkap 690 phishing tambahan terhadap LR bersama, tetapi 317 lebih sedikit daripada LR lengkap.

Bootstrap domain berpasangan 1.000 kali: delta recall CatBoost terhadap LR lengkap pada Phish360 sekitar **[-11,71; -8,15] percentage point**; terhadap LR bersama sekitar **[+19,85; +23,22] pp**. Wilson per kelas, balanced accuracy, precision, AP, Brier, kebijakan high serta interval semua benchmark tersedia dalam JSON.

Audit manusia kecil: CatBoost dan LR ringkas menangkap **0/22** phishing; LR lengkap v8 **2/22**. Nol FP dari 11 benign bukan bukti keamanan. Pada PhishTank 2026, CatBoost menangkap 2.715/9.269 dan LR lengkap 4.375/9.269; feed positif tidak menghasilkan accuracy dua kelas, FPR atau precision trafik. Accuracy 96,16% CatBoost pada URL-Phish yang didominasi benign tidak boleh dianggap accuracy universal: recall hanya 45,47%.

## Implikasi dan langkah setelah eksperimen

Hasil menunjukkan nonlinearitas membantu pada fitur bersama, tetapi belum mengatasi penurunan akibat representasi ringkas serta perbedaan sumber. Kontrol LR lengkap mencegah kemenangan semu terhadap pembanding yang lebih lemah. Tidak ada bukti dari eksperimen ini bahwa algoritma saja adalah penyebab tunggal kegagalan generalisasi.

Pertahankan baseline dan gunakan hasil development untuk protokol berikutnya: nilai representasi teks yang menjaga pola langka (misalnya character CNN atau text-aware boosting), tetap dengan pemisahan domain/waktu dan holdout baru yang tidak dipakai memilih perubahan. Selesaikan bukti label Indonesia sebelum klaim publik. Tidak menjanjikan accuracy model alternatif sebelum training.

## Reproduksi dan artifact

- Jalankan `guardian_lab_url_qr_comparison_v9.ipynb` menggunakan environment Python 3.12 proyek. Run All berikutnya memverifikasi spec/data/source hash dan memuat artifact beku; tidak refit atau memilih dari benchmark.
- Artifact, fitur `.npy`, tabel CSV dan grafik ada pada `ml/runs/notebook-model-comparison-v9/`; semuanya lokal dan diabaikan Git. Artifact `shared_catboost-frozen.joblib` mencakup classifier, encoder dan kalibrator; classifier native tersedia setelah validasi pada `artifacts/catboost-selected.cbm` dan tetap memerlukan encoder/kalibrator frozen.
- Validasi lokal end-to-end: `ml/.venv/Scripts/python.exe scripts/research/validate_family_comparison_v9.py`. [Laporan validasi](../ml/reports/model-comparison-validation-v9.json) mengikat checksum, native export parity, latency warm batch satu, dan eksekusi notebook. Angka latency lokal bukan janji latency deployment.
- Tidak ada URL baru: seluruh input sudah tercakup exposure v8; registry/gold Indonesia tidak diisi ulang atau diberi label otomatis. Tidak mengunjungi target, membaca HTML/DNS atau mengirim baris ke LLM.

## Verifikasi selesai

Notebook Run All selesai **7 sel kode, nol error**. Seluruh **83 tes lulus tanpa skip** (28,69 detik); Ruff check dan format memeriksa 45 berkas tanpa temuan. Tes mencakup fit-only vocabulary/SVD, penolakan overlap benchmark, parity artifact nyata, ikatan hash data/code/source, kebijakan feed positif, dan regresi shadow lama. Native CatBoost CBM menghasilkan probabilitas persis sama setelah reload.

Pada probe lokal warm batch satu, 64 URL benchmark yang sudah teramati: CatBoost p50 sekitar **18,04 ms**, p95 **26,00 ms**, dibanding LR lengkap v8 p50 **2,30 ms**, p95 **2,75 ms**. Transformasi fitur dan kalibrasi termasuk; pengukuran berjalan bersamaan dengan pemeriksaan lokal lain dan bukan benchmark deployment terisolasi. Artifact lengkap CatBoost sekitar **29,01 MiB**, LR lengkap v8 **1,94 MiB**. Komponen SVD ikut menambah ukuran dan biaya inferensi; jumlah pohon saja tidak menggambarkan biaya pipeline.
