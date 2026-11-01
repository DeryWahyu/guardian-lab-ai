# Model Utama Sementara: Logistic Regression v6

> Keputusan pengguna, 1 November 2026: gunakan **v6 dahulu** sebagai satu model utama untuk URL dan URL hasil dekode QR. Status penggunaan tetap riset/pengujian internal shadow.

## Identitas yang dipakai

| Komponen               | Pilihan                                                                     |
| ---------------------- | --------------------------------------------------------------------------- |
| Model                  | Logistic Regression + TF-IDF karakter/kata dan fitur numerik URL            |
| Versi artifact         | `notebook-url-core-v6`                                                      |
| Notebook utama         | [guardian_lab_url_qr_data_v6.ipynb](../guardian_lab_url_qr_data_v6.ipynb)   |
| Artifact lokal asli    | `ml/runs/notebook-tfidf-logistic-v6/artifacts/url-core-logistic-v6.joblib`  |
| SHA-256 artifact       | `f332bcbf7665955677e17daa73c487a7e1572a18d7f465b87e73caaa72e06319`          |
| Jumlah fitting         | 532.793 URL                                                                 |
| Threshold warning asli | `0.904713285827399`                                                         |
| Threshold high asli    | `0.9884744926236343`                                                        |
| Manifest runtime       | [shadow-runtime-manifest.json](../ml/policies/shadow-runtime-manifest.json) |
| API internal           | `guardian_ml.shadow_service:create_app`, `POST /predict`                    |

API internal sudah memuat v6 sebelum keputusan ini; pemilihan ini menyelaraskan dokumentasi dan fokus kerja. Tidak menyalin atau mengganti binary, merename notebook beku, melakukan training ulang, atau mengganti threshold. Nilai threshold kontrol v6 pada eksperimen v9/v10 bukan kebijakan runtime yang dipilih.

## Fokus dan batas penggunaan

Pekerjaan aktif berpusat pada v6. Notebook utama v3 sebelumnya menjadi arsip baseline; v7/v8, perbandingan CatBoost v9 dan persiapan CNN v10 tetap bukti riset. Data tambahan v10 belum masuk fitting dan CNN belum dilatih. Arsip tidak dihapus karena masih terikat checksum, registry exposure dan evaluasi.

V6 bukan pemenang universal semua benchmark dan keputusan ini tidak mengubah hasil eksperimen atau meluluskan release gate. API tetap `shadow`, `needs_review=true`, `production_ready=false`; LOW tidak menjamin aman. Bukti Indonesia dan target kualitas penggunaan publik masih perlu dipenuhi.

Input QR harus didekode menjadi URL terlebih dahulu. Model hanya membaca URL core yang disanitasi, tanpa query/fragment, kunjungan target, redirect, DNS atau HTML. APK dan QRIS tidak termasuk classifier ini.

## Menjalankan pengujian internal

Gunakan [kontrak API shadow](./shadow-api-contract.md) untuk pemasangan dependency dan menjalankan layanan lokal. Entry point layanan utama adalah API tersebut. `guardian_ml.predictor` dan `ml/run.py` merupakan CLI arsip v1; keduanya tidak ditafsirkan sebagai model utama v6.

Verifikasi pemilihan menggunakan loader `RichArtifact` dan tes `ml/tests/test_rich_runtime.py` serta `ml/tests/test_shadow_service.py`. Pemeriksaan harus mencakup SHA binary/metadata/source, versi model, threshold asli dan parity URL/QR. Jangan menurunkan guard karena model tersedia atau karena pengguna telah memilih versi ini.

Verifikasi pada keputusan ini: **25 tes runtime/API lulus** (14,99 detik). Loader memverifikasi artifact v6 dan threshold asli; smoke test TestClient dalam proses memastikan health model tersedia dan prediksi URL/QR identik. Manifest runtime tetap memiliki checksum yang sama; layanan tetap mode shadow.
