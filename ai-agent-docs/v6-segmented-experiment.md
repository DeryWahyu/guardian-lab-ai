# Eksperimen fitur URL terpisah dan data terarah

Instruksi pengguna pada 6 November 2026 Asia/Jakarta melanjutkan perbaikan kandidat riset, pencarian data, kalibrasi dan persiapan review. Identitas run `20261105` memakai tanggal UTC. API/notebook utama, binary, metadata, dependency dan threshold frozen v6 tetap asli. Seluruh kandidat baru tetap Logistic Regression, lokal, nonkomersial dan `production_ready=false`.

## Pradeklarasi dan pemisahan

[Protokol fitur](../ml/reports/v6-segmented-20261105-protocol.json) ditulis sebelum fitting classifier dan scoring data baru. Tiga ablation menggunakan 616.050 URL fitting sembilan sumber yang sama: struktur numerik tambahan, teks hostname/subdomain/path terpisah, dan gabungan keduanya. Vocabulary/scaler tambahan di-fit hanya pada fitting asli; encoder dasar dan cache berurutan dipakai ulang dengan checksum dan replay nyata. Tidak ada skema, query, fragment, live reputation, DNS, HTML atau source ID sebagai fitur.

Representasi tambahan tetap memakai sanitizer eksperimen berversi yang meredaksi assignment secret pendek. Teks host memakai char TF-IDF 3–5, subdomain/path memakai word TF-IDF 1–2, dengan batas vocabulary dan bobot tetap. Delapan belas fitur struktur membedakan panjang/depth/path segments, karakter digit/tanda baca dan entropy host/subdomain/path. Transformasi tetap heuristik dan tidak diklaim anonimisasi sempurna. Parser frozen runtime tidak berubah.

Classifier C=2/liblinear dan pembobotan sumber/domain dipertahankan untuk mengisolasi efek fitur. Setiap classifier mendapat sigmoid calibration dan beta calibration berbasis Logistic Regression pada `log(p), -log(1-p)` dengan source-equal weights. Kalibrator di-fit pada calibration terpisah dan wajib monoton positif; perubahan ranking tidak diklaim dari kalibrasi monoton. Threshold strict 1% per sumber dan pooled 1% dipilih hanya dari threshold partition.

