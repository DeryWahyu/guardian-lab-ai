# Pembobotan domain/sumber dan kalibrasi v6

## Keputusan

Pilihan riset: `source_equal_domain_sqrt__source_equal_sigmoid`. Kandidat yang diperiksa: `source_equal_domain_sqrt__source_equal_sigmoid`. Gate development lolos: **True**. Pemilihan hanya memakai tune; semua artifact/policy dibekukan sebelum test. Layanan/notebook tetap frozen v6 asli, production_ready=false.

Kandidat lolos gate development untuk penelitian; ini belum persetujuan produksi, validasi Indonesia atau bukti kebenaran label.

Regresi recall terhadap control pada cohort berikut tetap dilaporkan: tidak ada pada angka titik yang dilaporkan; ketidakpastian dan FPR tetap perlu diperiksa.

## Data, audit dan pemisahan

Fitting tetap **616.050 URL dari sembilan sumber**. Encoder fit-only yang sama dipakai ulang dengan checksum dan real-score parity; tidak ada fitting vocabulary/scaler pada holdout. Tiga bobot classifier dan dua sigmoid calibration diuji sesuai [protokol](v6-weighted-20261105-protocol.json). Calibration dan threshold memakai partisi terpisah; source ID bukan fitur.

[Audit development](v6-weighted-development-audit.md) memeriksa 107,094 URL dan menyiapkan 170 kasus review. Selesai review manusia: **0**; tidak ada relabel otomatis atau identitas reviewer yang dibuat.

