# Eksperimen pembobotan dan audit label setelah sembilan sumber

Instruksi pengguna pada 5 November 2026 mengizinkan audit kesalahan, eksperimen pembobotan domain/sumber, perbaikan kalibrasi dan pencarian bukti validasi tambahan. Pekerjaan tetap terisolasi dari layanan/notebook utama frozen v6. Tidak ada promosi produksi atau perubahan binary, metadata, threshold, dependensi inference maupun PSL runtime asli.

## Desain sebelum fitting

[Protokol](../ml/reports/v6-weighted-20261105-protocol.json) ditetapkan sebelum fitting kandidat baru. Semua classifier tetap Logistic Regression C=2/liblinear, memakai 616.050 URL fitting yang sama dari sembilan sumber dan encoder milik kandidat riset sebelumnya. SHA-256 artifact encoder/control `79e313b2deebd1bb0eff4c7cc28f8ca0694daa5e5aafabff8a47e4cccc65c025` mengikat vocabulary dan scaler yang sudah di-fit hanya pada fitting tersebut.

Encoder tidak di-fit ulang pada holdout. Matriks fitur disimpan lokal dengan checksum dan urutan baris terikat checksum tabel sumber. Fit/calibration mempertahankan representasi fitting sebelumnya; tune/threshold menggunakan sanitizer inference eksperimen yang sama dengan `predict_bundle`. Cache harus cocok dengan inferensi artifact nyata dan confusion counts control pada keseluruhan tune. Pemakaian ulang ini mengisolasi efek bobot sekaligus mengurangi pengulangan transformasi fitur.

Tiga bobot classifier yang diuji:

1. Bobot akar ukuran sumber sebelumnya, dibagi akar jumlah baris per domain.
2. Inverse akar jumlah baris per domain, dinormalisasi agar total bobot setiap sumber sama.
3. Bobot nomor 1 dengan koreksi akar imbalance kelas di dalam setiap sumber.

Semua bobot dinormalisasi mean satu dan tidak mengubah label. Setiap classifier mendapat sigmoid calibration biasa dan sigmoid dengan total bobot sama per sumber, di-fit hanya pada calibration. Varian kalibrasi kedua juga diperiksa pada classifier control tanpa fitting classifier/encoder ulang. Kalibrator harus mempertahankan ranking dengan slope positif; perubahan kalibrasi sendiri tidak disebut peningkatan kemampuan membedakan phishing.

Threshold utama ditentukan hanya pada threshold partition, dengan FPR empiris 1% per sumber yang memiliki minimal 100 benign. Kebijakan pooled 1% dilaporkan terpisah; budget development tidak menjamin FPR test atau per sumber. Kasus Wangchuk yang hanya memiliki 108 benign di threshold tetap dilaporkan dengan keterbatasan ketidakpastian, tidak dihapus agar hasil terlihat lebih baik.

Seleksi memakai tune saja: gate peningkatan recall membutuhkan macro recall naik minimal 2 percentage point, tanpa penurunan recall sumber >5 point dan tanpa kenaikan macro Brier >0,01. Gate kalibrasi membutuhkan macro Brier turun minimal 0,005, macro/source recall tidak turun >0,005 dan Brier sumber tidak naik >0,02. Jika tidak ada yang lolos, control dipertahankan. Challenger gagal-gate yang diperiksa untuk diagnosis harus dibekukan sebelum test; hasil test tidak mengubah pilihan.

## Audit development dan review manusia

Audit menghitung confusion counts per sumber dan struktur URL, konflik label penerbit pada representasi yang sama, serta kalibrasi. Antrean error development disimpan lokal sebagai locator hash: coordinator mengetahui kategori error dan label penerbit, sementara dua pack blind tidak memuat URL, skor model atau label penerbit. Semua kolom reviewer tetap kosong. Sampling error development tidak dipakai membentuk final gold set.

Ini audit konsistensi dan kesalahan relatif label penerbit, bukan verifikasi kebenaran label oleh manusia. Tidak ada reviewer, adjudikasi, label Indonesia atau perubahan label otomatis yang dibuat. Input gold Indonesia yang sebenarnya tetap diperiksa; jumlah baris saja tidak membuktikan dua reviewer independen atau ground truth valid.

