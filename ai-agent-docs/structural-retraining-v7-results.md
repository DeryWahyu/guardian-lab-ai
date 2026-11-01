# Hasil Training Ulang dan Evaluasi URL/QR v7

> Selesai: 1 November 2026. [Protokol sebelum fitting](./structural-retraining-v7-plan.md), [notebook terlatih](../guardian_lab_url_qr_structural_v7.ipynb), [laporan lengkap](../ml/reports/structural-retraining-v7.json), [audit sumber](../ml/reports/structural-source-audit-v7.json), dan [validasi implementasi](../ml/reports/structural-validation-v7.json).

## Keputusan

V7 memberi perbaikan terbatas: recall PhishTank teramati naik dan false alarm vendor turun, sedangkan recall pada test sumber baru Phish360 serta beberapa benchmark lama menurun. Simpan sebagai kandidat riset, pertahankan baseline dan runtime shadow v6. Tidak ada promosi produksi atau klaim peningkatan menyeluruh.

## Training yang benar-benar dijalankan

Fit v6 diaudit ulang. Sebanyak 40 baris pada 20 representasi berlabel konflik serta dua kasus ambigu audit manusia publik dikarantina dari fitting. Label tidak diubah. Keempat classifier memakai **532.751 URL** fitting yang sama. Tune 84.000, calibration 40.104 dan threshold 46.707 dipertahankan utuh. Vocabulary TF-IDF v6 memiliki provenance parent-fit-only; exposure unsupervised ke baris karantina tetap diungkapkan.

| Konfigurasi            | Macro recall tune pada batas FPR empiris 1% per sumber | Minimum recall sumber | Iterasi | Konvergen |
| ---------------------- | -----------------------------------------------------: | --------------------: | ------: | --------- |
| Repeat v6, C=2         |                                                43,671% |               40,751% |      22 | Ya        |
| Struktur linear, C=2   |                                            **43,773%** |               36,193% |      43 | Ya        |
| Struktur spline, C=0,5 |                                                39,463% |               28,418% |      13 | Ya        |
| Struktur spline, C=2   |                                                43,591% |               35,925% |      17 | Ya        |

Sesuai urutan seleksi yang ditetapkan sebelum fitting, kandidat terpilih adalah **Logistic Regression liblinear C=2 dengan fitur struktural linear, 118.734 fitur**. Macro recall hanya unggul sekitar 0,10 percentage point, sementara minimum source recall menurun. Ini sinyal development yang lemah, sehingga evaluasi luar development tetap diperlukan dan hasil test tidak dipakai memilih ulang kandidat.

Durasi tercatat keempat kandidat sekitar 432,56 detik secara total, mencakup fit, prediksi tune dan penyimpanan kandidat; persiapan fitur berada di luar timer. Angka ini bukan benchmark latency deployment.

## Kalibrasi dan kebijakan threshold

Sigmoid di-fit hanya pada calibration. Threshold v7 dibekukan sebelum test pada warning **0,9177038674825727** dan high **0,9887723682878329**. Warning menargetkan batas atas Wilson FPR 1% per sumber bila jumlah benign memadai; high menargetkan 0,1%.

Mendeley terlalu kecil untuk batas keyakinan warning, sehingga fallback empiris yang sudah diprotokolkan digunakan dan dicatat. High memiliki fallback pada Mendeley dan PhishVN. Tidak ada klaim jaminan confidence per sumber bila fallback berlaku.

Kontrol v6 dengan aturan threshold confidence yang sama dipilih hanya dari development dan dibekukan sebelum test. Kebijakan asli v6 tetap menjadi pembanding utama yang ditampilkan berikut.

## Test sumber tambahan Phish360

Dua aset penulis memuat 10.748 baris. Setelah sanitasi, pengecualian exposure v1-v6, deduplikasi dan domain cap, tersisa **7.516 URL: 3.201 phishing dan 4.315 legitimate pada 7.002 domain/tenant**. Seluruh data ini berada di luar fitting/tune/calibration/threshold. Hanya URL/Class/tag bahasa yang dibaca; tidak ada pengambilan HTML/screenshot atau kunjungan target.

Penulis melaporkan inspeksi/kurasi manual. Dua sheet review per kasus dan statistik kesepakatan tidak tersedia. Bukti ini berbeda dari audit manusia PhishVN. Phish360 merupakan dataset dari penerbit tambahan dengan domain yang dikeluarkan dari exposure lama; sebagian asal feed PhishTank/OpenPhish beririsan dengan lineage sumber lama, sehingga tidak diklaim sepenuhnya independen pada tingkat feed atau kampanye.

| Metrik pada Phish360 baru     | V6 asli |         V7 |
| ----------------------------- | ------: | ---------: |
| Accuracy                      |  75,65% | **75,15%** |
| Recall phishing               |  42,99% | **41,89%** |
| Phishing tertangkap / 3.201   |   1.376 |  **1.341** |
| False alarm                   |  0,116% | **0,185%** |
| Benign salah ditandai / 4.315 |       5 |      **8** |

**V7 menurun pada test sumber baru.** Delta recall bootstrap domain 95% terhadap v6 asli sekitar **[-2,07; -0,13] percentage point**. Tidak menyembunyikan penurunan ini dengan hasil kontrol threshold lain. Interval Wilson recall v7 sekitar [40,19%; 43,61%], sedangkan FPR [0,094%; 0,365%], dengan asumsi row-IID.

