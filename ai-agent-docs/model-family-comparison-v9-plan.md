# Protokol Perbandingan CatBoost dan Logistic Regression v9

> Ditetapkan sebelum fitting v9, 1 November 2026. Pengguna mengizinkan perbandingan model setelah pembahasan alternatif. Protokol ini memperluas eksperimen keluarga Logistic Regression; API shadow tetap frozen v6.

## Pertanyaan dan data

Apakah hubungan nonlinear meningkatkan recall pada batas false alarm rendah, dibanding classifier linear dengan informasi input yang sama? Gunakan dataset v8 tanpa menambah atau melabel ulang data: 535.504 fitting, 84.545 tune, 40.635 calibration dan 47.219 threshold. Verifikasi hash parent, core/digest/domain, keunikan serta pemisahan domain antar-role. Semua benchmark kini teramati; tidak ada klaim test independen baru atau validasi Indonesia.

Training dilakukan dalam `guardian_lab_url_qr_comparison_v9.ipynb`. Sumber data, notebook/model v3/v6/v7/v8 dan manifest shadow dilindungi checksum. Jangan membuka target, HTML, DNS, mengirim data ke LLM atau mencetak contoh dataset. URL dan QR memakai canonical core yang sama; query/fragment dan skema tidak menjadi fitur.

## Perbandingan yang ditetapkan

1. Logistic Regression pada representasi bersama: C=0,5 dan C=2, liblinear, max_iter=1500, tol=0,0001.
2. CatBoost pada representasi bersama: depth=6 dan depth=8, maksimal 600 pohon, learning_rate=0,06, l2_leaf_reg=5, Logloss, early stopping 60 iterasi pada tune, CPU empat thread, seed 20261101, tanpa file log target.
3. Frozen Logistic Regression v8 dengan seluruh TF-IDF/struktur sebagai kontrol praktis, serta frozen v6 untuk guard dan kontrol runtime. Keduanya tidak dilatih ulang; kebijakan threshold kontrol dihitung dari development yang sama.

Representasi bersama terdiri dari 64 komponen TruncatedSVD teks ditambah 33 fitur log-numerik scheme-free dan lima flag struktur v7 (102 fitur). Gunakan char/kata encoder frozen v8 yang sudah di-fit pada fitting v8 yang sama; fit SVD hanya pada sampel fitting per-sumber maksimal 12.000 dan total 60.000, seed tetap, randomized n_iter=5. Vocabulary tidak menerima tune/calibration/threshold/test. Transformasi batch membatasi RAM. CatBoost menerima nilai bersama asli; LR memakai StandardScaler fit-only. Tidak ada label/source ID sebagai fitur.

SVD dapat membuang sinyal teks langka. Perbandingan fitur bersama mengisolasi classifier lebih baik, tetapi tidak membuktikan kualitas seluruh keluarga CatBoost pada semua representasi. Kontrol LR lengkap mengukur dampak kompresi. CNN belum dilatih pada eksperimen ini.

Kedua keluarga memakai seluruh fitting yang sama dan sample_weight inverse source count, dinormalisasi mean satu, tanpa class-weight tambahan. Tune dipakai untuk early stopping/seleksi saja; kalibrasi dan threshold tetap terpisah. Anggaran dua konfigurasi per keluarga; tidak menambah trial sesudah melihat benchmark.

## Seleksi, kalibrasi dan evaluasi

Metrik utama tune: minimum recall per sumber, kemudian macro recall dan AP, pada global threshold dengan FPR empiris maksimal 1% per sumber. Guard terhadap frozen v6 mengizinkan penurunan recall paling besar 1 percentage point per sumber. Pilih satu kandidat per keluarga dari tune; jika tidak ada yang lolos, sebut kandidat diagnosis dan pertahankan v6. Tidak memilih pengganti dari accuracy benchmark.

Fit sigmoid calibration untuk setiap finalist pada calibration saja, termasuk kontrol untuk kebijakan yang sebanding. Pilih warning/high dari threshold partition dengan batas upper Wilson per-sumber 1%/0,1% bila ukuran memadai, fallback empiris sumber kecil dinyatakan. Bekukan artifact, data/spec/source/code hash serta threshold sebelum membaca prediksi benchmark. Skor kalibrasi bukan probabilitas trafik Indonesia.

Evaluasi seluruh finalist pada cohort identik: Phish360 (7.516), TR-OP (1.097), vendor DeepURLBench (20.000), audit manusia PhishVN (33), PhishTank 2026 (9.269 positif saja), Phresh domain baru (80.052), serta URL-Phish (85.824). Pastikan domain/URL tidak masuk development. Laporkan accuracy, recall, precision, FPR, ukuran kelas, Wilson, balanced accuracy, AP/Brier bila dua kelas tersedia, waktu fit/inferensi dan ukuran model. Bootstrap domain berpasangan 1.000 kali untuk CatBoost versus LR lengkap dan LR fitur bersama. Feed positif tidak memiliki accuracy biner, FPR atau precision trafik.

Hasil menunjukkan ranking pada benchmark teramati, bukan bukti kausal atau kualitas produksi. Target release recall lower Wilson 85%, FPR upper Wilson 1%, bukti Indonesia dan batas penggunaan sumber tetap berlaku. Tidak ada promosi runtime atau perubahan guard setelah melihat hasil.

## Bukti selesai

Notebook Run All tanpa error; artifact save/reload, URL/QR dan HTTP/HTTPS parity; tes leakage/fit-only/scoring serta artifact nyata; Ruff dan suite regresi. Simpan laporan agregat JSON/MD, grafik perbandingan, konfigurasi dan integritas. Dataset/model/features lokal tetap diabaikan Git. Tidak mengubah registry anotasi Indonesia karena tidak ada URL baru; seluruh cohort sudah terdaftar pada exposure v8.

Referensi implementasi: [CatBoost fit](https://catboost.ai/docs/en/concepts/python-reference_catboostclassifier_fit), [TruncatedSVD](https://scikit-learn.org/1.8/modules/generated/sklearn.decomposition.TruncatedSVD.html). Dependency terpasang CatBoost 1.2.10 dan scikit-learn 1.8.0; tidak mengikuti versi `stable` yang berbeda diam-diam.
