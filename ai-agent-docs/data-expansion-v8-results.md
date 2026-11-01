# Hasil Perluasan Data dan Seleksi URL/QR v8

> Selesai 1 November 2026. [Protokol](./data-expansion-v8-plan.md), [notebook terlatih](../guardian_lab_url_qr_expansion_v8.ipynb), [laporan metrik](../ml/reports/data-expansion-v8.json), [audit sumber](../ml/reports/data-source-audit-v8.json), dan [validasi implementasi](../ml/reports/data-expansion-validation-v8.json).

## Keputusan

Training v8 benar-benar memperluas fitting, refit vocabulary/scaler, dan menerapkan guard regresi per sumber. Ketiga kandidat konvergen. Semua gagal guard development yang ditetapkan sebelum fitting, sehingga keputusan seleksi adalah **mempertahankan frozen v6**. Kandidat terbaik menurut urutan sumber terlemah disimpan sebagai **diagnostic challenger**, bukan pengganti terpilih atau model produksi.

Challenger menunjukkan perbaikan pada holdout domain TR-OP dan Phish360 teramati, tetapi recall PhishTank dan audit manusia kecil menurun terhadap v7. Bukti ini tidak mendukung peningkatan menyeluruh atau pencapaian target recall 85%.

## Data yang benar-benar bertambah

Sumber tambahan TR-OP KnowPhish diperoleh dari link pada commit penulis `899982c9f0eef0f2ef758cbee96d2ceff0bd5e9a`. Paper melaporkan validasi manual benchmark; tidak ada dua lembar review independen per kasus. Data historis 2023 ini bukan gold Indonesia. Tidak menganggap ranking Tranco sendiri sebagai label keamanan.

Pemeriksaan 10.000 metadata kasus mengeluarkan 3.863 domain yang sudah dikenal dan 631 metadata tidak didukung. Sebanyak 5.506 anggota teks dibaca dengan HTTP range; semuanya diverifikasi CRC sebelum parsing. Dua input ditolak screening privasi. Setelah 40 duplikat dan 26 kelebihan cap domain dikeluarkan, tersisa **5.438 URL**.

Endpoint redirect awal menghasilkan banyak respons range yang tidak cocok; intake dihentikan dan tidak dipakai training. Proses dilanjutkan dari checkpoint valid melalui endpoint konten publik dengan cache key per anggota. Semua kasus terpilih selesai diverifikasi sebelum fitting; baris yang gagal integritas tidak diterima diam-diam. Tidak mengambil HTML/gambar, membuka target, atau mengirim baris untuk pelabelan LLM.

| Partition           | Data tambahan | Total development v8 |
| ------------------- | ------------: | -------------------: |
| Fitting             |     **2.753** |          **535.504** |
| Tune                |           545 |               84.545 |
| Calibration         |           531 |               40.635 |
| Threshold           |           512 |               47.219 |
| Holdout domain baru |     **1.097** |  Di luar development |

Fit v8 terdiri dari **201.161 berlabel phishing dan 334.343 benign**. Parent fit v7 532.751 URL tetap teridentifikasi; tidak ditemukan konflik representasi tambahan pada gabungan fit. Vocabulary TF-IDF serta scaler baru hanya di-fit pada fit gabungan, termasuk data tambahan. Phish360 tetap di luar training dan berstatus benchmark teramati.

Partisi domain sumber tambahan 50/10/10/10/20 ditentukan sebelum prediksi. Holdout memiliki 713 phishing dan 384 benign, domain berbeda dari seluruh development dan exposure v1-v7. Sumber/penerbit yang sama masuk development dan test; tidak ada klaim independent-source, pemisahan temporal atau kemerdekaan kampanye. Metadata arsip TR-OP sudah diperiksa pada v7 dan exposure tersebut diungkapkan.

## Seleksi yang memperhatikan sumber terlemah

