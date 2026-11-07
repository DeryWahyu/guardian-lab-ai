# Guardian Lab AI — Logistic Regression v6

Repository ini mempertahankan **satu model aktif: frozen Logistic Regression v6**, sesuai instruksi pengguna pada 3 November 2026. Notebook utama adalah [guardian_lab_url_qr_v6.ipynb](guardian_lab_url_qr_v6.ipynb). Model membaca URL dan URL hasil dekode QR; layanan berstatus riset/internal shadow. Eksperimen pengembangan terpisah diizinkan pengguna pada 5 November 2026 dan tidak mengganti model layanan.

**Ambang layanan aktif, 7 November 2026:** sesuai instruksi pengguna, warning sekarang **0,5**, sedangkan HIGH tetap **0,9884744926236343**. Binary, kalibrasi, skor dan metadata training v6 tetap asli. Kebijakan `v6-user-warning-0.5-20261107` dicatat terpisah dalam manifest; `geek.thresholds` menampilkan ambang aktif dan `geek.frozen_thresholds` menyimpan ambang historis. Perubahan dipilih pengguna setelah melihat diagnosis dataset, bukan validasi independen atau optimasi pada development. [Rincian kebijakan dan konsekuensinya](ai-agent-docs/v6-serving-threshold-0p5.md). Tabel benchmark lama di bawah tetap memakai ambang historis yang disebutkan.