Holdout tambahan dari [rilis Zenodo V2](https://zenodo.org/records/23477065), CC BY 4.0: 12,587 URL pada 11,401 domain/tenant, 9,643 benign dan 2,944 phishing. Semua dicadangkan, tidak masuk fitting/tune/calibration/threshold. Registry historis, seluruh sidecar dan cache v6 diperiksa; audit nyata terhadap sembilan berkas menemukan nol overlap domain/digest/representasi.

Penerbit memberi label literal legitimate/phishing. Pemeriksaan skema awal menghentikan asumsi label angka; amendemen sebelum prediksi mempertahankan arti label dan jumlah kelas penerbit. Hanya tabel URL diambil lewat HTTP Range sekitar 5,1 MB dari arsip 4,5 GB; CRC dan SHA-256 CSV dipin. MD5 seluruh arsip tidak dihitung ulang. Tidak ada gambar/HTML yang diekstrak, URL target dikunjungi atau raw URL dipersistensikan.

Ini holdout penerbit global dengan domain baru; tanggal publikasi 2026 bukan tanggal observasi. Tidak ada klaim temporal holdout kontemporer, independent campaigns atau gold Indonesia. Sumber PhishTank/Tranco dan label penerbit tetap memiliki keterbatasan. Semua benchmark lain sudah teramati dan hanya pemeriksaan regresi.

## Seleksi development

| Varian | Macro recall | Minimum source recall | Macro source Brier |
| --- | ---: | ---: | ---: |
| control_native | 45.74% | 24.93% | 0.094476 |
| control_equal_calibration__source_equal_sigmoid | 45.74% | 24.93% | 0.094424 |
| source_sqrt_domain_sqrt__row_sigmoid | 47.30% | 28.15% | 0.093794 |
| source_sqrt_domain_sqrt__source_equal_sigmoid | 47.30% | 28.15% | 0.093684 |
| source_equal_domain_sqrt__row_sigmoid | 50.09% | 36.75% | 0.092034 |
| source_equal_domain_sqrt__source_equal_sigmoid | 50.09% | 36.75% | 0.091928 |
| source_sqrt_domain_class_soft__row_sigmoid | 49.38% | 34.58% | 0.093077 |
| source_sqrt_domain_class_soft__source_equal_sigmoid | 49.38% | 34.58% | 0.092959 |

Seluruh varian menggunakan representasi dan fitting rows yang sama. Kalibrasi monoton tidak menambah kemampuan ranking; manfaat kalibrasi dinilai terpisah melalui Brier. Gate dan tie-break ditetapkan sebelum fitting; jika semua gagal, control tetap dipertahankan.

## Hasil utama pada kebijakan asli/strict yang beku

FPR aktual tiap model berbeda; kebijakan strict memilih budget development per sumber, bukan menjamin FPR test yang sama.

| Cohort | URL | Recall v6 aktif | Recall control riset | Recall kandidat | FPR v6 aktif | FPR control | FPR kandidat |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| new_external_publisher_holdout | 12,587 | 52.58% | 52.79% | 56.76% | 0.88% | 0.45% | 0.41% |
| observed_pwd | 3,544 | 49.89% | 55.34% | 60.11% | 0.54% | 0.24% | 0.36% |
| observed_expanded | 11,636 | 29.86% | 46.74% | 48.08% | 2.53% | 0.93% | 0.96% |
| observed_vendor | 20,000 | 46.31% | 43.65% | 47.31% | 0.94% | 0.64% | 0.90% |
| observed_phishtank_positive | 9,269 | 46.53% | 43.53% | 46.81% | Tidak tersedia | Tidak tersedia | Tidak tersedia |
| observed_legitphish | 42,716 | 66.01% | 69.55% | 73.59% | 0.00% | 0.00% | 0.00% |

### Counts, precision sampel dan ketidakpastian kandidat

| Cohort | TP | FN | FP | TN | Precision | Domain recall 95% | Domain FPR 95% | Wilson FPR 95% |
| --- | ---: | ---: | ---: | ---: | ---: | --- | --- | --- |
| new_external_publisher_holdout | 1671 | 1273 | 40 | 9603 | 97.66% | [54.89%; 58.65%] | [0.29%; 0.56%] | [0.30%; 0.56%] |
| observed_pwd | 1136 | 754 | 6 | 1648 | 99.47% | [57.48%; 63.05%] | [0.12%; 0.68%] | [0.17%; 0.79%] |
| observed_expanded | 4035 | 4358 | 31 | 3212 | 99.24% | [46.88%; 49.33%] | [0.65%; 1.31%] | [0.67%; 1.35%] |
| observed_vendor | 1046 | 1165 | 160 | 17629 | 86.73% | [45.19%; 49.57%] | [0.77%; 1.05%] | [0.77%; 1.05%] |
| observed_phishtank_positive | 4339 | 4930 | 0 | 0 | Tidak tersedia | [45.70%; 47.89%] | Tidak tersedia | Tidak tersedia |
| observed_legitphish | 31412 | 11276 | 0 | 28 | 100.00% | [73.00%; 74.13%] | [0.00%; 0.00%] | [0.00%; 12.06%] |

Bootstrap 1.000 domain/private tenants bersifat kondisional pada label penerbit dan tidak mengoreksi semua perbandingan eksploratif. Wilson row-IID mengabaikan korelasi domain/kampanye. PhishTank positif saja tidak menyediakan FPR/accuracy/precision trafik. LegitPhish hanya memiliki 28 benign; nol FP dan bootstrap degenerat tetap tidak menjamin FPR rendah (Wilson upper 95% sekitar 12,06% untuk 0/28). Precision sampel bukan precision trafik Indonesia.

Pada holdout penerbit baru, interval berpasangan 95% kandidat dikurangi control riset adalah recall [+3.15; +4.80] percentage point dan FPR [-0.135; +0.073] percentage point. Interval recall mendukung peningkatan; interval FPR masih mencakup nol, sehingga penurunan tiga FP belum bukti kuat perbaikan FPR terhadap control.

### Kalibrasi: control riset menuju kandidat

| Cohort | Brier control → kandidat | ECE control → kandidat | ROC AUC control → kandidat |
| --- | ---: | ---: | ---: |
| new_external_publisher_holdout | 0.136421 → 0.120153 | 0.214614 → 0.187055 | 0.927712 → 0.940538 |
| observed_pwd | 0.065670 → 0.062570 | 0.028514 → 0.019924 | 0.972573 → 0.973750 |
| observed_expanded | 0.109356 → 0.109331 | 0.032396 → 0.039901 | 0.910398 → 0.912251 |
| observed_vendor | 0.098732 → 0.106149 | 0.168058 → 0.174878 | 0.944463 → 0.941939 |
| observed_phishtank_positive | Tidak tersedia | Tidak tersedia | Tidak tersedia |
| observed_legitphish | 0.023614 → 0.021093 | 0.074780 → 0.062537 | 0.996310 → 0.996678 |

Brier/ECE lebih kecil lebih baik; ROC AUC lebih besar lebih baik. Skor tetap terkalibrasi pada campuran penelitian, bukan probabilitas trafik Indonesia.
Kalibrasi vendor memburuk dibanding control riset meskipun recall meningkat. Pada diagnosis development, FPR private hosting, URL panjang dan kelompok punycode juga naik. Karena itu keuntungan recall tidak dianggap peningkatan menyeluruh pada setiap aspek; support dan interval kelompok kecil tetap diperhatikan.

## Diagnosis struktur pada tune setelah seleksi

Analisis ini eksploratif setelah pilihan dibekukan, tidak dipakai mengubah pilihan atau threshold.

| Struktur | Nilai | Benign | Phishing | Recall control → kandidat | FPR control → kandidat | Wilson FPR kandidat 95% |
| --- | --- | ---: | ---: | ---: | ---: | --- |
| long_url | False | 60705 | 45745 | 42.77% → 44.30% | 0.28% → 0.39% | [0.35%; 0.45%] |
| long_url | True | 315 | 329 | 10.94% → 13.98% | 0.63% → 1.27% | [0.49%; 3.22%] |
| deep_path | False | 56899 | 43065 | 43.30% → 44.54% | 0.30% → 0.41% | [0.36%; 0.47%] |
| deep_path | True | 4121 | 3009 | 31.74% → 37.52% | 0.07% → 0.22% | [0.11%; 0.41%] |
| private_hosting | False | 59980 | 37043 | 31.56% → 33.36% | 0.24% → 0.34% | [0.30%; 0.39%] |
| private_hosting | True | 1040 | 9031 | 87.60% → 88.06% | 3.17% → 3.56% | [2.59%; 4.87%] |
| punycode | False | 60978 | 46020 | 42.58% → 44.11% | 0.29% → 0.40% | [0.35%; 0.45%] |
| punycode | True | 42 | 54 | 16.67% → 20.37% | 0.00% → 2.38% | [0.42%; 12.32%] |
| redacted | False | 57395 | 44507 | 43.03% → 44.48% | 0.30% → 0.41% | [0.36%; 0.46%] |
| redacted | True | 3625 | 1567 | 28.91% → 32.67% | 0.08% → 0.22% | [0.11%; 0.43%] |

## Kebijakan tambahan yang telah ditentukan sebelum test

Pooled 1% hanya analisis trade-off; tidak mengikat FPR per sumber atau test. Tidak ada threshold dipilih dari hasil di bawah.

### new_external_publisher_holdout

| Kebijakan | Recall | FPR | Precision sampel |
| --- | ---: | ---: | ---: |
| active_original | 52.58% | 0.88% | 94.79% |
| active_matched | 22.76% | 0.01% | 99.85% |
| control_strict | 52.79% | 0.45% | 97.31% |
| candidate_strict | 56.76% | 0.41% | 97.66% |
| control_pooled | 65.49% | 1.50% | 93.01% |
| candidate_pooled | 65.66% | 1.00% | 95.27% |

### observed_pwd

| Kebijakan | Recall | FPR | Precision sampel |
| --- | ---: | ---: | ---: |
| active_original | 49.89% | 0.54% | 99.05% |
| active_matched | 11.27% | 0.00% | 100.00% |
| control_strict | 55.34% | 0.24% | 99.62% |
| candidate_strict | 60.11% | 0.36% | 99.47% |
| control_pooled | 68.31% | 0.54% | 99.31% |
| candidate_pooled | 69.31% | 0.54% | 99.32% |

### observed_expanded

| Kebijakan | Recall | FPR | Precision sampel |
| --- | ---: | ---: | ---: |
| active_original | 29.86% | 2.53% | 96.83% |
| active_matched | 7.28% | 0.03% | 99.84% |
| control_strict | 46.74% | 0.93% | 99.24% |
| candidate_strict | 48.08% | 0.96% | 99.24% |
| control_pooled | 62.43% | 2.47% | 98.50% |
| candidate_pooled | 58.49% | 2.00% | 98.69% |

### observed_vendor

| Kebijakan | Recall | FPR | Precision sampel |
| --- | ---: | ---: | ---: |
| active_original | 46.31% | 0.94% | 85.91% |
| active_matched | 8.46% | 0.06% | 94.44% |
| control_strict | 43.65% | 0.64% | 89.52% |
| candidate_strict | 47.31% | 0.90% | 86.73% |
| control_pooled | 59.02% | 1.91% | 79.38% |
| candidate_pooled | 58.71% | 1.92% | 79.19% |

### observed_phishtank_positive

| Kebijakan | Recall | FPR | Precision sampel |
| --- | ---: | ---: | ---: |
| active_original | 46.53% | Tidak tersedia | Tidak tersedia |
| active_matched | 17.67% | Tidak tersedia | Tidak tersedia |
| control_strict | 43.53% | Tidak tersedia | Tidak tersedia |
| candidate_strict | 46.81% | Tidak tersedia | Tidak tersedia |
| control_pooled | 56.68% | Tidak tersedia | Tidak tersedia |
| candidate_pooled | 55.81% | Tidak tersedia | Tidak tersedia |

### observed_legitphish

| Kebijakan | Recall | FPR | Precision sampel |
| --- | ---: | ---: | ---: |
| active_original | 66.01% | 0.00% | 100.00% |
| active_matched | 0.82% | 0.00% | 100.00% |
| control_strict | 69.55% | 0.00% | 100.00% |
| candidate_strict | 73.59% | 0.00% | 100.00% |
| control_pooled | 89.48% | 0.00% | 100.00% |
| candidate_pooled | 87.37% | 0.00% | 100.00% |

## Keterbatasan dan bukti

Tidak ada dua reviewer manusia independen, gold Indonesia atau adjudikasi baru yang selesai. Minimum 1.000 phishing/3.000 benign saja tidak memenuhi gate. Layanan tetap shadow dan LOW tidak berarti SAFE. Binary/metadata/threshold v6 asli tetap utuh; seluruh kandidat turunan mewarisi batas penelitian nonkomersial.

Save/reload 130 probe nyata/sintetis: delta maksimum 0.0. Parity cache/inference: 0.0. Tes teknis tidak membuktikan label benar atau model siap produksi.

- [JSON lengkap](v6-weighted-evaluation.json), [grafik](v6-weighted-evaluation.png), [verifikasi](v6-weighted-verification.json).
- [Prosedur dan sumber](../../ai-agent-docs/v6-weighted-experiment.md), [diagnosis subgroup](v6-weighted-subgroup-diagnostics.json).
- [Intake asli](v6-weighted-holdout-intake-protocol.json), [inspeksi skema](v6-weighted-holdout-schema-inspection.json), [amendemen sebelum prediksi](v6-weighted-holdout-intake-amended.json), [exposure](../provenance/zenodo-websites-v2-exposure.json).
