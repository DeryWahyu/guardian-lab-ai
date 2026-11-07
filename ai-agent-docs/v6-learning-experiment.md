# Learning curve dan ablation Logistic Regression v6

Pengguna mengizinkan seluruh tindak lanjut tanpa menunggu gold Indonesia. Eksperimen ini tetap terpisah dari layanan/notebook frozen v6 dan tidak mengizinkan promosi produksi. Protokol `ml/reports/v6-learning-20261106-protocol.json` dibekukan sebelum fitting. Nama run mempertahankan tanggal penyusunan protokol; waktu mulai/selesai aktual dicatat dalam JSON.

## Hasil aktual

Delapan classifier baru selesai dan 221 tes lulus. Seluruh kandidat baru belum memenuhi gate; control riset source-equal/domain-sqrt sebelumnya dipertahankan. Recall rata-rata per sumber pada 25%, 50%, 75%, dan 100% grup fitting adalah 34,93%, 47,46%, 48,90%, dan 50,09%. Manfaat tambahan data mengecil pada rentang ini; satu kurva tidak membuktikan batas kemampuan model atau optimalitas ukuran data.

Varian `C=8` memiliki recall development tertinggi 50,84%, tetapi macro Brier memburuk dari 0,091928 menjadi 0,093991. Pembobotan private-host phishing menaikkan recall slice development dari 88,06% menjadi 90,68%, sekaligus menaikkan FPR dari 3,56% menjadi 5,29%. Penambahan ISCX menurunkan macro recall menjadi 49,34%. Kenaikan sebagian metrik tidak cukup untuk mengganti control.

Setelah keputusan dibekukan, challenger `C=8` diuji pada 8.849 kasus Ebbu (2.367 benign/6.482 phishing), 2.066 ISCX (70/1.996), dan 50.000 global yang sudah teramati (30.627/19.373). Recall Ebbu naik dari control 41,14% ke 41,95%, tetapi Brier memburuk dan FP bertambah satu. Recall ISCX berubah 38,48% ke 38,53% dengan interval selisih mencakup nol; 0/70 FP memiliki batas atas Wilson sekitar 5,20%. Recall global naik 30,00% ke 30,81%, dengan FP 16 ke 21 dan kalibrasi memburuk. Perbaikan private-host recall pada global (19,77% ke 25,21%) masih di bawah v6 aktif (28,94%). Tidak ada promosi model atau pemilihan ulang berdasarkan test.

## Pertanyaan dan rancangan

1. Ukur hasil ketika memakai 25%, 50%, 75% dan 100% domain/private tenant fitting dari korpus 616.050 URL. Subset ditentukan dengan hash grup yang bersarang dan seed tetap; jumlah baris tidak harus tepat 25/50/75%. Untuk setiap subset kecil, vocabulary, IDF dan scaler hanya di-fit pada subset itu. Titik 100% memakai control yang sudah dilatih dengan recipe penuh yang sama.
2. Uji regularisasi `C=0.5` dan `C=8` terhadap control `C=2` dengan encoder fitting yang sama.
3. Uji dua perubahan bobot secara terpisah: private-host phishing dua kali; hard benign dua kali. Massa sumber tetap sama dan mean bobot satu. Hard benign berarti URL scheme-free >120 karakter atau path >=4 slash. Label tidak diubah.
4. Uji penambahan 3.056 baris ISCX yang lolos novelty audit. Arm ini melatih ulang encoder pada gabungan fitting saja. Dengan tambahan tersebut, fitting menjadi 619.106 URL. Calibration, threshold, dan tune tetap sama untuk seluruh kandidat.
5. Kalibrasikan setiap classifier secara terpisah dengan sigmoid source-equal. Tentukan tiga kebijakan FPR empiris per sumber (0,5%, 1%, 2%) pada threshold partition. Kebijakan utama tetap 1%; dua kebijakan lain hanya menunjukkan trade-off.
6. Pilih kandidat menggunakan tune dan gate yang dideklarasikan, termasuk penjagaan recall private/non-private hosting. Bekukan artifact, threshold, keputusan dan hash sebelum scoring test baru. Learning curve tidak menjadi peserta seleksi.

