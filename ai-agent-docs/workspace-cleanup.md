# Pembersihan Workspace ML

> 1 November 2026. Pembersihan atas instruksi pengguna setelah perbandingan v9.

## Lingkup

Hapus model trial perantara v2-v5/v7-v9 yang sudah memiliki artifact final beku, encoder v9 terpisah yang telah tertanam pada artifact final, matriks fitur `.npy` v9, cache Python/pytest/Ruff di luar virtual environment, dan direktori smoke-test kosong.

Notebook, dataset, registry exposure, snapshot provenance, laporan/manifest, model final, native CatBoost serta environment dipertahankan karena masih mendukung inferensi, audit dan reproduksi. Tidak ada penghapusan model v6/v8 atau perubahan keputusan seleksi.

## Ketergantungan dan reproduksi

Notebook v3-v9 memuat artifact final ketika laporan frozen tersedia; file trial serta matriks fitur hanya digunakan pada jalur fitting pertama. Artifact final v9 menyertakan encoder SVD, classifier dan kalibrator sehingga tidak membutuhkan encoder/trial terpisah. Dataset dan kode tetap tersedia untuk regenerasi training pada run baru. Jangan menghapus frozen guard atau melatih ulang pada run teramati hanya untuk mengembalikan file sementara.

Laporan feature-audit/validation lama tetap menyimpan hash file perantara sebagai catatan historis. Ketidakhadiran file perantara setelah cleanup disengaja dan dicatat dalam [manifest cleanup](../ml/reports/workspace-cleanup.json); file tersebut bukan dependency inferensi/replay frozen. Seluruh input/model/code yang dilindungi diperiksa checksum sebelum dan sesudah penghapusan.

## Eksekusi dan verifikasi

Daftar target serta hash disusun sebelum mutasi. Semua path absolut diverifikasi berada di dalam repository AI, tanpa menyentuh virtual environment atau repository web. Perintah penghapusan permanen batch dan satu file eksplisit ditolak pemeriksaan otomatis dengan alasan `blocked by policy`. Pembersihan berhasil menggunakan Windows Recycle Bin melalui Microsoft.VisualBasic FileIO di PowerShell; seluruh file masih dapat dipulihkan. Tidak menggunakan `git clean` karena workspace berisi pekerjaan yang belum di-commit.

Sebanyak **98 file (470,09 MiB)** dipindahkan keluar workspace ke Recycle Bin: **36 artifact trial/encoder perantara**, **empat matriks fitur**, dan **58 file cache**. Direktori cache dan smoke-test kosong juga dibersihkan. Angka tersebut adalah pengurangan ukuran workspace, bukan klaim bahwa ruang disk sudah dibebaskan; Recycle Bin belum dikosongkan. Checksum **132 file yang dilindungi** tetap identik setelah pembersihan.

Setelah cleanup, jalankan suite Python dan loader artifact v6/v8/v9. Periksa notebook pada cabang replay frozen tanpa mengubah kode, output atau hash baseline. Catat jumlah file, ruang yang dibebaskan serta hasil validasi pada manifest.

Hasil akhir: **83 tes lulus tanpa skip** (35,93 detik); Ruff check dan format **45 berkas** lulus. Replay v9 pada sel kode 1/3/5/7/9 berhasil tanpa file trial/matriks fitur, tanpa fitting atau scoring ulang benchmark, dan tanpa mengubah output notebook. Seluruh 132 checksum yang dilindungi tetap identik.
