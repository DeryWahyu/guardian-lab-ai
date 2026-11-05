# Guardian Lab AI — Logistic Regression v6

Repository ini mempertahankan **satu model: frozen Logistic Regression v6**, sesuai instruksi pengguna pada 3 November 2026. Notebook utama adalah [guardian_lab_url_qr_v6.ipynb](guardian_lab_url_qr_v6.ipynb). Model membaca URL dan URL hasil dekode QR; layanan berstatus riset/internal shadow.

**Untuk pengembang web:** ikuti [panduan integrasi backend](ai-agent-docs/web-integration-v6.md). [GitHub Release v6](https://github.com/DeryWahyu/guardian-lab-ai/releases/tag/v6-shadow-20261103) menyediakan binary model dan metadata asli; laporan hasil serta notebook tersedia langsung di repository.

Guardian Lab memakai API ini untuk URL dan tautan hasil QR, termasuk hasil, riwayat, Share Card, dan snapshot komunitas. [Dockerfile](Dockerfile) memasang artifact terverifikasi saat build; Compose di repo web menghubungkan backend ke model melalui jaringan privat. Integrasi fitur tidak mengubah status riset atau menyelesaikan validasi sebelum rilis.

## Model dan batas penggunaan

- TF-IDF karakter/kata dan fitur numerik URL, dilatih pada **532.793 URL** dari lima sumber.
- Artifact: `ml/runs/notebook-tfidf-logistic-v6/artifacts/url-core-logistic-v6.joblib`.
- SHA-256: `f332bcbf7665955677e17daa73c487a7e1572a18d7f465b87e73caaa72e06319`.
- Threshold asli: warning `0.904713285827399`, high `0.9884744926236343`.
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
