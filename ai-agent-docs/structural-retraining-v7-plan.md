# Rencana Perbaikan Struktur dan Training Ulang URL/QR v7

> Ditulis 1 November 2026 sebelum training dan sebelum membaca prediksi test v7.
> Acuan: [audit keandalan](./model-hardening-plan.md), [hasil v6](./data-improvement-v6-plan.md), dan [riset dataset](./url-qr-dataset-research.md).

## Tujuan dan batas eksperimen

Tingkatkan recall pada anggaran false alarm rendah dengan satu keluarga classifier Logistic Regression. Audit development menemukan recall rendah pada URL panjang/punycode dan FPR tinggi pada private hosting. Angka tersebut menjadi hipotesis fitur, bukan vonis label atau alasan mengubah skor dengan aturan manual.

Notebook baru `guardian_lab_url_qr_structural_v7.ipynb` memuat audit, fitting nyata, pemilihan development, kalibrasi, pembekuan, dan evaluasi. Artifact/notebook v3-v6 serta runtime/API v6 tetap dipertahankan. Semua benchmark lama diberi status teramati. Tidak ada kunjungan target, DNS hidup, HTML, label LLM, atau kredensial asli.

## Hipotesis yang diuji

Normalisasi L2 per baris pada blok numerik v6 dapat mengaburkan besar absolut panjang/entropy URL. Model linear juga belum memiliki fitur yang memisahkan pengaruh private hosting dan pola path. Uji blok numerik dengan besaran yang dipertahankan, transformasi spline yang di-fit hanya pada fitting, serta interaksi struktur yang ditetapkan sebelum training. Ini hipotesis yang harus diuji, bukan kesimpulan kausal.

TF-IDF karakter/kata dan bobot sumber tetap mengikuti v6, tanpa fitting ulang pada tune/test. Vocabulary/scaler lama hanya boleh digunakan jika checksum/provenance membuktikan fit v6 yang sama. Tidak menambah HTTPS, label sumber, tanggal, popularitas, reputasi hidup, atau identitas brand resmi sebagai fitur/allowlist.

## Data dan penanganan ambiguitas

- Development awal berasal dari cache v6 703.604 URL: fit 532.793; tune 84.000; calibration 40.104; threshold 46.707. Domain/tenant dan canonical digest diverifikasi ulang sebelum fitting.
- Konflik representasi identik diidentifikasi pada fit sendiri; seluruh anggota konflik fit dikarantina dari fitting, tanpa mengambil label dari partition lain. Tiga usulan scam dari audit publik diperlakukan sebagai ambiguitas konteks; hanya anggota yang berada di fit dikarantina, tanpa relabel dan tanpa menganggap URL lain pada domain itu memiliki label yang sama.
- Tune, calibration, threshold serta benchmark lama tidak dibersihkan berdasarkan kesalahan prediksi. Laporkan jumlah karantina, fit tersisa, source/class counts, dan checksum before/after. Seluruh kandidat v7 memakai fit yang sama. Kontrol v6 beku tetap dilaporkan.
- Paket reviewer dan pilot Indonesia yang sudah ada tidak ditimpa dan tidak menghasilkan label baru.

## Konfigurasi dan pemilihan sebelum test

Empat konfigurasi Logistic Regression liblinear, `max_iter=1500`, seed 20261101:

1. `repeat_v6`: fitur asli v6 dan C=2 pada fit yang sudah dikarantina; kontrol perubahan data.
2. `structural_linear_c2`: blok TF-IDF tetap, numerik tanpa normalisasi per baris, indikator/interaksi struktur, C=2.
3. `structural_spline_c05`: numerik spline degree 2, empat knots quantile, interaksi struktur yang sama, C=0.5.
4. `structural_spline_c2`: fitur spline yang sama, C=2.

Rincian fitur dan bobot blok dibekukan dalam manifest sebelum fitting pertama. Transformasi spline/scaler/interaksi berbasis data hanya di-fit pada fit. Bobot sumber/kelas dan domain mengikuti fungsi v6. Konvergensi, durasi, jumlah fitur, dan checksum kandidat dicatat.

Pilih hanya dari tune menggunakan urutan leksikografis: macro-source recall pada threshold global yang memenuhi FPR empiris maksimal 1% di setiap sumber benign, minimum source recall, lalu average precision. Tie persis memilih konfigurasi lebih sederhana sesuai urutan di atas. Tidak memilih berdasarkan test atau subset manusia lama.

Kalibrasi sigmoid pada calibration saja. Pilih warning pada threshold partition dengan syarat batas atas Wilson 95% FPR maksimal 1% pada tiap sumber; high memakai anggaran 0,1%. Jika ukuran sampel tidak memungkinkan batas keyakinan, gunakan batas empiris sumber tersebut dan tandai eksplisit bahwa jaminan statistik tidak terpenuhi. Semua threshold dipilih dari development dan dibekukan sebelum test; hasil kontrol frozen v6 pada kebijakan aslinya tetap tersedia.