Field bahasa sumber memberi 7.226 dari 7.516 baris bertag English dan tidak memiliki tag Indonesia. Keandalan tag tersebut tidak diaudit ulang. Dataset historis ini tidak menjadi gold set Indonesia atau bukti kinerja trafik lokal. Deskripsi masa koleksi pada halaman dan paper berbeda; timestamp per kasus tidak tersedia.

## Benchmark teramati dan regresi

| Benchmark                    |    URL | Recall v6 asli |     Recall v7 |    FPR v6 asli |         FPR v7 |
| ---------------------------- | -----: | -------------: | ------------: | -------------: | -------------: |
| Vendor DeepURLBench          | 20.000 |         46,31% |        43,10% |         0,944% |         0,691% |
| PhishTank 2026, positif saja |  9.269 |         46,53% |    **48,43%** | Tidak tersedia | Tidak tersedia |
| Audit manusia PhishVN        |     33 |  18,18% (4/22) | 13,64% (3/22) |           0/11 |           0/11 |
| Phresh domain baru           | 80.052 |         43,10% |        37,34% |         0,161% |         0,154% |
| Mendeley                     |  1.002 |         70,34% |        69,77% |         0,329% |         0,000% |
| PhishVN core                 |  2.123 |         39,66% |        28,88% |         0,423% |         0,370% |
| PhiUSIIL                     | 20.219 |         35,84% |        34,80% |         0,025% |         0,025% |
| URL-Phish                    | 85.824 |         55,39% |    **58,78%** |         0,093% |         0,089% |

PhishTank bertambah **176 true positive**, dari 4.313 menjadi 4.489; masih ada 4.780 phishing terlewat. Delta recall bootstrap domain 95% sekitar **[+1,29; +2,45] percentage point**. Karena feed hanya phishing, FPR, accuracy biner, precision trafik dan F1 tidak tersedia.

Vendor v7 memberi 123 false positive dari 17.789 benign, turun dari 168. Batas atas Wilson FPR v7 sekitar **0,824%**, dibanding v6 sekitar 1,098%; recall vendor ikut turun. Perhitungan ini berbasis label vendor historis dan bukan jaminan trafik produksi.

### Kontrol threshold confidence development yang sama

| Data               | Recall v6 kontrol | Recall v7 | FPR v6 kontrol |         FPR v7 |
| ------------------ | ----------------: | --------: | -------------: | -------------: |
| Phish360 baru      |            36,61% |    41,89% |         0,116% |         0,185% |
| Vendor teramati    |            39,35% |    43,10% |         0,652% |         0,691% |
| PhishTank teramati |            42,04% |    48,43% | Tidak tersedia | Tidak tersedia |

Kontrol ini menunjukkan fitur baru membantu pada aturan seleksi threshold yang sebanding. FPR empiris tidak identik; interval selisih FPR mencakup nol. Kontrol tidak menggantikan hasil kebijakan asli, regresi test baru, atau kebutuhan validasi Indonesia.

## Diagnosis development, integritas dan tindak lanjut

Private-hosting pada tune: recall 90,55% menjadi 91,62%, FPR 6,31% menjadi 6,19%. Recall URL panjang naik 11,43% menjadi 12,70%. Punycode hanya memiliki 69 baris, sehingga angka per segmennya sangat tidak pasti. Ini diagnosis development teramati dan tidak membuktikan perbaikan generalisasi.

Notebook selesai penuh: 14 sel, tujuh sel kode, nol error. Seluruh **73 tes Python lulus tanpa skip**, termasuk artifact asli, save/reload, fitur offline/HTTP-HTTPS, transformasi fit-only, confidence fallback, serta penolakan pencatatan exposure ketika checksum tidak cocok. Model/notebook v3/v6 dan manifest runtime tetap utuh. Dataset serta binary model diabaikan Git.

Lokasi berkas yang dihasilkan pada workspace training:

| Berkas                          | Lokasi relatif root repo                                                   |
| ------------------------------- | -------------------------------------------------------------------------- |
| Dataset fitting, 532.751 URL    | `ml/runs/notebook-tfidf-logistic-v7/data/fit-v7.parquet`                   |
| Dataset uji Phish360, 7.516 URL | `ml/runs/notebook-tfidf-logistic-v7/data/phish360-new.parquet`             |
| Bundle kandidat v7              | `ml/runs/notebook-tfidf-logistic-v7/artifacts/url-core-logistic-v7.joblib` |
| Metadata pembekuan/checksum     | `ml/runs/notebook-tfidf-logistic-v7/reports/frozen-v7.json`                |

Registry exposure sesudah evaluasi mencatat sebelas cache: 1.148.933 hash URL dan 737.796 hash domain/tenant unik, tanpa run yang belum terdaftar. Snapshot registry v1-v6 sebelum intake tetap disimpan dan dipakai untuk memverifikasi kebaruan Phish360. Input anotasi Indonesia tidak ditimpa dan tetap belum menghasilkan gold set.

Langkah penelitian berikutnya perlu menangani minimum-source recall dan regresi Phish360 pada protokol baru, dengan sumber development tambahan yang sah dan holdout lain yang belum dipakai memilih model. Phish360 sekarang berstatus teramati; tidak boleh dipakai sebagai test baru pada iterasi berikut. Gate recall minimal dan bukti Indonesia belum terpenuhi. Tidak menurunkan gate atau menyesuaikan threshold dari hasil test v7.
