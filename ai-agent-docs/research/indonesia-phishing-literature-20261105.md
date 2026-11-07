# Penelusuran literatur untuk evaluasi URL phishing Indonesia

Tanggal pemeriksaan: 5 November 2026. Scope: metadata, artikel dan dokumentasi sumber publik. Tidak mengunduh baris dataset, mengunjungi URL target, menghubungi penulis atau mengirim formulir akses. Tidak ada training atau evaluasi model baru pada penelusuran ini.

Penelitian terdahulu dapat menyediakan kandidat URL, label penerbit, dan bukti review manusia yang dapat digunakan kembali. Label dari paper dapat mendukung benchmark eksternal setelah audit scope, privasi, hak penggunaan dan overlap. Bukti review penerbit perlu dicatat sesuai proses yang benar-benar terdokumentasi; keberadaan paper atau daftar penulis tidak membuktikan dua reviewer independen per kasus.

## Sumber yang ditemukan

### 1. SABER 2026: dataset Indonesia 2.054 URL

Sarasjati, Winarno dan Madani, *Karakterisasi Fitur dan Deteksi URL Phishing pada Dataset Indonesia Menggunakan LASSO+ dan Random Forest*, DOI 10.59841/saber.v4i3.3904. PDF bagian metode/Tabel 2 melaporkan 1.027 phishing dari IDADX dan 1.027 legitimate hasil crawling berbasis Majestic Million, dikumpulkan September 2023. Artikel terbit Juli 2026. [Artikel penerbit](https://jurnal.stikes-ibnusina.ac.id/index.php/SABER/article/view/3904), [PDF](https://jurnal.stikes-ibnusina.ac.id/index.php/SABER/article/download/3904/3763/19232).

Artikel/PDF publik dapat dibaca. Tautan unduh dataset mentah dan bukti dua reviewer independen per URL belum ditemukan pada materi yang diperiksa. Model artikel memakai 70 fitur termasuk respons, WHOIS, reputasi dan hyperlink. Hasilnya tidak langsung sebanding dengan v6 URL-only offline. Kandidat untuk benchmark Indonesia historis jika URL+label, hak akses dan provenance kasus tersedia; belum menjadi gold Indonesia kontemporer.

### 2. IndoPhis-D, tesis Telkom 2026: klaim 6.112 URL Indonesia

Katalog institusi untuk tesis M. Azwar Zulmi, *Adaptive Rule-Based Detection of Indonesian Phishing Website through Multi-Layered Filtering Based on URL Features*, menyebut 6.112 URL Indonesia dan mengklaim validasi oleh otoritas keamanan siber nasional. Bukti yang tersedia pada penelusuran adalah abstrak/katalog; ini tesis S2, bukan konfirmasi artikel jurnal atau audit label oleh proyek. Bab metode dan hasil ditandai perlu login, dan dataset mentah publik belum ditemukan. [Katalog resmi](https://repositori.telkomuniversity.ac.id/pustaka/245173/adaptive-rule-based-detection-of-indonesian-phishing-website-through-multi-layered-filtering-based-on-url-features-dalam-bentuk-buku-karya-ilmiah.html).

Prioritas tindak lanjut: dataset berizin, rincian validasi, kelas/tanggal dan relevansi di luar domain `.id`. Jangan menganggap klaim abstrak sebagai bukti review per kasus yang sudah diperiksa.

### 3. Indonesia Phishing URL Dataset, katalog KI Telkom

Katalog resmi menjelaskan kompilasi URL phishing/legitimate dengan karakteristik Indonesia. Halaman mencantumkan publikasi 1 November 2025 dan tanggal katalog 25 Februari 2026. Jumlah baris, lisensi data, prosedur anotasi dan unduhan data tidak terlihat pada halaman yang diperiksa. Ini catatan katalog kekayaan intelektual, bukan dataset terbuka atau jurnal yang otomatis dapat diunduh. [Halaman institusi](https://btp.telkomuniversity.ac.id/landing/ip/HCNA2602260302).

Kandidat relevan untuk ditelusuri akses/provenance-nya. Kesamaan anggota tim dengan tesis di atas tidak cukup untuk menyimpulkan keduanya menggunakan dataset identik.

### 4. LegitPhish 2025: dataset publik internasional

Potpelwar, Kulkarni dan Waghmare, *LegitPhish: A large-scale annotated dataset for URL-based phishing detection*, DOI 10.1016/j.dib.2025.111972. Abstrak mengklaim verifikasi manual, tetapi metode bagian 4 menyebut verifikasi manual **atau** pencocokan threat feed; algoritmanya juga menetapkan label berdasarkan sumber. Tidak cukup untuk menyimpulkan setiap URL dinilai dua manusia independen. Cakupannya worldwide dan keterbatasannya menyebut dominasi URL beraksara Inggris/Latin. [Artikel lengkap](https://pmc.ncbi.nlm.nih.gov/articles/PMC12538017/).

Repositori Mendeley V2 menyediakan halaman dataset, menyatakan 101.219 URL, mapping phishing=0/legitimate=1 dan lisensi CC BY 4.0. Hitungan kelas tertulis 63.678 + 37.540 = 101.218; selisih satu baris perlu dicek pada file jika digunakan. [Repositori dataset](https://data.mendeley.com/datasets/hx4m73v2sf/2).

Kandidat benchmark global tambahan setelah audit baris, scope phishing vs malware, privacy, sumber dan overlap v6. Belum membuktikan validasi Indonesia atau review independen per URL.

## Penggunaan bukti yang dapat dipertanggungjawabkan

1. Ambil URL+label dari rilis publik berizin; catat DOI/versi/hash, definisi kelas, tanggal dan proses anotasi yang sebenarnya. Metrik suatu paper tidak dipindahkan menjadi metrik v6.
2. Periksa overlap terhadap seluruh data/exposure v6 sebelum scoring. Benchmark yang sudah dipakai fitting atau diamati tetap mempunyai status paparan tersebut.
3. Jika proses review manusia penerbit terdokumentasi dan dapat dipetakan ke kasus, gunakan sebagai bukti penerbit dengan keterbatasannya. Jangan membuat identitas reviewer lokal atau mengisi kolom review manusia seolah proyek telah melakukannya.
4. Data Indonesia historis dapat menjadi evaluasi regional tambahan. Jendela 2026 pada protokol final tetap merupakan evaluasi temporal berbeda; data 2023 tidak diperlakukan sebagai observasi 2026.
5. Sebelum menyebut gold Indonesia memenuhi release gate, tetap perlukan kecukupan dua kelas, bukti label/reviewer independen, relevansi Indonesia, QA privasi/hak, audit waktu/kampanye dan holdout terkunci.

Hasil penelusuran ini memperluas pilihan sumber, tetapi belum menambahkan kandidat atau hasil review ke input gold lokal. Akses dataset dan bukti per kasus masih harus diperoleh untuk menjalankan evaluasi regional yang sah.

## Tindak lanjut pelaksanaan pada tanggal yang sama

Rilis LegitPhish V2 kemudian berhasil diunduh dan diuji terpisah: [pelaksanaan dan keterbatasan](../legitphish-v6-evaluation.md). CSV 101.219 baris ternyata memiliki satu URL tanpa label; 101.218 label lainnya cocok dengan jumlah kelas yang ditulis penerbit. Setelah penyaringan privasi/overlap/cap domain, hanya tersisa 28 benign, sehingga hasilnya terutama menambah bukti sensitivity global. Belum ada data SABER/Telkom atau label manusia Indonesia yang diimpor pada tindak lanjut ini.
