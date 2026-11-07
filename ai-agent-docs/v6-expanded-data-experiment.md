# Penggabungan dataset untuk kandidat turunan v6

Instruksi pengguna pada 5 November 2026 mengizinkan penambahan/penggabungan dataset publik dan eksperimen peningkatan model. Eksperimen ini melatih tiga Logistic Regression baru. Model layanan dan notebook utama tetap memakai frozen v6 asli; kandidat hanya untuk penelitian sampai syarat rilis terpenuhi.

[Protokol](../ml/reports/v6-expansion-20261105-protocol.json) ditetapkan sebelum training atau prediksi sumber tambahan. Daftar asset mengikat versi, ukuran dan checksum. Intake hanya memproses URL dan label; tidak mengunduh HTML atau menjalankan kode penerbit/target.

## Sumber dan tingkat bukti

- [CompPhish V4](https://data.mendeley.com/datasets/fmbs4kp9wz/4), 15.358 baris: hanya `Mapping_File.xlsx` yang diambil. Sumber menyebut phishing dari PhishTank/OpenPhish dan benign dari daftar DataForSEO. Label 0=legitimate/1=phishing. Scope beberapa kasus mengandung auto-download files; belum ada verifikasi phishing-vs-malware per kasus oleh proyek.
- [Dataset Wangchuk V1](https://data.mendeley.com/datasets/3jddhy2f6s/1), 149.726 baris: CSV berasal dari Common Crawl 2024 dan PhishTank. Mapping 0 benign/1 phishing dicocokkan dengan jumlah kelas yang ditulis penerbit, 94.919/54.807. Ini mapping skema berdasarkan bukti total kelas, bukan relabel kasus atau audit manusia baru.
- [PhishBD_2026 V2](https://data.mendeley.com/datasets/8d6zsfwc7z/2), 131.167 baris: URL+label saja dari CSV 75 kolom. Penerbit menyebut threat feeds/insiden Bangladesh serta benign dari ranking dan daftar regional. Label dan per-case provenance tetap bertingkat bukti penerbit; deskripsi proses mencakup penambahan benign untuk rasio kelas. Dataset ini bukan data Indonesia atau estimasi prevalensi trafik.

Ketiga sumber mencantumkan CC BY 4.0. Fondasi v6 tetap mengandung provenance nonkomersial sehingga kandidat gabungan tetap dibatasi riset nonkomersial. [PhiShark](https://phishark2026dataset.com/) memerlukan aplikasi akademik dan Data Use Agreement; tidak diambil, tidak ada formulir atau pesan ke pihak lain yang dikirim. Dataset Indonesia SABER/Telkom tetap belum tersedia sebagai rilis mentah publik yang ditemukan.

## Kurasi dan pembagian

Intake 296.251 baris menghasilkan 279.860 core tersanitasi dengan representasi eksperimen berversi. Guard menolak input unsupported. Redaksi tetap heuristik dan tidak membuktikan anonimisasi penuh; raw URL tidak dipersistensikan atau dikirim ke LLM.

Gabungan mengarantina 1.286 baris pada 10 representasi berlabel konflik, membuang 59.716 duplikat konsisten, mengecualikan 79.696 URL/domain yang pernah terpapar dan 20.843 baris melewati cap lima/domain. Tersisa 118.319 URL baru. Kurasi tidak memakai skor model atau mengganti label.

Audit exposure membaca registry historis, seluruh sidecar dan cache v6. Domain/private tenant baru dibagi deterministik dengan salt protokol: 60% bucket fit, 15% tune, 7% calibration, 8% threshold dan 10% test. Pembagian bucket tidak menjamin jumlah kelas persis pada setiap partisi. Holdout baru hanya berasal dari domain yang tidak muncul dalam paparan lama, dan tetap berbagi sumber penerbit dengan data tambahan development.

Fondasi mempertahankan empat partisi v6; hanya fit mengalami kurasi konflik/duplikat seperti eksperimen terdahulu. Representasi baru diterapkan seragam tanpa fitting pada holdout. Fitting gabungan berisi 595.934 URL dari delapan sumber. Tune 101.816; calibration 48.297; threshold 56.146; new domain holdout 11.636 (8.393 phishing, 3.243 benign).

Semua intake baru dicatat dalam sidecar lokal, termasuk kasus yang dikeluarkan dan holdout yang dicadangkan. [Manifest exposure](../ml/provenance/v6-expanded-data-exposure.json) mempertahankan paparan ini untuk audit berikutnya. Registry historis tidak dihapus atau ditimpa.

Hasil aktual: kandidat `expanded_domain_C2` dipilih hanya dari tune. Pada holdout baru yang sama, recall meningkat 29,86% ke 38,25% dan FPR turun 2,53% ke 0,40%. Tetapi recall vendor lama menurun 46,31% ke 31,48%, PhishTank 46,53% ke 35,92%, dan LegitPhish 66,01% ke 42,45%. Kandidat belum memperbaiki kemampuan menyeluruh atau mencapai target recall; tidak dipromosikan menggantikan layanan v6. Perbandingan kontrol development tambahan tetap dipisahkan dari hasil policy asli.

## Training dan evaluasi

Encoder TF-IDF karakter (2–5, maksimal 150.000 fitur) dan kata (1–2, maksimal 30.000), serta scaler numerik hanya di-fit pada fitting. Sampel vocabulary maksimal 60.000/sumber dan 180.000 total. Bobot word/numeric tetap 0,7/0,2, scheme dikeluarkan. Source ID bukan fitur classifier.

Tiga kandidat yang ditetapkan sebelum training adalah C=2 dan C=8 dengan bobot sumber akar kuadrat, serta C=2 dengan tambahan pembobotan domain. Solver liblinear, max_iter=300. Pemilihan hanya memakai macro recall sumber pada tune dengan constraint FPR empiris 1% per sumber yang memiliki setidaknya 100 benign. Sumber yang terlalu kecil/positif saja tetap dilaporkan dan tidak diberi FPR fiktif. Tie-break minimum source recall lalu AP.

Syarat peningkatan development: macro recall naik setidaknya 2 percentage point dibanding kontrol frozen v6 pada tune yang sama, tanpa penurunan recall sumber yang didukung >5 point. Bila syarat tidak terpenuhi, kandidat terbaik tetap diperiksa sebagai eksplorasi gagal-gate; tidak otomatis dipromosikan.

Kalibrasi sigmoid kandidat terpilih hanya pada calibration dengan slope positif. Threshold warning/HIGH dipilih hanya pada threshold dengan budget FPR empiris per sumber 1%/0,1%. Keputusan seleksi, artifact, source hashes dan threshold dibekukan sebelum scoring holdout baru maupun benchmark vendor, PhishTank dan LegitPhish yang sudah teramati.

[Hasil lengkap](../ml/reports/v6-expanded-data-evaluation.md), [JSON](../ml/reports/v6-expanded-data-evaluation.json), dan [grafik](../ml/reports/v6-expanded-data-evaluation.png) memuat perbandingan pada cohort yang sama, regresi, confidence intervals serta kalibrasi. Benchmark yang sudah teramati tidak menjadi independen kembali. Domain-disjointness belum membuktikan campaign/time independence, kebenaran label atau gold Indonesia.

Analisis tambahan [kontrol FPR development yang sama](../ml/reports/v6-expanded-matched-control-protocol.json) ditetapkan setelah hasil tune kandidat pertama tersedia, sebelum ada prediksi final test. Threshold kontrol v6 dipilih hanya pada partisi threshold gabungan dan dibekukan di run lokal; classifier/encoder/kalibrator serta policy layanan v6 asli tetap sama. Ini tambahan yang dideklarasikan terlambat, bukan bagian dari protokol awal. Tidak mengubah pemilihan kandidat. Hasil [kontrol tambahan](../ml/reports/v6-expanded-matched-control.json) dilaporkan terpisah dari perbandingan primary terhadap v6 dengan policy asli.

## Reproduksi lokal

Pasang extra `expansion` dengan environment proyek yang tetap memakai dependency inference v6 asli. Data, registry, sidecar dan artifact tetap diabaikan Git. Dataset tidak diunggah atau dipublikasikan oleh pengerjaan ini.

```powershell
ml/.venv/Scripts/python.exe -m pip install -e "./ml[expansion]"
ml/.venv/Scripts/python.exe scripts/intake_v6_expansion.py
ml/.venv/Scripts/python.exe scripts/experiment_v6_expanded_data.py --stage prepare
ml/.venv/Scripts/python.exe scripts/experiment_v6_expanded_data.py --stage train
ml/.venv/Scripts/python.exe scripts/experiment_v6_expanded_data.py --stage evaluate
ml/.venv/Scripts/python.exe scripts/plot_v6_expansion.py
ml/.venv/Scripts/python.exe scripts/format_v6_expansion_report.py
```

Direktori run yang sudah dibekukan/report selesai ditolak untuk overwrite. Perintah prepare bukan replay dari data yang kembali dianggap baru: sidecar lama harus tetap diperhitungkan. Untuk reproduksi penelitian baru, gunakan identitas run/protokol dan manifest exposure yang eksplisit; jangan menghapus exposure agar test tampak belum pernah dilihat.
