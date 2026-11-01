# Protokol Training Ulang v4 — Logistic Regression URL/QR

> Tanggal: 1 November 2026. Status awal: protokol sebelum fitting v4.

> **Status eksekusi:** selesai. Enam classifier benar-benar dilatih pada 432.793 URL; semuanya konvergen. Konfigurasi `repeat_v3` tetap menang dari tune. Tidak ada peningkatan accuracy pada benchmark teramati dan tidak ada promosi produksi.

## Tujuan dan alasan

Ketiadaan gold set Indonesia membatasi klaim validasi Indonesia, tetapi tidak menghentikan eksperimen pada development yang sudah tersedia. Eksperimen ini melanjutkan perbaikan model URL/QR pada data tersanitasi lama. Dua reviewer manusia tetap diperlukan untuk membuat gold set Indonesia; label sumber pada development tidak diganti atau disebut label manusia yang baru diverifikasi.

V3 menunjukkan trade-off recall dan false positive antar sumber. V4 menguji apakah perubahan pembobotan sumber serta domain saat fitting memperbaiki recall validasi dengan kebijakan FPR yang sama. Tidak menjanjikan kenaikan accuracy dan tidak memakai hasil benchmark untuk memilih kandidat.

## Berkas dan baseline

- Notebook eksperimen: `guardian_lab_url_qr_retraining_v4.ipynb`; satu keluarga Logistic Regression, solver liblinear.
- Baseline v3, notebook utamanya, bobot, threshold, serta laporan pembekuan dipertahankan tanpa perubahan.
- Data: `ml/runs/notebook-tfidf-logistic-v3/data/development-v3.parquet`, checksum dicocokkan dengan pembekuan v3. Fit 432.793 URL dari empat sumber; tune 64.000; calibration 30.104; threshold 31.707.
- Artifact dan laporan rinci baru: `ml/runs/notebook-tfidf-logistic-v4/`, lokal dan diabaikan Git. Laporan agregat tanpa URL target tersedia pada `ml/reports/retraining-v4.json` setelah eksekusi.

## Audit sebelum fitting

Periksa checksum data dan baseline tepercaya, versi dependency, hash implementasi fitur, hash canonical, label, query/fragment, input sensitif yang terdeteksi parser, duplikasi, serta pemisahan domain/tenant antara fit/tune/calibration/threshold. Audit seluruh core melalui parser saat transformasi; hitungan label/domain dilaporkan tanpa URL. Bukti kampanye dan kebenaran seluruh label belum terverifikasi.

Encoder TF-IDF/scaler v3 dipakai kembali secara sengaja untuk mengisolasi pengaruh bobot loss. Encoder tersebut dipelajari hanya dari partisi fit v3 yang sama, bukan dari tune/calibration/threshold/test. Fitur scheme-free, bobot word 0,7 dan numeric 0,2, preprocessing URL, serta PSL offline dipertahankan. V4 benar-benar memanggil `.fit()` untuk classifier baru; tidak sekadar memuat ulang bobot v3.

## Anggaran eksperimen yang dibekukan

Enam konfigurasi berikut ditetapkan sebelum training. `C` adalah inverse regularization Logistic Regression; source power dan domain power hanya mengubah bobot loss saat fitting.

| Kandidat                      |   C | Source power | Domain power |
| ----------------------------- | --: | -----------: | -----------: |
| `repeat_v3`                   |   2 |          0,5 |            0 |
| `source_none`                 |   2 |            0 |            0 |
| `source_equal`                |   2 |            1 |            0 |
| `source_sqrt_domain_sqrt`     |   2 |          0,5 |          0,5 |
| `source_equal_domain_sqrt`    |   2 |            1 |          0,5 |
| `source_sqrt_domain_sqrt_c05` | 0,5 |          0,5 |          0,5 |

Bobot sumber adalah `(maksimum_jumlah_sumber / jumlah_sumber)^source_power`. Bobot domain adalah `frekuensi_domain^-domain_power`, dinormalisasi agar rata-rata bobot domain dalam masing-masing sumber bernilai satu. Hasil perkalian dinormalisasi lagi agar rata-rata bobot seluruh fit bernilai satu. Identitas sumber/domain tidak dimasukkan sebagai fitur prediksi.