Semua kandidat adalah Logistic Regression liblinear C=2. Guard mengizinkan penurunan maksimal 1 percentage point pada setiap sumber terhadap kontrol v6, pada aturan threshold tune yang sama. Di antara kandidat yang lolos, urutan seleksi adalah minimum recall sumber, macro recall, lalu AP. Ini screening empiris; interval domain dilaporkan terpisah.

| Kandidat                                   | Macro recall tune | Minimum recall sumber | Guard                    | Durasi fit |
| ------------------------------------------ | ----------------: | --------------------: | ------------------------ | ---------: |
| Expanded rich, bobot sqrt                  |            45,59% |                38,34% | Gagal: PhishVN -2,41 pp  |   44,7 dtk |
| Expanded structural, bobot sqrt            |            46,89% |                35,92% | Gagal: PhishVN -4,83 pp  |   95,7 dtk |
| Expanded structural, bobot sumber seimbang |        **47,76%** |            **41,01%** | Gagal: PhiUSIIL -1,80 pp |   99,2 dtk |

Kontrol v6 pada tune gabungan memiliki macro recall 43,95% dan minimum source recall 40,75%. Kandidat sumber seimbang meningkatkan minimum/rata-rata, tetapi melanggar guard PhiUSIIL. Bootstrap domain development untuk delta recall PhiUSIIL sekitar **[-2,71; -1,02] pp**. Guard tidak dibatalkan setelah hasil test terlihat.

Challenger terpilih untuk diagnosis memakai bobot inverse source count. Kalibrasi hanya pada calibration; warning **0,9103663235299849**, high **0,9888354271812084** dipilih dari threshold partition dan dibekukan sebelum test. Upper Wilson per sumber 1%/0,1% diterapkan bila ukuran memungkinkan; fallback empiris sumber kecil tercatat dalam laporan. Source ID bukan fitur saat inferensi.

## Holdout domain baru TR-OP

| Metrik                      | V6 asli | V7 asli | Challenger v8 |
| --------------------------- | ------: | ------: | ------------: |
| Accuracy                    |  64,36% |  63,99% |    **73,29%** |
| Recall phishing             |  45,30% |  44,60% |    **58,91%** |
| Phishing tertangkap / 713   |     323 |     318 |       **420** |
| Benign salah ditandai / 384 |       1 |       0 |         **0** |
| FPR                         |  0,260% |  0,000% |    **0,000%** |

Dibanding v7, challenger menangkap 102 phishing tambahan. Interval delta recall bootstrap domain 95% sekitar **[+11,66; +17,29] pp**. Wilson recall v8 sekitar [55,26%; 62,46%], masih jauh dari target lower bound 85%. Nol FP pada 384 benign memiliki upper Wilson sekitar **0,9905%**, dengan asumsi row-IID; tidak berarti jaminan nol false alarm pada trafik nyata. Bias label, domain/kampanye dan data historis tetap membatasi klaim.

## Benchmark teramati dan trade-off

| Benchmark                       | Recall v7 |  Recall v8 |         FPR v7 |         FPR v8 |
| ------------------------------- | --------: | ---------: | -------------: | -------------: |
| Phish360, 7.516 URL             |    41,89% | **48,89%** |         0,185% |         0,301% |
| Vendor, 20.000 URL              |    43,10% | **45,73%** |         0,691% |         0,843% |
| PhishTank 2026, positif saja    |    48,43% | **47,20%** | Tidak tersedia | Tidak tersedia |
| Audit manusia PhishVN, 33 kasus |      3/22 |   **2/22** |           0/11 |           0/11 |
| Phresh domain baru              |    37,34% |     36,68% |         0,154% |         0,295% |
| Mendeley                        |    69,77% |     72,06% |         0,000% |         0,000% |
| PhishVN core                    |    28,88% |     37,93% |         0,370% |         0,053% |
| PhiUSIIL                        |    34,80% |     34,42% |         0,025% |         0,034% |
| URL-Phish                       |    58,78% |     60,44% |         0,089% |         0,169% |

