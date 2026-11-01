# Protokol Perluasan Data dan Seleksi Model URL/QR v8

> Ditetapkan sebelum intake teks URL baru, fitting dan prediksi test v8, 1 November 2026.
> Acuan: [hasil v7](./structural-retraining-v7-results.md), [audit dataset](./url-qr-dataset-research.md), dan [rencana ML](./machine-learning-plan.md).

## Tujuan dan kontrak

Tambahkan contoh training dari publikasi dengan validasi manusia, perbaiki seleksi yang sebelumnya memenangkan kenaikan macro recall kecil sambil menurunkan sumber terlemah, lalu ukur hasil pada holdout baru. Target proyek tetap lower Wilson 95% recall 85% dan upper FPR 1%; target tidak dilonggarkan untuk meluluskan eksperimen. Model tetap keluarga Logistic Regression dan fitting dilakukan dalam notebook baru `guardian_lab_url_qr_expansion_v8.ipynb`.

Tidak ada kunjungan target, HTML, DNS, label LLM atau review manusia rekaan. Query/fragment tetap dikeluarkan oleh sanitizer. Dataset dan artifact lama dipertahankan; sumber test v7 Phish360 tetap benchmark teramati di luar training v8. API shadow tetap artefak v6 hingga ada keputusan berbasis bukti.

## Data tambahan dan batas bukti

