# Guardian Lab AI

[Publikasi repository dan pemeriksaan CI](ai-agent-docs/github-publication.md).

**Model utama sementara: Logistic Regression v6**, sesuai pilihan pengguna. [Keputusan dan identitas model](ai-agent-docs/selected-model-v6.md), [notebook utama v6](guardian_lab_url_qr_data_v6.ipynb), dan [API internal v6](ai-agent-docs/shadow-api-contract.md). Gunakan artifact serta threshold v6 asli untuk pengujian internal; status tetap shadow, belum untuk penggunaan publik. Fokus pengerjaan saat ini pada v6; eksperimen versi lain dipertahankan sebagai arsip riset.

**Recall/CNN v10: tahap persiapan selesai, training masih menunggu data gate.** [Protokol](ai-agent-docs/recall-cnn-v10-plan.md), [notebook audit/persiapan](guardian_lab_url_qr_recall_cnn_v10.ipynb), dan [hasil aktual](ai-agent-docs/recall-cnn-v10-results.md). Audit 84.545 tune URL menemukan FPR hosting bersama 5,82% pada v8. Sumber publik memberi 4.469 benign historis dan tiga phishing terbaru setelah pemeriksaan overlap/privasi. Arsitektur CNN karakter diuji secara teknis, **belum dilatih atau dibandingkan** karena belum tersedia holdout temporal dua kelas yang memenuhi protokol. Runtime tetap frozen v6; tidak ada accuracy CNN atau gold Indonesia baru.

**Workspace dibersihkan:** artifact trial perantara, matriks fitur training v9, dan cache tool dipindahkan ke Recycle Bin. Dataset, notebook, model final dan seluruh bukti evaluasi tetap tersedia. [Catatan cleanup](ai-agent-docs/workspace-cleanup.md) menjelaskan file yang dibuang dan cara replay dari artifact final.

