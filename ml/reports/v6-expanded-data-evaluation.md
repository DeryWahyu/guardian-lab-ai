# Eksperimen penggabungan dataset turunan v6

**Kesimpulan:** kandidat memperbaiki recall dan false positive pada holdout domain baru, tetapi recall menurun pada semua benchmark lama yang diperiksa. Hasilnya belum menunjukkan perbaikan menyeluruh atau memenuhi syarat produksi. Model layanan tetap frozen v6 asli.

Kandidat terpilih hanya dari tune: **expanded_domain_C2**. Tiga classifier konvergen; artifact terpilih, kalibrator dan threshold dibekukan sebelum semua prediksi test. Syarat peningkatan development terpenuhi: **True**. Ini berbeda dari syarat rilis produksi.

## Data yang ditambahkan

| Sumber baru | Baris rilis | Lolos sanitasi |
| --- | ---: | ---: |
| compphish | 15,358 | 14,364 |
| wangchuk | 149,726 | 139,465 |
| phishbd | 131,167 | 126,031 |

Total intake 296.251 baris; 118.319 URL baru tersisa setelah penyaringan. Sepuluh representasi dengan 1.286 baris konflik dikarantina, 59.716 duplikat konsisten dibuang, 79.696 kasus paparan lama dan 20.843 kelebihan cap domain dikeluarkan. Label tidak diubah atau diisi oleh LLM.

| Partisi gabungan | URL | Domain/tenant | Benign | Phishing |
| --- | ---: | ---: | ---: | ---: |
| fit | 595,934 | 407,431 | 353,170 | 242,764 |
| tune | 101,816 | 89,197 | 58,512 | 43,304 |
| calibration | 48,297 | 42,670 | 28,339 | 19,958 |
| threshold | 56,146 | 50,564 | 34,544 | 21,602 |
| new_test | 11,636 | 10,446 | 3,243 | 8,393 |

Fitting berisi delapan sumber. Vocabulary/scaler hanya di-fit pada fitting. Partisi fondasi v6 dipertahankan, dan domain data baru dipisah deterministik sebelum fitting. Domain, digest dan representasi antar-partisi tidak overlap. Semua sumber tetap label penerbit dengan keterbatasan scope phishing, ranking benign dan timestamp, bukan gold Indonesia.

## Seleksi hanya pada development

| Model | Macro recall sumber pada budget FPR tune 1% | Minimum source recall |
| --- | ---: | ---: |
| v6 kontrol tune | 21.640% | 6.765% |
| expanded_C2 | 46.554% | 29.491% |
| expanded_C8 | 46.158% | 31.099% |
| expanded_domain_C2 | 48.453% | 32.172% |

Sumber gabungan mengubah constraint FPR yang paling ketat. Karena itu nilai kontrol tune di sini tidak langsung dibandingkan dengan macro tune empat/lima sumber pada eksperimen lama. Threshold tune hanya diagnostik pemilihan. Policy akhir kandidat memakai partisi threshold terpisah.

## Perbandingan utama: policy asli v6 versus kandidat beku

| Cohort | Model | URL | Precision | Recall | FPR | TP | FN | FP | TN |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| new_domain_holdout | v6 | 11,636 | 96.832% | 29.858% | 2.529% | 2506 | 5887 | 82 | 3161 |
| new_domain_holdout | candidate | 11,636 | 99.597% | 38.246% | 0.401% | 3210 | 5183 | 13 | 3230 |
| observed_vendor | v6 | 20,000 | 85.906% | 46.314% | 0.944% | 1024 | 1187 | 168 | 17621 |
| observed_vendor | candidate | 20,000 | 93.173% | 31.479% | 0.287% | 696 | 1515 | 51 | 17738 |
| observed_phishtank_positive | v6 | 9,269 | N/A | 46.531% | N/A | 4313 | 4956 | N/A | N/A |
| observed_phishtank_positive | candidate | 9,269 | N/A | 35.915% | N/A | 3329 | 5940 | N/A | N/A |
| observed_legitphish | v6 | 42,716 | 100.000% | 66.012% | 0.000% | 28179 | 14509 | 0 | 28 |
| observed_legitphish | candidate | 42,716 | 100.000% | 42.448% | 0.000% | 18120 | 24568 | 0 | 28 |

Pada holdout baru, kandidat menangkap 704 phishing tambahan dan mengurangi 69 false positive: recall 29,86% menjadi 38,25%, FPR 2,53% menjadi 0,40%. Domain-bootstrap berpasangan 95%: kenaikan recall [7,44; 9,37] percentage point, perubahan FPR [-2,71; -1,60] point. Perbandingan menggunakan data yang sama dan policy yang dibekukan sebelum scoring.