Beta calibration mengikuti keluarga pemetaan dari [Kull, Silva Filho dan Flach, AISTATS 2017](https://proceedings.mlr.press/v54/kull17a.html). Penelitian itu mendukung metode kalibrasinya, bukan jaminan peningkatan pada model phishing ini; manfaat aktual tetap ditentukan eksperimen terpisah dan holdout yang sesuai.

Seleksi menggunakan common tune saja. Gate recall minimal +2 percentage point, penurunan recall sumber maksimal 3 point, kenaikan macro Brier maksimal 0,001, kenaikan Brier sumber maksimal 0,005 dan kenaikan FPR sumber maksimal 0,25 point. Gate kalibrasi minimal penurunan macro Brier 0,002, penurunan recall maksimal 0,5 point dan kenaikan FPR maksimal 0,1 point. Brier juga mencerminkan discrimination/uncertainty; reliability bins dan ECE tetap dilaporkan. Bila tidak ada yang lolos, control riset sebelumnya dipertahankan; satu challenger gagal-gate dibekukan untuk diagnosis sebelum test.

## Sumber data tambahan

[Amendemen sumber sebelum fitting/prediksi](../ml/reports/v6-segmented-source-amendment.json) mempertahankan protokol awal dan mengizinkan arm augmentation terpisah. [StealthPhisher V1](https://data.mendeley.com/datasets/m2479kmybx/1), terbit 15 Januari 2025, CC BY 4.0, memiliki 336.749 URL dengan label literal `Phishing` 175.806 dan `Legitimate` 160.943, tepat sesuai jumlah penerbit. Hanya URL/label dipakai. Hash SHA-256 dan ukuran 93.319.036 byte dipin dari metadata repositori sebelum intake; pembacaan HTTP Range dibatasi, dilakukan dalam memori dan memverifikasi hash seluruh CSV. Gangguan transfer dicatat; raw CSV tidak disimpan dan target tidak dikunjungi.

Penerbit menyebut PhishTank, repositori spam dan user submissions. Tanggal observasi dan review independen setiap kasus tidak tersedia; klaim penerbit ini bukan human gold, Indonesia gold atau temporal 2026. Tidak ada label otomatis yang diperbaiki. Metadata sumber tidak menjamin kesesuaian setiap label.

Sanitasi mendukung 318.429 baris; 25 representasi konflik/50 baris dikarantina, 23.929 duplikat, 199.910 overlap URL/domain lama dan 7.311 melebihi domain cap dikeluarkan. Tersisa **87.229 URL baru**, dibagi domain deterministik sebelum training menjadi fit 52.334 (39.992 benign/12.342 phishing) dan test 34.895 (26.578 benign/8.317 phishing). Semua input tersanitasi, termasuk exclusions dan holdout, dicatat pada [pointer exposure](../ml/provenance/stealthphisher-segmented-exposure.json).

Arm `segmented_text_structure_augmented` memakai 668.384 URL fitting dari sepuluh sumber. Encoder tetap sama dan tidak di-fit ulang pada holdout. Calibration/threshold/tune lama tetap sama untuk perbandingan development; sumber tambahan belum terwakili dalam calibration. Holdout StealthPhisher adalah domain baru pada penerbit yang juga dipakai oleh arm augmentation, bukan independent-source benchmark untuk arm tersebut. Tidak memasukkan hasil prediksi test ke fitting atau seleksi.

[Audit coverage tanpa skor model](../ml/reports/v6-segmented-data-coverage.json) menemukan keterbatasan penting: tambahan fitting memiliki **nol benign dengan URL >120 karakter dan nol benign dengan path sedalam empat slash**. Hanya 43 benign pada private hosting. Sebanyak 9.334 phishing tambahan berada di luar private hosting, sehingga sumber membantu cakupan domain biasa tetapi belum menutup kebutuhan hard benign/path panjang. Holdout Stealth juga tidak memiliki URL >120 karakter. Bias struktur ini dapat membuat hasil sumber baru terlalu optimistis; benchmark lama dan diagnosis kelompok tetap wajib dilaporkan. Penambahan 52.334 kasus tidak dianggap bukti bahwa semua celah data sudah terpenuhi.

[PhishBench-External V2](https://data.mendeley.com/datasets/2ctjcnm9kn/2), terbit 27 Oktober 2025, CC BY 4.0, menyediakan 1.000 URL. Pemeriksaan pertama gagal pin integritas; retry selanjutnya cocok tepat ukuran/SHA. Nama target aktual `Results`, berbeda dengan `label` dalam deskripsi. [Amendemen intake sebelum prediksi](../ml/reports/v6-segmented-phishbench-intake-protocol.json) menetapkan alias dan mapping dokumentasi 0=benign/1=phishing setelah inspeksi agregat 500/500, tanpa melihat prediksi atau menebak dari URL.

Intake PhishBench dilakukan setelah seluruh StealthPhisher tercatat sebagai exposure. Dari 949 supported, setelah deduplikasi dan audit seluruh paparan tersisa **272 URL pada 232 domain: 270 phishing dan dua benign**. Semua dicadangkan, tidak masuk development. [Pointer exposure](../ml/provenance/phishbench-segmented-exposure.json) mempertahankan seluruh 949 supported termasuk exclusions. Dua benign tidak cukup untuk menilai FPR; bahkan 0/2 FP memiliki upper Wilson 95% sekitar 65,76%. Bukti label penerbit dan tanggal koleksi Juli 2025 tetap bukan Indonesia gold atau benign kontemporer.

## Review manusia dan Indonesia

Pengguna menyatakan belum ada reviewer. [Audit aktual](../ml/reports/v6-segmented-human-review-status.json) memeriksa 170 kasus di dua pack blind: nol pasangan review lengkap. Pemeriksa baru mendeteksi kolom yang merusak blind, ID kasus duplikat, locator berbeda dan reviewer ID sama. Dua ID/file tidak membuktikan independensi; bukti identitas dan pemeriksaan koordinator tetap diperlukan. Tidak ada label, reviewer, evidence atau adjudikasi yang dibuat.

Kelima CSV input Indonesia aktual tetap kosong. Sumber publik Indonesia yang diperiksa sebelumnya belum menyediakan raw URL beserta hak dan bukti review yang memenuhi protokol. Rilis [Phising URLs Khairun](https://zenodo.org/records/22054210) memiliki metadata terbatas dan tidak membuktikan relevansi Indonesia per kasus atau dua reviewer. Rilis [Negative Content Detection](https://zenodo.org/records/21137056) mencampur kategori UT1 gambling/adult/phishing/blog; blog atau kategori lainnya tidak otomatis diberi label benign. Tidak ada dataset tersebut diubah menjadi gold Indonesia. EdgePhish tetap tidak digabungkan karena provenance/koleksi yang belum direkonsiliasi. Tidak ada formulir akses atau kontak pihak lain dilakukan.

Target Indonesia tetap minimal 1.000 phishing/3.000 benign dengan dua reviewer independen, provenance/hak, QA privasi, waktu/kampanye dan holdout baru. Antrean error development tidak menjadi sampling frame gold final. Seluruh test lama, termasuk Zenodo websites V2 yang baru saja dinilai pada eksperimen sebelumnya, tetap teramati.

## Keputusan development

Keempat classifier baru konvergen. Bersama dua kalibrator per classifier dan beta calibration pada classifier control, terdapat sembilan varian baru. Seluruhnya gagal memenuhi gabungan gate yang sudah ditetapkan, sehingga **control riset sebelumnya dipertahankan**. Macro source recall control 50,09%; ablation struktur 50,47%, teks terpisah 50,61%, gabungan 50,32%, dan gabungan dengan tambahan data 50,06%. Macro Brier terbaik pada arm augmentation/beta turun dari 0,091928 menjadi 0,088479, tetapi recall sumber terburuk turun 3,22 percentage point. Ini belum memenuhi perbaikan deteksi dan pembatasan regresi.

Sesuai protokol, satu challenger gagal-gate `segmented_text__source_equal_beta` dibekukan untuk diagnosis, berdasarkan tune saja. Semua policy/artifact dan keputusan dipertahankan sebelum final scoring. Challenger ini tidak menjadi model pengganti; hasil test tidak dipakai memilih ulang kandidat atau threshold. Saved-model parity 130 kasus memiliki delta nol, dengan cache/inference delta nol. Seluruh 184 tes lokal lulus tanpa kegagalan, error atau skip.

## Hasil pengujian beku

[Laporan lengkap](../ml/reports/v6-segmented-evaluation.md), [JSON](../ml/reports/v6-segmented-evaluation.json), [grafik](../ml/reports/v6-segmented-evaluation.png) dan [verifikasi](../ml/reports/v6-segmented-verification.json) mencatat delapan cohort, uncertainty, kalibrasi, counts serta policy sekunder yang dibekukan sebelum test.

Challenger teks terpisah/beta, yang dilatih pada fitting asli 616.050 URL, memperoleh TP 5.142/FN 3.175/FP 2/TN 26.576 pada holdout Stealth 34.895 URL. Recall 61,83% dibanding control riset 60,51%; precision sampel 99,96% dan FPR 0,007525% dibanding control 0,003763% (FP 1). Interval domain berpasangan 95% kenaikan recall +0,80–1,78 percentage point, sedangkan selisih FPR mencakup nol. Brier memburuk 0,051211 menjadi 0,052526 dan ECE 0,104004 menjadi 0,109156. Benign tanpa URL panjang/path dalam membatasi klaim generalisasi; angka precision tinggi tidak menjadi estimasi trafik Indonesia.

PhishBench 272 URL menghasilkan TP 158/FN 112/FP 0/TN 2, recall 58,52% dibanding control 56,67%. Interval selisih recall [-0,37; +4,01] point mencakup nol. Dua benign dan bootstrap FPR degenerat tidak membuktikan FPR rendah; Wilson upper 95% 65,76% tetap dilaporkan. Brier sumber ini juga memburuk.

Pada benchmark teramati, recall angka titik naik di seluruh cohort: Zenodo websites V2 56,76% menjadi 57,61%, PWD 60,11% menjadi 62,33%, expanded 48,08% menjadi 48,55%, vendor 47,31% menjadi 48,85%, PhishTank positif saja 46,81% menjadi 48,52%, dan LegitPhish 73,59% menjadi 81,52%. FP vendor naik 160 menjadi 163 dan Zenodo 40 menjadi 44; selisih FPR tersebut belum pasti secara statistik. Semua regresi kualitas skor/kelompok tetap tercatat. Hasil test tidak dipakai mengubah gate, memilih ulang kandidat, threshold atau mengganti model.

**Keputusan tetap mempertahankan kandidat riset sebelumnya.** Challenger baru menjanjikan untuk penelitian berikutnya tetapi gagal gate development yang dipradeklarasikan. Eksperimen augmentation memang melatih 668.384 URL, tetapi arm itu gagal sebelum test dan bukan challenger yang hasil finalnya dilaporkan di atas. Penelitian konfirmasi berikutnya memerlukan protokol baru dan data final baru; test yang kini sudah dinilai tetap menjadi exposure teramati. V6 layanan/notebook asli tetap utuh dan belum ada kesiapan produksi atau gold Indonesia.

## Reproduksi lokal

Gunakan environment Python 3.12 dengan dependency inference v6 yang tetap dipin. Data, encoder, sparse matrices, model dan exposure tetap diabaikan Git. Run/intake beku tidak boleh ditimpa atau dihapus untuk mengklaim novelty.

```powershell
ml/.venv/Scripts/python.exe scripts/intake_v6_segmented.py
ml/.venv/Scripts/python.exe scripts/intake_v6_phishbench.py
ml/.venv/Scripts/python.exe scripts/audit_v6_human_review.py
ml/.venv/Scripts/python.exe scripts/experiment_v6_segmented.py --stage prepare
ml/.venv/Scripts/python.exe scripts/verify_v6_segmented.py --stage preflight
ml/.venv/Scripts/python.exe scripts/experiment_v6_segmented.py --stage train
ml/.venv/Scripts/python.exe scripts/experiment_v6_segmented.py --stage diagnose
ml/.venv/Scripts/python.exe scripts/experiment_v6_segmented.py --stage evaluate
ml/.venv/Scripts/python.exe -m pytest -p no:cacheprovider ml/tests -q --junitxml=ml/runs/v6-segmented-20261105/final-tests.xml
ml/.venv/Scripts/python.exe scripts/render_v6_segmented.py
ml/.venv/Scripts/python.exe scripts/verify_v6_segmented.py --stage final
```