## Holdout penerbit baru

Sumber tambahan adalah [Phishing and Legitimate Websites Dataset V2](https://zenodo.org/records/23477065), publikasi 19 Oktober 2026, CC BY 4.0. Penerbit menyebut 60.000 URL, 31.641 phishing dari PhishTank dan 28.359 legitimate dari Tranco. Tanggal observasi tiap URL tidak tersedia pada tabel terpilih; tanggal publikasi tidak dianggap waktu ancaman atau bukti benign kontemporer. Dataset global ini bukan gold Indonesia atau verifikasi manusia independen per kasus.

Arsip berukuran 4.476.190.126 byte juga memuat gambar yang tidak diperlukan. Reader ZIP64 memakai HTTP Range HTTPS ke Zenodo saja, menolak respons HTTP 200 penuh, membatasi ukuran, memeriksa Content-Range/CRC dan SHA-256 member, serta tidak mengekstrak atau menjalankan file. Hanya indeks ZIP dan `Phishing dataset/url/merged_features_final.csv` diambil: 5.104.259 byte per intake. SHA-256 CSV `83bca273fd7f3a778d3c83f0cba2085998231c258081c37253f9f2f56adf06ac` dipin sebelum parsing baris/prediksi. MD5 seluruh arsip milik penerbit dicatat tetapi **tidak dihitung ulang**, karena seluruh arsip tidak diunduh.

[Protokol intake asli](../ml/reports/v6-weighted-holdout-intake-protocol.json) dipertahankan. Pemeriksaan awal berhenti karena label bukan angka. [Inspeksi skema](../ml/reports/v6-weighted-holdout-schema-inspection.json) menemukan label literal `legitimate`/`phishing`, tanpa unknown/missing, dengan jumlah tepat sesuai penerbit. [Amendemen sebelum prediksi/fitting](../ml/reports/v6-weighted-holdout-intake-amended.json) menetapkan mapping project 0/1 sesuai arti label tersebut. Ini normalisasi skema, bukan relabel kasus atau klaim verifikasi manusia.

Dari 60.000 baris, 57.040 lolos sanitasi. Kurasi mengarantina 30 baris pada lima representasi konflik, mengeluarkan 6.124 duplikat, 38.296 paparan URL/domain lama dan tiga baris melewati cap domain. Tersisa **12.587 URL baru: 9.643 benign dan 2.944 phishing, pada 11.401 domain/tenant**. Semuanya dicadangkan untuk pengujian eksternal; tidak masuk fitting, tune, calibration atau threshold.

Intake mengaudit registry historis, seluruh sidecar dan cache v6 sebelum menulis sidecar baru. [Pointer exposure](../ml/provenance/zenodo-websites-v2-exposure.json) mengikat seluruh intake tersanitasi, termasuk kasus yang dikeluarkan serta holdout. Audit identitas nyata memeriksa holdout baru terhadap seluruh partisi development dan benchmark teramati sebelum fitting classifier baru. Disjoint domain/digest/representasi tidak membuktikan independent campaigns atau kebenaran label penerbit.

## Status validasi Indonesia

Pencarian kembali sumber publik Indonesia tetap menemukan [katalog dataset Telkom](https://btp.telkomuniversity.ac.id/landing/ip/HCNA2602260302), [tesis IndoPhis-D](https://repositori.telkomuniversity.ac.id/pustaka/245173/adaptive-rule-based-detection-of-indonesian-phishing-website-through-multi-layered-filtering-based-on-url-features-dalam-bentuk-buku-karya-ilmiah.html) dan [SABER](https://jurnal.stikes-ibnusina.ac.id/index.php/SABER/article/view/3904). Tidak ada rilis raw publik lengkap dengan hak penggunaan dan bukti review per kasus yang berhasil diperoleh. Tidak ada formulir akses, akun atau kontak kepada pihak lain yang dilakukan. Data email sintetis atau fitur tanpa URL tidak dipindahkan menjadi label phishing URL Indonesia.

Target validasi Indonesia tetap minimal 1.000 phishing, 3.000 benign dan dua reviewer manusia independen dengan QA relevansi, privasi, hak, waktu/kampanye serta holdout terkunci. Jumlah kelas holdout global yang mencukupi tidak memenuhi persyaratan geografis, periode atau review tersebut. Layanan tetap shadow, production_ready=false dan LOW bukan SAFE.

## Hasil yang diperoleh

Varian terpilih adalah `source_equal_domain_sqrt__source_equal_sigmoid`: pembobotan domain dengan total bobot sama per sumber dan sigmoid calibration berbobot sumber. Macro source recall tune naik dari control riset 45,74% menjadi 50,09%, tanpa penurunan recall sumber pada angka titik; macro Brier turun dari 0,094476 menjadi 0,091928. Pemilihan dibekukan sebelum scoring holdout baru.

Pada 12.587 URL holdout penerbit baru, kandidat memperoleh TP 1.671, FN 1.273, FP 40 dan TN 9.603: recall 56,76%, FPR 0,415% dan precision sampel 97,66%. Control riset sebelumnya memperoleh recall 52,79% dan FPR 0,446%; v6 aktif 52,58% dan 0,881%. Bootstrap domain berpasangan 95% untuk kenaikan recall terhadap control adalah 3,15–4,80 percentage point. Interval selisih FPR terhadap control mencakup nol, sehingga tiga FP lebih sedikit bukan bukti kuat penurunan FPR.

Recall angka titik meningkat pada seluruh enam cohort yang diperiksa, tetapi hasil bukan peningkatan menyeluruh. FPR vendor meningkat dari control 0,635% menjadi 0,899%, dengan Brier 0,098732 menjadi 0,106149 dan ECE 0,168058 menjadi 0,174878. FPR PWD/expanded serta beberapa kelompok struktur development juga naik. Hasil PhishTank positif saja tidak menyediakan FPR atau precision trafik; 28 benign LegitPhish tetap terlalu sedikit untuk memastikan FPR rendah. Benchmark selain holdout penerbit baru sudah pernah teramati.

[Laporan lengkap](../ml/reports/v6-weighted-evaluation.md), [JSON](../ml/reports/v6-weighted-evaluation.json), [grafik](../ml/reports/v6-weighted-evaluation.png), [audit development](../ml/reports/v6-weighted-development-audit.md) dan [verifikasi](../ml/reports/v6-weighted-verification.json) mencatat hasil serta keterbatasan. Seluruh 158 tes lulus tanpa kegagalan, error atau skip; 130 probe saved-model/cache memiliki delta nol. SHA binary dan metadata v6 aktif tetap sama. Antrean review 170 kasus tersedia lokal, dengan nol review selesai. Gold Indonesia, verifikasi manusia dan kesiapan produksi belum terbentuk.

## Reproduksi

Gunakan environment lokal yang tetap cocok dengan dependency inference v6 asli. Data, sparse matrix, exposure, reviewer packs dan semua artifact baru diabaikan Git.

```powershell
ml/.venv/Scripts/python.exe scripts/intake_v6_weighted_holdout.py
ml/.venv/Scripts/python.exe scripts/experiment_v6_weighted.py --stage prepare
ml/.venv/Scripts/python.exe scripts/verify_v6_weighted.py --stage preflight
ml/.venv/Scripts/python.exe scripts/render_v6_weighted.py --stage audit
ml/.venv/Scripts/python.exe scripts/experiment_v6_weighted.py --stage train
ml/.venv/Scripts/python.exe scripts/render_v6_weighted.py --stage subgroup
ml/.venv/Scripts/python.exe scripts/experiment_v6_weighted.py --stage evaluate
ml/.venv/Scripts/python.exe -m pytest -p no:cacheprovider ml/tests -q --junitxml=ml/runs/v6-weighted-20261105/final-tests.xml
ml/.venv/Scripts/python.exe scripts/render_v6_weighted.py --stage results
ml/.venv/Scripts/python.exe scripts/verify_v6_weighted.py --stage final
```

Run/intake yang sudah dibekukan menolak overwrite. Reproduksi penelitian berikutnya harus memakai identitas baru dan tetap menghitung seluruh exposure; jangan menghapus sidecar untuk mengklaim test baru.