Solver liblinear, random seed 20261101, max_iter 300, tol 0,0001. Kandidat yang tidak konvergen tidak boleh menang. Repeat v3 digunakan sebagai pemeriksaan reproduksi dan tetap dapat terpilih jika kandidat lain tidak lebih baik pada aturan validasi.

## Seleksi, kalibrasi, dan pembekuan

1. Fit classifier hanya pada fit. Transformasi tidak dipelajari ulang pada data lain.
2. Pada tune, tentukan operating point yang menjaga FPR empiris maksimal 1% pada setiap sumber. Pilih macro-source recall tertinggi, lalu minimum-source recall, lalu average precision gabungan. Aturan sama dengan v3; threshold tune bukan threshold deployment.
3. Satu kandidat pemenang dikalibrasi sigmoid hanya pada calibration. Kalibrator harus konvergen dan slope positif; jika tidak, hentikan, bukan mengubah aturan dari benchmark.
4. Pilih warning/HIGH pada threshold partition dengan target FPR empiris per sumber 1%/0,1%. Target ini belum merupakan jaminan atau batas atas statistik pada trafik nyata.
5. Simpan model, metadata, checksum, konfigurasi, hasil validasi, dan threshold sebelum evaluasi benchmark. Jangan refit pemenang pada gabungan semua partisi karena itu akan membatalkan kalibrasi dan evaluasi.

## Evaluasi dan batas klaim

Setelah pembekuan, bandingkan v3 dan v4 pada benchmark Phresh domain baru, group holdout Mendeley/PhishVN/PhiUSIIL, serta URL-Phish yang sudah pernah teramati. **Seluruhnya disebut benchmark teramati pada siklus v4, bukan final test independen baru.** Tidak ada sumber baru, gold set Indonesia, atau klaim generalisasi 2026 pada eksperimen ini.

Laporkan accuracy, balanced accuracy, precision, recall, FPR, F1, AP, Brier/log loss, jumlah kelas/domain, Wilson row-IID, dan interval delta berpasangan dengan bootstrap domain. Laporkan kedua threshold beserta HIGH yang tidak aktif bila tidak ada operating point yang memadai. Precision/calibration benchmark tidak mewakili prevalensi trafik.

Rata-rata lintas sumber hanya deskriptif. Semua regresi tetap ditampilkan. Tidak mengubah konfigurasi/threshold setelah membaca evaluasi; tidak melakukan promosi produksi otomatis, mengganti baseline, atau memilih ulang kandidat dari benchmark. Jika kandidat tidak membaik, catat hasil itu secara terbuka.

## Pengujian dan hubungan dengan gold set

- Periksa reproduksi prediksi mentah kandidat repeat v3 terhadap baseline pada tune.
- Verifikasi kesamaan fitur/probabilitas URL dan QR, input unsupported, serta HTTP/HTTPS pada representasi scheme-free.
- Verifikasi parity save/reload dan checksum model; pastikan baseline v3 tidak berubah.
- Jalankan seluruh cell notebook, pemeriksaan Ruff, format dokumen, dan audit agregat hasil nyata.

[Protokol gold set Indonesia](./indonesia-gold-set-plan.md) tetap berlaku untuk pengumpulan dan validasi Indonesia. Training pengembangan v4 ini dapat dikerjakan paralel secara proses; hasilnya tidak menyelesaikan kebutuhan anotasi, custodian, atau holdout baru pada protokol gold set.

## Catatan pra-training

Audit ulang seluruh 736.901 core pada cache v3 menemukan 0 perubahan core. Pada 1.534 baris, parser tetap menaikkan penghitung redaksi karena path sudah berisi placeholder `REDACTED`. Karena itu pemeriksaan idempotensi menggunakan kesamaan canonical core, bukan syarat penghitung redaksi nol. Koreksi dilakukan sebelum classifier pertama dilatih; protokol awal dan koreksi dicatat pada `preflight-repair.json`. Tidak ada baris, label, fitur, atau konfigurasi loss yang diubah. Pemeriksaan kandidat gold set juga menerima placeholder yang sudah stabil sambil tetap menahan path yang masih memerlukan sanitasi.

