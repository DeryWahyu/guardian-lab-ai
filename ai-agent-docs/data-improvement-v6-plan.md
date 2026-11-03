# Protokol v6 — Perbaikan Data dan Holdout Baru URL/QR

> Tanggal: 1 November 2026. Ditulis sebelum kurasi, fitting, dan scoring v6. Model tetap satu Logistic Regression.

## Masalah yang dibuktikan v5

Enam variasi fitur tidak mengalahkan baseline. Pada data baru DeepURLBench, baseline mencatat recall 52,79% dengan FPR 5,41%; pada audit manusia tertangkap 9/22 phishing. Ini menunjukkan keterbatasan generalisasi data development lama. Tidak menaikkan klaim dari accuracy 89,82% yang didominasi benign.

Hipotesis v6: perlu memperluas contoh phishing/benign yang didokumentasikan sumbernya, terutama benign sulit, daripada terus mengubah bobot/fitur pada korpus yang sama. Semua test v5 dipertahankan sebagai benchmark teramati dan tidak dipakai melatih/menentukan threshold.

## Data pengembangan tambahan dan pemisahan

1. Gunakan delapan shard DeepURLBench yang sama dan dipin v5, dengan URL/label saja. Label vendor adalah heuristic terdokumentasi; tidak disebut human gold. Lisensi CC BY-NC 4.0: penggunaan riset nonkomersial.
2. Sanitasi di memori dan persist hanya core/hash/group/label/provenance aman. Malware/unsupported/konflik canonical ditahan sebelum prediksi. Tidak membuka target, HTML, DNS, atau mengirim baris dataset ke LLM.
3. Keluarkan semua URL/domain/tenant dari registry v1–v4, test DeepURLBench v5, audit manusia v5, serta seluruh domain PhishTank yang akan direservasi untuk pengujian v6.
4. Domain tambahan diberi bucket deterministik `sha256('v6-domain:' + group) mod 100`: fit <60; tune <75; calibration <82; threshold <90; holdout baru sisanya. Group tidak melintasi partisi. Campaign overlap yang belum diketahui tetap batas audit.
5. Deduplikasi canonical dan batasi maksimal 5 URL per group menurut digest. Ambil digest terkecil per partisi dengan batas fit 100.000, tune 20.000, calibration 10.000, threshold 15.000, holdout 20.000. Sampling tidak memakai skor model atau menyeimbangkan label.
6. Gabungkan hanya empat partisi development dengan development lama; test v5/human/holdout baru tidak ikut fitting/kalibrasi/threshold. Laporkan hitungan kelas/domain dan checksum aktual tiap partisi.

Holdout DeepURLBench v6 adalah domain baru pada **sumber yang kini sudah dipakai mengembangkan model**, bukan independent-source benchmark. Waktu first_seen historis bukan bukti ancaman baru 2026.

## Data phishing terkini dengan verifikasi komunitas

