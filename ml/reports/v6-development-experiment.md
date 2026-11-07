# Eksperimen pengembangan v6

Tiga kandidat Logistic Regression dilatih terpisah. Layanan tetap menggunakan frozen v6 asli. Kandidat dipilih hanya dari tune; hasil di bawah adalah pemeriksaan benchmark yang sudah pernah teramati, bukan validasi independen baru.

Kandidat terpilih: **hard_segments**. Lolos syarat peningkatan development: **False**. Tidak ada promosi produksi.

**Kesimpulan analisis setelah evaluasi:** eksperimen ini belum menunjukkan peningkatan deteksi yang meyakinkan. Macro recall tune naik 0,85 percentage point, di bawah syarat 2 point. Pada benchmark vendor, kandidat menangkap 1.015 dari 2.211 phishing (v6: 1.024) dan salah memberi warning pada 174 dari 17.789 benign (v6: 168). Interval delta recall dan FPR mencakup nol. Model aktif tetap v6; hasil ini tidak menjadi dasar memilih ulang threshold atau mencoba kandidat lain pada benchmark yang sama.

Seluruh **90 tes lulus**, termasuk 20 tes baru untuk privasi, leakage, pembatasan FPR dan aturan seleksi. [Catatan verifikasi](v6-development-verification.json) mengikat hash source/protokol/artifact dan hasil tes.

## Pemilihan development

| Kandidat | Macro recall per sumber pada FPR tune <=1% | Recall sumber terendah |
| --- | ---: | ---: |
| v6 kontrol tune | 43.67% | 40.75% |
| privacy_retrain | 43.72% | 40.48% |
| source_class_balance | 41.58% | 37.17% |
| hard_segments | 44.52% | 42.63% |

Threshold tune di tabel hanya diagnostik pemilihan. Threshold kandidat akhir ditentukan pada partisi threshold setelah kalibrasi terpisah.

## Benchmark teramati, warning

| Data | Model | URL | Accuracy | Precision | Recall | FPR |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| vendor | frozen_v6 | 20,000 | 93.225% | 85.906% | 46.314% | 0.944% |
| vendor | candidate | 20,000 | 93.150% | 85.366% | 45.907% | 0.978% |
| community_positive | frozen_v6 | 9,269 | N/A | N/A | 46.531% | N/A |
| community_positive | candidate | 9,269 | N/A | N/A | 46.488% | N/A |

Interval bootstrap berpasangan 95% untuk delta kandidat terhadap v6 (percentage point):

- vendor: delta recall [-1.275, 0.452]; delta FPR [-0.023, 0.096].
- community_positive: delta recall [-0.391, 0.301]; delta FPR N/A.

Pada private hosting di vendor, false positive turun dari 36/706 menjadi 30/706, tetapi phishing tertangkap juga turun dari 289/334 menjadi 272/334. Jadi berkurangnya false alarm pada slice ini dibayar dengan recall yang lebih rendah. Pada URL panjang vendor, kedua model menangkap 11/16 phishing; sampelnya kecil. Tidak ada bukti peningkatan yang konsisten pada kasus sulit.

Brier score vendor membaik sedikit dari 0,09024 menjadi 0,08986, log loss dari 0,30004 menjadi 0,29877, dan ECE dari 0,15450 menjadi 0,15394. Perubahan kecil ini tidak mengatasi rendahnya recall dan tidak membuktikan kalibrasi untuk trafik Indonesia.

## Data, privasi dan reproduksi

Fitting memakai 524,699 baris setelah 40 baris konflik (20 representasi) dikarantina dan 8,054 duplikat konsisten dibuang. Label tidak diubah. Tune/calibration/threshold dan benchmark tidak dikurangi berdasarkan label atau kesalahan model.

Sanitizer eksperimen mengubah 3 dari 703,604 core development. Ini menutup pola assignment path yang diuji, bukan jaminan anonimisasi lengkap. Parser v6 asli tetap beku.

Partisi: `{"calibration": {"classes": {"0": 26075, "1": 14029}, "groups": 35409, "rows": 40104}, "fit": {"classes": {"0": 333330, "1": 191369}, "groups": 344036, "rows": 524699}, "threshold": {"classes": {"0": 31951, "1": 14756}, "groups": 42183, "rows": 46707}, "tune": {"classes": {"0": 53462, "1": 30538}, "groups": 73262, "rows": 84000}}`.

Artifact eksperimen lokal: `ml/runs/v6-development-20261105-run1/selected-candidate.joblib`, SHA-256 `5ed22f7ed129325d0979b6ec1b7a95ffc079af8196bb1faba83529b680107143`. Artifact/data tidak masuk Git dan tidak diterima otomatis oleh loader layanan v6. Save/reload parity 132 kasus: max delta 0.0.

Sumber runtime, metadata, binary, threshold v6 dan registry exposure tetap utuh. Detail kalibrasi, counts, interval Wilson/domain, segment URL panjang/private hosting/punycode dan kebijakan HIGH ada dalam JSON pendamping.

Jalankan ulang menggunakan direktori/output baru:

```powershell
ml/.venv/Scripts/python.exe scripts/experiment_v6_development.py --run-dir ml/runs/v6-development-replay --output-stem ml/reports/v6-development-replay
```

Memerlukan environment proyek dengan extra `quality` dan cache v6 lokal. Protokol disimpan sebelum training; konfigurasi tidak diubah setelah melihat benchmark.

## Batas kesimpulan

- Existing development and benchmarks have prior exposure; this run cannot establish new independent generalization or Indonesian validation.
- Labels retain publisher provenance and are not new human-reviewed gold labels.
- Historical benign and recent positive-only feed remain separate distributions; positive-only FPR, precision and binary accuracy are unavailable.
- Sanitizer remains heuristic and does not establish full anonymization.
- Research noncommercial use only; API stays frozen v6 shadow with production_ready=false.

Pedoman metode: [pencegahan leakage](https://scikit-learn.org/stable/common_pitfalls.html#data-leakage), [pemilihan threshold](https://scikit-learn.org/stable/modules/classification_threshold.html), [kalibrasi](https://scikit-learn.org/stable/modules/calibration.html). Dependency proyek tetap pada versi training asli.
