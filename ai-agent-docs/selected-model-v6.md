# Satu Model: Frozen Logistic Regression v6

> Instruksi pengguna, 3 November 2026: hapus model lain dan pertahankan v6 saja. Penggunaan tetap riset/internal shadow.

| Komponen | Identitas |
| --- | --- |
| Model | Logistic Regression + TF-IDF karakter/kata + fitur numerik URL |
| Versi | `notebook-url-core-v6` |
| Notebook utama mandiri | [guardian_lab_url_qr_v6.ipynb](../guardian_lab_url_qr_v6.ipynb) |
| Artifact lokal | `ml/runs/notebook-tfidf-logistic-v6/artifacts/url-core-logistic-v6.joblib` |
| SHA-256 artifact | `f332bcbf7665955677e17daa73c487a7e1572a18d7f465b87e73caaa72e06319` |
| Metadata frozen | `ml/runs/notebook-tfidf-logistic-v6/reports/frozen-v6.json` |
| SHA-256 metadata | `4d2e6955af24d0507abce7bdfb65c7af7637183d3e26af75beaaa733846a2fb5` |
| Fitting | 532.793 URL, 118.689 fitur, classifier konvergen |
| Threshold warning asli | `0.904713285827399` |
| Threshold high asli | `0.9884744926236343` |
| API | `guardian_ml.shadow_service:create_app`, `POST /predict` |
| Manifest runtime | [shadow-runtime-manifest.json](../ml/policies/shadow-runtime-manifest.json) |

Binary, metadata training dan threshold asli tidak diganti. Notebook utama baru hanya memuat/memeriksa artifact dan laporan v6. Notebook training asli yang dahulu bernama `guardian_lab_url_qr_data_v6.ipynb` tetap utuh dalam snapshot lokal; [v6-origin.json](../ml/provenance/v6-origin.json) mencatat hash byte dan hash kode training. Referensi sintetis dibuat dari fungsi notebook asli sebelum dependensi model lama dihapus.

Loader memverifikasi subset dependency inferensi yang lengkap dan dinyatakan eksplisit. Set kosong, sebagian, tambahan tak dikenal atau versi berbeda dari metadata training ditolak. PyArrow hanya diperlukan untuk replay dataset; Matplotlib dan classifier lain tidak dibutuhkan untuk melayani v6. Referensi baseline dalam metadata training adalah bukti sejarah, bukan binary yang perlu dimuat saat inferensi.

V6 tidak dipilih sebagai pemenang universal dari accuracy test. Recall, regresi dan keterbatasan dalam [laporan asli](../ml/reports/data-improvement-v6.json) tetap berlaku. API tetap shadow, needs_review, production_ready=false. LOW bukan SAFE; validasi Indonesia belum tersedia.

Gunakan [kontrak API shadow](shadow-api-contract.md) untuk menjalankan layanan. CLI/model entry point lama dihapus. Tidak melakukan training, commit, push atau deployment sebagai bagian cleanup.
