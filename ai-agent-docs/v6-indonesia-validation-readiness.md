# Persiapan evaluasi Indonesia dan review label v6

Audit 5 November 2026 memeriksa berkas aktual di `ml/data/indonesia-gold/input/`. Berkas kandidat, reviewer A, reviewer B dan adjudikasi masih kosong. Tidak ada pengujian accuracy/precision/recall/FPR Indonesia yang dapat dijalankan dengan ground truth terverifikasi saat ini. Pilot historis 73 kasus tetap development teramati dan belum punya label manusia.

[Protokol persiapan](../ml/policies/v6-indonesia-validation-protocol.json) menetapkan scope, jendela observasi, sampling, review, privasi, exposure dan aturan pembekuan. Statusnya persiapan; belum merupakan manifest dataset final yang terkunci.

[Penelusuran jurnal dan repositori terdahulu](research/indonesia-phishing-literature-20261105.md) menemukan dataset Indonesia dalam SABER 2026, tesis IndoPhis-D, katalog dataset Telkom, serta LegitPhish internasional. Label dan review manusia penerbit dapat dipakai sebagai bukti sesuai dokumentasinya; tidak harus mengulang seluruh anotasi dari nol. Bukti dua reviewer independen tidak boleh diasumsikan dari publikasi saja. Dataset Indonesia tahun 2023 dapat mendukung benchmark regional historis setelah audit akses/overlap, sedangkan pengujian temporal 2026 tetap memerlukan bukti pada periode yang ditetapkan.

Audit lanjutan [eksperimen pembobotan](v6-weighted-experiment.md) memeriksa 107.094 URL development dan menyiapkan 170 kasus review blind lokal; belum ada review manusia selesai. Holdout baru Zenodo berisi 12.587 URL global berlabel penerbit, termasuk 9.643 benign dan 2.944 phishing, tetapi tidak memiliki bukti relevansi Indonesia atau dua reviewer independen. Jumlah tersebut tidak mengisi gold Indonesia. Input kandidat, reviewer A/B, adjudikasi dan error review Indonesia aktual tetap kosong; seluruh exposure Zenodo tetap dihitung pada audit berikutnya.

Pada 6 November 2026 Asia/Jakarta, pengguna menyatakan **belum ada reviewer**. [Audit berkas aktual](../ml/reports/v6-segmented-human-review-status.json) menemukan 170 kasus development dengan nol pasangan review lengkap, serta kelima CSV Indonesia tetap nol baris. [Eksperimen fitur/data lanjutan](v6-segmented-experiment.md) memakai StealthPhisher global dan PhishBench sebagai bukti label penerbit; keduanya tidak mengisi gold Indonesia. Pemeriksa review baru menjaga pack blind, konsistensi locator dan kelengkapan attestation; dua file atau dua ID sendiri tetap tidak membuktikan independensi manusia. Tidak ada label, identitas reviewer, evidence atau adjudikasi yang dibuat otomatis.

## Data yang perlu disiapkan

Evaluasi 6 November 2026 sudah menjalankan [benchmark eksternal dan subset `.id`](../ml/reports/v6-indonesia-external-evaluation.md) pada domain yang belum terpapar. Subset `.id` berisi 306 URL (298 phishing/8 benign) dengan label penerbit; recall v6 aktif 38,59% dan kandidat riset 40,94%, dengan interval delta mencakup nol. Suffix `.id` tidak menetapkan relevansi manusia Indonesia, dan 0/8 FP memiliki Wilson upper 32,44%. [Census nama file aktual](../ml/reports/v6-indonesia-evidence-status.json) tetap menunjukkan kelima CSV Indonesia kosong serta 170 kasus development belum direview. Karena itu metrik gold Indonesia tetap tidak tersedia. [Audit sumber lanjutan](research/indonesia-independent-source-audit-20261106.md) mendokumentasikan akses dan keterbatasan jurnal/repositori, termasuk publikasi ACIIDS 2026. Tidak ada perubahan label otomatis, training atau promosi model.

Pencarian lanjutan pada 5 November 2026 dicatat dalam [audit sumber tambahan](research/v6-targeted-source-audit-20261105.md). PWD2021 menyediakan 80.000 URL berlabel penerbit global historis; setelah kurasi tersisa 34.084 URL baru untuk eksperimen domain terpisah. Rilis Frontiers yang diperiksa tidak memuat URL asli, sedangkan arsip riwayat sintetis Scientific Data yang diperiksa tidak memuat Indonesia. Tidak satu pun temuan ini mengisi gold Indonesia atau kolom reviewer manusia. Catatan paparan PWD2021 tetap wajib masuk audit novelty berikutnya.

