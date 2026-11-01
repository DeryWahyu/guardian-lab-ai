# Riset dan Seleksi Dataset URL/QR — Guardian Lab

## Intake publik dan audit kesalahan v10

[Audit sumber v10](../ml/reports/data-source-audit-v10.json) meninjau sepuluh sumber primer. [IOBHunter penulis NDSS2026](https://github.com/dpliu/iobhunter-dataset/tree/4267788db6b73a0d30c99f53a72a2addcc47994b) menyediakan hard-negative FQDN yang diterima peneliti, dengan review 2019-2024. CSV berbeda dari README: 4.809 accepted=yes dan 32 accepted=no; hanya accepted=yes/VT-clean diterima dan 32 kasus dikeluarkan. Setelah pemeriksaan overlap/privasi, deduplikasi dan cap domain, tersedia 4.469 benign historis; label tidak diwariskan ke path arbitrer atau periode sekarang. Lisensi eksplisit tidak dinyatakan; tidak meredistribusikan atau mengklaim izin produksi.

Feed PhishTank verified-online memberi tiga phishing baru setelah filter tanggal, domain/URL exposure, dan privasi. Seluruh tambahan v10 belum masuk fitting dan belum diprediksi; reserve 913 benign historis dan dua positif terbaru tidak menggantikan temporal holdout dua kelas. PhiShark2026 memerlukan akses/DUA; pengguna memilih melanjutkan sumber publik. Tanggal rilis 2026 pada dataset lain tidak otomatis menjadi tanggal observasi baru. [Hasil lengkap](./recall-cnn-v10-results.md) serta [manifest intake](../ml/reports/public-intake-v10.json) mencatat lineage, keterbatasan dan gate training yang tetap gagal.

## Perluasan data v8 dan holdout domain TR-OP

[Audit v8](../ml/reports/data-source-audit-v8.json) mendokumentasikan intake TR-OP dari [KnowPhish](https://github.com/imethanlee/KnowPhish/tree/899982c9f0eef0f2ef758cbee96d2ceff0bd5e9a) dan [paper penulis](https://arxiv.org/html/2403.02253v2). Penulis melaporkan validasi manual benchmark. Metadata sudah diperiksa pada v7; URL-text baru diambil untuk v8. Dari 10.000 metadata kasus, 5.506 anggota teks melewati prefilter; setelah CRC, sanitasi, deduplikasi/cap diperoleh 5.438 URL baru di luar exposure v1-v7. Dibagi domain 50/10/10/10/20 sebelum prediksi: 2.753 fit, 545 tune, 531 calibration, 512 threshold dan 1.097 test.

Dataset historis 2023 ini memakai label validasi penulis tanpa dua sheet review independen per kasus. Sumber yang sama masuk development dan test melalui domain berbeda, sehingga tidak disebut independent-source, temporal holdout atau gold Indonesia. Hanya info.txt dibaca; tidak ada HTML/screenshot/kunjungan target. Kegagalan range awal dihentikan, diatasi melalui endpoint konten publik dan dilanjutkan dari checkpoint; seluruh anggota terpilih diverifikasi sebelum fitting. Data dan binary model tidak didistribusikan.

[Hasil v8](./data-expansion-v8-results.md) menunjukkan recall holdout 58,91% dan 0/384 FP pada diagnostic challenger, sementara guard development gagal dan sebagian benchmark teramati menurun. Seluruh intake tersanitasi yang valid ikut registry exposure, termasuk baris yang dikeluarkan oleh cap, agar tidak disalahartikan sebagai data belum teramati pada iterasi berikut.

## Sumber uji tambahan untuk v7

[Audit sumber v7](../ml/reports/structural-source-audit-v7.json) mencatat Phish360 dari [halaman penulis](https://web.cs.hacettepe.edu.tr/~selman/phish360-dataset/) dan [repository resmi](https://github.com/almakhamreh/Multimodal-Phishing-Benchmarks/tree/01a0f2d6be31f1e90dedb0775ce2327d870ae638). Dari 10.748 baris, tersisa 7.516 core tersanitasi di luar URL/domain registry v1-v6: 3.201 phishing dan 4.315 legitimate, 7.002 kelompok. Label berasal dari klaim kurasi manual penulis; dua review independen per kasus tidak tersedia. Provider dataset tambahan tidak dianggap feed/kampanye sepenuhnya independen karena ada lineage PhishTank/OpenPhish.

Kolom URL/Class/tag bahasa dibaca dengan HTTP range sekitar 611 KB, tanpa HTML/screenshot/kunjungan target. Hash projection/footer dan file ID disimpan; tidak mengklaim hash seluruh file sumber. Sumber historis ini bukan gold Indonesia, dan masa koleksi halaman/paper tidak konsisten. Rilis akademik tidak otomatis menjadi izin produksi/redistribusi. [Evaluasi v7](./structural-retraining-v7-results.md) dilakukan setelah pemilihan/kalibrasi/threshold dibekukan. Phish360 kini benchmark teramati dan ditambahkan ke registry exposure.

Katalog [Indonesia Phishing URL Dataset Telkom University](https://btp.telkomuniversity.ac.id/landing/ip/HCNA2602260302) belum menyediakan unduhan URL/label atau metode audit yang dapat diverifikasi pada halaman yang diperiksa. LegitPhish tidak dipilih karena cakupan URLhaus/phishing belum terpisah dengan bukti kasus. Metadata arsip KnowPhish TR-OP diperiksa dan dilaporkan; tidak ada URL-text atau prediksi modelnya yang dipakai dalam v7. Keputusan serta batas pemeriksaan sumber dicatat dalam audit, tanpa klaim telah memeriksa semua dataset di internet.

## Audit lanjutan dengan bukti manusia terpublikasi

Sesuai pilihan pengguna, tahap keandalan memakai audit manusia PhishVN yang dipin di bawah. [Notebook audit](../guardian_lab_model_hardening.ipynb) mencocokkan keseluruhan 200 kasus publik ke development v6: 57 exact canonical pada core tersanitasi, 11 domain-only, 130 tidak cocok, dan 2 unsupported. Tiga exact canonical dengan verdict scam di luar scope biner ditandai untuk pemeriksaan semantik/waktu/query; tidak ada label otomatis yang diubah. Angka ini berbeda dari subset 33 kasus evaluasi v5 yang sudah difilter overlap. Keseluruhan 200 kasus tidak disebut test independen baru, bukti Indonesia, atau anotasi baru oleh agent. Lihat [hasil dan keterbatasan](./model-hardening-plan.md).

## Tambahan audit sumber untuk eksperimen v5

[Protokol v5](./recall-improvement-v5-plan.md) menetapkan dua evaluasi baru sebelum fitting/prediksi. DeepURLBench dipin pada commit `bf17c3fef854ff0ea40bcf93e373fc2c6dc30081`; delapan shard dipilih berdasarkan hash nama file. Pemeriksaan 1.731.328 baris mencatat 134.460 malware di luar cakupan, 62.606 input tidak didukung/ditolak screening privasi, 292.831 overlap URL/domain historis, serta lima canonical hash dengan konflik label (19 baris). Setelah deduplikasi dan sampling hash yang sudah ditetapkan, test berisi 50.000 core (5.707 phishing/44.293 benign), pada 48.154 domain/tenant. Semua proses hanya mengambil aset dataset, tidak membuka target.

Label DeepURLBench memakai aturan konsensus vendor berbobot yang dipaparkan [penulis](https://arxiv.org/html/2501.00356v1), bukan label manusia per URL. Benign berdasarkan tidak adanya deteksi vendor masih bisa salah. Data historis dan lisensi [CC BY-NC 4.0](https://github.com/deepinstinct-algo/DeepURLBench) membatasi klaim temporal serta penggunaan; tidak dipakai melatih v5 dan tidak disebut gold Indonesia.

Audit manusia [PhishVN](https://github.com/vuthainguyen1602/phishvn/tree/2bc80412a4b94ae546211e488ced996c8e0b78f1/docs/verify) dipin terpisah. Dari 200 kasus dengan dua sheet dan adjudikasi publik, 103 scam/unsure dikeluarkan dari binary phishing, 16 keputusan tidak memiliki jenis evidence yang disyaratkan, dan 48 kasus overlap domain/URL historis. Tersisa 33 kasus dengan bukti capture/archive/urlscan/registry: 22 phishing dan 11 legitimate, masing-masing pada domain/tenant berbeda. Label berasal dari review manusia penerbit yang dapat ditelusuri, bukan review baru yang dibuat agent. Sampel kecil dan sumber dasarnya sama dengan sebagian development: jangan menyebutnya independent-source benchmark atau bukti FPR 1%.

CompPhish, PhishBD_2026, PhishMMF, dan Dataset_Phising tidak dipilih menjadi test primer v5 karena batas cakupan ancaman, provenance, unit label email, atau mapping/audit label yang belum memadai. Tidak menebak semantik label dari hostname. Manifest aset/checksum dan audit subset disimpan lokal di `ml/runs/notebook-tfidf-logistic-v5/reports/frozen-new-test-manifest.json`; source code kurasi direproduksi di notebook v5.

> **Tanggal pemeriksaan:** 1 November 2026.  
> **Cakupan:** Classifier phishing berbasis teks URL; QR didekode menjadi URL yang masuk ke classifier yang sama.  
> **Status:** Rekomendasi sumber dan audit struktur data, bukan dataset final siap training atau hasil akurasi model.  
> **Bukti:** [Laporan audit agregat](./research/url-dataset-source-audit.json) dan [script reproduksi](../scripts/research/audit_url_dataset_sources.py).

## 1. Keputusan penelitian

**PhreshPhish adalah kandidat fondasi utama yang paling sesuai dari sumber yang ditinjau, dengan syarat perbaikan representasi URL dan audit sebelum training.** Gunakan split train untuk pengembangan, pertahankan test/benchmark sebagai evaluasi, dan tambahkan holdout baru untuk kasus Indonesia serta perubahan modus pada 2026. Dataset besar atau paper dengan akurasi tinggi tidak otomatis lolos seleksi.

PhiUSIIL berguna untuk pembanding dan pemeriksaan generalisasi, bukan sumber yang langsung digabungkan tanpa audit. CompPhish dan Web page phishing detection menjadi kandidat pengujian tambahan setelah URL mentah, definisi label, serta overlap sumber diperiksa. Data tanpa asal, label yang jelas, atau hak penggunaan yang dapat diperiksa tidak menjadi fondasi.

Pembedaan bukti dalam laporan ini:

- **Sumber primer:** Dataset card pemilik, repositori resmi, ketentuan penyedia, dan paper penulis. Angka katalog bukan hasil audit pribadi.
- **Audit berkas:** Pembacaan aset resmi dengan script; hanya metadata dan statistik agregat yang disimpan. Tidak ada URL korban atau HTML yang disimpan dalam repositori ini.
- **Rekomendasi:** Keputusan desain Guardian Lab berdasarkan bukti, bukan klaim bahwa sumber tersebut bebas kesalahan.

## 2. Standar kelulusan

| Pemeriksaan        | Syarat penggunaan                                                                                                                        |
| ------------------ | ---------------------------------------------------------------------------------------------------------------------------------------- |
| Cakupan label      | Phishing harus dibedakan dari malware, spam, defacement, domain mati, dan sekadar domain mencurigakan.                                   |
| Masukan            | Tersedia URL yang dapat diproses oleh extractor kita; fitur HTML/WHOIS tidak menjadi ketergantungan tersembunyi.                         |
| Waktu              | Bedakan tanggal rilis, tanggal diunduh, first-seen, tanggal verifikasi, dan observasi halaman. Tahun publikasi bukan umur setiap sampel. |
| Provenance         | Pemilik, sumber awal, versi, label mapping, lisensi, dan pembatasan penyedia dapat dilacak.                                              |
| Negatif yang sulit | URL benign memiliki path, query, TLD, subdomain, serta variasi situs yang realistis; popularitas bukan ground truth aman.                |
| Kebocoran          | Audit duplikasi URL, domain terdaftar, tenant hosting, kampanye, near-duplicate, dan overlap antarsumber sebelum menentukan split.       |
| Representasi       | Normalisasi dan sanitasi tidak berbeda menurut kelas atau sumber.                                                                        |
| Privasi            | PII/credential screening berlaku untuk kedua kelas; raw URL dan konten halaman tidak masuk log atau artifact penelitian.                 |
| Reproduksibilitas  | Pin versi/commit dan checksum; simpan manifest serta alasan setiap pengeluaran data.                                                     |
| Evaluasi           | Laporkan false positive, precision/recall, kalibrasi, ukuran sampel, dan hasil per segmen, bukan accuracy saja.                          |

Tidak digunakan skor bintang atau ranking numerik buatan karena belum semua berkas kandidat diaudit. Sumber terbuka untuk dibaca tidak otomatis bebas dipakai untuk semua tujuan.

## 3. Penelusuran kandidat dan keputusan

Tabel ini mencakup 21 dataset, studi dataset, feed, dan sumber referensi yang ditinjau. Hanya sumber yang disebut sebagai audit berkas pada bagian berikut yang sudah diperiksa isi asetnya secara langsung.

| Kandidat / sumber primer                                                                                  | Kecocokan dan keterbatasan yang ditemukan                                                                               | Keputusan untuk tahap pertama                                                                              |
| --------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------- |
| [PhreshPhish](https://huggingface.co/datasets/phreshphish/phreshphish)                                    | URL, label, tanggal, train/test dan benchmark; bundle juga memuat HTML besar.                                           | **Fondasi bersyarat**; gunakan proyeksi kolom dan tangani bias query.                                      |
| [PhiUSIIL — UCI](https://archive.ics.uci.edu/dataset/967/phiusiil+phishing+url+dataset)                   | URL tersedia; label 0 adalah phishing. Tabel juga berisi fitur halaman.                                                 | Pembanding; ekstrak ulang fitur, deduplikasi, dan jangan mengklaim temporal holdout.                       |
| [Web page phishing detection v3](https://data.mendeley.com/datasets/c2gw7fy2j4/3)                         | 11.430 URL seimbang dari Mei 2020; 87 fitur mencampurkan URL, halaman, dan layanan eksternal. CC BY 4.0.                | Pembanding historis bersyarat; hanya URL/label, bukan semua fitur bawaan.                                  |
| [URL-Phish v1](https://data.mendeley.com/datasets/65z9twcx3r/1)                                           | 111.660 URL; 100.000 benign dari ROR dan 11.660 phishing. CC BY 4.0.                                                    | Tambahan bersyarat; audit dominasi homepage/institusi pada kelas benign.                                   |
| [CompPhish v4](https://data.mendeley.com/datasets/fmbs4kp9wz/4)                                           | 15.358 sampel; koleksi September 2024–Agustus 2025, URL/HTML dan 70 fitur. CC BY 4.0.                                   | Kandidat holdout tambahan; periksa perbedaan label phishing dan tautan unduhan berbahaya.                  |
| [DeepURLBench](https://github.com/deepinstinct-algo/DeepURLBench)                                         | URL, first_seen, tiga kelas; CC BY-NC 4.0.                                                                              | Eksperimen riset terpisah; saring phishing/benign dan periksa kebijakan penggunaannya.                     |
| [GramBeddings](https://web.cs.hacettepe.edu.tr/~selman/grambeddings-dataset/)                             | Pemilik menyatakan 800.000 URL seimbang, koleksi Mei 2019–Juni 2021; akses melalui formulir.                            | Cadangan historis; berkas, lisensi, dan timestamp per baris belum diverifikasi.                            |
| [PhishVN v4](https://data.mendeley.com/datasets/b97hxbxtpd/4)                                             | 53.116 baris, tier label dan split kelompok; konteks Vietnam. Audit pemilik mengungkap noise pada tier bronze.          | Kandidat transfer regional, bukan bukti kecocokan Indonesia; utamakan core tervalidasi.                    |
| [PhiShark2026](https://phishark2026dataset.com/)                                                          | Halaman akses menyebut 53.591 observasi; akses akademik dibatasi dan perlu perjanjian.                                  | Ditunda; akses belum diperoleh dan jumlah rilis perlu dicocokkan dengan paper.                             |
| [LegitPhish v2](https://data.mendeley.com/datasets/hx4m73v2sf/2)                                          | Mapping 0=phishing; sumber menyertakan URLhaus. Jumlah total pada deskripsi tidak cocok tepat dengan penjumlahan kelas. | Tahan sampai audit label dan jumlah; URLhaus sendiri berfokus pada distribusi malware.                     |
| [PhiLegit-100K](https://data.mendeley.com/datasets/726pyz4j53/1)                                          | Gabungan PhiUSIIL dan LegitPhish; mempertahankan source-specific features.                                              | Jangan dianggap sumber independen atau dicampur dengan induknya tanpa deduplikasi.                         |
| [ISCX-URL2016 — UNB](https://www.unb.ca/cic/datasets/url-2016.html)                                       | Memisahkan benign, phishing, malware, spam, dan defacement; data berumur lama.                                          | Pembanding historis; jangan melebur seluruh kelas berbahaya menjadi phishing.                              |
| [UCI Phishing Websites 2015](https://archive.ics.uci.edu/dataset/327/phishing+websites)                   | 11.055 sampel, 30 fitur integer; representasi fitur lama, bukan korpus URL lengkap yang diperlukan.                     | Tidak menjadi fondasi pipeline URL mentah.                                                                 |
| [Tan 2018 Feature Evaluation](https://data.mendeley.com/datasets/h3cgnj8hft/1)                            | 10.000 halaman, 48 fitur; koleksi 2015/2017.                                                                            | Referensi fitur historis, bukan fondasi model URL 2026.                                                    |
| [PhishTrap](https://huggingface.co/datasets/saidutta69/PhishTrap)                                         | Feed/domain dan Tranco; memiliki metadata pembaruan. Contoh dan sumber berorientasi domain.                             | Jangan memakai kemudahan akses sebagai pengganti audit label, URL penuh, split, dan ketentuan sumber awal. |
| [Studi dataset Indonesia — SABER](https://jurnal.stikes-ibnusina.ac.id/index.php/SABER/article/view/3904) | Paper lokal ditemukan; berkas URL mentah, lisensi dataset, dan akses unduh belum berhasil diverifikasi.                 | Relevan sebagai petunjuk sumber; belum menjadi dataset yang tersedia untuk kita.                           |
| [PhishBench-External D4v](https://data.mendeley.com/datasets/2ctjcnm9kn/1)                                | 1.000 contoh dari Juli 2025; 27 fitur termasuk domain/network.                                                          | Kandidat sanity check kecil setelah memastikan URL tersedia; bukan dasar estimasi FPR sangat rendah.       |
| [PhishTank](https://phishtank.org/developer_info.php)                                                     | Feed phishing terverifikasi dengan waktu submit/verifikasi; bukan dataset dua kelas.                                    | Sumber kandidat positif terbaru, dengan akses dan ketentuan penyedia yang sesuai.                          |
| [OpenPhish](https://openphish.com/academic_use.html)                                                      | Feed dan program akademik; ada batas nonkomersial dan larangan berbagi data.                                            | Bersyarat; tidak dimasukkan otomatis ke dataset atau artifact yang akan dibagikan.                         |
| [Tranco](https://tranco-list.eu/)                                                                         | Ranking domain berversi; bukan label URL benign. Ketentuan sumber komponennya perlu dicatat.                            | Referensi pemilihan situs dan domain, bukan seluruh kelas negatif.                                         |
| [URLhaus](https://urlhaus.abuse.ch/)                                                                      | Intelijen URL distribusi malware.                                                                                       | Tidak menjadi ground truth phishing hanya karena berbahaya.                                                |

## 4. Mengapa PhreshPhish menjadi kandidat terkuat

[Dataset card](https://huggingface.co/datasets/phreshphish/phreshphish) memisahkan 498.255 train dan 168.060 test, dengan total 666.315 sampel. Field `url`, `label`, `date`, dan identitas sampel cukup untuk memulai audit URL. Card menyebut CC BY 4.0 serta penggunaan untuk riset anti-phishing. Pemakaian produk/publikasi tetap mengikuti ketentuan yang benar-benar berlaku, bukan asumsi dari tag lisensi.

[Paper penulis](https://arxiv.org/html/2507.10854v2) menjelaskan koleksi Juli 2024–Desember 2025, pembersihan halaman, pemisahan temporal, pengurangan kemiripan, dan benchmark dengan berbagai base rate. Ini merupakan alasan pemilihan sumber, bukan bukti bahwa model URL-only kita otomatis mewarisi performa paper.

Catatan pembatas:

- Dataset dirancang untuk pasangan URL/HTML. Kita hanya memakai teks URL dan harus melaporkan eksperimen sebagai adaptasi URL-only.
- Query pada kelas benign telah dihapus dalam proses privasi penulis. Kehadiran query pada kelas lain dapat menjadi shortcut pengumpulan data; rincian audit ada di bagian 5.
- Sanitasi PII sumber tidak menggantikan kewajiban scrubber Guardian Lab.
- Split resmi tidak langsung diasumsikan bebas overlap registered-domain atau kampanye. Kita perlu protokol tambahan untuk mengukur generalisasi domain baru.
- Tanggal pada berkas bertipe hari; batas train/test dalam hari yang sama perlu diperlakukan eksplisit ketika menerapkan pemisahan temporal yang ketat.
- Tidak ada klaim bahwa distribusi globalnya sudah mewakili semua modus Indonesia.

Revision yang diperiksa: `eca603e0ecd4f698f8d4d226c088659e72681239`. Metadata resmi dapat dibaca tanpa gate akun pada pemeriksaan ini. Bundel aset yang terdaftar sekitar 36,6 GB; penggunaan HTTP range/column projection menghindari pengunduhan kolom HTML untuk penelitian ini. Besarnya bundle bukan ukuran hasil ekspor URL saja.

## 5. Audit berkas dan hasil yang dapat direproduksi

[Script audit](../scripts/research/audit_url_dataset_sources.py) membaca ZIP UCI di memori dan kolom URL/label/tanggal dari Parquet resmi. Ia tidak mengunjungi URL target, menjalankan HTML, menyimpan baris URL mentah, atau mengirim data kepada LLM. Statistik disimpan pada [laporan JSON](./research/url-dataset-source-audit.json).

### PhiUSIIL: pemeriksaan seluruh CSV

| Temuan                    | Hasil audit                                                        |
| ------------------------- | ------------------------------------------------------------------ |
| Jumlah baris              | 235.795                                                            |
| Kelas sumber              | `0`: 100.945 phishing; `1`: 134.850 benign                         |
| Duplikat URL persis       | 425 baris duplikat; bukan ukuran near-duplicate/domain overlap     |
| Query pada kelas phishing | 6.079 dari 100.945 baris                                           |
| Query pada kelas benign   | 0 dari 134.850 baris                                               |
| Timestamp                 | Tidak ditemukan kolom timestamp observasi pada CSV                 |
| SHA-256 ZIP               | `0a639fd03aea6308c5b1c10c92aa23c2ce1505447a9137271865cd0badc9a59a` |

Label mapping dikonfirmasi dari [dokumentasi UCI](https://archive.ics.uci.edu/dataset/967/phiusiil+phishing+url+dataset). Parser kita harus memetakan label sumber `0` menjadi label proyek `1` untuk phishing, dan sebaliknya untuk benign. Jangan menyalin label numerik begitu saja.

Jumlah duplikat tersebut merupakan hasil perbandingan string URL mentah menggunakan digest di memori. Audit ini tidak memverifikasi kebenaran seluruh label, tidak mendeteksi seluruh variasi URL, dan tidak menggantikan deduplikasi sesudah normalisasi/sanitasi. Fitur seperti `URLSimilarityIndex`, `TLDLegitimateProb`, title, atau data halaman tidak otomatis boleh digunakan: ekstrak ulang hanya fitur yang tersedia saat inferensi.

### PhreshPhish: audit kolom URL

Audit selesai untuk seluruh **666.315 baris** pada **77 shard**: 56 train dan 21 test. Yang dibaca adalah kolom `url`, `label`, `date`, dan `lang`, tanpa kolom HTML. Pemeriksaan awal dua shard juga disimpan dalam JSON, tetapi keputusan berikut memakai hitungan seluruh korpus:

| Ukuran                                    | Train                        | Test                         |
| ----------------------------------------- | ---------------------------- | ---------------------------- |
| Jumlah baris                              | 498.255                      | 168.060                      |
| Benign                                    | 276.729                      | 91.260                       |
| Phishing                                  | 221.526                      | 76.800                       |
| Benign dengan query                       | 16 (sekitar 0,006%)          | 52 (sekitar 0,057%)          |
| Phishing dengan query                     | 16.351 (sekitar 7,38%)       | 18.398 (sekitar 23,96%)      |
| Benign tanpa skema HTTP/HTTPS eksplisit   | 4.189                        | 1.552                        |
| Phishing tanpa skema HTTP/HTTPS eksplisit | 0                            | 0                            |
| Duplikat URL persis dalam split           | 0                            | 0                            |
| Konflik label pada URL persis dalam split | 0                            | 0                            |
| Rentang tanggal yang tercatat             | 2 Juli 2024–8 September 2025 | 8 September–16 Desember 2025 |

Tidak ditemukan URL string identik yang berpindah dari train ke test. Ini belum membuktikan tidak ada near-duplicate, overlap domain/tenant, atau kampanye yang sama. Tidak semua label telah ditinjau ulang secara manual.

Ada dua konsekuensi tambahan: train dan test berbagi hari batas **8 September 2025**, sedangkan ketelitian `date` hanya satu hari; dan URL terpanjang train mencapai **25.523 karakter**, melebihi batas API saat ini 16.384 karakter. Jumlah serta alasan sampel yang ditolak oleh kebijakan input harus dilaporkan, bukan dipotong diam-diam.

Transfer yang tercatat untuk audit awal dan audit penuh sekitar **40,25 MiB** total, menggunakan pembacaan kolom/range. Tidak mengunduh seluruh bundle 36,6 GB. Tidak ada model dilatih dan tidak ada akurasi dihitung dari pembacaan ini.

Jumlah kandidat pola sensitif pada JSON hanyalah hasil screening regex, bukan jumlah korban atau PII yang telah dikonfirmasi. Hostname berakhiran `.id` juga bukan bukti bahwa sampel menargetkan Indonesia. Tidak ada baris contoh korban yang disertakan dalam laporan ini.

## 6. Implikasi: representasi model tidak boleh mengikuti artefak label

**Keberadaan query, nilai parameter, dan encoding tidak boleh langsung menjadi fitur model fondasi ketika proses dataset menghapusnya hanya pada kelas benign.** Model bisa mengenali perlakuan dataset, bukan karakteristik phishing. Hal serupa berlaku pada skema yang ditambahkan, homepage-only negatives, source ID, serta waktu ingestion yang berbeda antar kelas.

Konfigurasi fondasi yang direkomendasikan untuk eksperimen pertama adalah **URL core**: skema ternormalisasi, hostname, dan path; query dan fragment dikeluarkan secara identik pada kedua kelas sebelum pembentukan fitur maupun TF-IDF. Ini keputusan desain mitigasi, bukan klaim bahwa menghapus query menghilangkan seluruh bias.

Ketentuan eksperimen:

1. Terapkan representasi yang sama pada ingestion, validasi, test, dan inferensi. Tidak boleh training tanpa query lalu memberi model fitur query pada aplikasi.
2. Fitur panjang, entropy, keyword, dan rasio karakter dihitung setelah kebijakan representasi. Jangan menyisakan sinyal query melalui panjang URL asli atau TF-IDF teks asli.
3. Catat versi kebijakan representasi dalam manifest dan metadata analisis.
4. Pertahankan kandidat query-aware sebagai eksperimen terpisah hanya setelah memiliki URL benign lengkap dengan query yang valid, bukan parameter acak buatan untuk mempercantik distribusi.
5. Jangan menyeimbangkan panjang/path/TLD dengan membuang semua kasus sulit tanpa laporan; evaluasi pada strata asalnya tetap diperlukan.
6. Jelaskan batas kemampuan: ancaman yang hanya tampak pada parameter atau tujuan shortlink dapat terlewat oleh model URL core.

## 7. Komposisi data yang direkomendasikan

| Lapisan             | Bahan dan tujuan                                                                                   | Aturan                                                                                                         |
| ------------------- | -------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------- |
| Fondasi             | PhreshPhish train untuk baseline, CatBoost, dan XGBoost                                            | Normalisasi/privacy/URL core sama untuk kedua kelas; buat train/validasi internal berbasis waktu dan kelompok. |
| Evaluasi resmi      | PhreshPhish test dan benchmark yang disediakan                                                     | Jangan dicampur ke training; laporkan hasil URL-only dan perubahan akibat filter kita.                         |
| Generalisasi sumber | PhiUSIIL, CompPhish, atau Web page phishing detection yang lolos audit                             | Evaluasi terpisah; sumber yang berbagi feed tidak otomatis independen.                                         |
| Perubahan waktu     | Snapshot phishing terverifikasi setelah periode training, dengan negatif kontemporer yang ditinjau | Feed positif saja tidak cukup mengukur precision, FPR, atau kalibrasi.                                         |
| Indonesia           | Gold set lokal yang diobservasi dan ditinjau                                                       | Pisahkan dari training sebelum tuning; jangan hanya mengandalkan `.id`, kata brand, atau label LLM.            |
| QR                  | Gambar QR dari URL holdout yang sama, ditambah payload non-URL                                     | Menguji decoder dan kesamaan prediksi; bukan sumber kelas phishing baru.                                       |

Belum ditetapkan rasio campuran yang mengarang jumlah final. Jumlah setelah audit URL tidak valid, data sensitif, duplikasi, domain/kampanye, dan kebijakan temporal akan berbeda dari ukuran katalog. Jangan sekadar menggabungkan seluruh CSV agar jumlah data besar.

## 8. Kebutuhan lokal Indonesia yang belum terpenuhi

Penelusuran menemukan [paper SABER 2026](https://jurnal.stikes-ibnusina.ac.id/index.php/SABER/article/download/3904/3763) yang memakai 2.054 URL: 1.027 phishing dari IDADX dan 1.027 benign hasil crawling berbasis Majestic Million. Koleksinya berasal dari September 2023, meskipun paper terbit pada 2026. Berkas URL, lisensi dataset, dan mekanisme unduh publik yang memadai belum diverifikasi pada halaman/paper yang diperiksa. Paper ini belum dapat dihitung sebagai dataset yang sudah kita peroleh.

Untuk gold set Indonesia, cakupan yang perlu diukur mencakup bank/e-wallet, kurir, bantuan/hadiah, pemerintah, undangan, domain sah yang disusupi, serta tenant hosting bersama. Sertakan pembanding benign yang sulit, seperti halaman login resmi, promosi resmi, tracking paket, URL panjang, dan query sah. Sampel yang hanya terkait unduhan APK tidak otomatis berlabel phishing; label harus sesuai tugas model.

Gunakan dua peninjau independen untuk subset gold, catat dasar label dan waktu observasi, ukur kesepakatan, lalu adjudikasi konflik. Penilaian tidak meminta kredensial korban atau mengunjungi target langsung dari browser lokal. Dataset yang tidak ditemukan dalam pencarian ini bukan berarti tidak ada di mana pun; cakupan lokal tetap merupakan pekerjaan terbuka.

PhishVN dapat menguji transfer regional setelah pemeriksaan tier dan sumber, tetapi konteks Vietnam tidak menggantikan data Indonesia. Dokumentasi pemiliknya sendiri mencatat noise pada label bronze; jangan menaikkan semua tier menjadi ground truth gold.

## 9. Hak penggunaan dan akses yang perlu dibedakan

- [OpenPhish Academic Use](https://openphish.com/academic_use.html) mensyaratkan afiliasi akademik, atribusi, penggunaan nonkomersial, dan tidak membagikan data ke pihak ketiga. [Ketentuan umumnya](https://openphish.com/terms.html) juga membatasi pemanfaatan layanan. Tidak dilakukan pengajuan akun atau pengiriman pesan dalam penelitian ini.
- [PhishTank Terms](https://phishtank.org/terms.php) menunjuk ketentuan Cisco yang berlaku saat ini dan memisahkannya dari ketentuan arsip. Pernyataan pada terms lama tidak dipakai sendirian untuk menyimpulkan izin penggunaan saat ini. Dokumentasi teknis juga menyebut application key dan rate limit.
- [DeepURLBench](https://github.com/deepinstinct-algo/DeepURLBench) mencantumkan CC BY-NC 4.0. Evaluasi nonkomersial dan deployment produk harus diperlakukan sesuai batas lisensinya.
- [PhiShark](https://phishark2026dataset.com/) memerlukan persetujuan akses dan Data Use Agreement; berkasnya belum diaudit. Jumlah pada halaman rilis dan paper berbeda, sehingga versi tidak boleh dicampur.
- [Tranco](https://tranco-list.eu/) memiliki sumber komponen dengan ketentuan berbeda. Catat konfigurasi serta list ID; jangan menyalin lisensi salah satu komponen sebagai lisensi seluruh hasil turunan.

Untuk dataset turunan, catat sumber awal dan batas penggunaannya; lisensi yang ditulis pengunggah ulang tidak menghapus ketentuan sumber awal. Hal ini merupakan pemeriksaan kelayakan sumber, bukan persetujuan mengirim data atau meminta akses atas nama pengguna.

## 10. Metrik untuk standar evaluasi tinggi

Jangan memilih dataset atau model dari accuracy tertinggi. Laporkan sekurangnya:

- Recall phishing dan precision pada threshold yang dibekukan dari validasi.
- FPR pada kelas benign lengkap, benign sulit, domain baru, dan gold set Indonesia.
- Kurva precision–recall, average precision, kalibrasi, ukuran sampel, serta interval ketidakpastian.
- Hasil temporal serta domain/tenant-disjoint; duplikasi string nol tidak membuktikan kampanye tidak bocor.
- Analisis menurut asal data, waktu, hosting, URL core versus query-aware, dan contoh di luar cakupan.

Sebagai stress test matematis, pada prevalensi phishing 0,1%, recall 95%, dan FPR 1%, precision hanya sekitar 8,7%. Angka tersebut hasil perhitungan, bukan prevalensi pengguna Guardian Lab atau hasil model. Karena itu, sasaran FPR 1% pada rencana awal bukan satu-satunya standar kelulusan: ukur juga operasi 0,1% dan 0,01% bila dukungan sampel memadai, serta bandingkan beberapa base rate.

Jangan mengklaim FPR nol dari holdout kecil atau mengkalibrasi model hanya pada data seimbang buatan. Tentukan ukuran gold set dari batas FPR dan ketidakpastian yang ingin diukur, bukan angka bulat yang mudah dicapai.

## 11. Audit lanjutan sebelum training

**Pembaruan v3:** [Notebook utama](../guardian_lab_url_qr.ipynb) mencatat pengembangan multi-sumber serta perubahan peran data secara eksplisit. Hanya gold/silver PhishVN dipakai; bronze/LLM dikeluarkan. URL-Phish dipakai sebagai challenge tambahan setelah seluruh domain/URL sebelumnya dikeluarkan. Audit aset resminya menemukan 116.600 baris, 115.231 URL mentah unik, dan 1.369 duplikat persis, sedangkan katalog menyebut 111.660 URL unik. Selisih tidak dijelaskan hanya oleh duplikasi; angka katalog bukan hasil audit berkas. Tantangan tersebut dibatasi sebagai label sumber dengan bias institusi, bukan gold yang seluruh labelnya diverifikasi.

**Pembaruan implementasi:** Audit lanjutan dan training v1 sudah dijalankan. Hasil dan pengecualian ada pada [audit data](../ml/reports/data-audit.json) dan [model card](../ml/reports/model-card.md). Sumber mentah tetap 902.110 baris; 302.812 sampel digunakan untuk fitting, sedangkan validasi dan evaluasi dipisahkan. Seluruh 16 pemeriksaan otomatis akhir lulus. Gold set Indonesia, label kampanye, dan verifikasi manual seluruh label tetap belum tersedia.

- [x] Simpan metadata sumber, versi/commit, checksum, ketentuan, tanggal akses, serta label mapping.
- [x] Ekspor hanya kolom yang diperlukan, dengan sanitasi kedua kelas dan manifest hasil.
- [x] Deduplikasi ulang setelah normalisasi/sanitasi; keluarkan konflik representasi dan catat perubahan identitas akibat redaksi. Ini bukan verifikasi manual setiap label.
- [x] Audit registered-domain dan tenant berdasarkan PSL berversi dengan private suffix offline; batas identifikasi tenant/kampanye tetap dilaporkan.
- [ ] Ukur overlap URL/domain/kampanye di dalam dan antar dataset. Sumber turunan diperlakukan sebagai satu keluarga provenance.
- [x] Audit waktu dengan granularity yang tersedia; purge hari batas yang sama antara train dan test.
- [x] Uji URL core terlebih dahulu; larang fitur query terselubung pada eksperimen ini.
- [ ] Pisahkan final holdout lokal/terbaru sebelum fitting, calibration, dan pemilihan threshold.
- [ ] Verifikasi bahwa hasil parser, sanitizer, extractor, dan representasi identik pada training dan API.
- [x] Bekukan dataset, model, kalibrator, dan threshold sebelum test; terbitkan model card dengan hasil aktual serta batas kemampuan.

Untuk reproduksi audit struktur yang telah dilakukan, baca batas akses/transfer pada script, lalu jalankan:

```powershell
python scripts/research/audit_url_dataset_sources.py
python scripts/research/audit_url_dataset_sources.py --full-phresh
```

Dependensi utilitas audit yang digunakan adalah requests dan pyarrow; versi pyarrow dicatat pada JSON. Ini bukan perintah training. Mode kedua menggunakan hasil audit awal dan membaca semua shard URL tanpa kolom HTML; pembacaan dibatasi anggaran transfer. Kegagalan akses atau batas transfer tidak boleh dilaporkan sebagai audit lengkap.