Setiap arm mengubah satu hal utama; tidak ada kombinasi terbaik yang dipilih ulang menggunakan hasil test. Gate deteksi meminta kenaikan macro recall >=2 percentage point disertai batas regresi per sumber dan kalibrasi. Jalur perbaikan kalibrasi meminta penurunan macro Brier >=0,002 tanpa regresi recall yang melampaui batas. Jika tidak ada yang lolos, control riset tetap dipertahankan. Challenger terbaik dari tune tetap dapat dievaluasi sebagai kandidat gagal-gate, dengan status itu dipertahankan setelah test.

## Data, paparan dan pengujian

[Audit sumber](research/v6-learning-source-audit-20261106.md) mencatat unduhan yang diterima maupun sumber yang tidak dapat digunakan. Dari 118.918 URL raw, sebanyak 118.038 lolos sanitizer. Setelah kurasi, 3.056 menjadi tambahan fitting ISCX, 8.849 menjadi test Ebbu eksternal saja, dan 2.066 menjadi test ISCX pada domain terpisah. Hanya 40 hard benign unik dan 104 private-host phishing ditambahkan ke fitting; ini belum menutup kekurangan data sah yang sulit.

Novelty audit mencakup registry historis, setiap sidecar, cache v6 asli, seluruh development/test aktual, dan semua 169.393 Mendeley reserved. Tidak ada kasus Mendeley tersebut yang dipindahkan ke fitting/development. Sidecar baru menyimpan hash exposure semua input supported, termasuk yang dikeluarkan. Folder data dan artifact tetap diabaikan Git.

Ebbu dan ISCX memakai label penerbit historis, bukan label manusia Indonesia. PWD2021 sebelumnya memakai sebagian data asal Ebbu, sehingga pemisahan domain/URL tidak menjamin independensi mekanisme pengumpulan. ISCX adalah replika benchmark penelitian; byte dipin tetapi kesamaannya dengan unduhan penerbit asli belum dapat dibuktikan. Lisensi dataset Ebbu serta hak data asli ISCX juga belum jelas. Tidak ada formulir akses dikirim atau pihak lain dihubungi. Artifact tidak dinyatakan boleh digunakan secara komersial.

Global Mendeley 50.000 yang sudah teramati hanya dipakai sebagai pemeriksaan regresi. Hasil test tidak memilih ulang model atau threshold. Laporan mencakup counts, confusion matrix, recall, precision sampel, FPR, Wilson, bootstrap domain berpasangan, Brier, ECE, reliability bins, dan subgroup. Nol FP pada kelompok kecil tetap dibaca bersama batas ketidakpastian.

## Artifact dan pemeriksaan

- Run lokal: `ml/runs/v6-learning-20261106/`.
- Intake lokal: `ml/data/v6-learning-20261106/`.
- [Protokol](../ml/reports/v6-learning-20261106-protocol.json).
- [Laporan](../ml/reports/v6-learning-evaluation.md), [angka lengkap](../ml/reports/v6-learning-evaluation.json), [grafik PNG](../ml/reports/v6-learning-evaluation.png), [SVG](../ml/reports/v6-learning-evaluation.svg), [verifikasi](../ml/reports/v6-learning-verification.json).

Runner memiliki tahap `prepare`, `train`, `evaluate`, dan `check`. Tahap intake/persiapan/seleksi/evaluasi menolak overwrite. Checkpoint training hanya dilanjutkan jika source, protokol, cache, exposure, dan artifact masih cocok. `scripts/evaluate_v6_learning_final.py` mencatat waktu mulai test terhadap seleksi yang sudah dibekukan. `scripts/verify_v6_learning.py` memeriksa ulang novelty, seluruh exposure, chronology, aturan seleksi, subset bersarang, parity dan tes. Jangan menghapus sidecar untuk membuat data terlihat baru.

Model layanan tetap `guardian_ml.shadow_service:create_app` dengan binary, metadata, dan threshold v6 asli. `LOW` tidak berarti aman dan `production_ready=false` tetap berlaku.
