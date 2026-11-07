# Perbaikan kesiapan v6: model, lisensi sumber, dan gateway

**Gateway shadow telah diperkuat dan teruji. Eksperimen model belum memenuhi syarat penggantian.** Model aktif tetap frozen v6; seluruh respons tetap production_ready=false. Tidak ada server publik diluncurkan, reviewer dibuat, atau label Indonesia diisi otomatis.

## Perbaikan operasional yang sudah selesai

- Entry point baru `guardian_ml.shadow_gateway:create_app` memakai backend Bearer key wajib; key kosong/lemah ditolak. Primary service asli tidak diubah.
- Token bucket global per proses, batas prediksi bersamaan, batas aktual body/response, deadline body dan inferensi, serta penolakan overload dengan Retry-After.
- Timeout respons tidak membatalkan thread inference. Slot tetap dihitung sampai komputasi berakhir; pembatalan klien juga tidak melepaskan slot lebih awal.
- Assignment path yang terdeteksi berisi credential/secret ditolak sebagai unsupported tanpa score/band. Representasi model asli tidak diubah; sanitizer tetap heuristik dan cakupan input gateway berkurang.
- Monitoring hanya counters/histogram; tidak menyimpan key, IP, URL, body, atau event per request. Metrics kualitas online tetap null.
- Manifest gateway mengikat dua source baru, parent runtime manifest, delapan versi dependency inferensi dan empat dependency layanan. Source manifest dan binary/metadata/threshold asli tetap utuh.

## Uji beban dan parity

Uji menggunakan model v6 asli dan URL sintetis melalui ASGI in-process pada workstation ini. Kuota benchmark sengaja dilonggarkan ke 10.000 request/menit dan burst 1.000; kapasitas inferensi tetap 2. Default operasional adalah 60 request/menit, burst 10, kapasitas 2, timeout inference 5 detik/body 3 detik. Hasil ini tidak membuktikan throughput jaringan, TLS, beberapa worker/replica, atau SLA deployment.

| Fase | Request | Konkurensi client | HTTP 200 | HTTP 503 | p95 semua respons | p95 respons berhasil | Peak inference |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| steady | 100 | 2 | 100 | 0 | 17.82 ms | 17.82 ms | 2 |
| saturation | 160 | 16 | 2 | 158 | 1.36 ms | 163.18 ms | 2 |

Status overload memiliki score/band null. Semua prediksi berhasil sama dengan prediksi langsung artifact asli (delta maksimum nol). Tes tambahan memeriksa autentikasi, kuota, body chunked/slow, output terlalu besar, exception privat, deadline threadpool nyata, pembatalan klien, manifest/dependency tampering dan abstention input sensitif.

## Penyaringan sumber dan pelatihan

DeepURLBench (NC menurut catatan proyek) dan ISCX replica (hak data asal belum jelas) dikeluarkan dari seluruh fitting, vocabulary, scaler, calibration, threshold dan tune. Estimator baseline dilatih dari nol; hanya constructor v6 yang di-clone. Tidak ada fitted vocabulary/IDF/scaler/koefisien lama digunakan. Sembilan sumber yang dipertahankan mendeklarasikan CC BY 4.0 pada metadata penerbit. Ini penyaringan deklarasi penerbit, bukan commercial clearance: sumber hulu PWD2021/Ebbu, PhishBD/ISCX, attribution, privasi dan linkage versi masih perlu review.

| Partisi setelah filter | Total | Benign | Phishing | Private benign | Private phishing |
| --- | ---: | ---: | ---: | ---: | ---: |
| fit | 568,431 | 313,587 | 254,844 | 1,533 | 61,012 |
| calibration | 40,749 | 20,642 | 20,107 | 167 | 4,135 |
| threshold | 43,840 | 22,433 | 21,407 | 173 | 4,517 |
| tune | 87,094 | 43,214 | 43,880 | 319 | 8,712 |

Ketimpangan benign private hosting masih besar. Dua expert Logistic Regression memakai encoder baseline yang hanya di-fit pada fitting, C=0,5/C=2, bobot soft kelas/sumber/domain yang dibatasi, kalibrator private terpisah, dan threshold private FPR 1%/0,1% pada threshold partition. Probabilitas tidak dipetakan ulang untuk menyamarkan threshold kelompok; Brier/ECE dihitung dari probabilitas asli, confusion/bootstrap dari keputusan routing.

| Varian development | Private recall | Private FPR | Macro recall sumber | Macro Brier | Lolos gate |
| --- | ---: | ---: | ---: | ---: | --- |
| baseline | 86.651% | 3.135% | 44.784% | 0.092641 | control |
| private_matched | 60.067% | 0.627% | 37.423% | 0.092641 | control |
| private_c05 | 56.635% | 0.940% | 36.349% | 0.093871 | False |
| private_c2 | 65.347% | 1.254% | 38.378% | 0.093598 | False |

