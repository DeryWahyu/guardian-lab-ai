# Audit development kandidat sembilan sumber

Audit relatif label penerbit, bukan penentuan kebenaran label manusia. Data tune tidak menjadi final gold sampling frame.

107,094 URL; false negative relatif penerbit 26,471. Label tidak diubah otomatis.

| Sumber | Benign | Phishing | TP | FN | FP | Recall | FPR | Porsi FN sampel |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| compphish | 495 | 513 | 343 | 170 | 1 | 66.86% | 0.20% | 0.64% |
| deepurlbench | 17806 | 2194 | 937 | 1257 | 111 | 42.71% | 0.62% | 4.75% |
| mendeley2020 | 487 | 573 | 214 | 359 | 2 | 37.35% | 0.41% | 1.36% |
| phishbd | 4345 | 10318 | 4637 | 5681 | 35 | 44.94% | 0.81% | 21.46% |
| phishvn_core | 1901 | 373 | 93 | 280 | 6 | 24.93% | 0.32% | 1.06% |
| phiusiil | 18258 | 11060 | 4063 | 6997 | 1 | 36.74% | 0.01% | 26.43% |
| phresh | 15010 | 16338 | 6599 | 9739 | 16 | 40.39% | 0.11% | 36.79% |
| pwd2021 | 2508 | 2770 | 1456 | 1314 | 1 | 52.56% | 0.04% | 4.96% |
| wangchuk | 210 | 1935 | 1261 | 674 | 1 | 65.17% | 0.48% | 2.55% |

Porsi FN hanya mengikuti komposisi sampel penelitian; bukan estimasi kontribusi pada trafik Indonesia.

| Struktur | Nilai | URL | FN | Recall | FPR |
| --- | --- | ---: | ---: | ---: | ---: |
| long_url | False | 106450 | 26178 | 42.77% | 0.28% |
| long_url | True | 644 | 293 | 10.94% | 0.63% |
| deep_path | False | 99964 | 24417 | 43.30% | 0.30% |
| deep_path | True | 7130 | 2054 | 31.74% | 0.07% |
| private_hosting | False | 97023 | 25351 | 31.56% | 0.24% |
| private_hosting | True | 10071 | 1120 | 87.60% | 3.17% |
| punycode | False | 106998 | 26426 | 42.58% | 0.29% |
| punycode | True | 96 | 45 | 16.67% | 0.00% |
| redacted | False | 101902 | 25357 | 43.03% | 0.30% |
| redacted | True | 5192 | 1114 | 28.91% | 0.08% |

## Konflik penerbit dan review

| Partisi | Representasi konflik | Baris |
| --- | ---: | ---: |
| fit | 0 | 0 |
| calibration | 3 | 6 |
| threshold | 3 | 6 |
| tune | 7 | 14 |

170 kasus disiapkan dalam coordinator dan dua pack blind lokal. Selesai review manusia: **0**. Pack blind hanya memuat case ID/locator hash dan kolom reviewer yang kosong; URL, skor model dan label penerbit tidak diberikan kepada reviewer pada tahap awal.

Konflik representasi bisa disebabkan scheme/query/waktu atau label sumber; audit ini tidak menetapkan label yang benar. False negative/positive adalah ketidakcocokan terhadap label penerbit, bukan bukti target kini phishing atau aman.

## Input Indonesia aktual

| Berkas | Baris |
| --- | ---: |
| indonesia-adjudication.csv | 0 |
| indonesia-candidates.csv | 0 |
| indonesia-error-review.csv | 0 |
| indonesia-reviewer-a.csv | 0 |
| indonesia-reviewer-b.csv | 0 |

Tidak ada reviewer, label Indonesia atau adjudikasi yang dibuat oleh agent. Review nyata memerlukan identitas manusia independen serta evidence reference per kasus. Data global berlabel penerbit tidak otomatis memenuhi kebutuhan itu.
