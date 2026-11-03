# Provenance Sumber URL/QR untuk v6

Catatan ini merangkum bukti sumber historis yang digunakan v6; tidak mengklaim pemeriksaan akses/lisensi terbaru. [Audit sumber asal](research/url-dataset-source-audit.json) dan [manifest dalam laporan v6](../ml/reports/data-improvement-v6.json) mempertahankan checksum, versi, mapping label dan pengecualian.

Fitting v6 terdiri dari PhreshPhish 302.812 URL, PhiUSIIL 116.096, DeepURLBench 100.000, PhishVN core 9.769 serta Mendeley 2020 4.116: total 532.793 URL. Label vendor DeepURLBench adalah tingkat bukti berbeda dari audit manusia terpublikasi. PhishVN bukan gold Indonesia. Sumber asal dan perbandingan yang pernah teramati tetap teramati setelah file eksperimen lain dihapus.

Audit resmi awal membaca 666.315 baris PhreshPhish dan 235.795 baris PhiUSIIL, hanya kolom yang dibutuhkan tanpa HTML. Mapping PhiUSIIL dibalik ke skema proyek: phishing=1, benign=0. Query benign pada sumber tersebut sangat jarang atau dibuang oleh penerbit. Karena itu query/fragment dikeluarkan identik dari kedua kelas sebelum seluruh fitur; ini mitigasi shortcut data dan sekaligus membatasi deteksi ancaman yang hanya tampak di parameter.

DeepURLBench holdout v6 berisi 20.000 URL pada domain berbeda, tetapi sumbernya juga masuk development. Data benign historis dengan label vendor bukan traffic benign Indonesia yang ditinjau saat ini. DeepURLBench tercatat CC BY-NC 4.0; model turunan dibatasi untuk riset nonkomersial.

PhishTank v6 berisi 9.269 phishing laporan/verifikasi komunitas 2026 setelah pemeriksaan overlap, sanitasi dan cap domain. Timestamp laporan/verifikasi bukan tanggal pembuatan URL. Feed positif saja hanya mengukur sensitivity/recall; FPR, precision trafik dan accuracy biner tidak tersedia. Jangan menggabungkan feed ini dengan benign historis untuk mengklaim validasi temporal dua kelas.

Sanitasi di memori, canonical digest, konflik label, domain/tenant dengan PSL offline/private suffix, time boundaries dan registry exposure wajib diperhatikan. Campaign overlap tetap belum sepenuhnya terverifikasi. Regex redaksi bukan bukti anonimisasi sempurna; gunakan data sintetis untuk tes dan jangan memuat baris dataset ke LLM atau membuka target.

Gold Indonesia memerlukan kandidat baru dengan provenance, dua penilaian manusia independen, QA privasi/relevansi, adjudikasi serta holdout final yang benar-benar tidak terpapar. `.id`, keyword brand, ranking popularitas atau skor model tidak menetapkan label. Registry exposure lokal dipertahankan sebagai bukti historis; penghapusan model tidak menghapus paparan data.