Kedua expert gagal guard development. `private_c2` dibekukan sebagai challenger diagnostik berdasarkan tune, bukan dipromosikan. Contohnya expert C=2 menambah private recall 5,28 pp dibanding baseline dengan batas private FPR yang sama, tetapi kehilangan 21,30 pp dibanding native baseline. Keputusan itu dipertahankan setelah test.

## Replay historis warning

Semua 11 cohort sudah pernah teramati. Source NC dapat dipakai untuk diagnostik riset historis di sini; tidak dipakai fitting/calibration/threshold/tune. Reference scores sebelumnya diikat hash ke cohort/model dan diverifikasi replay. Ini bukan final holdout independen baru atau gold Indonesia.

| Cohort | Model | N benign / phishing | TP / FN / FP / TN | Accuracy | Recall | FPR | Private recall | Brier |
| --- | --- | ---: | --- | ---: | ---: | ---: | ---: | ---: |
| observed_vendor | frozen_v6 | 17789 / 2211 | 1024 / 1187 / 168 / 17621 | 93.225% | 46.314% | 0.944% | 86.527% | 0.090239 |
| observed_vendor | previous_current | 17789 / 2211 | 1017 / 1194 / 141 / 17648 | 93.325% | 45.997% | 0.793% | 81.437% | 0.103913 |
| observed_vendor | baseline | 17789 / 2211 | 993 / 1218 / 447 / 17342 | 91.675% | 44.912% | 2.513% | 79.940% | 0.195072 |
| observed_vendor | private_matched | 17789 / 2211 | 863 / 1348 / 429 / 17360 | 91.115% | 39.032% | 2.412% | 41.018% | 0.195072 |
| observed_vendor | private_c2 | 17789 / 2211 | 890 / 1321 / 432 / 17357 | 91.235% | 40.253% | 2.428% | 49.102% | 0.197691 |
| observed_phishtank_positive | frozen_v6 | 0 / 9269 | 4313 / 4956 / 0 / 0 | n/a | 46.531% | n/a | 62.278% | n/a |
| observed_phishtank_positive | previous_current | 0 / 9269 | 4209 / 5060 / 0 / 0 | n/a | 45.409% | n/a | 57.200% | n/a |
| observed_phishtank_positive | baseline | 0 / 9269 | 4040 / 5229 / 0 / 0 | n/a | 43.586% | n/a | 53.972% | n/a |
| observed_phishtank_positive | private_matched | 0 / 9269 | 3313 / 5956 / 0 / 0 | n/a | 35.743% | n/a | 27.602% | n/a |
| observed_phishtank_positive | private_c2 | 0 / 9269 | 3272 / 5997 / 0 / 0 | n/a | 35.300% | n/a | 26.115% | n/a |
| observed_expanded | frozen_v6 | 3243 / 8393 | 2506 / 5887 / 82 / 3161 | 48.702% | 29.858% | 2.529% | 91.188% | 0.161907 |
| observed_expanded | previous_current | 3243 / 8393 | 3952 / 4441 / 33 / 3210 | 61.550% | 47.087% | 1.018% | 88.378% | 0.112279 |
| observed_expanded | baseline | 3243 / 8393 | 3640 / 4753 / 28 / 3215 | 58.912% | 43.369% | 0.863% | 86.207% | 0.112268 |
| observed_expanded | private_matched | 3243 / 8393 | 3392 / 5001 / 27 / 3216 | 56.789% | 40.415% | 0.833% | 54.534% | 0.112268 |
| observed_expanded | private_c2 | 3243 / 8393 | 3404 / 4989 / 26 / 3217 | 56.901% | 40.558% | 0.802% | 56.066% | 0.112621 |
| observed_pwd2021 | frozen_v6 | 1654 / 1890 | 943 / 947 / 9 / 1645 | 73.025% | 49.894% | 0.544% | 80.184% | 0.085531 |
| observed_pwd2021 | previous_current | 1654 / 1890 | 1093 / 797 / 4 / 1650 | 77.398% | 57.831% | 0.242% | 78.802% | 0.063471 |
| observed_pwd2021 | baseline | 1654 / 1890 | 994 / 896 / 4 / 1650 | 74.605% | 52.593% | 0.242% | 74.654% | 0.064137 |
| observed_pwd2021 | private_matched | 1654 / 1890 | 906 / 984 / 3 / 1651 | 72.150% | 47.937% | 0.181% | 34.101% | 0.064137 |
| observed_pwd2021 | private_c2 | 1654 / 1890 | 920 / 970 / 3 / 1651 | 72.545% | 48.677% | 0.181% | 40.553% | 0.063962 |
| observed_zenodo | frozen_v6 | 9643 / 2944 | 1548 / 1396 / 85 / 9558 | 88.234% | 52.582% | 0.881% | 88.552% | 0.153102 |
| observed_zenodo | previous_current | 9643 / 2944 | 1627 / 1317 / 41 / 9602 | 89.211% | 55.265% | 0.425% | 85.971% | 0.139146 |
| observed_zenodo | baseline | 9643 / 2944 | 1600 / 1344 / 32 / 9611 | 89.068% | 54.348% | 0.332% | 82.604% | 0.175321 |
| observed_zenodo | private_matched | 9643 / 2944 | 1391 / 1553 / 30 / 9613 | 87.424% | 47.249% | 0.311% | 59.147% | 0.175321 |
| observed_zenodo | private_c2 | 9643 / 2944 | 1407 / 1537 / 31 / 9612 | 87.543% | 47.792% | 0.321% | 60.943% | 0.176587 |
| observed_legitphish | frozen_v6 | 28 / 42688 | 28179 / 14509 / 0 / 28 | 66.034% | 66.012% | 0.000% | 61.236% | 0.042691 |
| observed_legitphish | previous_current | 28 / 42688 | 39778 / 2910 / 0 / 28 | 93.188% | 93.183% | 0.000% | 57.303% | 0.011586 |
| observed_legitphish | baseline | 28 / 42688 | 39736 / 2952 / 0 / 28 | 93.089% | 93.085% | 0.000% | 65.169% | 0.005339 |
| observed_legitphish | private_matched | 28 / 42688 | 39673 / 3015 / 0 / 28 | 92.942% | 92.937% | 0.000% | 29.775% | 0.005339 |
| observed_legitphish | private_c2 | 28 / 42688 | 39664 / 3024 / 0 / 28 | 92.921% | 92.916% | 0.000% | 24.719% | 0.005365 |
| observed_stealth | frozen_v6 | 26578 / 8317 | 4865 / 3452 / 15 / 26563 | 90.064% | 58.495% | 0.056% | 91.815% | 0.060737 |
| observed_stealth | previous_current | 26578 / 8317 | 5452 / 2865 / 0 / 26578 | 91.790% | 65.552% | 0.000% | 89.527% | 0.041282 |
| observed_stealth | baseline | 26578 / 8317 | 5379 / 2938 / 0 / 26578 | 91.580% | 64.675% | 0.000% | 87.036% | 0.046536 |
| observed_stealth | private_matched | 26578 / 8317 | 4713 / 3604 / 0 / 26578 | 89.672% | 56.667% | 0.000% | 53.177% | 0.046536 |
| observed_stealth | private_c2 | 26578 / 8317 | 4827 / 3490 / 0 / 26578 | 89.999% | 58.038% | 0.000% | 58.973% | 0.046511 |
| observed_phishbench | frozen_v6 | 2 / 270 | 144 / 126 / 0 / 2 | 53.676% | 53.333% | 0.000% | 85.455% | 0.086105 |
| observed_phishbench | previous_current | 2 / 270 | 154 / 116 / 0 / 2 | 57.353% | 57.037% | 0.000% | 87.273% | 0.046809 |
| observed_phishbench | baseline | 2 / 270 | 158 / 112 / 0 / 2 | 58.824% | 58.519% | 0.000% | 83.636% | 0.026006 |
| observed_phishbench | private_matched | 2 / 270 | 133 / 137 / 0 / 2 | 49.632% | 49.259% | 0.000% | 38.182% | 0.026006 |
| observed_phishbench | private_c2 | 2 / 270 | 148 / 122 / 0 / 2 | 55.147% | 54.815% | 0.000% | 65.455% | 0.027485 |
| observed_ebbu | frozen_v6 | 2367 / 6482 | 2266 / 4216 / 8 / 2359 | 52.266% | 34.958% | 0.338% | 64.706% | 0.124672 |
| observed_ebbu | previous_current | 2367 / 6482 | 2785 / 3697 / 11 / 2356 | 58.097% | 42.965% | 0.465% | 58.824% | 0.085564 |
| observed_ebbu | baseline | 2367 / 6482 | 2073 / 4409 / 61 / 2306 | 49.486% | 31.981% | 2.577% | 47.059% | 0.086396 |
| observed_ebbu | private_matched | 2367 / 6482 | 2067 / 4415 / 61 / 2306 | 49.418% | 31.888% | 2.577% | 11.765% | 0.086396 |
| observed_ebbu | private_c2 | 2367 / 6482 | 2066 / 4416 / 61 / 2306 | 49.407% | 31.873% | 2.577% | 5.882% | 0.086943 |
| observed_iscx | frozen_v6 | 70 / 1996 | 632 / 1364 / 0 / 70 | 33.979% | 31.663% | 0.000% | 22.535% | 0.148829 |
| observed_iscx | previous_current | 70 / 1996 | 1022 / 974 / 0 / 70 | 52.856% | 51.202% | 0.000% | 49.296% | 0.067721 |
| observed_iscx | baseline | 70 / 1996 | 632 / 1364 / 0 / 70 | 33.979% | 31.663% | 0.000% | 19.718% | 0.077935 |
| observed_iscx | private_matched | 70 / 1996 | 623 / 1373 / 0 / 70 | 33.543% | 31.212% | 0.000% | 7.042% | 0.077935 |
| observed_iscx | private_c2 | 70 / 1996 | 618 / 1378 / 0 / 70 | 33.301% | 30.962% | 0.000% | 0.000% | 0.077798 |
| observed_global | frozen_v6 | 30627 / 19373 | 4977 / 14396 / 14 / 30613 | 71.180% | 25.690% | 0.046% | 28.940% | 0.112897 |
| observed_global | previous_current | 30627 / 19373 | 6254 / 13119 / 13 / 30614 | 73.736% | 32.282% | 0.042% | 20.917% | 0.086940 |
| observed_global | baseline | 30627 / 19373 | 5263 / 14110 / 9 / 30618 | 71.762% | 27.167% | 0.029% | 18.625% | 0.079578 |
| observed_global | private_matched | 30627 / 19373 | 5219 / 14154 / 8 / 30619 | 71.676% | 26.940% | 0.026% | 6.017% | 0.079578 |
| observed_global | private_c2 | 30627 / 19373 | 5212 / 14161 / 9 / 30618 | 71.660% | 26.903% | 0.029% | 4.011% | 0.088854 |

