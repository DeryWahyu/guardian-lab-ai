# Rencana ML Guardian Lab — v6

Model aktif tunggal adalah [frozen Logistic Regression v6](selected-model-v6.md). Notebook utama [guardian_lab_url_qr_v6.ipynb](../guardian_lab_url_qr_v6.ipynb) memeriksa dan memuat artifact; tidak melakukan training ulang.

Representasi menggunakan hostname/path tersanitasi, tanpa query/fragment dan tanpa skema sebagai fitur classifier. TF-IDF karakter/kata serta fitur numerik dipakai oleh classifier dan kalibrator sigmoid yang sudah dibekukan. Data fitting 532.793 URL dipisahkan berdasarkan domain/tenant dari tune 84.000, calibration 40.104 dan threshold 46.707. Vocabulary/scaler hanya di-fit pada fitting.

Prioritas berikutnya adalah pemeriksaan privasi, parity inferensi, kualitas bukti label serta validasi Indonesia. Pemilihan v6 tidak menghapus recall yang rendah, regresi benchmark atau kebutuhan benign kontemporer. Perubahan sanitizer harus berversi dan tidak menimpa binary/notebook training asli.

Inferensi URL-only sepenuhnya offline. QR perlu didekode caller. API tetap shadow dan tidak menyatakan LOW sebagai aman. Halaman/redirect, DNS, sandbox, APK dan QRIS berada di luar scope ini.

Gunakan [protokol data v6](data-improvement-v6-plan.md), [riset sumber](url-qr-dataset-research.md), [kontrak layanan](shadow-api-contract.md), [release policy](../ml/policies/url-qr-release-gates.json) dan [rencana gold Indonesia](indonesia-gold-set-plan.md). Tidak memilih threshold/model dari benchmark teramati dan tidak membuat reviewer atau label manusia otomatis.