Namun, pada vendor lama recall turun 46,31% menjadi 31,48%; pada feed positif PhishTank 46,53% menjadi 35,92%; pada LegitPhish 66,01% menjadi 42,45%. Interval delta recall berpasangan seluruh benchmark lama berada di bawah nol. Penurunan ini tetap dilaporkan dan menjadi alasan kandidat tidak menggantikan layanan aktif.

| Cohort | 95% delta recall kandidat-v6, percentage point | 95% delta FPR, percentage point |
| --- | --- | --- |
| new_domain_holdout | [7.438, 9.372] | [-2.708, -1.6] |
| observed_vendor | [-16.549, -13.084] | [-0.791, -0.539] |
| observed_phishtank_positive | [-11.325, -9.929] | N/A |
| observed_legitphish | [-24.017, -23.098] | [0.0, 0.0] |

## Kontrol tambahan dengan budget FPR development yang sama

Kontrol tambahan dideklarasikan setelah hasil tune kandidat pertama, sebelum final test. Ia memakai classifier/encoder/kalibrator v6 asli; hanya threshold referensi yang ditentukan pada threshold partition gabungan. Ini tambahan terlambat yang dilaporkan terpisah, tidak mengubah policy v6 atau pemilihan kandidat.

| Cohort | Recall v6 kontrol | Recall kandidat | FPR v6 kontrol | FPR kandidat |
| --- | ---: | ---: | ---: | ---: |
| new_domain_holdout | 7.280% | 38.246% | 0.031% | 0.401% |
| observed_vendor | 8.458% | 31.479% | 0.062% | 0.287% |
| observed_phishtank_positive | 17.672% | 35.915% | N/A | N/A |
| observed_legitphish | 0.818% | 42.448% | 0.000% | 0.000% |

Budget development yang sama tidak berarti FPR test sama. Contohnya, pada holdout baru kontrol memperoleh FPR 0,031% dan kandidat 0,401%; peningkatan recall terhadap kontrol juga disertai tambahan false alarm. Jangan mengganti perbandingan terhadap v6 policy asli dengan tabel kontrol untuk menyembunyikan regresi.

## Kalibrasi dan syarat rilis

| Cohort | Model | Brier | Log loss | ECE 10 bins |
| --- | --- | ---: | ---: | ---: |
| new_domain_holdout | v6 | 0.161907 | 0.486489 | 0.113510 |
| new_domain_holdout | candidate | 0.107969 | 0.335887 | 0.034652 |
| observed_vendor | v6 | 0.090239 | 0.300043 | 0.154501 |
| observed_vendor | candidate | 0.096478 | 0.315688 | 0.164440 |
| observed_legitphish | v6 | 0.042691 | 0.174637 | 0.120744 |
| observed_legitphish | candidate | 0.025145 | 0.109913 | 0.078378 |

Holdout baru memenuhi jumlah minimum diagnostik (8.393 phishing/3.243 benign), tetapi Wilson lower 95% recall 37.212% masih jauh di bawah target 85%. Wilson upper 95% FPR 0.685% berada di bawah 1% pada label/sampel ini. Jumlah dan angka FPR tersebut tidak melengkapi bukti human review, Indonesia, hak/provenance per kasus atau audit kampanye/waktu.

Pada LegitPhish hanya ada 28 benign: nol FP dan bootstrap [0;0] tetap tidak membuktikan FPR populasi nol. Precision sampel bukan precision trafik. PhishTank hanya positif sehingga FPR/traffic precision/accuracy biner tidak tersedia. Tidak ada cohort digabung untuk membuat estimasi trafik atau temporal palsu.

Save/reload parity kandidat: 130 kasus development/sintetis, max probability delta 0.0. Seluruh 116 tes terkait proyek dan kontrol tambahan lulus (114 suite utama + 2 guard kontrol). Runtime v6 asli dan dependency inference tetap terverifikasi.

## Artifact dan reproduksi

Kandidat lokal: `ml/runs/v6-expanded-data-20261105/selected-candidate.joblib`, SHA-256 `2f875b64d93a4b9999b1e1c9e028ad809ddc54845e3e34acf0c492d76242285a`. Dataset, source caches, model dan exposure sidecars diabaikan Git. Metadata pemilihan dan threshold dibekukan sebelum test; semua kasus intake tercatat sebagai exposure untuk percobaan mendatang.

[Prosedur](../../ai-agent-docs/v6-expanded-data-experiment.md), [protokol utama](v6-expansion-20261105-protocol.json), [protokol kontrol tambahan](v6-expanded-matched-control-protocol.json), [hasil kontrol](v6-expanded-matched-control.json), [grafik](v6-expanded-data-evaluation.png).

Kesimpulan tetap riset: ada manfaat pada distribusi tambahan dan pengurangan false alarm, tetapi target recall belum tercapai dan regresi lama signifikan secara eksplorasi. Tidak ada perubahan model layanan, promosi produksi, reviewer atau label Indonesia otomatis.