Target awal adalah minimum 1.000 phishing dan 3.000 benign dalam jendela bukti penerbit 7 Oktober–5 November 2026, dengan provenance dan relevansi Indonesia yang ditinjau manusia. Sampling perlu mencakup path normal yang dalam dan tenant hosting, agar kelas benign tidak hanya berisi homepage. Jumlah minimum saja tidak menjamin release gate terpenuhi.

Dokumentasi [PhishTank](https://phishtank.org/developer_info.php) menyediakan feed dan kolom waktu pelaporan/verifikasi serta status komunitas. Data itu bisa menjadi kandidat positif, tetapi tetap membutuhkan review scope, relevansi Indonesia, hak penggunaan dan overlap. Feed positif tidak menyediakan benign atau FPR. Agent belum mengunduh kandidat baru pada audit ini.

Untuk benign, perlukan bukti publik mengenai fungsi URL dan kepemilikan yang sah pada periode sebanding, kemudian dua review independen. [Tranco](https://tranco-list.eu/) menjelaskan produknya sebagai ranking domain populer; ranking dapat membantu membentuk kerangka kandidat, tetapi tidak menetapkan label benign pada URL/path atau membuktikan relevansi Indonesia. Ini batas penggunaan yang diterapkan protokol proyek, bukan sertifikasi label dari penyedia ranking. Jangan mengganti bukti benign kontemporer dengan historical negatives atau ketiadaan URL di feed phishing.

## Urutan pelaksanaan

1. Koordinator mencatat versi/checksum, sumber, bukti publik, waktu observasi, hak penggunaan dan dasar relevansi Indonesia pada template `ml/templates/indonesia-candidates.csv`. Jangan memakai skor model untuk menentukan kandidat atau label.
2. Lakukan redaksi berversi dan QA privasi sebelum persistensi. Nilai secret pendek pada assignment path adalah keterbatasan parser v6 beku; jangan menyimpan raw URL sensitif. Catat perubahan representasi dan penolakan secara seimbang untuk kedua kelas.
3. Audit URL/digest, representasi scheme-free, domain/private tenant, tanggal dan kampanye terhadap registry serta semua run yang pernah teramati. Registry yang ada dipertahankan; cakupan run baru perlu diperiksa sebelum holdout dikunci.
4. Dua manusia independen mengisi template reviewer A/B: identitas nyata, label `benign`, `phishing`, `uncertain` atau `out_of_scope`, alasan, evidence reference dan waktu review. Identitas dan independensi perlu bukti koordinator; dua nama CSV saja tidak membuktikannya.
5. Adjudikator menyelesaikan perbedaan berdasarkan bukti. Kasus uncertain/out_of_scope tetap dicatat pada coverage, tidak otomatis diberi label biner. Pemeriksaan tidak meminta credential atau membuka target dari mesin agent.
6. Custodian membekukan manifest kandidat, review, QA, exposure, pembagian dan final holdout sebelum eksperimen baru. Sampling/split harus menjaga domain/tenant dan kampanye; skor final tidak digunakan memilih ulang kandidat/threshold.
7. Evaluasi model yang sudah beku: counts kelas/domain, precision sesuai prevalensi sampel, recall, FPR, Wilson/domain/campaign uncertainty, kalibrasi, penolakan input dan regresi per kelompok. Precision pada sampel 1.000/3.000 bukan estimasi otomatis precision trafik nyata.

Template asli dan input kosong dipertahankan di tempatnya. Tidak ada reviewer, label, status gold atau hasil Indonesia yang diisi oleh agent. Review manusia dan pengumpulan bukti masih perlu diselesaikan sebelum tahap 6–7 dapat dilakukan.

## Antrean konflik development

Audit otomatis membuat antrean lokal di `ml/data/v6-diagnostic-evaluation/`: `conflict-reviewer-a.csv`, `conflict-reviewer-b.csv` dan daftar koordinator `conflict-coordinator.csv`. Antrean blind hanya memakai ID kasus dan locator hash cache, tanpa target, skor model atau label penerbit. Semua kolom review tetap kosong.

Koordinator mengambil bukti dari sumber penerbit untuk kasus tersebut dan menyiapkan tampilan lokal yang sudah lolos QA privasi; jangan memberikan kolom label sumber atau prediksi kepada reviewer pada penilaian awal. Locator menunjuk cache lokal, bukan alamat untuk dikunjungi. Jika bukti tidak cukup atau konteks query/waktu tidak tersedia, keputusan `uncertain` sah dan tidak perlu ditebak.

Antrean ini menyangkut data development yang sudah terpapar. Hasil reviewnya dapat menjelaskan masalah label atau representasi, tetapi tidak menjadi final holdout Indonesia baru.

Detail hasil otomatis: [laporan diagnostik](../ml/reports/v6-diagnostic-evaluation.md) dan [angka lengkap](../ml/reports/v6-diagnostic-evaluation.json).
