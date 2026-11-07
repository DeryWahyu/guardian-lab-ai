# Metode evaluasi eksternal dan `.id`, 6 November 2026

Pengguna mengizinkan evaluasi dan perbaikan lebih lanjut. [Laporan hasil](../ml/reports/v6-indonesia-external-evaluation.md) membedakan benchmark domain baru dari validasi Indonesia manusia yang belum selesai. Keputusan tetap mempertahankan v6 asli untuk shadow; tidak ada promosi atau fitting baru.

## Artefak dan urutan

1. [Protokol](../ml/reports/v6-indonesia-external-20261106-protocol.json) membekukan rilis, dua hash model, threshold, cohort dan sampling sebelum unduhan/prediksi. [Audit skema](../ml/reports/v6-indonesia-external-schema-audit.json) kemudian mencocokkan hitungan literal label; [amendemen](../ml/reports/v6-indonesia-external-schema-amendment.json) mengikat hash parent dan mapping tanpa skor model.
2. `scripts/evaluate_v6_indonesia_external.py intake` memeriksa semua paparan lama dan identitas cache aktual. Download HTTPS range dibatasi, ukuran dan SHA-256 diverifikasi. Sanitizer eksperimen digunakan di memori; hanya data tersanitasi disimpan lokal. Heuristik redaksi bukan jaminan anonimisasi penuh. Tidak ada fetch URL target.
3. `ml/data/v6-indonesia-external-20261106/frozen.json` mengikat source code, sumber, registry/sidecar/cache, seluruh partisi dan checksum sebelum prediksi. Semua 169.393 domain-disjoint rows dicadangkan; 50.000 global serta seluruh 306 `.id` diprediksi sesuai protokol. Cohort bertumpang tindih 82 baris dan tidak dianggap sampel independen satu sama lain.
4. `evaluate` menulis marker awal sebelum prediksi; tidak bisa ditimpa/dijalankan sebagai percobaan ulang. Dua model menggunakan ambang masing-masing yang telah beku. Prediksi tersimpan pada ignored `ml/runs/v6-indonesia-external-20261106/`. Reload dua model pada 128 probe tiap cohort menghasilkan delta nol.
5. `scripts/audit_v6_indonesia_evidence.py` memeriksa nama/template CSV Indonesia aktual dan antrean development blind. Auditor ini mengoreksi census nama file awal pada laporan beku secara eksplisit dan terpisah. Tidak membuat reviewer, evidence, adjudikasi atau label.
6. `scripts/verify_v6_indonesia_external.py` memeriksa hash, urutan waktu, identitas reserved terhadap registry dan cache lama, cakupan sidecar, parity, evidence census dan JUnit. Ia tidak memilih model atau menghitung ulang threshold.

Sidecar baru dicatat di [provenance](../ml/provenance/mendeley-vfs-indonesia-external-exposure.json); semua 446.068 supported inputs wajib dianggap terpapar pada audit berikutnya. Registry lama dan keenam sidecar sebelumnya tetap byte-identik. Replay artifact historis memakai `scripts/v6_historical_replay.py` yang mengizinkan tambahan sidecar tetapi menolak sidecar lama hilang/berubah. Loader ini hanya untuk parity; audit novelty baru tetap membaca **semua** sidecar terkini. Kode/binding/protokol eksperimen segmented lama tidak diubah.

## Verifikasi lokal

Dengan cache dan artifact tepercaya yang telah tersedia:

```powershell
ml/.venv/Scripts/python.exe -m pytest ml/tests -q --junitxml=ml/runs/v6-indonesia-external-20261106/final-tests.xml
ml/.venv/Scripts/python.exe scripts/audit_v6_indonesia_evidence.py
ml/.venv/Scripts/python.exe scripts/verify_v6_indonesia_external.py
```

Jangan menjalankan ulang `intake` atau `evaluate` untuk menimpa hasil yang sudah terkunci. Studi berikutnya memakai ID/protokol baru, mempertahankan semua paparan, dan tidak menjadikan hasil test ini kriteria seleksi ulang.

## Syarat validasi Indonesia

Benchmark `.id` memiliki label penerbit global historis dengan hanya delapan benign. Itu belum mencukupi relevansi pengguna Indonesia, validasi label dua manusia, audit waktu/kampanye, benign sulit atau dukungan statistik FPR. Lihat [penelusuran sumber](research/indonesia-independent-source-audit-20261106.md) dan [protokol Indonesia](../ml/policies/v6-indonesia-validation-protocol.json). Izin pengguna memberi kewenangan mengerjakan pipeline, bukan bukti untuk mengisi field manusia atau menyatakan kesiapan produksi.