Untuk memisahkan dampak fitur dan perubahan kebijakan threshold, hitung juga threshold kontrol v6 dari threshold partition dengan aturan confidence v7 yang sama, lalu bekukan sebelum test. Kontrol ini ditetapkan sebelum fitting v7; ia tidak menggantikan hasil kebijakan asli v6. Semua hasil keduanya ditampilkan, tanpa pemilihan dari test.

## Pencarian dan penerimaan test independen

Utamakan aset publik dengan audit manusia penerbit, label biner yang dapat ditelusuri, URL asli yang dapat disanitasi, hak penggunaan, serta versi/checksum. Verifikasi metode dari paper/dokumentasi primer; klaim judul, akurasi paper atau ranking domain tidak menggantikan audit label.

Prioritas sumber Indonesia tetap berlaku. Katalog yang tidak menyediakan data/label/metode yang dapat diverifikasi, dataset pesan tanpa unit label URL, malware umum, label LLM, dan data sintetis tidak disebut gold URL Indonesia. Catat penerimaan/penolakan serta batas akses tanpa menghubungi penulis atau mengarang review.

Untuk sumber yang lolos, sanitize di memori, catat metadata/checksum aset, keluarkan overlap canonical/domain/tenant dengan registry exposure v1-v6 dan seluruh development, keluarkan konflik label, deduplikasi, lalu cap maksimal 5 URL per domain dan 20.000 total berdasarkan hash deterministik. Jangan melihat prediksi sebelum manifest test dibekukan. Laporkan tier label: audit manusia per kasus, verifikasi komunitas, atau label sumber; tier berbeda tidak digabung menjadi satu accuracy.

Test baru tidak dipakai fitting, pemilihan konfigurasi, kalibrasi, atau threshold. Jika sumber dengan audit manusia yang memadai belum tersedia, nyatakan batasnya dan tetap selesaikan training/evaluasi development serta regresi benchmark teramati. Jangan menyebut test lama sebagai test baru. Holdout baru dari provider lama tetap bukan independent-source evidence.

### Sumber yang diterima sebelum fitting v7

Phish360 dari [halaman penulis](https://web.cs.hacettepe.edu.tr/~selman/phish360-dataset/), [repository resmi](https://github.com/almakhamreh/Multimodal-Phishing-Benchmarks/tree/01a0f2d6be31f1e90dedb0775ce2327d870ae638), dan [paper CrossPhire](https://doi.org/10.3390/app16020751) dipakai sebagai test sumber tambahan. Penulis melaporkan inspeksi/kurasi manual, tetapi tidak merilis dua sheet independen per kasus. Tier bukti tetap klaim kurasi penulis, tidak disetarakan dengan gold set dua reviewer. Rilis untuk riset akademik tidak dianggap izin penggunaan komersial atau redistribusi.

Dua file memuat 10.748 baris. Pembacaan hanya URL/Class/tag bahasa mentransfer sekitar 611 KB, tanpa HTML/screenshot. Pemeriksaan awal menyisakan 7.516 core, 3.201 phishing dan 4.315 legitimate pada 7.002 domain/tenant, setelah pengecualian exposure dan sanitasi. Hash footer/projection dicatat; tidak mengklaim hash seluruh file sumber. Halaman sumber menyebut 2020–2023, sedangkan paper menyebut 2020–2024; perbedaan dicatat dan tidak ada klaim temporal baru. Tag bahasa bukan bukti sasaran Indonesia.

Katalog Indonesia Telkom University yang ditemukan belum menyediakan URL unduhan/label/metode audit yang dapat diverifikasi pada halaman yang diperiksa. LegitPhish belum diterima sebagai test utama karena pencampuran URLhaus dan phishing serta dokumentasi audit per kasus yang tidak tersedia. KnowPhish TR-OP dapat ditelusuri ke paper dengan validasi manual, tetapi belum digunakan pada eksperimen ini; seluruh hasilnya tetap belum diketahui. Tidak menghubungi penulis atau mengisi form dengan identitas pengguna.

## Evaluasi, integritas, dan keputusan

Laporkan jumlah kelas/domain, confusion matrix, recall, FPR, precision, accuracy, Brier, kalibrasi, Wilson 95% dengan asumsi row-IID, dan bootstrap domain berpasangan. Feed positif saja hanya menghasilkan sensitivitas. Gunakan seed tetap dan 1.000 bootstrap untuk delta recall/FPR pada benchmark yang cukup besar; tidak menafsirkan interval sebagai mengatasi bias label/campaign.

Tes bermakna meliputi transformasi fit-only, URL/QR parity, tidak bergantung pada skema HTTP/HTTPS, model save/reload, konsistensi kalibrasi/threshold, checksum model lama, dan tidak ada target pada output notebook. Jalankan notebook penuh, Ruff, dan suite Python yang relevan. Grafik dan laporan agregat boleh dilacak; dataset/model binary tetap lokal dan diabaikan Git.

Sukses eksperimen berarti ada hasil training nyata dan evaluasi jujur. Promosi produksi tetap memerlukan bukti yang dipersyaratkan release gate; tidak menurunkan target demi meloloskan hasil. Perbaikan development atau satu benchmark tidak menjadi klaim peningkatan menyeluruh. Keputusan model dan API produksi tidak otomatis berubah.
