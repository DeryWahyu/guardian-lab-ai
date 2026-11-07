# Eksperimen terarah v6: sumber data dan batas peringatan

## Keputusan

Kandidat `expanded_plus_pwd2021` dipilih hanya pada tune; fitting 616,050 URL. Gate peningkatan development: **True**. Artifact baru tetap riset nonkomersial, production_ready=false. Layanan dan notebook utama tetap frozen v6 asli.

Recall kebijakan utama menurun terhadap v6 aktif pada benchmark teramati berikut: observed_vendor, observed_phishtank_positive. Karena itu belum ada peningkatan menyeluruh.

## Data dan provenance

PWD2021 dari [rilis peneliti Mendeley V1](https://data.mendeley.com/datasets/n96ncsr5g4/1) menyediakan 80.000 URL (50.000 benign/30.000 phishing), CC BY 4.0. SQL diparse sebagai literal tanpa dieksekusi; HTML tidak diambil. Ini label penerbit global historis 2020–2021, bukan gold Indonesia atau review manusia independen per kasus. [Audit sumber tambahan](../../ai-agent-docs/research/v6-targeted-source-audit-20261105.md) menjelaskan sumber jurnal lain yang diperiksa dan alasan tidak digunakan.

78.102 URL lolos sanitasi; 109 baris berlabel konflik dikarantina, 5998 duplikat konsisten dikeluarkan, 36989 URL/domain terpapar sebelumnya dikeluarkan, 922 melewati cap lima/domain. Tersisa **34,084 URL baru**. Tidak ada relabel otomatis.

| Partisi | URL | Benign | Phishing | Domain/tenant |
| --- | ---: | ---: | ---: | ---: |
| fit | 616,050 | 362,725 | 253,325 | 424,123 |
| tune | 107,094 | 61,020 | 46,074 | 93,549 |
| calibration | 50,749 | 29,488 | 21,261 | 44,695 |
| threshold | 58,840 | 35,876 | 22,964 | 52,830 |
| new_test | 3,544 | 1,654 | 1,890 | 2,906 |

Registry historis, seluruh sidecar dan cache v6 masuk audit novelty. Sidecar PWD2021 mencatat seluruh intake tersanitasi, termasuk baris yang dikeluarkan dan holdout cadangan. Domain, digest dan representasi tidak melintasi partisi; kemerdekaan kampanye belum dibuktikan. Raw URL tidak dipersistensikan; cache tersanitasi, registry dan binary tetap diabaikan Git. Pada PWD semua model dinilai atas core tersanitasi versi eksperimen, termasuk kontrol v6; ini bukan scoring atas seluruh raw URL penerbit dan tidak mengubah parser layanan aktif.

## Ablasi sumber pada development

Semua kandidat memakai LR C=2/liblinear, resep TF-IDF dan source_sqrt yang sama. Encoder di-fit ulang pada fitting subset setiap kandidat. Tune/calibration/threshold sama untuk seluruh kandidat. Pemilihan memakai macro recall dengan budget FPR 1% per sumber yang cukup didukung; tie-break minimum source recall lalu AP. Test tidak dipakai memilih kandidat.

| Kandidat | Fit | Macro recall tune strict | Minimum source recall |
| --- | ---: | ---: | ---: |
| foundation | 524,699 | 17.33% | 5.07% |
| plus_compphish | 528,582 | 15.61% | 3.84% |
| plus_wangchuk | 533,245 | 28.79% | 10.78% |
| plus_phishbd | 583,505 | 27.00% | 13.14% |
| expanded_three | 595,934 | 35.79% | 18.23% |
| expanded_plus_pwd2021 | 616,050 | 45.74% | 24.93% |

Ini uji pengaruh sumber dalam resep yang tetap; bukan bukti bahwa satu penerbit menyebabkan perubahan pada setiap jenis phishing. Source ID tidak menjadi fitur. Kalibrasi sigmoid di-fit hanya pada calibration dengan slope positif; threshold dipilih hanya pada threshold partition.

## Hasil utama setelah pembekuan

Ketiga model di bawah memakai kebijakan warning/strict masing-masing yang dibekukan sebelum scoring baru. Kebijakan dan jumlah sumber development berbeda; tabel ini tidak mengasumsikan FPR test yang sama.

| Cohort | URL | Recall v6 aktif | Recall kandidat sebelumnya | Recall kandidat baru | FPR v6 aktif | FPR sebelumnya | FPR baru |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| new_pwd_domain_holdout | 3,544 | 49.89% | 35.56% | 55.34% | 0.54% | 0.18% | 0.24% |
| observed_expanded_domain_holdout | 11,636 | 29.86% | 38.25% | 46.74% | 2.53% | 0.40% | 0.93% |
| observed_vendor | 20,000 | 46.31% | 31.48% | 43.65% | 0.94% | 0.29% | 0.64% |
| observed_phishtank_positive | 9,269 | 46.53% | 35.92% | 43.53% | Tidak tersedia | Tidak tersedia | Tidak tersedia |
| observed_legitphish | 42,716 | 66.01% | 42.45% | 69.55% | 0.00% | 0.00% | 0.00% |

PWD holdout adalah domain baru dari sumber historis yang juga digunakan development. Empat cohort lain sudah teramati sebelum eksperimen ini dan hanya pemeriksaan regresi. Protokol didorong temuan test terdahulu; hasil baru tidak menghapus adaptasi tersebut.

### Counts dan ketidakpastian kandidat baru

| Cohort | TP | FN | FP | TN | Precision sampel | Domain recall 95% | Domain FPR 95% | Wilson FPR 95% (row IID) |
| --- | ---: | ---: | ---: | ---: | ---: | --- | --- | --- |
| new_pwd_domain_holdout | 1046 | 844 | 4 | 1650 | 99.62% | [52.57%; 58.17%] | [0.06%; 0.53%] | [0.09%; 0.62%] |
| observed_expanded_domain_holdout | 3923 | 4470 | 30 | 3213 | 99.24% | [45.53%; 48.04%] | [0.61%; 1.29%] | [0.65%; 1.32%] |
| observed_vendor | 965 | 1246 | 113 | 17676 | 89.52% | [41.57%; 45.94%] | [0.53%; 0.75%] | [0.53%; 0.76%] |
| observed_phishtank_positive | 4035 | 5234 | 0 | 0 | Tidak tersedia | [42.44%; 44.59%] | Tidak tersedia | Tidak tersedia |
| observed_legitphish | 29690 | 12998 | 0 | 28 | 100.00% | [68.99%; 70.09%] | [0.00%; 0.00%] | [0.00%; 12.06%] |

Bootstrap memakai 1.000 pengambilan ulang domain/private tenant. Interval kondisional pada label penerbit dan tidak mengoreksi semua perbandingan eksploratif. Wilson row-IID mengabaikan korelasi domain/kampanye. LegitPhish hanya memiliki 28 benign: 0/28 FP, bila terjadi, tetap memiliki Wilson upper 95% sekitar 12,06%; bootstrap nol yang degenerat bukan jaminan FPR. PhishTank positif saja tidak menyediakan FPR, binary accuracy atau precision trafik.

### Kalibrasi dan pemisahan risiko: v6 aktif menuju kandidat baru

| Cohort | Brier v6 → baru | ECE v6 → baru | ROC AUC v6 → baru | AP v6 → baru |
| --- | ---: | ---: | ---: | ---: |
| new_pwd_domain_holdout | 0.085531 → 0.065670 | 0.039496 → 0.028514 | 0.955919 → 0.972573 | 0.963817 → 0.977968 |
| observed_expanded_domain_holdout | 0.161907 → 0.109356 | 0.113510 → 0.032396 | 0.830132 → 0.910398 | 0.925604 → 0.965741 |
| observed_vendor | 0.090239 → 0.098732 | 0.154501 → 0.168058 | 0.940358 → 0.944463 | 0.743153 → 0.760110 |
| observed_phishtank_positive | Tidak tersedia | Tidak tersedia | Tidak tersedia | Tidak tersedia |
| observed_legitphish | 0.042691 → 0.023614 | 0.120744 → 0.074780 | 0.992436 → 0.996310 | 0.999995 → 0.999998 |

Brier/ECE lebih kecil lebih baik; ROC AUC/AP lebih besar lebih baik dengan keterbatasan distribusi kelas. Pada vendor, Brier dan ECE justru memburuk walaupun ROC AUC sedikit meningkat secara angka. Skor terkalibrasi pada distribusi riset. Precision dan kalibrasi sampel tidak menjadi estimasi probabilitas/precision trafik Indonesia.

## Perbandingan kebijakan tambahan yang ditetapkan sebelum test

Pooled budget 0,1%, 0,5%, 1%, 2% ditentukan pada threshold partition untuk kedua model. Pooled budget tidak mengikat FPR tiap sumber dan tidak menjamin FPR test. Tidak ada kebijakan yang dipromosikan atau dipilih dari hasil test.

### new_pwd_domain_holdout

| Kebijakan | Recall | FPR | Precision sampel |
| --- | ---: | ---: | ---: |
| v6_original | 49.89% | 0.54% | 99.05% |
| v6_matched_source_1pct | 11.27% | 0.00% | 100.00% |
| candidate_strict_source_1pct | 55.34% | 0.24% | 99.62% |
| candidate_pooled_0.001 | 35.34% | 0.00% | 100.00% |
| candidate_pooled_0.005 | 59.31% | 0.30% | 99.56% |
| candidate_pooled_0.01 | 68.31% | 0.54% | 99.31% |
| candidate_pooled_0.02 | 76.46% | 1.09% | 98.77% |
| v6_pooled_0.001 | 21.96% | 0.00% | 100.00% |
| v6_pooled_0.005 | 46.24% | 0.48% | 99.09% |
| v6_pooled_0.01 | 58.78% | 0.60% | 99.11% |
| v6_pooled_0.02 | 68.15% | 1.57% | 98.02% |

### observed_expanded_domain_holdout

| Kebijakan | Recall | FPR | Precision sampel |
| --- | ---: | ---: | ---: |
| v6_original | 29.86% | 2.53% | 96.83% |
| v6_matched_source_1pct | 7.28% | 0.03% | 99.84% |
| candidate_strict_source_1pct | 46.74% | 0.93% | 99.24% |
| candidate_pooled_0.001 | 27.40% | 0.15% | 99.78% |
| candidate_pooled_0.005 | 52.31% | 1.20% | 99.12% |
| candidate_pooled_0.01 | 62.43% | 2.47% | 98.50% |
| candidate_pooled_0.02 | 71.36% | 4.66% | 97.54% |
| v6_pooled_0.001 | 12.39% | 0.28% | 99.14% |
| v6_pooled_0.005 | 27.14% | 2.13% | 97.06% |
| v6_pooled_0.01 | 37.69% | 3.89% | 96.17% |
| v6_pooled_0.02 | 49.66% | 7.22% | 94.68% |

### observed_vendor

| Kebijakan | Recall | FPR | Precision sampel |
| --- | ---: | ---: | ---: |
| v6_original | 46.31% | 0.94% | 85.91% |
| v6_matched_source_1pct | 8.46% | 0.06% | 94.44% |
| candidate_strict_source_1pct | 43.65% | 0.64% | 89.52% |
| candidate_pooled_0.001 | 24.29% | 0.22% | 93.07% |
| candidate_pooled_0.005 | 48.67% | 1.02% | 85.60% |
| candidate_pooled_0.01 | 59.02% | 1.91% | 79.38% |
| candidate_pooled_0.02 | 69.29% | 3.50% | 71.09% |
| v6_pooled_0.001 | 17.05% | 0.20% | 91.28% |
| v6_pooled_0.005 | 41.97% | 0.76% | 87.22% |
| v6_pooled_0.01 | 55.50% | 1.61% | 81.10% |
| v6_pooled_0.02 | 65.76% | 3.04% | 72.92% |

### observed_phishtank_positive

| Kebijakan | Recall | FPR | Precision sampel |
| --- | ---: | ---: | ---: |
| v6_original | 46.53% | Tidak tersedia | Tidak tersedia |
| v6_matched_source_1pct | 17.67% | Tidak tersedia | Tidak tersedia |
| candidate_strict_source_1pct | 43.53% | Tidak tersedia | Tidak tersedia |
| candidate_pooled_0.001 | 29.74% | Tidak tersedia | Tidak tersedia |
| candidate_pooled_0.005 | 47.97% | Tidak tersedia | Tidak tersedia |
| candidate_pooled_0.01 | 56.68% | Tidak tersedia | Tidak tersedia |
| candidate_pooled_0.02 | 66.71% | Tidak tersedia | Tidak tersedia |
| v6_pooled_0.001 | 25.67% | Tidak tersedia | Tidak tersedia |
| v6_pooled_0.005 | 43.60% | Tidak tersedia | Tidak tersedia |
| v6_pooled_0.01 | 54.47% | Tidak tersedia | Tidak tersedia |
| v6_pooled_0.02 | 64.90% | Tidak tersedia | Tidak tersedia |

### observed_legitphish

| Kebijakan | Recall | FPR | Precision sampel |
| --- | ---: | ---: | ---: |
| v6_original | 66.01% | 0.00% | 100.00% |
| v6_matched_source_1pct | 0.82% | 0.00% | 100.00% |
| candidate_strict_source_1pct | 69.55% | 0.00% | 100.00% |
| candidate_pooled_0.001 | 19.79% | 0.00% | 100.00% |
| candidate_pooled_0.005 | 79.01% | 0.00% | 100.00% |
| candidate_pooled_0.01 | 89.48% | 0.00% | 100.00% |
| candidate_pooled_0.02 | 93.37% | 0.00% | 100.00% |
| v6_pooled_0.001 | 7.14% | 0.00% | 100.00% |
| v6_pooled_0.005 | 58.11% | 0.00% | 100.00% |
| v6_pooled_0.01 | 80.67% | 0.00% | 100.00% |
| v6_pooled_0.02 | 89.82% | 0.00% | 100.00% |

## Pemeriksaan dan batas penggunaan

Semua classifier konvergen. Save/reload 130 probe nyata/sintetis, delta maksimum 0.0. Model aktif v6, metadata, dependensi inference, PSL offline dan threshold aslinya tetap sama. Verifikasi teknis tidak membuktikan label benar atau detection recall tinggi.

Tidak ada gold Indonesia, dua reviewer independen atau two-class temporal holdout terkini. Holdout PWD mempunyai 1.654 benign, di bawah minimum 3.000 pada gate proyek; jumlah sampel saja juga tidak cukup. LOW tidak berarti SAFE. Model tetap research/internal shadow.

## Bukti dan reproduksi

- [Protokol utama](v6-targeted-20261105-protocol.json), [hasil numerik lengkap](v6-targeted-evaluation.json), [grafik](v6-targeted-evaluation.png).
- [Kontrol kandidat sebelumnya](v6-targeted-previous-control.json), [protokol kontrol](v6-targeted-previous-control-protocol.json); tambahan dinyatakan selama training, sebelum test, tanpa mengubah seleksi.
- [Manifest exposure](../provenance/pwd2021-targeted-exposure.json), [verifikasi akhir](v6-targeted-verification.json).
- Jalankan intake_v6_targeted.py, experiment_v6_targeted.py --stage prepare/train/evaluate, lalu v6_targeted_previous_control.py sesuai urutan freeze sebelum scoring/evaluate sesudahnya. Run beku tidak boleh ditimpa atau sidecar dihapus demi mengklaim novelty.