Accuracy Phish360 menjadi **78,06%**, dibanding v7 75,15%; jumlah FP naik 8 menjadi 13. Delta recall domain 95% sekitar [+6,01; +8,05] pp. Vendor upper Wilson FPR v8 sekitar 0,9886%, tetapi point FPR lebih tinggi daripada v7.

PhishTank tertangkap 4.375/9.269, turun dari v7 4.489; 4.894 masih terlewat. Interval delta recall domain terhadap v7 sekitar [-1,85; -0,64] pp. Feed positif tidak menghasilkan FPR, accuracy biner atau precision trafik. Audit manusia kecil tetap sangat tidak pasti dan tidak menutupi penurunan jumlah kasus yang tertangkap.

## Integritas, perbaikan tampilan dan lokasi berkas

Notebook selesai Run All dengan tujuh sel kode dan nol error. Suite Python **79 tes lulus tanpa skip**. Tes mencakup CRC/ukuran ZIP, penolakan server yang mengabaikan Range sebelum membaca seluruh arsip, fit-only vocabulary, guard sumber, artifact nyata, parity URL/QR/HTTP-HTTPS dan pencatatan exposure.

Eksekusi awal menyelesaikan fitting, pembekuan, scoring dan penulisan laporan, lalu gagal menampilkan tabel karena daftar kandidat lolos kosong. Perbaikan hanya mengganti satu ekspresi tampilan DataFrame menjadi Series. Metadata code/spec/artifact hash dimigrasikan dengan [ledger perbaikan](../ml/reports/presentation-repair-v8.json); snapshot asli tetap lokal. Fingerprint estimator/encoder/kalibrator pada payload tersimpan sama sebelum/sesudah. Tidak ada refit, pemilihan ulang, perubahan threshold atau tuning berdasarkan test. Notebook kemudian dijalankan penuh dengan memuat artifact beku; metrik numerik diperiksa terhadap laporan sebelum perbaikan.

| Berkas lokal yang dihasilkan                                 | Lokasi relatif root                                                        |
| ------------------------------------------------------------ | -------------------------------------------------------------------------- |
| Dataset development, 707.903 URL                             | `ml/runs/notebook-tfidf-logistic-v8/data/development-v8.parquet`           |
| Holdout domain baru, 1.097 URL                               | `ml/runs/notebook-tfidf-logistic-v8/data/tr-op-test-v8.parquet`            |
| Exposure intake tersanitasi, termasuk baris yang terkena cap | `ml/runs/notebook-tfidf-logistic-v8/data/intake-exposure-v8.parquet`       |
| Artifact diagnostic challenger                               | `ml/runs/notebook-tfidf-logistic-v8/artifacts/url-core-logistic-v8.joblib` |
| Pembekuan dan ledger repair                                  | `ml/runs/notebook-tfidf-logistic-v8/reports/`                              |

Data/model/checkpoint tetap lokal dan diabaikan Git. Registry exposure sesudah evaluasi memuat **14 cache, 1.154.397 hash URL dan 742.979 hash domain/tenant**, tanpa run yang belum terdaftar. Snapshot sebelum v8 dipertahankan. Input anotasi Indonesia tidak diisi otomatis; penelusuran katalog/paper Indonesia belum menghasilkan dataset URL-label dengan audit kasus yang dapat diverifikasi.

Dependency intake dipasang melalui `ml/.venv/Scripts/python.exe -m pip install -e "./ml[test,dev,research]"`. Eksekusi memerlukan artifact/cache parent lokal. Model/notebook v3, v6, v7 dan API shadow v6 tidak berubah. Hasil selanjutnya perlu menangani regresi PhiUSIIL, Phresh dan audit manusia pada protokol baru dengan bukti label/fitur tambahan; holdout TR-OP kini teramati dan tidak boleh dipakai memilih perubahan lalu disebut test baru.