Model URL-only untuk membantu pilar **Recognize** Guardian Lab mengenali indikasi phishing sebelum pengguna membuka tautan. URL hasil dekode QR memakai model yang sama. Aplikasi web dan sandbox berada di [guardian_lab](https://github.com/DeryWahyu/guardian_lab).

**Notebook utama saat ini:** [guardian_lab_url_qr_data_v6.ipynb](guardian_lab_url_qr_data_v6.ipynb), Logistic Regression v6 dengan 532.793 URL fitting. Pilih kernel Python 3.12 proyek dan jalankan Run All untuk memuat artifact beku sesuai protokol. [Notebook v3](guardian_lab_url_qr.ipynb) tetap menjadi arsip baseline beserta audit, kalibrasi, evaluasi dan contoh inferensi. Baseline SGD serta eksperimen lain tersedia untuk perbandingan historis.

**Perbandingan CatBoost versus Logistic Regression v9 selesai:** [protokol](ai-agent-docs/model-family-comparison-v9-plan.md), [notebook](guardian_lab_url_qr_comparison_v9.ipynb), dan [hasil](ai-agent-docs/model-family-comparison-v9-results.md). Dua konfigurasi per keluarga dilatih pada **535.504 URL fitting yang sama**, memakai 102 fitur bersama. CatBoost terbaik mengungguli LR ringkas, tetapi kalah dari kontrol LR dengan TF-IDF lengkap: accuracy Phish360 **73,92% versus 78,06%**, recall **38,99% versus 48,89%**, FPR **0,162% versus 0,301%**. Semua kandidat baru gagal guard development per sumber; runtime tetap frozen v6. Seluruh benchmark sudah teramati; kompresi SVD membatasi kesimpulan tentang keluarga model secara umum. CNN belum dilatih dan tidak ada promosi publik.

**Alur validasi Indonesia berikutnya:** [protokol gold set](ai-agent-docs/indonesia-gold-set-plan.md), [notebook persiapan anotasi](guardian_lab_gold_set_indonesia.ipynb), dan [template CSV kosong](ml/templates/). Notebook persiapan tidak melatih model atau membuat label manusia. Kandidat baru, dua reviewer independen, dan QA masih diperlukan sebelum gold set atau evaluasi Indonesia dapat dinyatakan tersedia.

**Training ulang development v4:** [protokol sebelum fitting](ai-agent-docs/retraining-v4-plan.md) dan [notebook eksperimen](guardian_lab_url_qr_retraining_v4.ipynb). Ketiadaan gold set Indonesia tidak menghentikan eksperimen pada data development lama. V4 mempertahankan satu keluarga Logistic Regression dan menguji pembobotan sumber/domain; baseline v3 tetap dibekukan. Semua benchmark pada siklus v4 telah teramati sebelumnya dan tidak disebut test independen baru.

**Hasil v4:** enam konfigurasi benar-benar dilatih ulang pada 432.793 URL dan semuanya konvergen. Konfigurasi v3 tetap menang pada tune; accuracy warning pada benchmark tidak meningkat: Phresh domain baru 73,85% dan URL-Phish 97,09%, dengan recall masing-masing 59,10% dan 64,01%. Rata-rata deskriptif lima accuracy tetap 84,37%. [Laporan agregat v4](ml/reports/retraining-v4.json) mencatat seluruh konfigurasi, metrik, interval, serta pemeriksaan artifact; baseline v3 dipertahankan tanpa promosi produksi.

**Eksperimen recall v5:** [protokol](ai-agent-docs/recall-improvement-v5-plan.md) dan [notebook](guardian_lab_url_qr_recall_v5.ipynb). Menguji transformasi log-count-ratio dan pemisahan fitur host/path dengan classifier Logistic Regression yang sama. Pengujian baru memakai 50.000 URL DeepURLBench berlabel konsensus vendor serta 33 kasus audit manusia terpublikasi setelah pemeriksaan overlap. Kedua tingkat bukti dilaporkan terpisah; subset manusia kecil dan tidak menggantikan gold set Indonesia.

**Hasil v5:** tidak mengalahkan baseline; test baru menunjukkan recall 52,79% dan FPR 5,41% pada DeepURLBench, serta 9/22 phishing tertangkap pada audit manusia. [Laporan v5](ml/reports/recall-improvement-v5.json) mencatat kegagalan generalisasi ini.

**Eksperimen data v6 selesai:** [notebook model](guardian_lab_url_qr_data_v6.ipynb), [protokol/hasil lengkap](ai-agent-docs/data-improvement-v6-plan.md), dan [laporan](ml/reports/data-improvement-v6.json). Satu Logistic Regression dilatih pada 532.793 URL; test baru mencakup 20.000 holdout domain vendor dan 9.269 phishing laporan/verifikasi komunitas 2026. Pada target false alarm development sekitar 1%, [kontrol tambahan](guardian_lab_url_qr_v6_control.ipynb) menunjukkan recall PhishTank 26,59% menjadi 46,53%, dengan FPR vendor 1,01% versus 0,94%. Kontrol tersebut dideklarasikan terlambat; threshold dipilih dari development dan model tidak diubah dari test. Dibanding kebijakan asli v3, recall PhishTank justru turun 55,48% menjadi 46,53%; audit manusia turun 9/22 menjadi 4/22. V6 memperbaiki kemampuan pada batas false alarm rendah, belum lebih andal di semua kondisi, dan tidak dipromosikan ke produksi. FPR feed positif tidak tersedia; validasi Indonesia belum selesai.

**Audit keandalan dan API internal:** [rencana/hasil](ai-agent-docs/model-hardening-plan.md), [notebook audit](guardian_lab_model_hardening.ipynb), [laporan agregat](ml/reports/model-hardening-audit.json), dan [kontrak/cara menjalankan API](ai-agent-docs/shadow-api-contract.md). Audit memeriksa 84.000 URL development tune dan mencocokkan 200 kasus audit manusia PhishVN terpublikasi. Ditemukan 33 representasi berlabel bertentangan dan 3 kasus scam di luar scope yang masih memerlukan verifikasi konteks; tidak ada relabel otomatis atau training baru. Pilot Indonesia berisi 73 kandidat belum berlabel. API shadow memakai artifact v6 asli dengan output Manusia/Geek, input unsupported/kegagalan tanpa skor rendah, dan monitoring agregat tanpa target. Release gate tetap gagal/pending; aplikasi publik belum diaktifkan.

**Training ulang struktur v7 selesai:** [protokol](ai-agent-docs/structural-retraining-v7-plan.md), [notebook](guardian_lab_url_qr_structural_v7.ipynb), dan [hasil lengkap](ai-agent-docs/structural-retraining-v7-results.md). Empat konfigurasi Logistic Regression benar-benar dilatih pada 532.751 URL setelah 42 baris fitting ambigu dikarantina tanpa relabel. Kandidat struktur linear C=2 dipilih hanya dari tune. Recall PhishTank teramati naik 46,53% menjadi 48,43%, sementara FPR vendor turun 0,944% menjadi 0,691%. Pada 7.516 URL Phish360 dari penerbit tambahan dan domain di luar exposure lama, recall justru turun 42,99% menjadi 41,89% dengan accuracy 75,15%; audit manusia kecil juga menurun. Seluruh 73 tes lulus. V7 tetap kandidat riset, runtime shadow tetap v6, dan validasi Indonesia belum tersedia. Data Phish360 kini teramati dan masuk registry exposure untuk eksperimen berikutnya.

**Perluasan data v8 selesai:** [protokol](ai-agent-docs/data-expansion-v8-plan.md), [notebook](guardian_lab_url_qr_expansion_v8.ipynb), dan [hasil lengkap](ai-agent-docs/data-expansion-v8-results.md). Sebanyak 2.753 URL fitting tambahan dari benchmark TR-OP dengan validasi manual yang dilaporkan penulis memperluas fit menjadi **535.504 URL**; vocabulary/scaler di-fit ulang. Holdout domain baru 1.097 URL terpisah sebelum prediksi, dari sumber yang juga masuk development. Tiga kandidat konvergen tetapi semuanya gagal guard regresi per sumber. Diagnostic challenger mencapai recall 58,91% dan 0/384 FP pada holdout baru; recall Phish360 teramati naik 41,89% menjadi 48,89%, tetapi PhishTank dan audit manusia kecil menurun dibanding v7. Keputusan seleksi tetap frozen v6, tanpa promosi produksi. Notebook selesai penuh dan 79 tes lulus. Perbaikan satu ekspresi tampilan akhir dicatat dalam ledger metadata dengan payload numerik tetap identik.

## Hasil iterasi v3

Fitting kini memakai **432.793 URL** dari empat sumber. Domain dipisahkan antara fitting, tuning, kalibrasi, threshold, dan group holdout. Sumber yang pernah dievaluasi lalu ditambahkan ke pengembangan tidak lagi dianggap test independen. Challenge URL-Phish baru dipisahkan dari seluruh domain/URL sebelumnya dan hanya diprediksi setelah model dibekukan.

Rata-rata deskriptif dengan bobot setara pada lima evaluasi: accuracy **73,75% → 84,37%**, balanced accuracy **71,44% → 78,45%**. Rata-rata ini mencakup sumber yang sudah teramati atau masuk pengembangan; ia bukan estimasi accuracy trafik nyata.

| Evaluasi                                 | Accuracy v1 | Accuracy v3 | FPR v3 |
| ---------------------------------------- | ----------: | ----------: | -----: |
| Phresh domain baru, benchmark teramati   |      80,48% |      73,85% |  0,38% |
| URL-Phish, challenge tambahan 85.824 URL |      75,87% |      97,09% |  0,44% |

**Hasil tidak meningkat seragam.** V3 mengurangi false positive lintas sumber dengan trade-off recall pada beberapa benchmark. Challenge baru didominasi benign dan memiliki selisih jumlah antara katalog dan berkas resmi, sehingga 97,09% tidak boleh disebut accuracy universal. Notebook memuat balanced accuracy, recall, ukuran kelas, interval per domain, analisis kegagalan v2, dan keterbatasan label. Belum ada promosi produksi atau penggantian layanan web otomatis.

## Arsip hasil eksperimen pertama

Model sudah dilatih dan dievaluasi. **TF-IDF karakter + Logistic Regression dengan optimizer SGD** mengungguli CatBoost dan XGBoost pada aturan pemilihan validasi: recall tertinggi dengan FPR maksimal 0,1%. CatBoost adalah rekomendasi awal; hasil eksperimen menentukan pemenang.

Audit memeriksa 902.110 baris resmi dari PhreshPhish dan PhiUSIIL. Setelah sanitasi dan kurasi, fitting memakai 302.812 sampel PhreshPhish. Tune, kalibrasi, threshold, dan test dipisahkan; PhiUSIIL hanya dipakai untuk evaluasi eksternal. Seluruh 16 pemeriksaan data akhir lulus.

Test utama terdiri dari **80.052 sampel pada domain/tenant baru** dengan periode lebih baru dari data pengembangan. Kedua threshold dibekukan sebelum test:

| Kebijakan                | Recall phishing | False-positive rate |
| ------------------------ | --------------: | ------------------: |
| Peringatan MEDIUM + HIGH |          69,86% |             0,9744% |
| Indikasi kuat HIGH       |          31,51% |             0,0618% |

**Status: kandidat riset terlatih, belum layak menjadi satu-satunya penentu keamanan.** Recall masih terbatas, verifikasi manual seluruh label belum dilakukan, dan gold set Indonesia serta holdout terbaru 2026 masih diperlukan. Precision benchmark bukan accuracy atau probabilitas keamanan pada trafik nyata. Hasil LOW tidak menjamin tautan aman.

Bundle lokal `ml/artifacts/url-core-v1.joblib` berukuran 811.300 byte. Dataset dan binary model diabaikan Git; repo menyimpan kode, manifest, checksum, dan laporan agregat. Inferensi CPU terukur p50 4,24 ms dan p95 6,58 ms untuk batch satu pada lingkungan eksperimen.

## Bukti dan dokumentasi

- [Model card, metrik, batas kemampuan, dan keputusan](ml/reports/model-card.md)
- [Audit data dan pengecualian sampel](ml/reports/data-audit.json)
- [Protokol sebelum training](ml/reports/run-protocol.json)
- [Perbandingan validasi](ml/reports/validation-results.json)
- [Model, kalibrasi, dan threshold yang dibekukan](ml/reports/frozen-selection.json)
- [Test final dan ketidakpastian per domain](ml/reports/final-test.json)
- [Hasil dua threshold pada domain baru](ml/reports/operating-thresholds.json)
- [Rencana ML dan integrasi mendatang](ai-agent-docs/machine-learning-plan.md)
- [Riset sumber dan bias dataset](ai-agent-docs/url-qr-dataset-research.md)

## Menyiapkan lingkungan

Python 3.12 diperlukan. Jalankan dari root repo. Contoh PowerShell:

```powershell
python -m venv ml/.venv
ml/.venv/Scripts/python.exe -m pip install -e "./ml[test,dev]"
ml/.venv/Scripts/python.exe -m pytest ml/tests -q
ml/.venv/Scripts/python.exe -m ruff check ml/src ml/tests ml/run.py
ml/.venv/Scripts/python.exe -m ruff format --check ml/src ml/tests ml/run.py
```

Pada Linux/macOS, executable environment berada di `ml/.venv/bin/python`. Tes artifact nyata memerlukan bundle lokal; tes tersebut dilewati pada clone yang hanya memiliki kode/laporan. Pada lingkungan yang menghasilkan laporan ini, seluruh tes termasuk artifact nyata telah dijalankan.

## Arsip reproduksi eksperimen perbandingan v1

Laporan v1 yang dilacak Git tidak boleh ditimpa. Gunakan ID reproduksi baru agar data, laporan, dan model masuk ke `ml/runs/<run_id>/` yang diabaikan Git:

```powershell
ml/.venv/Scripts/python.exe ml/run.py reproduce-v1 dataset
ml/.venv/Scripts/python.exe ml/run.py reproduce-v1 train
ml/.venv/Scripts/python.exe ml/run.py reproduce-v1 evaluate
ml/.venv/Scripts/python.exe ml/run.py reproduce-v1 report
ml/.venv/Scripts/python.exe ml/run.py reproduce-v1 test
```

Ingestion membaca kolom URL/label/tanggal dari aset resmi yang dipin, tanpa HTML dan tanpa membuka URL target. Pengambilan sumber membutuhkan jaringan; proses training dan inferensi tidak membutuhkan jaringan. Pipeline menghentikan proses jika audit gagal, checksum berubah, atau seleksi pada run yang sama sudah dibekukan. Jangan menghapus guard untuk tuning setelah melihat test; eksperimen baru memerlukan protokol serta holdout yang sesuai. Timestamp dan checksum bundle reproduksi dapat berbeda.

Untuk mengulang audit cache pada run yang sama, gunakan `ml/run.py reproduce-v1 dataset --reuse-staging`. Ini tetap menjalankan kurasi dan pemeriksaan berkas tersimpan.

## Arsip inferensi CLI v1

Untuk model utama v6, gunakan [API internal](ai-agent-docs/shadow-api-contract.md). Perintah pada bagian ini mereproduksi CLI v1 yang diarsipkan.

Bundle dari eksperimen awal tersedia di mesin tempat training dilakukan. Gunakan input sintetis melalui stdin:

```powershell
'{"url":"https://example.org/login","input_type":"QR"}' | ml/.venv/Scripts/python.exe -m guardian_ml.predictor
```

Untuk bundle reproduksi, ganti pemanggilan modul dengan `ml/.venv/Scripts/python.exe ml/run.py reproduce-v1 predictor`. Tidak ada permintaan untuk memakai kredensial asli. Loader menolak checksum, schema, dependency, atau implementasi inferensi yang tidak cocok. Artifact joblib hanya boleh dimuat dari training yang dipercaya.

Query/fragment dikeluarkan secara konsisten saat training dan inferensi. Model tidak mengikuti shortlink, membaca HTML, memeriksa malware APK, atau memvalidasi merchant QRIS. Layanan HTTP riset v6 tersedia melalui [API shadow](ai-agent-docs/shadow-api-contract.md); integrasi Next.js dan deployment publik masih belum diaktifkan. CLI arsip di atas tetap menggunakan model v1.

## Struktur

```text
ai-agent-docs/              Rencana dan riset sumber
scripts/research/           Audit awal aset resmi
ml/pyproject.toml           Dependency runtime/test/tooling yang dipin
ml/run.py                  Reproduksi pada direktori run terisolasi
ml/src/guardian_ml/         Data, sanitasi, fitur, training, evaluasi, inferensi
ml/tests/                  Privasi, leakage, kalibrasi, dan artifact nyata
ml/reports/                Laporan v1-v6, audit keandalan, model card, dan grafik
ml/policies/               Release gate dan manifest runtime shadow
ml/data/                   Dataset lokal tersanitasi; diabaikan Git
ml/artifacts/              Bundle lokal v1; diabaikan Git
ml/runs/                   Reproduksi lokal; diabaikan Git
```
