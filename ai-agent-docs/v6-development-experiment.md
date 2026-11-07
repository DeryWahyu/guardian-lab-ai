# Eksperimen pengembangan dari v6

Instruksi pengguna 5 November 2026 mengizinkan eksperimen pengembangan. Model layanan, notebook utama, binary, metadata training, dan threshold frozen v6 tetap utuh. Eksperimen baru memakai Logistic Regression; implementasi model lama yang dihapus tidak dipulihkan.

## Pertanyaan eksperimen

Apakah sanitasi path berversi dan kurasi fitting, penyeimbangan kelas per sumber, atau pembobotan kasus sulit dapat meningkatkan recall pada batas false positive yang sama? Protokol ditulis sebelum fitting kandidat dan scoring benchmark di [v6-development-experiment-protocol.json](../ml/reports/v6-development-experiment-protocol.json).

Tiga kandidat memakai satu encoder baru yang di-fit hanya pada partisi fitting. Recipe fitur tetap TF-IDF karakter/kata dan fitur numerik scheme-free v6. Semua classifier menggunakan Logistic Regression liblinear C=2; variasi hanya bobot fitting setelah perubahan sanitasi/kurasi bersama:

1. `privacy_retrain`: bobot sumber akar kuadrat seperti recipe v6.
2. `source_class_balance`: tambahan bobot agar massa kedua kelas seimbang di dalam masing-masing sumber.
3. `hard_segments`: bobot dua kali untuk phishing dengan URL scheme-free >120 karakter dan benign pada private hosting, berdasarkan label sumber di fitting.

Sanitizer eksperimen meredaksi nilai secret pendek pada assignment path, termasuk key terenkode. Ini versi representasi baru dan tetap heuristik. Parser runtime v6 tidak diganti. Tidak ada URL target yang dikunjungi, HTML dieksekusi, atau baris dataset dikirim ke LLM. Tidak dibuat salinan dataset URL baru.

Konflik label pada representasi fitting dikarantina tanpa relabel. Duplikat fitting dengan label konsisten ditentukan berdasarkan digest terkecil. Label tune/benchmark tidak digunakan untuk memutuskan curation fitting. Partisi lain tetap lengkap, sehingga kasus sulit tidak dihilangkan dari evaluasi.

## Pemisahan dan pemilihan

Pembagian domain/private tenant asli tetap dipakai: fit, tune, calibration, threshold. Guard memeriksa hash cache dan overlap domain, digest, serta representasi development. Benchmark dicek identitasnya sebelum training tanpa memuat label untuk seleksi.

Pemilihan kandidat hanya memakai tune: macro recall per sumber pada batas FPR empiris 1% per sumber, lalu minimum source recall dan AP sebagai tie-break. Syarat peningkatan development adalah kenaikan macro recall minimal 2 percentage point dibanding kontrol v6 pada tune, tanpa penurunan recall sumber lebih dari 5 percentage point. Bila tidak ada yang memenuhi, kandidat development terbaik tetap dievaluasi sebagai eksplorasi yang gagal memenuhi syarat; tidak menjadi model aktif.

Kalibrator sigmoid di-fit hanya pada calibration, dengan slope positif. Threshold warning/HIGH dipilih hanya pada threshold, dengan batas FPR empiris per sumber 1%/0,1%. Batas empiris bukan jaminan FPR populasi. Artifact, source hashes, protokol, keputusan seleksi dan threshold dibekukan sebelum scoring benchmark.

## Evaluasi dan reproduksi

[Hasil eksperimen](../ml/reports/v6-development-experiment.md), [JSON lengkap](../ml/reports/v6-development-experiment.json), dan [grafik](../ml/reports/v6-development-experiment.png) membandingkan kandidat terpilih dengan v6 asli pada 20.000 URL DeepURLBench dan 9.269 positif PhishTank. Keduanya sudah pernah teramati. Benchmark tidak digunakan memilih ulang model atau threshold.

Hasil aktual: `hard_segments` terpilih dari tune, tetapi macro recall hanya naik dari 43,67% ke 44,52%, belum memenuhi syarat kenaikan 2 percentage point. Pada vendor, recall turun 46,31% ke 45,91% dan FPR naik 0,944% ke 0,978%; interval delta mencakup nol. Pada feed positif, recall 46,53% ke 46,49%. Tidak ada bukti peningkatan menyeluruh, sehingga v6 tetap aktif. Model eksperimen tersimpan di `ml/runs/v6-development-20261105-run1/selected-candidate.joblib`.

Laporan mencakup counts, precision, recall, FPR, calibration, Wilson, domain bootstrap, interval delta berpasangan, serta slice URL panjang/private hosting/punycode. Data positif saja tidak menyediakan FPR, precision trafik, atau accuracy biner. Sumber label, ketergantungan kampanye yang belum diaudit, paparan development sebelumnya, serta belum adanya gold Indonesia tetap membatasi kesimpulan.

Dengan environment proyek, extra `quality`, dan cache lokal v6:

```powershell
ml/.venv/Scripts/python.exe scripts/experiment_v6_development.py --run-dir ml/runs/v6-development-replay --output-stem ml/reports/v6-development-replay
```

Gunakan direktori/output baru untuk setiap replay; runner menolak overwrite. Jika development selesai tetapi benchmark belum dijalankan, lanjutkan direktori yang sama dengan `--stage benchmark`; source, protokol dan artifact harus cocok dengan hash pembekuan.

Model kandidat hanya disimpan di direktori `ml/runs/` yang diabaikan Git. Loader API v6 tetap hanya menerima manifest/binary v6 asli. Registry exposure asli berada di `ml/data/indonesia-gold/registry/known-exposure.sqlite` dan diperiksa hash sebelum/sesudah training. Tidak ada klaim holdout baru, reviewer baru, validasi Indonesia atau kelayakan produksi.

Rujukan metode: [data leakage](https://scikit-learn.org/stable/common_pitfalls.html#data-leakage), [threshold tuning](https://scikit-learn.org/stable/modules/classification_threshold.html), [calibration](https://scikit-learn.org/stable/modules/calibration.html). Versi dependency inference tetap sesuai metadata training asli; dokumentasi tersebut tidak menjadi instruksi upgrade.
