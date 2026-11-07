# Recipe v6 asli dengan data fitting saat ini

Pengguna meminta pelatihan menggunakan model v6 dengan data yang sekarang tersedia. Eksperimen ini memakai constructor/hyperparameter dari binary frozen v6 yang terverifikasi: Logistic Regression liblinear C=2, seed 20261101, TF-IDF karakter 2–5 maksimal 100.000, TF-IDF kata 1–2 maksimal 20.000, numeric scheme-free, bobot kata 0,7/numeric 0,2, bobot sumber akar kuadrat, dan kalibrator sigmoid tanpa bobot.

Ini berbeda dari eksperimen pembobotan/learning curve sebelumnya yang memakai encoder lebih besar serta bobot equal-source/domain. Estimator di-clone lalu dilatih dari nol: vocabulary, IDF, scaler, coefficient dan kalibrator lama tidak diwariskan. Parameter hasil training dibandingkan kembali dengan parameter artifact asli. Binary dan metadata v6 layanan tetap utuh.

## Hasil aktual

**Ada peningkatan pada banyak benchmark historis, tetapi belum merata.** Setelah dilatih ulang pada 671.440 URL dari 11 sumber, recall warning meningkat pada 9 dari 11 cohort dibanding frozen v6 dengan threshold aslinya. Accuracy meningkat pada semua 10 cohort dua kelas; angka ini tetap bergantung pada prevalensi masing-masing sampel dan tidak menggantikan recall/FPR.

| Benchmark teramati | Recall v6 asli → retrain | FPR v6 asli → retrain |
| --- | ---: | ---: |
| Global, 50.000 URL | 25,69% → **32,28%** | 0,0457% → 0,0424% |
| Expanded sources, 11.636 | 29,86% → **47,09%** | 2,53% → **1,02%** |
| PWD2021, 3.544 | 49,89% → **57,83%** | 0,54% → **0,24%** |
| Zenodo V2, 12.587 | 52,58% → **55,26%** | 0,88% → **0,43%** |
| StealthPhisher, 34.895 | 58,49% → **65,55%** | 0,0564% → 0/26.578 benign |
| Vendor, 20.000 | 46,31% → 46,00% | 0,94% → **0,79%** |
| PhishTank, 9.269 positif | 46,53% → **45,41% (regresi)** | Tidak tersedia |

Pada global, accuracy 71,18% menjadi **73,736%**, dengan 6.254 TP, 13.119 FN, 13 FP dan 30.614 TN. Recall bertambah 6,59 percentage point; interval bootstrap domain berpasangan 95% adalah **+6,08 hingga +7,07 pp**. Brier membaik 0,112897 menjadi 0,086940. Penurunan FP dari 14 menjadi 13 merupakan pengamatan satu sampel; interval selisih FPR masih mencakup nol.

Regresi tetap material. Recall private hosting global (349 phishing/1.900 benign) turun **28,94% menjadi 20,92%**, meskipun FP turun 4 ke 1. Pada feed PhishTank, interval delta recall adalah **−1,74 hingga −0,49 pp**. Pada vendor, delta recall memiliki interval yang mencakup nol, tetapi Brier memburuk 0,090239 menjadi 0,103913 dan ECE 0,154501 menjadi 0,178063.

Kontrol tambahan data dengan recipe/partisi development yang sama menaikkan macro recall tune dari 16,61% (lima sumber fitting) menjadi 47,44% (11 sumber). Frozen v6 pada threshold layanan asli memperoleh 45,50% pada tune yang sama. Angka 16,61% memakai threshold baru yang harus memenuhi batas pada seluruh sembilan sumber development, sehingga tidak boleh disajikan sebagai recall layanan v6 asli. Batas regresi FPR development/private-hosting terhadap kontrol belum terpenuhi; tidak ada promosi model. Hasil ini juga tidak membuktikan kemenangan terhadap seluruh kandidat riset terdahulu.

**237 tes lulus**, tanpa gagal/error/skip. Constructor classifier, vectorizer, scaler dan kalibrator cocok dengan v6 asli; confusion matrix warning/HIGH dihitung ulang dari skor tersimpan dan parity diuji setelah pemuatan ulang. Seluruh 195.834 kasus evaluasi sudah teramati sebelumnya; tidak ada klaim holdout independen baru, gold Indonesia atau kesiapan produksi.

Model baru tersimpan lokal di `ml/runs/v6-current-retrain-20261107/current_v6_recipe.joblib`. Layanan dan notebook utama tetap menggunakan binary v6 asli.

## Kontrol untuk pengaruh data

