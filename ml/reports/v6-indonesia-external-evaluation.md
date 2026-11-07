# Evaluasi eksternal v6 dan audit subset `.id`

Tanggal: 6 November 2026. **Model belum siap produksi. Pengujian Indonesia independen dengan label manusia belum selesai.** Pengujian yang terlaksana adalah benchmark eksternal pada domain baru dengan label penerbit, termasuk subset `.id`. Tidak ada training, perubahan threshold atau pemilihan model dari hasil ini; v6 aktif tetap asli.

## Data dan independensi

[Rilis Mendeley V1](https://data.mendeley.com/datasets/vfszbj9b36/1), DOI 10.17632/vfszbj9b36.1, menyediakan 450.176 URL berlabel, diterbitkan 2 April 2024 dengan CC BY 4.0. Label penerbit berasal dari PhishTank, Majestic Million dan sumber lain; tanggal observasi serta review per kasus tidak tersedia. Ini bukan trafik Indonesia kontemporer atau jaminan kepemilikan/keamanan URL.

- 446.068 baris lolos parser/sanitasi; 4.108 ditolak. Raw CSV diproses di memori, tidak disimpan; tidak ada URL target yang dikunjungi.
- Penolakan mencakup 559 dari 345.738 benign (0,162%) dan 3.549 dari 104.438 phishing (3,398%). Metrik berikut bersyarat pada input yang didukung dan lolos kurasi; penolakan tidak dihitung sebagai prediksi benar atau label aman.
- Dikeluarkan 154 baris dari dua representasi konflik, 58.478 duplikat konsisten, 175.534 overlap URL/representasi/domain dan 42.509 baris karena batas lima URL/domain.
- Tersisa **169.393 URL dari 119.683 domain/private tenant**, semuanya dicadangkan untuk test: 103.209 benign dan 66.184 phishing.
- Pengujian global memakai **50.000 digest terkecil**, dengan 30.627 benign dan 19.373 phishing pada 40.530 domain.
- Pengujian `.id` memakai seluruh **306 URL pada 186 domain**: 8 benign dan 298 phishing. Sebanyak 82 baris juga ada dalam cohort global; kedua hasil tidak boleh dijumlahkan sebagai dua sampel independen. Total unik yang diprediksi 50.224.

Penyaringan memeriksa registry historis, keenam sidecar sebelum intake, cache v6 asli, empat partisi development terkini, fit tambahan StealthPhisher, serta kedelapan cohort test yang sudah teramati. Domain baru tidak membuktikan kampanye independen atau sumber upstream berbeda. Semua 446.068 input supported kini dicatat pada sidecar baru, termasuk yang dikeluarkan dan yang tidak diprediksi.

[Protokol](v6-indonesia-external-20261106-protocol.json) menetapkan model, ambang, sampling dan subgroup sebelum intake/prediksi. Skema literal label diperiksa dan diamendemen sebelum scoring. Tidak ada fitting transformasi, kalibrasi, threshold atau penentuan pemenang menggunakan test.

## Hasil utama pada threshold yang dibekukan

`Kandidat riset` di bawah adalah kandidat pembobotan yang sudah dipertahankan dari eksperimen sebelumnya, bukan model baru yang dilatih pada turn ini. Ia tidak menggantikan layanan v6.

| Cohort | Model | TP / FN | FP / TN | Recall | FPR | Precision sampel |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| Global 50.000 | v6 aktif | 4.977 / 14.396 | 14 / 30.613 | 25,69% | 0,0457% | 99,72% |
| Global 50.000 | Kandidat riset | 5.812 / 13.561 | 16 / 30.611 | 30,00% | 0,0522% | 99,73% |
| Proxy `.id`, 306 | v6 aktif | 115 / 183 | 0 / 8 | 38,59% | 0/8 | 100% |
| Proxy `.id`, 306 | Kandidat riset | 122 / 176 | 0 / 8 | 40,94% | 0/8 | 100% |

Precision di tabel mengikuti prevalensi dan label cohort. Precision 100% pada subset dengan hanya delapan benign **bukan** bukti precision trafik Indonesia atau model yang aman. Kandidat masih melewatkan **176 dari 298 phishing** pada subset `.id`.

| Ketidakpastian 95% | v6 aktif | Kandidat riset |
| --- | ---: | ---: |
| Recall global, Wilson row-IID | 25,08–26,31% | 29,36–30,65% |
| FPR global, Wilson row-IID | 0,0272–0,0767% | 0,0322–0,0849% |
| Recall `.id`, Wilson row-IID | 33,24–44,23% | 35,51–46,60% |
| Recall `.id`, bootstrap domain | 30,81–46,21% | 32,69–48,76% |
| FPR `.id`, Wilson row-IID | 0–32,44% | 0–32,44% |

Bootstrap domain berpasangan sebanyak 1.000 pengulangan memberi delta recall kandidat terhadap v6 **+3,83 sampai +4,78 percentage point** pada global, dan **−1,80 sampai +6,72 percentage point** pada `.id`. Interval `.id` mencakup nol: keunggulan regional belum meyakinkan. Untuk `.id`, 997 pengulangan memuat kedua kelas; tiga pengulangan tanpa benign dikeluarkan. Bootstrap FPR yang menghasilkan [0,0] akibat tidak ada FP teramati tidak boleh dianggap kepastian FPR nol; Wilson menunjukkan lemahnya dukungan delapan benign. Independensi kampanye dan ketepatan label tetap belum terbukti.

## Kalibrasi dan kelompok sulit

| Cohort | Brier v6 → riset | ECE 10 bin v6 → riset |
| --- | ---: | ---: |
| Global | 0,112897 → 0,096128 | 0,059382 → 0,032857 |
| Proxy `.id` | 0,138982 → 0,105972 | 0,253635 → 0,192052 |

Nilai lebih kecil menunjukkan perbaikan skor pada cohort tersebut, bukan probabilitas terkalibrasi untuk trafik Indonesia.

| Subgroup global | Benign / phishing | Recall v6 → riset | FPR v6 → riset |
| --- | ---: | ---: | ---: |
| URL >120 karakter tanpa scheme | 179 / 127 | 44,09 → 49,61% | 0/179 → 0/179 |
| Path dengan ≥4 slash | 3.463 / 5.514 | 41,89 → 49,49% | 0/3.463 → 2/3.463 |
| Private hosting | 1.900 / 349 | **28,94 → 19,77%** | 4/1.900 → 2/1.900 |
| Di luar private hosting | 28.727 / 19.024 | 25,63 → 30,19% | 10/28.727 → 14/28.727 |

Kandidat mengalami regresi recall private hosting meskipun recall global meningkat. Subset `.id` tidak memiliki benign panjang/path dalam atau private-hosting, sehingga tidak menutup celah validasi tersebut. Pada global, nol FP dari 179 benign panjang masih memiliki Wilson upper sekitar 2,10%.

## Keputusan dan pekerjaan yang masih memerlukan bukti

1. **Tidak mempromosikan model.** Recall masih jauh dari release gate; gate meminta batas bawah recall 95% ≥85% dan batas atas FPR ≤1%, bersama bukti label, relevansi, waktu, privasi, hak penggunaan dan regresi.
2. **Status Indonesia gold belum tersedia.** [Census aktual](v6-indonesia-evidence-status.json) menemukan lima CSV Indonesia masih kosong dan 170 kasus development belum memiliki pasangan review lengkap. Pengguna menyatakan belum ada reviewer. Suffix `.id` tidak menggantikan review konteks Indonesia, termasuk serangan pada `.com`/hosting privat.
3. [Audit sumber primer](../../ai-agent-docs/research/indonesia-independent-source-audit-20261106.md) menemukan penelitian regional yang relevan, tetapi belum memperoleh rilis URL berlabel dengan bukti yang memenuhi protokol. Langkah yang diperlukan adalah akses dataset regional berizin beserta bukti labelnya, atau dua reviewer nyata dengan pengumpulan kasus kedua kelas pada periode sebanding. Target awal tetap 1.000 phishing/3.000 benign; jumlah minimum saja tidak cukup.
4. Hasil baru mengarahkan pengembangan berikutnya pada phishing di domain biasa dan regresi private hosting. Data test ini tetap dicadangkan; jangan memasukkannya ke training atau memilih threshold yang mengoptimalkan hasilnya. Data pengembangan tambahan harus terpisah dan benar-benar mengandung benign panjang/path dalam.

API/notebook tetap frozen v6, `production_ready=false`, untuk riset/internal shadow. LOW tidak berarti aman. Batas riset nonkomersial dari provenance training asli juga tetap berlaku; lisensi CC BY rilis test ini tidak mengubah lisensi artifact.

## Audit teknis dan replay

Hasil lengkap: [JSON beku](v6-indonesia-external-evaluation.json), [verifikasi](v6-indonesia-external-verification.json), [status bukti manusia](v6-indonesia-evidence-status.json). Data, prediksi, model dan sidecar tetap lokal/diabaikan Git. Dokumentasi metode ada di [panduan eksperimen](../../ai-agent-docs/v6-indonesia-external-evaluation.md).

Verifikasi akhir: **202 tes lulus**, nol gagal/error/skip; lint dan pemeriksaan format pada 78 berkas lulus. Pemeriksaan ulang 169.393 baris reserved terhadap 21 registry/sidecar/cache menemukan nol overlap identitas/domain dengan paparan sebelum intake. Seluruh supported inputs terdaftar pada sidecar baru. Reload kedua artifact pada 128 probe per cohort menghasilkan delta prediksi nol; binary, metadata dan threshold v6 asli tidak berubah. Kelulusan teknis ini tidak memenuhi kekurangan label atau recall Indonesia.

Audit metadata pascaprediksi memperbaiki dua hal tanpa mengubah hasil model: tes replay historis semula menolak tambahan sidecar yang sah; loader khusus parity sekarang mengizinkan penambahan sambil tetap menolak penghapusan/perubahan setiap hash historis. Guard eksperimen lama, kode dan protokol bekunya tidak diubah. Selain itu, census awal evaluator mencari nama CSV tanpa awalan `indonesia-`; [census tambahan](v6-indonesia-evidence-status.json) menggantikannya dengan pemeriksaan nama/schema aktual. Laporan numerik awal dipertahankan untuk jejak audit. Kedua koreksi memiliki tes regresi.