Prioritaskan KnowPhish TR-OP dari [repository penulis](https://github.com/imethanlee/KnowPhish) dan [paper](https://arxiv.org/html/2403.02253v2). Paper melaporkan validasi manual atas 5.000 phishing OpenPhish dan 5.000 benign Tranco. Tidak menyamakan ranking Tranco dengan bukti keamanan; dasar penerimaan adalah laporan validasi penulis atas benchmark. Dua sheet review independen per kasus tidak tersedia. Rilis publik untuk evaluasi/penelitian tidak dianggap izin produksi atau redistribusi.

Metadata arsip sudah diperiksa pada v7; tidak ada URL-text atau prediksi model TR-OP yang dipakai pada tahap tersebut. Ungkapkan exposure metadata ini. Data historis 2023 dan sumber global tidak disebut gold Indonesia. Cari sumber Indonesia yang dapat diakses, catat batas akses dan kualitas; jangan meminta identitas pengguna atau menghubungi penulis tanpa instruksi.

Hanya baca `info.txt` dari arsip sumber dengan HTTP range terbatas. Abaikan HTML/gambar/JSON aplikasi. Verifikasi header ZIP, panjang, metode kompresi dan CRC sebelum parsing; gunakan library standar untuk dekompresi. Header/nama file/URL mentah tidak dicetak atau disimpan. Pin commit README, ukuran arsip, digest indeks metadata dan digest konten projection. Jangan memuat pickle/joblib milik penerbit.

Gunakan registry exposure v1-v7 sebelum intake sebagai snapshot readonly. Prefilter domain metadata hanya optimisasi; periksa kembali core URL aktual terhadap hash/domain registry serta seluruh development. Sanitasi, deduplikasi, keluarkan konflik label dan batasi lima URL per tenant/domain. Semua penolakan dan cakupan data tidak terbaca harus dicatat. Jangan menganggap arsip baru berarti semua URL baru.

Partisi sumber tambahan ditetapkan berdasarkan `sha256('v8-domain:' + group) mod 100`: fit 0–49, tune 50–59, calibration 60–69, threshold 70–79, test 80–99. Alokasi test 20% memberi dukungan benign lebih besar untuk mengukur false alarm. Pembagian dilakukan sebelum prediksi, mempertahankan seluruh satu domain/tenant dalam satu partition. Holdout baru adalah domain-disjoint dari sumber yang juga dipakai dalam development; bukan sumber/penerbit independen atau holdout temporal. Ketidakpastian campaign tetap dicatat. Jika dukungan kelas test terlalu kecil, laporkan ketidakcukupan dan jangan menjanjikan FPR 1%.

Gabungkan fit tambahan dengan 532.751 fit v7; tune/calibration/threshold lama tetap pada perannya lalu ditambah partition baru yang sesuai. Jangan menambahkan holdout lama ke fit. Audit representasi scheme-free dan konflik pada fit gabungan sendiri, karantina seluruh anggota konflik, jangan mengambil label test untuk membersihkan fitting. Catat jumlah data tambahan pada setiap partition dan checksum final.

## Fitur dan konfigurasi sebelum fitting

Refit TF-IDF char/kata pada sampel fit gabungan saja, cap per sumber 60.000 dan total 150.000 berdasarkan seed 20261101. Char 100.000 fitur, ngram 2–5, min_df 4; word 20.000 fitur, ngram 1–2, token huruf minimal dua, min_df 4. Bobot char 1, word 0,7. Numerik mengikuti sanitizer v6 dan fitur struktur v7; HTTPS, label sumber, tanggal dan reputasi hidup tidak masuk fitur.

Tiga kandidat ditetapkan: `expanded_rich_c2_sqrt` (fitur v6, C=2, bobot sumber sqrt), `expanded_structural_c2_sqrt` (fitur struktur linear v7, C=2, bobot sqrt), dan `expanded_structural_c2_equal` (struktur sama, bobot inverse source count). Semua bobot dinormalisasi rata-rata satu. Solver liblinear, max_iter 1500, tol 0,0001, seed tetap. Kontrol frozen v6 dan v7 diprediksi pada tune tanpa fitting ulang dan tetap tersedia bila kandidat baru tidak memenuhi seleksi.

Simpan matriks sementara secara lokal dan lepaskan blok teks sebelum fitting untuk membatasi puncak RAM. Perubahan pengelolaan memori tidak mengubah spesifikasi fitur. Catat durasi fit/prediksi dan konvergensi secara terpisah jika memungkinkan.

## Seleksi dan pembekuan

Pada tune gabungan, gunakan threshold global dengan FPR empiris maksimal 1% per sumber sebagaimana eksperimen lama. Tidak menggunakan identitas sumber saat inferensi. Setiap kandidat harus memiliki recall setiap sumber tidak lebih rendah dari frozen v6 sebesar 1 percentage point, pada aturan pemilihan threshold development yang sama. Ini guard development yang dibekukan, bukan klaim non-inferiority statistik. Laporkan interval domain untuk menilai ketidakpastian.

Di antara kandidat yang lolos guard, pilih minimum source recall tertinggi, lalu macro source recall, lalu average precision. Kandidat yang tidak lolos tetap dilaporkan. Jika tidak ada kandidat lolos, pertahankan frozen v6 sebagai keputusan seleksi dan simpan kandidat eksperimen terbaik berdasarkan urutan tersebut sebagai diagnostic challenger; jangan mempromosikannya sebagai pemenang. Dengan demikian training nyata tetap selesai dan kegagalan guard dapat ditinjau.

Kalibrator sigmoid hanya di-fit pada calibration gabungan untuk challenger terpilih. Warning/high dipilih pada threshold gabungan dengan aturan upper Wilson per sumber 1%/0,1% jika ukuran memungkinkan; fallback empiris sumber kecil diungkapkan. Bekukan model, kode, source hash, data, test manifest dan threshold sebelum scoring test. Catat kontrol threshold v6 yang dihitung dari threshold development gabungan menggunakan aturan yang sama; kebijakan v6 asli tetap terlihat.

## Evaluasi dan bukti selesai

Test TR-OP baru dikeluarkan dari semua fitting/selection/calibration/threshold, termasuk vocabulary. Laporkan jumlah kelas/domain, accuracy, precision, recall, FPR, kalibrasi, Wilson dan bootstrap domain berpasangan 1.000 ulang. Feed PhishTank positif hanya menghasilkan sensitivitas. Semua benchmark v3-v7 termasuk Phish360 diberi status teramati dan tetap dipakai memeriksa regresi, tanpa memilih model dari hasilnya.

Selesaikan notebook Run All, pemeriksaan checksum baseline, tes artifact asli, fit-only transformer, guard seleksi, decoder ZIP bounded/CRC, URL/QR/scheme parity, dan tidak ada target pada output. Perbarui registry exposure hanya setelah provenance v8 lengkap dan terverifikasi. Publikasikan laporan agregat serta MD hasil; data/model lokal tetap diabaikan Git. Integrasi kandidat ke API hanya disiapkan bila hasil mendukung, tanpa mengaktifkan produksi ketika gate gagal atau bukti Indonesia belum ada.