Ambil satu snapshot publik `online-valid.csv.gz` PhishTank memakai User-Agent deskriptif. [Dokumentasi resmi](https://phishtank.org/developer_info.php) menyatakan feed berisi URL yang diverifikasi komunitas; [FAQ](https://phishtank.org/faq.php) menjelaskan prosesnya. Akses publik tanpa key dibatasi beberapa unduhan per hari; tidak mengakali pembatasan atau membuat akun.

Syarat: `verified=yes`, `online=yes`, submission dan verification bertimezone dari 1 Januari 2026 sampai waktu snapshot. Ini waktu pelaporan/verifikasi, bukan tanggal pembuatan URL dan bukan verifikasi langsung oleh agent. Sanitasi segera; keluarkan overlap seluruh data lama/test v5, canonical duplicates, batasi 5 URL per domain dan maksimal 10.000 digest terkecil. Jangan menyimpan raw feed atau data korban.

Reservasi domain PhishTank dilakukan sebelum memilih development DeepURLBench agar tidak melintasi fit/test. Tidak memasukkan feed ke training. URL komunitas tetap bisa salah label; bukti per kasus dan tinjauan Indonesia belum dibuat oleh tim proyek.

Feed hanya positif: laporkan TP/FN, recall, dukungan domain, Wilson/bootstrap recall. **FPR, precision trafik, dan accuracy binary tidak dapat ditentukan dari feed positif saja** dan harus ditampilkan tidak tersedia. False alarm diukur terpisah pada benign holdout DeepURLBench baru dengan keterbatasan label vendornya.

## Satu model dan konfigurasi sebelum fitting

Satu classifier baru: Logistic Regression liblinear, C=2, max_iter=300, tol=0,0001, seed 20261101. C=2 dipertahankan dari konfigurasi baseline yang menang pada validasi sebelumnya; tidak ada trial tambahan atau ensemble. Bandingkan dengan baseline beku, tanpa memilih dari skor test.

Fit vocabulary/scaler ulang hanya pada fit campuran: rich char TF-IDF (2,5), max_features=100.000, min_df=4, sublinear_tf; word TF-IDF (1,2), maksimal 20.000, min_df=4; numeric scheme-free sama dengan v3. Bobot word 0,7/numeric 0,2. Sampling vocabulary maksimal 60.000 per sumber dan 150.000 total. Rasio source weighting akar ukuran sumber dinormalisasi mean satu, seperti baseline. Source ID bukan fitur.

Data tune digunakan untuk diagnostik dengan FPR per sumber 1%; tidak memilih konfigurasi lain. Kalibrasi sigmoid hanya pada calibration; wajib konvergen dan slope positif. Threshold warning/HIGH dipilih hanya pada threshold partition dengan FPR empiris per sumber 1%/0,1%. Semua model, metadata, checksum, serta threshold dibekukan sebelum test.

## Evaluasi dan kriteria bukti

- Uji berpasangan baseline vs v6 pada holdout domain DeepURLBench baru dan PhishTank 2026 yang dipisahkan sebelum fitting.
- Laporkan recall/FPR beserta interval, counts, domain/tenant, coverage/rejection, label provenance; tambahkan accuracy/balanced accuracy/AP/Brier pada test binary. Feed positif dilaporkan sebagai sensitivity test terpisah.
- Peningkatan harus memperlihatkan recall membaik dan false alarm rendah pada bukti yang sesuai. Target FPR 1%/recall 85% tetap target, bukan hasil. Interval yang tidak mendukung berarti belum meyakinkan. Perbandingan dua distribusi sumber/tahun bukan estimasi trafik gabungan.
- Benchmark v5 serta audit manusia boleh dibandingkan ulang sebagai **teramati**, tanpa memilih threshold ulang dari hasilnya. Laporkan regresi, termasuk yang tertutup rata-rata.
- Simpan baseline v3–v5 tanpa perubahan. Tidak melakukan promosi produksi otomatis atau menyatakan validasi Indonesia selesai.

## Deliverable dan audit

Notebook v6, run terisolasi `ml/runs/notebook-tfidf-logistic-v6/`, manifest sumber/partisi/test sebelum fitting, bobot dan threshold beku, laporan agregat tanpa URL target, pemeriksaan source/partition leakage, URL/QR/HTTP-HTTPS parity, save/reload, unsupported input, serta checksum baseline. Jika akses feed gagal, catat alasan dan jangan mengarang data terkini atau label manusia.

## Kontrol tambahan untuk perbandingan batas false alarm yang sama

Diagnostik tune lima sumber menunjukkan baseline hanya mencapai macro recall 20,50% pada FPR 1% per sumber, sedangkan model baru 43,67%. Kebijakan threshold asli baseline ditentukan pada empat sumber lama; perbandingan tambahan diperlukan agar kemampuan pada batas false alarm yang sama dapat dinilai.

Tambahan ini ditetapkan setelah model v6 dibekukan dan evaluasi utama dijalankan, sebelum hasil test v6 dibaca untuk menetapkan kontrol. Baseline asli tetap dilaporkan. Kontrol memakai classifier/encoder/kalibrator v3 yang sama tanpa fitting ulang; hanya threshold referensi ditentukan dari **threshold partition v6**, dengan FPR 1%/0,1% per sumber yang sama. Threshold kontrol dibekukan sebelum scoring kontrol. Test tidak dipakai memilihnya, dan threshold model v6 tidak berubah.

Laporkan baseline asli, baseline dengan threshold kontrol development, dan model v6 secara terpisah. Ini analisis tambahan yang dideklarasikan terlambat, bukan bagian dari preregistrasi awal. Hasil tidak dipakai memilih model/policy produksi. Semua perbaikan maupun trade-off tetap ditampilkan, bersama interval dan provenance label.

## Hasil aktual dan keputusan v6

Training selesai: **532.793 URL fitting** dari lima sumber, satu classifier Logistic Regression C=2 yang konvergen. Tune 84.000, calibration 40.104, threshold 46.707 dipisahkan berdasarkan domain. Semua 12 pemeriksaan akhir lolos; notebook model memuat 18 cell / 9 cell kode yang dieksekusi tanpa error.

### Kebijakan asli baseline dibanding model baru

| Benchmark                        |    URL | Recall v3 | Recall v6 | FPR v3 | FPR v6 |
| -------------------------------- | -----: | --------: | --------: | -----: | -----: |
| DeepURLBench domain holdout baru | 20,000 |    53,51% |    46,31% |  5,23% |  0,94% |
| DeepURLBench test v5 (teramati)  | 50,000 |    52,79% |    45,58% |  5,41% |  1,03% |
| Audit manusia v5 (teramati)      |     33 |    40,91% |    18,18% |  0,00% |  0,00% |
| Phresh domain baru (teramati)    | 80,052 |    59,10% |    43,10% |  0,38% |  0,16% |
| Mendeley (teramati)              |  1,002 |    73,93% |    70,34% |  0,99% |  0,33% |
| PhishVN (teramati)               |  2,123 |    49,14% |    39,66% |  1,11% |  0,42% |
| PhiUSIIL (teramati)              | 20,219 |    41,33% |    35,84% |  0,05% |  0,03% |
| URL-Phish (teramati)             | 85,824 |    64,01% |    55,39% |  0,44% |  0,09% |

Pada PhishTank 2026 yang baru, recall baseline asli 55,48% (5142/9269) dan v6 46,53% (4313/9269). Feed hanya positif: FPR tidak tersedia. **Recall mentah menurun**, sedangkan false alarm pada kontrol vendor turun dari 5,23% menjadi 0,94%. Tidak menyebutnya peningkatan menyeluruh.

Audit manusia kecil juga menurun dari 9/22 menjadi 4/22 phishing tertangkap; 11 benign tetap tanpa false positive. Data manusia ini telah teramati dan terlalu kecil untuk membuktikan FPR rendah. Regresi pada Phresh serta sumber lain tetap terbuka di tabel dan laporan.

### Kontrol tambahan pada target false alarm development yang sama

Kontrol berikut ditetapkan terlambat sebagaimana dijelaskan pada bagian sebelumnya. Threshold baseline kontrol dipilih hanya pada threshold partition v6, lalu dibekukan sebelum prediksi kontrol; tidak ada fitting, model selection, atau threshold v6 yang diubah. Baseline asli tetap tersedia di atas.

| Referensi warning                          | Recall holdout vendor | FPR holdout vendor | Recall PhishTank 2026 |
| ------------------------------------------ | --------------------: | -----------------: | --------------------: |
| Baseline v3 asli                           |                53,51% |              5,23% |                55,48% |
| Baseline v3, threshold kontrol development |                19,27% |              1,01% |                26,59% |
| Model v6                                   |                46,31% |              0,94% |                46,53% |

Pada operasi false alarm sekitar 1%, peningkatan recall v6 terhadap baseline kontrol adalah **27,05 percentage point pada holdout vendor** dan **19,94 percentage point pada PhishTank 2026**. Bootstrap domain berpasangan memberi interval 95% delta recall masing-masing sekitar [24,89; 29,36] dan [19,02; 20,66] percentage point. Selisih FPR terhadap baseline kontrol tidak berbeda meyakinkan dari nol; keduanya sekitar 1%.

**Batas bukti:** FPR v6 168/17.789 = 0,9444%, dengan Wilson 95% row-IID sekitar [0,8125%; 1,0975%]. Interval melintasi 1%, sehingga belum membuktikan jaminan FPR di bawah 1%. Domain/campaign correlation dan kesalahan label vendor tetap dapat memperlemah bukti. Sensitivity pada feed komunitas dan FPR pada benign historis adalah dua distribusi berbeda; jangan menggabungkannya menjadi accuracy atau precision trafik.

**Keputusan:** v6 adalah kandidat riset yang memperbaiki kemampuan pada batas false alarm rendah dibanding baseline kontrol. Ia tidak menggantikan baseline secara otomatis karena recall mentah serta audit manusia memburuk dan target recall 85% belum tercapai. Tidak ada promosi produksi atau klaim gold set Indonesia. Peningkatan keandalan menyeluruh tetap memerlukan evaluasi/label lokal dan sumber benign kontemporer yang lebih kuat.

Bukti: [notebook model v6](../guardian_lab_url_qr_v6.ipynb), snapshot lokal notebook kontrol historis (lihat [cleanup](v6-only-cleanup.md)), [laporan utama](../ml/reports/data-improvement-v6.json), [laporan kontrol tambahan](../ml/reports/v6-low-fpr-control.json). Dataset tersanitasi berada lokal pada `ml/runs/notebook-tfidf-logistic-v6/data/`; raw feed dan URL ber-PII tidak disimpan.


## Cleanup 3 November 2026

Notebook utama kini hanya memuat/memeriksa v6; kode training asli tetap byte-identik dalam snapshot lokal. Model lain dihapus atas instruksi pengguna. Protokol/hasil historis di atas tetap berlaku dan tidak menyatakan training ulang atau readiness baru.