| Model | Fitting | Sumber | Tujuan |
| --- | ---: | ---: | --- |
| Frozen v6 asli | 532.793 | 5 | Referensi binary dan kebijakan layanan asli |
| Recipe v6 / foundation terkurasi | 524.699 | 5 | Kontrol dengan lima sumber awal dan kurasi privasi saat ini |
| Recipe v6 / fitting terbaru | 671.440 | 11 | Seluruh partisi fitting yang diizinkan saat ini |

Fitting terbaru menggabungkan base sembilan sumber 616.050 URL, StealthPhisher fit 52.334 dan ISCX fit 3.056. Perbandingan dua model baru menjaga recipe, representasi dan tiga partisi development tetap sama; ini mengukur pengaruh tambahan data dalam rancangan tersebut. Perbandingan langsung dengan frozen v6 juga melibatkan kurasi privasi dan komposisi development yang berubah, sehingga tidak seluruh selisih boleh disebut akibat jumlah data.

Metadata asli menyebut sumber kelima `mendeley2020`; alias deskriptif `mendeley` pada rancangan awal diperbaiki saat preflight, sebelum model dilatih atau test diprediksi. [Audit schema](../ml/reports/v6-current-retrain-source-schema-audit.json) menyimpan hash protokol sebelum/sesudah koreksi. Tidak ada label kasus yang diganti.

[Catatan perbaikan runner](../ml/reports/v6-current-retrain-preflight-repair.json) juga menyimpan kesalahan pembungkus threshold yang terdeteksi sebelum fitting pertama, arsip preflight, serta tes regresi penanganan policy. Aturan threshold asli tidak berubah; yang diperbaiki adalah pemakaian nilai hasil helper dalam runner baru.

## Pemisahan dan evaluasi

Kedua model memakai calibration 50.749, threshold 58.840 dan tune 107.094 yang sama. Semua dataset memakai sanitizer eksperimen berversi yang meredaksi assignment secret pendek. Curation fitting mempertahankan 671.440 URL tanpa konflik/duplikat tambahan. Sanitizer tetap heuristik dan bukan bukti anonimisasi penuh. Tidak ada target dikunjungi, HTML dieksekusi, atau baris dataset dikirim ke LLM.

Domain/private tenant, digest dan representasi diperiksa antara fitting, calibration, threshold, tune serta semua cohort test. Semua 169.393 Mendeley reserved, Ebbu external-only dan seluruh holdout lama tetap dipertahankan. Delapan exposure sidecar serta registry historis diikat checksum dan tidak dihapus/diganti. Data gabungan dan model disimpan pada folder lokal yang diabaikan Git.

Threshold warning/HIGH mengikuti aturan asli v6 pada threshold partition: FPR empiris per sumber 1%/0,1%. Frozen v6 dilaporkan dengan dua referensi: threshold layanan asli dan threshold yang dihitung dari development yang sama, tanpa mengganti score, binary, kalibrator atau konfigurasi layanan. Dua model baru ditetapkan sejak awal; tidak ada pencarian hyperparameter atau pemilihan pemenang dari test. Artifact/policy dibekukan sebelum replay.

Sebelas cohort historis dievaluasi: vendor, PhishTank positif saja, expanded sources, PWD2021, Zenodo V2, LegitPhish, StealthPhisher, PhishBench, Ebbu, ISCX dan global Mendeley. **Semua telah teramati sebelumnya.** Ini pengujian regresi atas eksperimen retraining yang terkontrol, bukan test independen baru atau validasi Indonesia. Laporan menyertakan counts, accuracy pada dua kelas, precision sampel, recall, FPR, Wilson, domain bootstrap berpasangan, Brier/ECE, reliability bins, warning/HIGH dan subgroup.

## Hasil dan reproduksi

- [Protokol sebelum fitting](../ml/reports/v6-current-retrain-20261107-protocol.json).
- [Laporan hasil](../ml/reports/v6-current-retrain-evaluation.md), [JSON](../ml/reports/v6-current-retrain-evaluation.json), [grafik](../ml/reports/v6-current-retrain-evaluation.png), [verifikasi](../ml/reports/v6-current-retrain-verification.json).
- Run lokal: `ml/runs/v6-current-retrain-20261107/`.
- Runner: `scripts/experiment_v6_current_retrain.py`, tahap `prepare`, `train`, `evaluate`, `check`.
- Verifikasi/laporan: `scripts/report_v6_current_retrain.py`.

Runner menolak overwrite freeze/evaluasi dan memeriksa hash sebelum melanjutkan checkpoint. Replay training memerlukan direktori/protokol baru dengan input terpin; jangan menghapus exposure agar data terlihat baru. Lisensi nonkomersial foundation dan ketidakjelasan hak data replika ISCX tetap berlaku. Tidak ada reviewer atau label Indonesia yang dibuat. Serving tetap shadow dengan `production_ready=false`; LOW tidak berarti aman.
