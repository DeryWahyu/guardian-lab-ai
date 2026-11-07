# Audit sumber untuk learning curve dan perbaikan kelompok URL

Audit ini mendahului fitting kandidat dalam protokol `ml/reports/v6-learning-20261106-protocol.json`. Sumber ditemukan melalui publikasi dan repositori penelitian. Tidak ada formulir akses dikirim, pihak lain dihubungi, URL target dikunjungi, HTML dijalankan, atau baris dataset ditampilkan ke LLM. File URL dibaca di memori; hanya representasi tersanitasi dan registry hash disimpan di direktori yang diabaikan Git. Sanitasi tetap heuristik, bukan jaminan anonimisasi lengkap.

## Sumber yang diperiksa

| Sumber | Bukti primer dan keputusan |
| --- | --- |
| Ebbu2017 | [Artikel Expert Systems with Applications](https://doi.org/10.1016/j.eswa.2018.09.029) dan [repositori penulis](https://github.com/ebubekirbbr/pdd). Dua JSON mencakup tepat 36.400 legitimate dan 37.175 phishing sesuai publikasi. Pin commit `90b394d8f9fb5d5dc48400e8bf46b001ce42999f`. Semua kasus baru dicadangkan untuk evaluasi; tidak ditambahkan ke fitting. Tidak ditemukan lisensi dataset eksplisit: jangan menganggap izin redistribusi atau penggunaan komersial sudah jelas. |
| ISCX-URL2016 | [Dokumentasi University of New Brunswick](https://www.unb.ca/cic/datasets/url-2016.html) membedakan benign, phishing, malware, spam dan defacement. Hanya dua file benign/phishing pada [replika benchmark peneliti GramBeddings](https://github.com/fcdalgic/GramBeddings/tree/222157e1a61a01783383d1632269ad13a7542d96/data/ISCXURL2016) yang digunakan: 35.378 dan 9.965 baris. Byte replika dipin; kesamaan dengan byte unduhan penerbit asli belum dapat dibuktikan karena akses asli memakai formulir. Lisensi MIT repositori kode tidak membuktikan hak data asal. Tidak ada klaim clearance komersial/redistribusi. |
| PILU-90K / PILU-60K | [Artikel IEEE Access](https://doi.org/10.1109/ACCESS.2022.3168681) relevan untuk legitimate login URLs. Endpoint institusi mengembalikan HTTP 403 saat audit; tidak diintake. |
| GramBeddings 800K | [Halaman penulis](https://web.cs.hacettepe.edu.tr/~selman/grambeddings-dataset/) menjelaskan pengumpulan historis dan keragaman path legitimate. Unduhan mengarah ke formulir identitas/institusi; formulir tidak dikirim. Dataset utama tidak diintake. Replika ISCX pada repositori yang sama adalah sumber berbeda. |
| PhiShark 2026 | [Halaman penerbit](https://phishark2026dataset.com/) menyediakan mekanisme akses akademik terbatas dengan permohonan/DUA. Tidak diintake. |
| Scrapio / Bridging the Gap | [Publikasi](https://arxiv.org/abs/2509.09592) dan [kode penulis](https://github.com/ShahilPatel-IITDh/scrapio) diperiksa. Kandidat benign diturunkan dari laporan PhishTank berstatus tidak valid; bukti ini belum cukup untuk menganggap semuanya legitimate. Kode pengumpul tidak dijalankan; sumber tidak ditambahkan. |
| MURL | [Mendeley V1](https://data.mendeley.com/datasets/5fk24y4xmg/1) menyebut delapan kelas tetapi mencantumkan tujuh dan tidak cukup menjelaskan asal setiap label. Tidak ditambahkan hanya karena ukurannya besar. |
| PhishLegitURLs | [Mendeley](https://data.mendeley.com/datasets/j43jtv3zzc/1) menyebut URLHaus untuk kelas phishing; kategori malware tidak otomatis berarti phishing. Tidak diintake untuk target biner ini. |
| PhishStorm | [Portal Aalto](https://doi.org/10.24342/f49465b2-c68a-4182-9171-075f0ed797d5) menyediakan sumber historis, tetapi lisensi ditandai unspecified. Dicatat sebagai sumber potensial; tidak diintake pada eksperimen ini. |

## Hasil intake aktual

Total input dua sumber adalah 118.918 baris. Sebanyak 118.038 lolos sanitizer (Ebbu 73.127; ISCX 44.911). Kurasi bersama menghapus 40.367 duplikat representasi, 59.106 kasus dengan URL/domain yang pernah terpapar dan 4.593 kasus melampaui batas lima URL per domain/private tenant. Satu kasus ISCX tambahan dikeluarkan karena domainnya ada pada sumber Ebbu yang dicadangkan untuk evaluasi. Tidak ditemukan konflik label antarrepresentasi dalam intake ini; itu bukan bukti bahwa semua label benar.

| Bagian | Total | Benign | Phishing | Domain/private tenant |
| --- | ---: | ---: | ---: | ---: |
| ISCX fitting tambahan | 3.056 | 108 | 2.948 | 2.262 |
| Ebbu eksternal, seluruhnya tidak untuk fitting | 8.849 | 2.367 | 6.482 | 6.354 |
| ISCX holdout domain | 2.066 | 70 | 1.996 | 1.497 |

Tambahan fitting memiliki 104 phishing private hosting dan 2.844 phishing non-private. Hanya ada 40 hard benign unik (panjang scheme-free >120 atau path dengan >=4 slash), termasuk 10 panjang dan 35 path dalam yang saling tumpang tindih. Arm penambahan memenuhi kriteria protokol karena private-host phishing >=100. Ini belum menutup kebutuhan hard benign dalam jumlah besar.

Novelty diperiksa terhadap registry historis, seluruh tujuh sidecar sebelumnya, cache v6 asli, identitas development/test aktual, serta semua 169.393 kasus Mendeley yang telah dicadangkan, termasuk yang belum pernah diprediksi. Sidecar baru `ml/data/exposure-sidecars/ebbu-iscx-learning-20261106.sqlite` menyimpan exposure seluruh 118.038 input tersanitasi, bukan hanya 13.971 kasus yang akhirnya dipakai. Pointer publik: `ml/provenance/ebbu-iscx-learning-exposure.json`.

Ebbu berhubungan dengan sumber benign PWD2021 yang sudah dipakai sebelumnya. Penghapusan domain/URL menutup overlap identitas yang terukur; hal itu tidak membuktikan independensi kampanye atau mekanisme pengumpulan. Holdout ISCX juga berasal dari penerbit yang sama dengan tambahan fitting. Keduanya adalah pengujian historis global berlabel penerbit, bukan gold manusia Indonesia dan bukan holdout temporal kontemporer. Angka akurasi publikasi tidak dipindahkan menjadi klaim akurasi model kita.
