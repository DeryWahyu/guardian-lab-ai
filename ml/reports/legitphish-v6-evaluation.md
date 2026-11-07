# Frozen v6 pada LegitPhish V2

Evaluasi eksternal historis mengikuti label penerbit. Model dan threshold v6 asli dipakai tanpa fitting. Cakupan global; tidak mengklaim gold Indonesia atau holdout temporal dua kelas 2026.

Sumber: [LegitPhish V2](https://data.mendeley.com/datasets/hx4m73v2sf/2), DOI 10.17632/hx4m73v2sf.2, CC BY 4.0. File `8685e7901c3b4e73eb43c106cb166cc932dd14f76960a032c713c2c32f09dbcd` diverifikasi sebelum parsing; raw CSV hanya dibaca di memori.

CSV aktual: **101,219 baris**; label penerbit `{"0": 63678, "1": 37540, "missing_label_quarantined": 1}`. Mapping dibalik menjadi benign=0/phishing=1. Klaim total publik 101.219 berbeda dari file jika flag discrepancy bernilai `False`.

Selisih hitungan kelas pada publikasi terjelaskan: satu URL tidak mempunyai label. Intake pertama dihentikan sebelum prediksi. [Amendemen QA](legitphish-v6-protocol-amended.json) kemudian menetapkan karantina baris tanpa label; [protokol awal](legitphish-v6-protocol.json) tetap tersimpan. Tidak ada label yang ditebak atau diubah berdasarkan skor model.

Lolos parser dan guard privasi: 100,853. Retained setelah konflik, duplikat, paparan URL/domain lama dan cap 5/domain: **42,716 baris**, 26,137 domain/private tenant, kelas `{"0": 28, "1": 42688}`, domain per kelas `{"0": 28, "1": 26109}`.

## Hasil pada cohort yang tersisa

| Policy asli | Accuracy | Precision | Recall phishing | FPR | TP | FN | FP | TN |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| warning | 66.034% | 100.000% | 66.012% | 0.000% | 28179 | 14509 | 0 | 28 |
| high | 1.444% | 100.000% | 1.380% | 0.000% | 589 | 42099 | 0 | 28 |

Domain bootstrap 95% warning: recall `[0.6546177382161702, 0.6656228842613517]`, FPR `[0.0, 0.0]` (rasio 0–1). Brier 0.042691; log loss 0.174637; ECE 0.120744. Interval Wilson, balanced accuracy dan reliability bins ada pada JSON.

**Keterbatasan utama: hanya 28 benign pada 28 domain.** Nol FP dari 28 menghasilkan interval Wilson 95% FPR **[0%; 12,064%]** dengan asumsi baris independen. Bootstrap empiris menghasilkan [0; 0] karena tidak ada FP teramati yang dapat di-resample; interval tersebut tidak membuktikan FPR populasi nol. Precision sampel 100% tidak menjadi jaminan precision trafik atau bukti bahwa model telah aman untuk produksi.

Recall warning 66,01% berarti 14.509 URL berlabel phishing masih terlewat; interval bootstrap domain sekitar [65,46%; 66,56%]. Policy HIGH hanya menangkap 589/42.688 (1,38%). Recall ini tidak membuktikan peningkatan dari benchmark vendor sebelumnya karena model sama dan distribusi datanya berbeda.

Subset akhir berisi 99,934% label phishing. Referensi konstan "selalu phishing" akan memperoleh accuracy 99,934% pada subset ini dan balanced accuracy 50%; ini hanya penjelas ketimpangan kelas, bukan model alternatif yang dilatih. Karena itu accuracy 66,034% dan precision 100% tidak boleh dipakai sendirian untuk menyimpulkan kualitas keseluruhan.

**Kesimpulan:** evaluasi ini berguna sebagai sensitivity benchmark tambahan berbasis label penerbit. Ia belum mendukung pengukuran false alarm yang kuat, validasi Indonesia, atau promosi produksi. Seluruh 107 tes proyek lulus; kelulusan tes teknis tidak memperkuat kebenaran label sumber.

Angka hanya berlaku pada subset label penerbit yang tersisa. Attrition dan cap domain mengubah distribusi sumber; precision bukan precision trafik. Label phishing-vs-malware belum diverifikasi independen, dan overlap kampanye tidak diketahui.

## Audit intake

```json
{
  "sanitization": {
    "raw_label_1": 63678,
    "unsupported_sensitive_host_candidate_label_1": 281,
    "unsupported_invalid_or_local_host_label_1": 24,
    "unsupported_control_whitespace_or_backslash_label_1": 53,
    "unsupported_non_public_ip_label_1": 1,
    "unsupported_invalid_authority_label_1": 1,
    "unsupported_decoded_control_or_backslash_label_1": 1,
    "raw_label_0": 37540,
    "unsupported_sensitive_host_candidate_label_0": 4
  },
  "curation": {
    "conflicting_representations": 0,
    "conflicting_rows": 0,
    "consistent_duplicate_rows": 3748,
    "old_url_rows_label_0": 36964,
    "old_domain_rows_label_0": 37304,
    "old_url_or_domain_rows_label_0": 37304,
    "old_url_rows_label_1": 118,
    "old_domain_rows_label_1": 1389,
    "old_url_or_domain_rows_label_1": 1389,
    "pre_domain_cap_rows": 58412,
    "domain_cap_excluded_rows": 15696
  }
}
```

Jumlah old_url dan old_domain dapat tumpang tindih; old_url_or_domain adalah gabungannya. Baris dengan konflik label dikarantina tanpa relabel. Guard assignment path mengecualikan input jika redaksi tambahan akan mengubah representasi frozen v6. Parser tetap heuristik dan tidak membuktikan anonimisasi lengkap.

Hash seluruh intake yang lolos privasi dicatat dalam sidecar exposure lokal, termasuk baris yang akhirnya dikeluarkan dari skor. Registry lama utuh; pemeriksaan novelty berikutnya wajib memakai gabungan registry, sidecar dan cache v6. Dataset/core/hash target tetap diabaikan Git.

## Provenance label dan batas kesimpulan

[Metode artikel](https://pmc.ncbi.nlm.nih.gov/articles/PMC12538017/) menyebut pemeriksaan manual atau pencocokan threat feed; tidak ada bukti dua reviewer independen untuk setiap baris. Tanggal publikasi tidak membuktikan waktu observasi tiap URL. Klaim hasil paper lain tidak dipindahkan menjadi hasil v6.

- Publisher methods mix manual review and threat-feed matching; no claim that all rows had two independent human reviews.
- The dataset includes URLhaus provenance; phishing-vs-malware scope and per-case labels remain unverified.
- Shared upstream sources may cause overlap even though this release has not been evaluated by this run.
- Domain-disjoint and hash-disjoint filtering does not establish campaign independence or correct labels.
- Unknown collection timestamps and absence of verified Indonesia relevance prevent temporal/Indonesia claims.
- Privacy heuristics are not proof of full anonymization; no raw targets are persisted or visited.

Reproduksi dari cache lokal yang sudah dibekukan:

```powershell
ml/.venv/Scripts/python.exe scripts/evaluate_legitphish_v6.py --stage evaluate --output-stem ml/reports/legitphish-v6-replay
```

Replay tetap dataset teramati. Gunakan extra `quality` untuk parquet/grafik; artifact dan cache lokal diperlukan.