**Untuk pengembang web:** ikuti [panduan integrasi backend](ai-agent-docs/web-integration-v6.md). [GitHub Release v6](https://github.com/DeryWahyu/guardian-lab-ai/releases/tag/v6-shadow-20261103) menyediakan binary model dan metadata asli; laporan hasil serta notebook tersedia langsung di repository.

**Perbaikan operasional terbaru:** [gateway internal terautentikasi](ai-agent-docs/v6-shadow-gateway.md) menambahkan key backend wajib, kuota per proses, batas konkurensi/ukuran, deadline, perlindungan path sensitif dan monitoring agregat. Uji model asli memperoleh 100/100 sukses pada konkurensi 2, p95 lokal sekitar 17,8 ms; burst berlebih ditolak tanpa score/band dan peak inference tetap 2. Ini ASGI in-process dengan kuota benchmark yang dilonggarkan, bukan bukti SLA deployment. Manifest gateway baru mengikat source/dependency dan manifest v6 asli; prediksi yang didukung tetap identik. **274 tes lulus**.

[Eksperimen kesiapan model](ml/reports/v6-readiness-improvements.md) juga melatih ulang 568.431 URL dengan sumber direct NC/tidak jelas dikeluarkan dari fitting dan seluruh development, serta menguji dua expert Logistic Regression private hosting. Expert gagal guard dan filter sumber menurunkan recall global menjadi 27,17% dari kandidat 11 sumber sebelumnya 32,28%; FPR vendor meningkat menjadi 2,51%. Kandidat tidak dipromosikan. Deklarasi CC BY penerbit belum menyelesaikan hak sumber hulu atau commercial clearance. Input Indonesia dan pasangan review manusia tetap kosong. Layanan tetap shadow dengan `production_ready=false`; [verifikasi lengkap](ml/reports/v6-readiness-verification.json) mempertahankan semua regresi dan hambatan produksi.

## Model dan batas penggunaan

- TF-IDF karakter/kata dan fitur numerik URL, dilatih pada **532.793 URL** dari lima sumber.
- Artifact: `ml/runs/notebook-tfidf-logistic-v6/artifacts/url-core-logistic-v6.joblib`.
- SHA-256: `f332bcbf7665955677e17daa73c487a7e1572a18d7f465b87e73caaa72e06319`.
- Threshold asli: warning `0.904713285827399`, high `0.9884744926236343`.
- Threshold layanan aktif: warning `0.5`, high `0.9884744926236343`; skor model tidak berubah.
- Tidak membaca halaman, mengikuti redirect, melakukan DNS, mendekode gambar QR, memeriksa APK atau mengautentikasi QRIS.
- LOW tidak menjamin aman. Skor terkalibrasi pada data riset, bukan probabilitas trafik Indonesia. Validasi Indonesia dan release gate belum terpenuhi.
- Model turunan DeepURLBench dibatasi untuk riset nonkomersial sesuai provenance yang tercatat.

## Hasil v6 dengan threshold warning asli

| Evaluasi | Jumlah URL | Accuracy | Recall phishing | FPR |
| --- | ---: | ---: | ---: | ---: |
| DeepURLBench holdout domain v6 | 20.000 | 93,23% | 46,31% | 0,944% |
| PhishTank 2026, positif saja | 9.269 | Tidak tersedia | 46,53% | Tidak tersedia |
| Phresh, benchmark teramati | 80.052 | 63,75% | 43,10% | 0,161% |
| URL-Phish, benchmark teramati | 85.824 | 96,82% | 55,39% | 0,093% |
| Audit manusia teramati | 33 | 45,45% | 18,18% (4/22) | 0/11 benign |

Pada holdout vendor, 1.187 dari 2.211 phishing terlewat. Interval Wilson FPR sekitar [0,812%; 1,098%], sehingga angka 0,944% belum membuktikan batas FPR di bawah 1%. Nol FP dari 11 benign pada audit manusia tidak membuktikan FPR rendah. Holdout vendor berasal dari sumber yang juga digunakan dalam development; benchmark historis tetap berstatus teramati.

[Laporan v6 lengkap](ml/reports/data-improvement-v6.json) mempertahankan seluruh metrik, interval, kalibrasi, provenance dan perbandingan historis. Pada kontrol tambahan dengan target false alarm development yang sama, recall PhishTank v6 46,53% dibanding baseline kontrol 26,59%; dibanding kebijakan baseline asli 55,48%, recall v6 menurun. [Kontrol yang dideklarasikan terlambat](ml/reports/v6-low-fpr-control.json) tetap dilaporkan terpisah.

[Pengujian ulang kualitas v6](ml/reports/v6-quality-evaluation.md) memprediksi ulang 29.269 URL yang sudah pernah teramati, memeriksa pemisahan domain/digest, menjalankan 70 tes, serta mengukur interval per domain, kalibrasi dan latency lokal. Hasil menegaskan bahwa recall masih rendah dan release gate belum terpenuhi. [Grafik evaluasi](ml/reports/v6-quality-evaluation.png) serta [laporan numerik](ml/reports/v6-quality-evaluation.json) tersedia; ini bukan holdout independen baru dan tidak mengubah model/threshold.

## Eksperimen pengembangan terpisah

[Eksperimen pengembangan v6](ai-agent-docs/v6-development-experiment.md) melatih tiga kandidat Logistic Regression dengan sanitasi path berversi, kurasi fitting, serta variasi bobot sumber/kelas/kasus sulit. Seleksi memakai tune; calibration dan threshold tetap terpisah. [Hasil dan perbandingan](ml/reports/v6-development-experiment.md), [JSON lengkap](ml/reports/v6-development-experiment.json), dan [grafik](ml/reports/v6-development-experiment.png) mencatat pemeriksaan pada benchmark yang sudah pernah teramati. Ini bukan holdout independen baru atau validasi Indonesia. Artifact kandidat tersimpan lokal, sementara API dan notebook utama tetap memakai v6 asli.

Hasilnya belum menunjukkan peningkatan menyeluruh: kandidat terpilih memperoleh recall vendor 45,91% dengan FPR 0,978%, dibanding v6 46,31% dan 0,944%. Syarat peningkatan development tidak terpenuhi; 90 tes teknis lulus, tetapi kelulusan tes tidak berarti kandidat lebih akurat atau siap produksi.

[Evaluasi diagnostik lanjutan](ml/reports/v6-diagnostic-evaluation.md) mengaudit 84.000 URL tune dan 29.269 URL benchmark teramati, menyiapkan antrean review konflik secara lokal, serta membandingkan lima kebijakan threshold hanya pada development. Sebagian besar false negative vendor berada di luar private hosting; penurunan threshold meningkatkan recall sekaligus false alarm. Semua 33 konflik scheme-free berasal dari pasangan HTTP/HTTPS PhiUSIIL; label yang benar masih perlu bukti manusia. [Persiapan validasi Indonesia](ai-agent-docs/v6-indonesia-validation-readiness.md) mencatat bahwa kandidat dan review aktual masih kosong, sehingga metrik Indonesia belum tersedia.

[Benchmark LegitPhish V2](ml/reports/legitphish-v6-evaluation.md) memakai 42.716 URL setelah audit privasi, duplikat dan overlap: 42.688 label phishing dan hanya 28 benign. Recall warning v6 66,01% (28.179 TP/14.509 FN); 0/28 FP belum membuktikan FPR rendah karena Wilson upper 95% mencapai 12,064%. Ini benchmark global historis berbasis label penerbit, bukan validasi Indonesia atau bukti model meningkat. [Prosedur dan replay](ai-agent-docs/legitphish-v6-evaluation.md) mencatat amendemen QA untuk satu baris tanpa label, pembekuan sebelum scoring, serta sidecar exposure lokal. Seluruh 107 tes teknis lulus; model/threshold aktif tetap v6 asli.

[Eksperimen penggabungan tiga dataset tambahan](ml/reports/v6-expanded-data-evaluation.md) mengaudit 296.251 baris CompPhish/Wangchuk/PhishBD dan mempertahankan 118.319 URL baru. Tiga kandidat Logistic Regression dilatih pada 595.934 URL dari delapan sumber, dengan holdout domain baru 11.636 URL yang dipisahkan sebelum training. Pada holdout yang sama, kandidat terpilih menaikkan recall 29,86% menjadi 38,25% dan menurunkan FPR 2,53% menjadi 0,40%. Recall benchmark lama justru menurun, sehingga kandidat tetap riset dan tidak menggantikan v6 aktif. [Prosedur dan caveat sumber](ai-agent-docs/v6-expanded-data-experiment.md), [hasil numerik](ml/reports/v6-expanded-data-evaluation.json), [grafik](ml/reports/v6-expanded-data-evaluation.png), serta [kontrol tambahan yang dideklarasikan terlambat](ml/reports/v6-expanded-matched-control.json) mempertahankan semua regresi. Jumlah tes terkait kini 116 lulus; validasi Indonesia dan syarat produksi belum terpenuhi.

[Eksperimen sumber data terarah](ml/reports/v6-targeted-evaluation.md) menambahkan PWD2021 dari rilis peneliti berlisensi CC BY 4.0: 80.000 URL mentah, dengan 34.084 URL baru setelah sanitasi, deduplikasi dan audit paparan. Enam kandidat Logistic Regression diuji dengan resep yang sama; kandidat terpilih dilatih pada 616.050 URL dari sembilan sumber. Pada holdout domain PWD berisi 3.544 URL historis, recall naik dari v6 aktif 49,89% menjadi 55,34%, sementara FPR turun 0,54% menjadi 0,24%. Dibanding kandidat riset sebelumnya, recall naik 35,56% menjadi 55,34%, dengan FP bertambah dari 3 menjadi 4 pada 1.654 benign.

Peningkatan belum menyeluruh terhadap v6 aktif: recall vendor 43,65% dibanding 46,31%, dan PhishTank 43,53% dibanding 46,53%. Pada vendor FPR turun menjadi 0,635%, tetapi kalibrasi Brier/ECE memburuk. Semua hasil, ketidakpastian dan kebijakan tambahan yang ditetapkan sebelum test tersedia di [laporan lengkap](ml/reports/v6-targeted-evaluation.json), [grafik](ml/reports/v6-targeted-evaluation.png), [kontrol kandidat sebelumnya](ml/reports/v6-targeted-previous-control.json), serta [audit jurnal/repositori](ai-agent-docs/research/v6-targeted-source-audit-20261105.md). [Verifikasi akhir](ml/reports/v6-targeted-verification.json) mencatat 132 tes lulus tanpa kegagalan/skip dan parity 130 probe dengan delta nol. PWD adalah data global historis, bukan gold Indonesia; layanan dan notebook utama tetap frozen v6 asli, `production_ready=false`.

[Eksperimen pembobotan terbaru](ml/reports/v6-weighted-evaluation.md) mempertahankan 616.050 URL fitting dari sembilan sumber, menguji tiga pembobotan domain/sumber dengan dua kalibrator, serta mengaudit 107.094 URL development. Dari rilis publik Zenodo V2, 12.587 URL baru setelah audit overlap dicadangkan seluruhnya untuk test: 9.643 benign dan 2.944 phishing. Pada holdout ini, recall kandidat riset sebelumnya naik **52,79% menjadi 56,76%**, dengan FPR 0,446% menjadi 0,415%; v6 aktif memperoleh recall 52,58% dan FPR 0,881%. Interval berpasangan 95% kenaikan recall terhadap control riset adalah 3,15–4,80 percentage point; selisih FPR terhadap control masih mencakup nol.

Trade-off tetap ada: pada benchmark vendor teramati, recall control riset naik 43,65% menjadi 47,31%, tetapi FPR naik 0,635% menjadi 0,899% dan kalibrasi memburuk. Recall PhishTank positif saja naik 43,53% menjadi 46,81%; hasil ini tidak menyediakan FPR. Beberapa kelompok URL development juga mengalami kenaikan FPR. [Prosedur dan sumber](ai-agent-docs/v6-weighted-experiment.md), [angka lengkap](ml/reports/v6-weighted-evaluation.json), [grafik](ml/reports/v6-weighted-evaluation.png), [audit](ml/reports/v6-weighted-development-audit.md) dan [verifikasi](ml/reports/v6-weighted-verification.json) tersimpan lokal. Sebanyak **158 tes lulus**, dengan parity 130 kasus dan delta nol. Antrean 170 kasus sudah disiapkan, tetapi review manusia dan gold Indonesia tetap kosong. Kandidat tetap riset; model layanan/notebook asli tidak diganti dan `production_ready=false`.

[Eksperimen fitur URL dan data lanjutan](ai-agent-docs/v6-segmented-experiment.md) menguji tiga variasi hostname/subdomain/path, sigmoid/beta calibration, serta arm terpisah dengan **52.334 URL fitting tambahan** dari StealthPhisher: total 668.384 URL dari sepuluh sumber. Sebanyak 34.895 URL StealthPhisher dicadangkan pada domain terpisah; PhishBench menyediakan 272 URL penerbit baru, tetapi hanya dua benign sehingga FPR-nya tidak dapat dinilai dengan yakin. Semua sumber merupakan bukti label penerbit global, bukan gold Indonesia.

**Kandidat riset sebelumnya tetap dipertahankan.** Sembilan varian baru belum lolos seluruh gate development: recall rata-rata per sumber terbaik naik hanya 50,09% menjadi 50,61%, dan beberapa sumber mengalami regresi. Penambahan data memperbaiki macro Brier menjadi 0,088479 dari 0,091928, tetapi recall rata-rata menjadi 50,06% dan recall salah satu sumber turun 3,22 percentage point. [Audit cakupan](ml/reports/v6-segmented-data-coverage.json) juga menemukan nol benign tambahan dengan URL panjang/path dalam; kebutuhan hard benign belum tertutup. [Laporan beku](ml/reports/v6-segmented-evaluation.md), [angka lengkap](ml/reports/v6-segmented-evaluation.json), [grafik](ml/reports/v6-segmented-evaluation.png) dan [verifikasi](ml/reports/v6-segmented-verification.json) memuat evaluasi challenger gagal-gate tanpa menggunakannya untuk memilih ulang pemenang. Seluruh **184 tes lulus**; 130 probe saved-model tetap identik. Pengguna menyatakan belum ada reviewer: 170 kasus tetap menunggu review, dan input Indonesia aktual masih kosong. Layanan/notebook tetap frozen v6 asli, `production_ready=false`.

Pengujian challenger yang telah dibekukan pada 34.895 URL StealthPhisher memperoleh recall 61,83% dibanding control riset 60,51% (delta berpasangan 95% +0,80–1,78 percentage point), dengan FP 2 dibanding 1 pada 26.578 benign. Brier/ECE sumber baru memburuk, dan distribusi benign tidak mencakup URL panjang/path dalam. Pada PhishBench, recall 58,52% dibanding 56,67%, tetapi interval selisih mencakup nol dan hanya tersedia dua benign. Hasil yang menjanjikan ini tetap diagnosis kandidat gagal-gate; keputusan seleksi tidak diubah memakai hasil test.

**Evaluasi eksternal, 6 November 2026:** [uji eksternal dan subset `.id`](ml/reports/v6-indonesia-external-evaluation.md) mengaudit 450.176 URL penerbit, menyisihkan seluruh overlap, lalu menguji 50.000 URL global dan 306 URL `.id` pada domain baru. Recall global v6 aktif 25,69% dibanding kandidat riset yang sudah ada 30,00%; pada `.id`, 38,59% dibanding 40,94% (115 dibanding 122 dari 298 phishing). Selisih `.id` belum meyakinkan secara statistik, dan hanya delapan benign sehingga 0 FP tidak membuktikan FPR rendah. Ini benchmark label penerbit dengan proxy suffix, **bukan validasi manusia Indonesia yang selesai**. Tidak ada training/promosi baru. [Census aktual](ml/reports/v6-indonesia-evidence-status.json) tetap menemukan input Indonesia kosong dan nol pasangan review pada 170 kasus development; [metode dan verifikasi](ai-agent-docs/v6-indonesia-external-evaluation.md) tersedia. Model tetap belum siap produksi.

**Eksperimen lanjutan, 7 November 2026:** [learning curve dan lima ablation](ai-agent-docs/v6-learning-experiment.md) selesai dengan delapan classifier baru dan **221 tes lulus**. Recall rata-rata per sumber pada 25%, 50%, 75%, dan 100% domain fitting adalah **34,93% → 47,46% → 48,90% → 50,09%**. Penambahan 3.056 URL ISCX membuat fitting menjadi 619.106 URL, tetapi recall turun menjadi 49,34%. Regularisasi `C=8` memperoleh 50,84% dengan kalibrasi yang memburuk; seluruh kandidat baru gagal memenuhi gate, sehingga control riset sebelumnya tetap dipertahankan.

Pada **8.849 URL Ebbu eksternal**, challenger `C=8` menaikkan recall control riset 41,14% menjadi 41,95% (delta berpasangan 95% +0,20–1,46 percentage point), dengan FP 11 menjadi 12 dari 2.367 benign; Brier memburuk 0,091345 menjadi 0,096791. Pada **2.066 URL ISCX holdout**, recall 38,48% menjadi 38,53% dan interval selisih mencakup nol. Nol FP dari hanya 70 benign mempunyai batas atas Wilson sekitar 5,20%, sehingga tidak membuktikan FPR populasi rendah. Pada benchmark global 50.000 yang sudah teramati, recall naik 30,00% menjadi 30,81%, tetapi FP 16 menjadi 21 dan Brier memburuk. Hasil test tidak mengubah keputusan seleksi yang telah dibekukan.

[Laporan lengkap](ml/reports/v6-learning-evaluation.md), [JSON](ml/reports/v6-learning-evaluation.json), [grafik](ml/reports/v6-learning-evaluation.png), [verifikasi](ml/reports/v6-learning-verification.json), dan [audit sumber](ai-agent-docs/research/v6-learning-source-audit-20261106.md) tersedia. Seluruh 118.038 input supported baru dicatat dalam sidecar exposure; semua 169.393 Mendeley reserved tetap tidak dipakai untuk training/development. Kekurangan hard benign belum tertutup: tambahan fitting hanya memiliki 40 kasus unik. Hak data Ebbu dan replika ISCX belum memiliki clearance komersial/redistribusi; artifact tambahan tetap lokal riset. Layanan/notebook tetap frozen v6 asli, tanpa klaim gold Indonesia atau kesiapan produksi.

**Retraining recipe v6 asli dengan data saat ini, 7 November 2026:** [dua model terkontrol](ai-agent-docs/v6-current-data-retraining.md) memakai constructor/hyperparameter asli v6: char 100k, word 20k, C=2, bobot sumber akar kuadrat dan sigmoid tanpa bobot. Model utama dilatih dari nol pada **671.440 URL dari 11 sumber**, dibanding kontrol lima sumber terkurasi 524.699 URL serta binary frozen v6. Seluruh test tetap dicadangkan; tidak ada parameter dipilih dari hasil test.

Dibanding v6 asli, recall meningkat pada **9 dari 11 benchmark historis**. Pada global 50.000 URL, accuracy naik **71,18% menjadi 73,74%**, recall **25,69% menjadi 32,28%**, dan FP 14 menjadi 13 pada 30.627 benign. Interval berpasangan 95% kenaikan recall adalah +6,08–7,07 percentage point; perubahan FPR masih mencakup nol. Expanded sources memperoleh recall 29,86% → 47,09% dan FPR 2,53% → 1,02%; PWD2021 49,89% → 57,83% dan FPR 0,54% → 0,24%. Holdout domain tersebut tetap berstatus teramati, bukan pengujian independen baru.

Regresi tetap ada: recall PhishTank positif turun **46,53% → 45,41%**, recall private hosting global **28,94% → 20,92%**, dan kalibrasi vendor memburuk. Karena itu peningkatan belum menyeluruh dan gate regresi development belum terpenuhi. **237 tes lulus**, serta seluruh skor/confusion matrix dan kecocokan recipe diperiksa ulang. [Laporan lengkap](ml/reports/v6-current-retrain-evaluation.md), [JSON](ml/reports/v6-current-retrain-evaluation.json), [grafik](ml/reports/v6-current-retrain-evaluation.png), dan [verifikasi](ml/reports/v6-current-retrain-verification.json) tersedia. Model baru berada di `ml/runs/v6-current-retrain-20261107/current_v6_recipe.joblib`; layanan/notebook tetap v6 asli, `production_ready=false`.

## Memakai v6 di Next.js tanpa training ulang

**Bisa. Model v6 sudah dilatih dan tersimpan sebagai `.joblib`.** Pengembang cukup mengunduh artifact beserta metadata aslinya, lalu menjalankan inferensi. Tidak perlu training ulang, mengunduh dataset atau menjalankan notebook terlebih dahulu.

Alurnya: **frontend Next.js → backend Next.js → API Python v6 → hasil prediksi JSON**.

1. Siapkan Python 3.12 dan dependency sesuai bagian [Menjalankan v6](#menjalankan-v6).
2. Jalankan `python scripts/install_v6_model.py` menggunakan Python environment proyek untuk mengunduh serta memverifikasi model beku.
3. Jalankan layanan `guardian_ml.shadow_service:create_app` sesuai perintah Uvicorn di bawah.
4. Atur `GUARDIAN_ML_URL=http://127.0.0.1:8001` pada konfigurasi server Next.js. Backend Next.js mengirim `POST /predict` dengan body JSON, misalnya `{"url":"https://example.org/login","input_type":"URL"}`.

Jika Next.js dan API Python berada pada server berbeda, gunakan alamat layanan yang dapat dijangkau backend Next.js melalui jaringan privat. Alamat localhost hanya sesuai jika keduanya berjalan pada host yang sama. Tampilan web memakai `human` dan `risk_band` dari respons; timeout, unsupported atau unavailable tetap perlu verifikasi dan tidak menjadi SAFE.

[Panduan integrasi backend](ai-agent-docs/web-integration-v6.md) menyediakan langkah pemasangan lengkap, contoh pemanggilan JavaScript dan makna hasil. Penggunaan tetap untuk riset nonkomersial/internal shadow dengan `production_ready=false`.

## Menjalankan v6

Python 3.12 diperlukan. Dari root repository:

```powershell
python -m venv ml/.venv
ml/.venv/Scripts/python.exe -m pip install -e "./ml[test,dev,serve]"
ml/.venv/Scripts/python.exe scripts/install_v6_model.py
ml/.venv/Scripts/python.exe -m pytest -p no:cacheprovider ml/tests -q
ml/.venv/Scripts/python.exe scripts/validate_v6.py
ml/.venv/Scripts/python.exe -m uvicorn guardian_ml.shadow_service:create_app --factory --host 127.0.0.1 --port 8001 --no-access-log
```

Pada Linux/macOS gunakan `ml/.venv/bin/python`. Installer memperoleh artifact dan metadata `reports/frozen-v6.json` dari release resmi dan memverifikasi checksum sebelum pemasangan. Binary tetap tidak disimpan dalam history Git. Tanpa artifact, layanan mengembalikan unavailable tanpa skor/risk band; notebook tetap menampilkan laporan agregat. Tes artifact nyata dilewati pada checkout tanpa binary.

Buka notebook utama dengan kernel Python proyek dan jalankan Run All. Tooling notebook dapat dipasang dengan `python -m pip install -e "./ml[notebook]"` menggunakan Python environment proyek. Notebook memverifikasi artifact, menampilkan hanya hasil v6, memeriksa referensi prediksi sintetis serta parity URL/QR; tidak training, mengubah threshold atau mengunjungi target. Jupyter/IPython adalah tooling notebook, bukan kebutuhan layanan inferensi.

Replay dua holdout asli v6 memerlukan cache lokal dan extra evaluasi:

```powershell
ml/.venv/Scripts/python.exe -m pip install -e "./ml[evaluation]"
ml/.venv/Scripts/python.exe scripts/validate_v6.py --evaluate-local --output ml/reports/v6-only-validation.json
ml/.venv/Scripts/python.exe -m ruff check --no-cache ml/src ml/tests scripts guardian_lab_url_qr_v6.ipynb
ml/.venv/Scripts/python.exe -m ruff format --check --no-cache ml/src ml/tests scripts guardian_lab_url_qr_v6.ipynb
```

Untuk mereproduksi pemeriksaan kualitas dan grafik dengan cache v6 asli yang tersedia lokal, pasang extra `quality`, lalu gunakan nama output baru agar laporan yang sudah selesai tetap tersimpan:

```powershell
ml/.venv/Scripts/python.exe -m pip install -e "./ml[quality]"
ml/.venv/Scripts/python.exe scripts/evaluate_v6_quality.py --plot --output-stem ml/reports/v6-quality-replay-local
```

## Bukti dan pemeliharaan

- [Identitas v6](ai-agent-docs/selected-model-v6.md), [kontrak API](ai-agent-docs/shadow-api-contract.md), [model card](ml/reports/model-card.md).
- [Protokol dan hasil v6](ai-agent-docs/data-improvement-v6-plan.md), [persiapan validasi Indonesia](ai-agent-docs/indonesia-gold-set-plan.md).
- [Provenance v6](ml/provenance/v6-origin.json) dan [referensi prediksi sintetis](ml/provenance/v6-runtime-reference.json), tanpa baris dataset.
- [Pembersihan v6 saja](ai-agent-docs/v6-only-cleanup.md). Model lain beserta notebook/kode/tes eksperimennya dihapus dari workspace aktif. Snapshot source sebelum cleanup dan notebook training v6 asli disimpan lokal dan diabaikan Git.

Parser/sanitizer v6 tetap beku. Redaksi regex memiliki keterbatasan, termasuk secret pendek pada parameter path seperti `/password=nilai`; perubahan representasi berikutnya perlu versi baru, pembaruan manifest dan tes parity. Metadata training asli tetap utuh, sementara loader hanya memeriksa subset dependency inferensi yang dinyatakan eksplisit dan cocok dengan versi training.
