# Eksperimen fitur URL terpisah, kalibrasi dan data terarah

Kandidat riset yang dipertahankan: `control_native`. Challenger yang diuji: `segmented_text__source_equal_beta`. Gate development lolos: **False**. Semua pilihan dan threshold dibekukan dari development sebelum final scoring. V6 aktif tidak diganti, production_ready=false.

Jika control_native dipertahankan, hasil challenger berikut adalah diagnosis kandidat gagal-gate, bukan bukti model pengganti telah disetujui. Seluruh benchmark lama, termasuk Zenodo websites V2, tetap berstatus teramati.

## Data dan metode

Tiga ablation memakai 616.050 URL fitting yang sama dari sembilan sumber: tambahan struktur numerik, teks host/subdomain/path terpisah, dan gabungan keduanya. Encoder dasar dipakai ulang tanpa refit; vocabulary/scaler tambahan di-fit hanya pada fitting asli. Arm augmentation terpisah memakai tambahan data baru tanpa refit encoder pada holdout. Semua classifier tetap Logistic Regression C=2/liblinear, dengan source/domain weighting yang sama dan sigmoid atau beta calibration monoton pada calibration terpisah.

[StealthPhisher](https://data.mendeley.com/datasets/m2479kmybx/1), CC BY 4.0: 336,749 baris mentah, 318,429 didukung setelah sanitasi, 87,229 URL baru setelah konflik/duplikat/exposure/domain cap. Literal Phishing/Legitimate mengikuti penerbit; tidak ada label diganti berdasarkan model.

| Alokasi StealthPhisher | URL | Benign | Phishing | Domain/tenant |
| --- | ---: | ---: | ---: | ---: |
| fit | 52,334 | 39,992 | 12,342 | 50,466 |
| new_test | 34,895 | 26,578 | 8,317 | 33,620 |

Arm augmentation memiliki 668.384 URL fitting dari sepuluh sumber. Partisi calibration, threshold dan tune tetap sama dengan control, sehingga sumber tambahan belum diwakili dalam calibration. Holdout StealthPhisher adalah domain baru dari penerbit yang juga dipakai oleh salah satu arm, bukan independent-source benchmark untuk arm tersebut. Tanggal penerbitan Januari 2025 bukan tanggal observasi tiap kasus atau bukti benign kontemporer.

[Audit coverage](v6-segmented-data-coverage.json) menemukan nol benign tambahan dengan URL >120 karakter atau path sedalam empat slash, dan hanya 43 benign private hosting. Ada 9.334 phishing tambahan di luar private hosting. Data membantu cakupan domain biasa, tetapi belum menutup gap hard benign/path panjang; holdout Stealth juga tidak memiliki URL >120 karakter. Bias ini membatasi klaim generalisasi hasil sumber baru.

[PhishBench-External V2](https://data.mendeley.com/datasets/2ctjcnm9kn/2), CC BY 4.0, menyediakan pengujian penerbit tambahan yang seluruhnya dicadangkan. Pemeriksaan awal mencatat kegagalan integritas; retry kemudian cocok tepat dengan pin byte/SHA penerbit. CSV memakai kolom Results, bukan label; amendemen sebelum prediksi memetakan 0=benign/1=phishing sesuai dokumentasi, setelah menghitung 500 kasus masing-masing. Setelah sanitasi/exposure tersisa 272 URL: 270 phishing dan **hanya dua benign**. Tidak ada label dibuat dari prediksi atau nama institusi.

Seluruh input tersanitasi, termasuk exclusions, fitting dan holdout, terdaftar dalam sidecar. Historical registry, setiap sidecar, cache v6 dan identitas nyata seluruh partisi/benchmark lama diaudit sebelum fitting. URL target tidak dikunjungi, HTML tidak dieksekusi, raw URL tidak disimpan. Redaksi tetap heuristik, bukan anonimisasi sempurna.

## Seleksi development

Gate mempertahankan peningkatan recall tanpa regresi besar pada FPR dan Brier per sumber. Brier mengukur kualitas probabilitas gabungan, bukan kalibrasi murni; ECE dan reliability bins juga dilaporkan. Kalibrasi monoton sendiri tidak meningkatkan ranking. Semua kriteria ada dalam protokol sebelum fitting; hasil test tidak dipakai memilih pemenang.

| Varian | Macro source recall | Minimum source recall | Macro source Brier | Lolos gate |
| --- | ---: | ---: | ---: | --- |
| control_native | 50.09% | 36.75% | 0.091928 | Control |
| control_beta__source_equal_beta | 50.09% | 36.75% | 0.091579 | False |
| structure__source_equal_sigmoid | 50.47% | 35.92% | 0.090299 | False |
| structure__source_equal_beta | 50.47% | 35.92% | 0.089898 | False |
| segmented_text__source_equal_sigmoid | 50.61% | 34.58% | 0.091379 | False |
| segmented_text__source_equal_beta | 50.61% | 34.58% | 0.090908 | False |
| segmented_text_structure__source_equal_sigmoid | 50.32% | 34.58% | 0.089851 | False |
| segmented_text_structure__source_equal_beta | 50.32% | 34.58% | 0.089325 | False |
| segmented_text_structure_augmented__source_equal_sigmoid | 50.06% | 33.78% | 0.088896 | False |
| segmented_text_structure_augmented__source_equal_beta | 50.06% | 33.78% | 0.088479 | False |

### Regresi development per sumber

| Varian | Macro recall delta, point | Worst recall delta, point | Worst FPR increase, point | Worst Brier increase |
| --- | ---: | ---: | ---: | ---: |
| control_beta__source_equal_beta | +0.000 | +0.000 | +0.000 | +0.002215 |
| structure__source_equal_sigmoid | +0.387 | -1.072 | +0.476 | +0.001463 |
| structure__source_equal_beta | +0.387 | -1.072 | +0.476 | +0.001950 |
| segmented_text__source_equal_sigmoid | +0.522 | -2.413 | +0.060 | +0.004163 |
| segmented_text__source_equal_beta | +0.522 | -2.413 | +0.060 | +0.005302 |
| segmented_text_structure__source_equal_sigmoid | +0.234 | -2.413 | +0.033 | +0.002868 |
| segmented_text_structure__source_equal_beta | +0.234 | -2.413 | +0.033 | +0.004104 |
| segmented_text_structure_augmented__source_equal_sigmoid | -0.031 | -3.217 | +0.020 | +0.001305 |
| segmented_text_structure_augmented__source_equal_beta | -0.031 | -3.217 | +0.020 | -0.000110 |

## Pengujian beku

Strict berarti budget development 1% per sumber yang cukup support; FPR test tiap model dapat berbeda. Active memakai threshold warning asli. Precision adalah precision sampel, bukan precision trafik Indonesia.

| Cohort | URL | Recall aktif | Recall control | Recall challenger | FPR control | FPR challenger |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| new_phishbench_publisher_holdout | 272 | 53.33% | 56.67% | 58.52% | 0.0000% | 0.0000% |
| new_stealth_domain_holdout | 34,895 | 58.49% | 60.51% | 61.83% | 0.0038% | 0.0075% |
| observed_zenodo_websites_v2 | 12,587 | 52.58% | 56.76% | 57.61% | 0.4148% | 0.4563% |
| observed_pwd | 3,544 | 49.89% | 60.11% | 62.33% | 0.3628% | 0.3628% |
| observed_expanded | 11,636 | 29.86% | 48.08% | 48.55% | 0.9559% | 0.8634% |
| observed_vendor | 20,000 | 46.31% | 47.31% | 48.85% | 0.8994% | 0.9163% |
| observed_phishtank_positive | 9,269 | 46.53% | 46.81% | 48.52% | Tidak tersedia | Tidak tersedia |
| observed_legitphish | 42,716 | 66.01% | 73.59% | 81.52% | 0.0000% | 0.0000% |

### Counts dan ketidakpastian challenger

| Cohort | TP | FN | FP | TN | Precision | Recall domain 95% | FPR domain 95% | FPR Wilson 95% |
| --- | ---: | ---: | ---: | ---: | ---: | --- | --- | --- |
| new_phishbench_publisher_holdout | 158 | 112 | 0 | 2 | 100.00% | [52.22%; 65.55%] | [0.0000%; 0.0000%] | [0.0000%; 65.7620%] |
| new_stealth_domain_holdout | 5142 | 3175 | 2 | 26576 | 99.96% | [60.58%; 63.03%] | [0.0000%; 0.0189%] | [0.0021%; 0.0274%] |
| observed_zenodo_websites_v2 | 1696 | 1248 | 44 | 9599 | 97.47% | [55.74%; 59.43%] | [0.3226%; 0.6003%] | [0.3401%; 0.6119%] |
| observed_pwd | 1178 | 712 | 6 | 1648 | 99.49% | [59.73%; 65.29%] | [0.1207%; 0.6983%] | [0.1664%; 0.7892%] |
| observed_expanded | 4075 | 4318 | 28 | 3215 | 99.32% | [47.35%; 49.75%] | [0.5773%; 1.1965%] | [0.5980%; 1.2450%] |
| observed_vendor | 1080 | 1131 | 163 | 17626 | 86.89% | [46.64%; 51.13%] | [0.7900%; 1.0523%] | [0.7865%; 1.0673%] |
| observed_phishtank_positive | 4497 | 4772 | 0 | 0 | Tidak tersedia | [47.42%; 49.60%] | Tidak tersedia | Tidak tersedia |
| observed_legitphish | 34801 | 7887 | 0 | 28 | 100.00% | [81.01%; 81.98%] | [0.0000%; 0.0000%] | [0.0000%; 12.0643%] |

Bootstrap 1.000 domain/private tenants bersifat kondisional pada label penerbit dan tidak membuktikan kampanye independen. Wilson row-IID mengabaikan korelasi domain. **Dua benign pada PhishBench tidak cukup untuk menilai FPR**; nol FP sekalipun memiliki upper Wilson 95% sekitar 65,76%. LegitPhish memiliki hanya 28 benign; nol FP memberi upper sekitar 12,06%. PhishTank positif saja tidak menyediakan FPR/accuracy/precision trafik.

### Perbedaan berpasangan terhadap control riset

| Cohort | Recall delta domain 95%, percentage point | FPR delta domain 95%, percentage point |
| --- | --- | --- |
| new_phishbench_publisher_holdout | [-0.37; +4.01] | [+0.0000; +0.0000] |
| new_stealth_domain_holdout | [+0.80; +1.78] | [-0.0075; +0.0188] |
| observed_zenodo_websites_v2 | [+0.14; +1.62] | [-0.0412; +0.1257] |
| observed_pwd | [+1.14; +3.30] | [-0.1798; +0.1804] |
| observed_expanded | [+0.05; +0.89] | [-0.2780; +0.0923] |
| observed_vendor | [+0.54; +2.59] | [-0.0620; +0.1063] |
| observed_phishtank_positive | [+1.24; +2.17] | Tidak tersedia |
| observed_legitphish | [+7.64; +8.25] | [+0.0000; +0.0000] |

Interval selisih yang mencakup nol tidak mendukung klaim perbedaan pasti. Angka delta di atas bersatuan percentage point dan tetap kondisional pada label penerbit.

### Kualitas skor: control menuju challenger

| Cohort | Brier | ECE 10 bin | ROC AUC |
| --- | ---: | ---: | ---: |
| new_phishbench_publisher_holdout | 0.055086 → 0.059838 | 0.128116 → 0.126237 | 0.974074 → 0.987037 |
| new_stealth_domain_holdout | 0.051211 → 0.052526 | 0.104004 → 0.109156 | 0.973662 → 0.972027 |
| observed_zenodo_websites_v2 | 0.120153 → 0.111018 | 0.187055 → 0.181431 | 0.940538 → 0.944673 |
| observed_pwd | 0.062570 → 0.061308 | 0.019924 → 0.015549 | 0.973750 → 0.974747 |
| observed_expanded | 0.109331 → 0.107934 | 0.039901 → 0.041122 | 0.912251 → 0.915283 |
| observed_vendor | 0.106149 → 0.099919 | 0.174878 → 0.170372 | 0.941939 → 0.945161 |
| observed_phishtank_positive | Tidak tersedia | Tidak tersedia | Tidak tersedia |
| observed_legitphish | 0.021093 → 0.019601 | 0.062537 → 0.043755 | 0.996678 → 0.996627 |

## Kebijakan pooled tambahan

Seluruh threshold pooled dibekukan dari threshold partition sebelum test; tidak dipilih dari tabel ini.

| Cohort | Recall control pooled | FPR control pooled | Recall challenger pooled | FPR challenger pooled |
| --- | ---: | ---: | ---: | ---: |
| new_phishbench_publisher_holdout | 64.81% | 0.0000% | 67.04% | 0.0000% |
| new_stealth_domain_holdout | 68.88% | 0.0263% | 69.76% | 0.0376% |
| observed_zenodo_websites_v2 | 65.66% | 0.9955% | 67.43% | 1.0370% |
| observed_pwd | 69.31% | 0.5441% | 70.58% | 0.6046% |
| observed_expanded | 58.49% | 2.0043% | 59.88% | 1.7885% |
| observed_vendor | 58.71% | 1.9169% | 59.84% | 1.8607% |
| observed_phishtank_positive | 55.81% | Tidak tersedia | 57.59% | Tidak tersedia |
| observed_legitphish | 87.37% | 0.0000% | 89.84% | 0.0000% |

## Struktur URL pada tune

Diagnosis setelah seleksi dibekukan; tidak mengubah pilihan atau threshold.

| Kelompok | Benign | Phishing | Recall control → challenger | FPR control → challenger | FPR challenger Wilson 95% |
| --- | ---: | ---: | ---: | ---: | --- |
| long_url | 315 | 329 | 13.98% → 11.85% | 1.27% → 1.27% | [0.49%; 3.22%] |
| deep_path | 4121 | 3009 | 37.52% → 38.65% | 0.22% → 0.29% | [0.17%; 0.51%] |
| private_hosting | 1040 | 9031 | 88.06% → 87.76% | 3.56% → 3.56% | [2.59%; 4.87%] |
| punycode | 42 | 54 | 20.37% → 22.22% | 2.38% → 0.00% | [0.00%; 8.38%] |
| redacted | 3625 | 1567 | 32.67% → 33.89% | 0.22% → 0.28% | [0.15%; 0.51%] |
| non_private_hosting | 59980 | 37043 | 33.36% → 34.46% | 0.34% → 0.36% | [0.32%; 0.41%] |

## Review, privasi dan keputusan

Antrean development: 170 kasus, 0 pasangan review lengkap. Pengguna menyatakan belum ada reviewer. Berkas Indonesia aktual tetap kosong; agent tidak membuat reviewer, adjudikasi atau label Indonesia. Pemeriksa baru menolak pack tidak blind, locator tertukar dan klaim independensi hanya dari dua file/ID.

Saved-model parity 130 kasus: delta 0.0; cache/inference delta 0.0. Kelulusan tes teknis bukan bukti kebenaran label atau kesiapan produksi. Binary, metadata, dependency dan threshold asli v6 tetap utuh. LOW bukan SAFE.

[JSON lengkap](v6-segmented-evaluation.json), [protokol](v6-segmented-20261105-protocol.json), [amendemen sumber](v6-segmented-source-amendment.json), [review aktual](v6-segmented-human-review-status.json), [grafik](v6-segmented-evaluation.png).
