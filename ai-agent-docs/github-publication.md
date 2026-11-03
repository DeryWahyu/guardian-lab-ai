# Pemeriksaan Repository v6

Tree aktif berisi satu notebook v6, runtime v6, tes terkait, laporan agregat dan dokumen pendukung. Dataset, registry exposure, environment, snapshot lokal dan model binary diabaikan Git. Layanan tetap shadow/internal; publikasi kode tidak berarti promosi model.

Workflow [.github/workflows/ml.yml](../.github/workflows/ml.yml) memeriksa source, notebook utama dan tes pada Python 3.12. Tanpa binary lokal, tes artifact nyata dilewati dan API tetap mengembalikan unavailable tanpa skor. Pengujian lokal dengan artifact asli tetap diperlukan untuk membuktikan parity.

[Manifest runtime](../ml/policies/shadow-runtime-manifest.json) mengikat source dan identitas binary/frozen metadata. `.gitattributes` mempertahankan byte untuk file yang diikat checksum. Metadata training asli tidak ditulis ulang untuk menghilangkan provenance historis.

Pada 3 November 2026 pengguna mengizinkan commit/push hasil v6 agar dapat dipakai pengembang web. Source, notebook dan laporan agregat dikirim dari feature branch setelah pemeriksaan. Binary model dan metadata asli dibagikan sebagai ZIP GitHub Release prerelease, di luar history Git; dataset, registry, credential dan arsip source lokal tetap tidak dibagikan.

[Manifest distribusi](../ml/policies/v6-distribution.json) mengikat checksum ZIP, nama/ukuran dua anggota, checksum binary dan metadata frozen asli. `scripts/install_v6_model.py` menolak checksum/member/path yang salah dan file lokal berbeda. `scripts/package_v6_model.py` mereproduksi ZIP dari dua file asli saja. Installer tidak mengunduh dataset, mengubah threshold atau melakukan training.

Panduan untuk teman pengembang ada di [web-integration-v6.md](web-integration-v6.md). Publikasi hasil dan paket model tetap untuk riset nonkomersial/internal shadow dan tidak mengaktifkan deployment publik.
