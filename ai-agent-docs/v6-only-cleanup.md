# Pembersihan Workspace: v6 Saja

> 3 November 2026. Instruksi pengguna menghapus model lain menggantikan aturan sebelumnya untuk mempertahankan seluruh arsip model di tree aktif.

Notebook aktif tunggal adalah [guardian_lab_url_qr_v6.ipynb](../guardian_lab_url_qr_v6.ipynb), yang memuat frozen v6 dan menampilkan hasilnya tanpa training atau ketergantungan model lain. Implementasi/entry point lama, CNN, perbandingan classifier lain, notebook eksperimen, tes khusus eksperimen dan binary model non-v6 dihapus.

Snapshot seluruh source tracked sebelum cleanup dan perubahan notebook lokal yang belum di-commit disimpan dalam `ml/data/local-research-archive/v6-only-20261103/source-before-cleanup.zip`. Notebook training v6 asli disimpan byte-identik sebagai `frozen-training-v6.ipynb` di folder yang sama. Arsip berisi source/laporan; binary model lain tidak disimpan dalam snapshot ini. Folder ini diabaikan Git.

SHA binary v6, metadata frozen, kode training dan threshold asli tetap sama; [provenance](../ml/provenance/v6-origin.json) mencatat identitasnya. Sebanyak 62 input sintetis dibuat sebelum cleanup dan diprediksi menggunakan fungsi notebook training asli. Keluaran runtime sebelum cleanup persis sama, kemudian referensi dipakai tes runtime baru tanpa notebook/model lama.

Perubahan runtime terbatas pada pemisahan dependency inferensi dari tooling training. Set dependency wajib lengkap, bernama eksplisit dan memiliki versi yang sama dengan metadata training. Manifest source diperbarui; tidak menurunkan guard binary/schema/PSL. Parser, feature extractor, classifier dan kalibrator tidak berubah.

Dataset/cache v6 dan registry exposure historis dipertahankan. Laporan asli v6 masih menyertakan perbandingan baseline sebagai bukti, bukan model aktif. Penghapusan eksperimen tidak menghapus status benchmark teramati, penurunan recall, keterbatasan privasi atau kebutuhan validasi Indonesia.

[Manifest penghapusan](../ml/reports/v6-only-cleanup.json) mencatat path/hash dan ukuran tanpa baris dataset. [Validasi v6](../ml/reports/v6-only-validation.json) mencatat parity serta replay holdout asli bila cache lokal tersedia. Seluruh hasil tetap riset/shadow, tidak ada pelatihan ulang atau promosi produksi.

## Verifikasi setelah cleanup

Seluruh **60 tes lulus tanpa skip** (21,71 detik), Ruff check/format lulus untuk 20 berkas. Notebook utama menjalankan **5 sel kode, nol error**. Replay 20.000 holdout vendor dan 9.269 positif PhishTank menghasilkan confusion counts yang sama dengan laporan v6 asli.

Checkout terisolasi tanpa artifact menjalankan notebook dan 43 tes portable; 17 tes berartifact/data dilewati sesuai scope. API tanpa artifact mengembalikan unavailable tanpa skor/risk band. Setelah hanya binary dan metadata v6 disalin, notebook dan 62 referensi sintetis lulus. Inferensi juga lulus ketika import serta query versi CatBoost, XGBoost, Torch, Matplotlib dan PyArrow diblokir. Salinan checkout uji kemudian dihapus; satu binary model v6 tetap tersedia di run aslinya.
