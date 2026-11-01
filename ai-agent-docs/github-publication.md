# Publikasi Repository dan Verifikasi

Repository GitHub diinisialisasi dari commit dasar kosong agar implementasi masuk melalui feature branch dan PR ke `main`. Model utama tetap Logistic Regression v6 untuk API shadow internal; publikasi kode tidak mengaktifkan layanan publik.

Yang dipublikasikan adalah source Python, notebook, dokumentasi, template anotasi kosong dan laporan agregat. Dataset, registry lokal, environment dan model binary tetap diabaikan Git. Menjalankan inferensi v6 memerlukan artifact lokal tepercaya beserta metadata/checksum yang dijelaskan pada [model terpilih](./selected-model-v6.md) dan [kontrak API](./shadow-api-contract.md).

`.gitattributes` mempertahankan byte asli untuk source/notebook/manifes yang diikat checksum. Salinan publik notebook arsip v4 menormalkan satu path runtime lokal pada output; kode notebook dan hasil model tidak berubah. Notebook asli di workspace penelitian dipertahankan. [Ledger publikasi](../ml/reports/publication-audit.json) mencatat hash asli, hash salinan publik serta hash kode yang sama.

Workflow GitHub Actions memeriksa Ruff dan pytest pada Python 3.12 dengan dependency core/serving. Tes artifact/data lokal serta tes CNN opsional dilewati bila dependency/input tersebut tidak tersedia; ini tidak menggantikan pengujian 89 kasus pada workspace lengkap. CNN v10 masih belum dilatih dan gate holdout/produksi tetap berlaku.