Rujukan implementasi: [`LogisticRegression.fit(..., sample_weight=...)`](https://scikit-learn.org/1.8/modules/generated/sklearn.linear_model.LogisticRegression.html) dan [pemisahan fit/transform untuk mencegah kebocoran](https://scikit-learn.org/1.8/common_pitfalls.html). Pemilihan formula bobot dan anggaran enam konfigurasi merupakan rancangan eksperimen proyek.

## Hasil aktual v4

Seleksi tetap menggunakan tune sesuai protokol. Macro-source recall pada operating point FPR maksimal 1% per sumber:

| Kandidat                      | Macro-source recall tune |
| ----------------------------- | -----------------------: |
| `repeat_v3`                   |                   44,14% |
| `source_none`                 |                   31,58% |
| `source_equal`                |                   39,51% |
| `source_sqrt_domain_sqrt`     |                   42,86% |
| `source_equal_domain_sqrt`    |                   40,51% |
| `source_sqrt_domain_sqrt_c05` |                   41,49% |

Enam proses fitting classifier memerlukan total sekitar 149,81 detik, di luar encoding, kalibrasi, dan evaluasi. Repeat v3 mereproduksi probabilitas mentah baseline pada tune dengan maksimum selisih absolut 0. Koefisien classifier terpilih identik dengan v3; kalibrator hanya berbeda pada skala pembulatan floating point sekitar 1,1e-16. Tidak menafsirkan perubahan byte joblib atau metadata versi sebagai perbaikan kemampuan model.

Evaluasi warning setelah pembekuan, seluruhnya pada benchmark yang sudah teramati:

| Benchmark              | Jumlah URL | Accuracy v3 | Accuracy v4 | Recall v4 | FPR v4 |
| ---------------------- | ---------: | ----------: | ----------: | --------: | -----: |
| Phresh domain baru     |     80.052 |      73,85% |      73,85% |    59,10% |  0,38% |
| Mendeley group holdout |      1.002 |      81,54% |      81,54% |    73,93% |  0,99% |
| PhishVN group holdout  |      2.123 |      93,45% |      93,45% |    49,14% |  1,11% |
| PhiUSIIL group holdout |     20.219 |      75,93% |      75,93% |    41,33% |  0,05% |
| URL-Phish              |     85.824 |      97,09% |      97,09% |    64,01% |  0,44% |

Rata-rata deskriptif lima accuracy tetap 84,37%; recall rata-rata 57,50% dan FPR rata-rata 0,5953%. Tidak ada penurunan atau peningkatan keputusan klasifikasi terhadap v3 pada sampel ini. Perbedaan probabilitas pada presisi floating point tidak dianggap peningkatan. URL-Phish memiliki dominasi benign dan bias sumber; angka 97,09% tidak boleh disajikan sebagai accuracy universal/Indonesia.

Notebook dijalankan penuh: 16 cell, 8 cell kode, tanpa error. Sembilan pemeriksaan akhir termasuk save/reload, URL/QR, HTTP/HTTPS, unsupported input, reproduksi baseline, serta baseline tidak berubah telah lolos. Hasil rinci, kedua threshold, ketidakpastian, konfigurasi, dan checksum tersedia pada [laporan agregat](../ml/reports/retraining-v4.json) dan [notebook](../guardian_lab_url_qr_retraining_v4.ipynb).

**Keputusan:** mempertahankan baseline v3. Variasi bobot yang dicoba tidak memperbaiki objective validasi; jangan menambah trial atau mengubah threshold dari hasil benchmark ini. Siklus berikutnya memerlukan hipotesis/protokol baru dan bukti data yang lebih baik. Kebutuhan gold set Indonesia tetap terbuka untuk klaim validasi Indonesia, sementara eksperimen development lain tetap diperbolehkan dengan batas klaim yang jujur.
