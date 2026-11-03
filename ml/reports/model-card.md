# Model Card — Frozen Logistic Regression v6

Satu model untuk indikator phishing dari URL dan URL hasil dekode QR. Versi `notebook-url-core-v6`; status riset nonkomersial/internal shadow, `production_ready=false`. Artifact lokal dan metadata training asli dipertahankan.

## Representasi dan data

Hostname/path tersanitasi, query/fragment dikeluarkan identik dari kedua kelas dan skema tidak digunakan sebagai fitur classifier. TF-IDF karakter/kata serta 33 fitur numerik membentuk 118.689 fitur. Logistic Regression C=2, liblinear, konvergen pada 532.793 URL. Kalibrasi sigmoid dan dua threshold menggunakan partisi terpisah. Vocabulary/scaler hanya berasal dari fitting; domain/private tenant dipisah antar role.

Fitting: PhreshPhish 302.812, PhiUSIIL 116.096, DeepURLBench 100.000, PhishVN core 9.769 dan Mendeley 2020 4.116. Label vendor, komunitas dan audit manusia adalah tingkat bukti berbeda. Gold Indonesia belum tersedia; campaign independence belum sepenuhnya terverifikasi.

## Hasil dengan kebijakan asli

Warning 0.904713285827399, high 0.9884744926236343. Holdout vendor 20.000 URL memiliki warning confusion matrix TN=17.621, FP=168, FN=1.187, TP=1.024: accuracy 93,225%, precision 85,91%, recall 46,31%, FPR 0,9444%, balanced accuracy 72,68%, ROC-AUC 0,9404, Brier 0,09024. Wilson recall sekitar [44,24%; 48,40%], FPR [0,8125%; 1,0975%], dengan asumsi row-IID. Holdout domain berbeda berasal dari sumber yang juga dipakai development.

PhishTank positif saja: warning TP=4.313/9.269, recall 46,53%, Wilson sekitar [45,52%; 47,55%]; accuracy biner, FPR dan traffic precision tidak tersedia. Audit manusia teramati hanya menangkap 4/22 phishing, dengan 0/11 benign salah ditandai; sampel kecil ini tidak membuktikan FPR rendah.

[Laporan asli](data-improvement-v6.json) mencakup seluruh benchmark, kebijakan high, kalibrasi, interval dan regresi. Dibanding baseline asli, recall beberapa sumber menurun. [Kontrol tambahan](v6-low-fpr-control.json) memakai threshold baseline berbeda pada anggaran false alarm development yang sama dan dideklarasikan terlambat; tidak menggantikan perbandingan asli.

## Keterbatasan dan penggunaan

LOW bukan aman. Skor riset bukan probabilitas trafik Indonesia. Model tidak memeriksa konten/redirect/DNS, QR image, QRIS atau APK. Sanitizer regex tidak membuktikan anonimisasi lengkap dan memiliki gap pada secret pendek dalam assignment path. Feed positif dan benign historis tidak membentuk bukti temporal dua kelas yang valid.

Runtime menggunakan artifact/hash/metadata/schema/PSL offline yang diverifikasi. Unsupported/unavailable tanpa score/risk band. Monitoring hanya agregat dan metrik kualitas online null tanpa reviewed ground truth. Sumber DeepURLBench tercatat CC BY-NC 4.0 dan model dibatasi untuk riset nonkomersial. Aktivasi publik memerlukan release gate dan bukti manusia Indonesia yang belum dipenuhi.

Notebook utama [guardian_lab_url_qr_v6.ipynb](../../guardian_lab_url_qr_v6.ipynb) hanya memuat dan memeriksa model beku. Cleanup tidak mengubah bobot/threshold atau melakukan training. Identitas asli ada di [v6-origin.json](../provenance/v6-origin.json).