Dampak penting: baseline yang disaring memperoleh recall global 27,17% dibanding model riset 11 sumber sebelumnya 32,28%, dan FPR vendor 2,51% dibanding 0,79%. Expert diagnostik hanya menangkap 4,01% phishing private hosting global pada policy private yang ketat. Penyaringan hak sumber membutuhkan pengganti benign yang berkualitas; membuang sumber saja tidak menjamin perbaikan model. Seluruh regresi dipertahankan. Tidak ada kandidat percobaan ini yang menggantikan artifact layanan atau menjadi pemenang produksi.

JSON lengkap memuat precision sampel, calibration bins/ECE/logloss, counts, Wilson dan 1.000 bootstrap domain berpasangan, warning/HIGH serta private hosting. Feed positif saja tidak diberi FPR/precision/accuracy. Sampel PhishBench hanya dua benign; nol FP tetap mempunyai ketidakpastian besar.

## Yang masih menghalangi produksi

- Input Indonesia aktual seluruhnya kosong, dan 170 kasus review development belum memiliki pasangan review manusia yang lengkap. Antrean development bukan final gold baru.
- Target recall/FPR pada independent Indonesia gold, audit kampanye/waktu serta regresi private hosting belum terselesaikan.
- Hak sumber hulu, attribution dan izin penggunaan produksi belum ditetapkan hanya dengan membaca metadata CC BY penerbit.
- Uji jaringan/TLS/multiworker, kuota terdistribusi, resource/process supervision dan SLA di lingkungan deployment belum dilakukan. Thread yang macet memerlukan isolasi proses/supervisor; timeout respons tidak menghentikannya paksa.

**274 tes lulus**, nol gagal/error/skip. Parity dan confusion matrix seluruh 11 cohort diperiksa ulang. Semua sidecar/registry, holdout termasuk 169.393 Mendeley reserved, binary, metadata dan threshold asli tetap utuh. production_ready=false.

[Protokol](v6-readiness-20261107-protocol.json), [evaluasi JSON](v6-readiness-model-evaluation.json), [verifikasi](v6-readiness-verification.json), [load test](v6-shadow-gateway-load-test.json), [audit sumber](../provenance/v6-readiness-license-screening.json), [panduan gateway](../../ai-agent-docs/v6-shadow-gateway.md).

Reproduksi pemeriksaan: `python scripts/verify_v6_readiness.py` dan `python scripts/render_v6_readiness.py`. Run/data/model/score berada pada `ml/runs/v6-readiness-20261107/` yang diabaikan Git. Runner menolak overwrite model/evaluasi yang telah dibekukan.
