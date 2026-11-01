# Rencana Pengerjaan Keandalan Model URL/QR

> Tanggal: 1 November 2026. Ditulis sebelum implementasi tahap ini.
> Acuan: [hasil v6](./data-improvement-v6-plan.md), [gold set Indonesia](./indonesia-gold-set-plan.md), dan [rencana ML](./machine-learning-plan.md).

## Tujuan dan keputusan awal

Membuat hasil riset dapat diaudit dan dipakai melalui antarmuka internal yang jujur tentang keterbatasan, sambil menyiapkan bukti yang masih kurang sebelum rilis publik. Satu classifier Logistic Regression v6 dipertahankan; tidak melakukan training baru tanpa hipotesis yang didukung audit development dan label yang sah.

V6 menangkap 46,53% phishing PhishTank 2026, FPR kontrol vendor 0,94% dengan batas atas Wilson sekitar 1,10%, dan hanya 4/22 phishing pada audit manusia teramati. Karena itu status tetap riset. Kontrol tambahan pada anggaran FPR sama tidak menggantikan hasil baseline asli atau menghapus regresi.

## Urutan dan bukti pekerjaan

| Tahap | Pekerjaan                                       | Bukti yang dihasilkan                                                                                | Batas penyelesaian                                                             |
| ----- | ----------------------------------------------- | ---------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------ |
| H0    | Bekukan alur dan release gate                   | MD ini dan policy JSON                                                                               | Otomatis                                                                       |
| H1    | Audit kesalahan pada development tune           | Notebook, metrik per sumber/slice, collision audit, paket review buta                                | Otomatis; diagnosis penyebab semantik memerlukan manusia                       |
| H2    | Audit cakupan label dan siapkan pilot Indonesia | Pencocokan audit manusia terpublikasi, kandidat tersanitasi tanpa label/prediksi pada paket reviewer | Tidak mengarang label/identitas reviewer; pilot teramati bukan final holdout   |
| H3    | Tentukan kelayakan model dari bukti             | Laporan gate aktual, alasan gagal/pending                                                            | Tidak menyebut model siap produksi jika gate gagal                             |
| H4    | Siapkan inferensi dan API internal shadow       | Adapter frozen v6, kontrak URL/QR, human/geek output, abstention, tes nyata                          | Tidak mengaktifkan aplikasi publik atau mengubah model/threshold               |
| H5    | Monitoring agregat                              | Counts/latency tanpa URL/IP/PII; quality metrics hanya dengan label tervalidasi                      | Tidak menebak FP/FN dari skor atau feedback otomatis                           |
| H6    | Integrasi aplikasi dan sinyal lanjutan          | Kontrak integrasi dan checklist uji/sandbox terverifikasi                                            | Aktivasi publik/kolektor redirect/HTML menunggu gate dan isolasi yang terbukti |

H1 dikerjakan sebelum eksperimen model berikutnya. H4/H5 adalah persiapan yang dapat diuji secara lokal meskipun H2/H3 belum lolos. Tidak mengubah batas validasi menjadi alasan menghentikan seluruh pekerjaan yang independen.

## Audit development dan label

- Gunakan tune v6 sebagai cohort audit utama; fitting, calibration dan threshold tidak digabung ke skor audit. Semua test v5/v6 tetap teramati dan tidak dipakai memilih fitur/threshold tahap ini.
- Hitung FN/FP, recall/FPR, confidence interval, Brier/reliability, serta dukungan kelas/domain per sumber. Slice struktur URL hanya deskripsi, bukan vonis label atau penyebab otomatis.
- Audit representasi scheme-free yang sama dengan classifier. Konflik label pada representasi identik dicatat sebagai batas informasi. Query asli tidak ada pada core cache; frekuensi ancaman yang hanya dapat dibedakan dari query tidak boleh dikarang.
- Cocokkan audit manusia PhishVN yang sudah dipublikasikan dengan development berdasarkan canonical URL/domain. Exact match dan domain-only match dilaporkan terpisah; domain-only match tidak membenarkan relabel seluruh path. Scam/unsure bukan otomatis phishing atau benign.
- Label sumber, skor, error kind, dan jawaban reviewer lain tidak boleh muncul pada paket reviewer buta. Koordinator menyimpan mapping dan provenance terpisah.
- Sampling review dari sumber/error band ditetapkan sebelum tinjauan; tidak menghapus kesalahan dari evaluasi sesudah prediksi.

## Pilot Indonesia dan batas review manusia

Siapkan kandidat pilot dari development yang sudah tersanitasi dengan petunjuk brand/konteks Indonesia. Petunjuk string hanya pencarian kandidat; relevansi Indonesia dan label tetap belum terverifikasi. `.id` sendiri, HTTPS, popularitas, nama bank, atau skor model tidak menjadi label.

Kandidat lama diberi peran `development_pilot` dan exposure teramati. Pilot tidak disebut dataset baru atau gold set Indonesia. Jangan mengisi `privacy_reviewed=yes`, `human_review_confirmed=yes`, label, evidence hasil kunjungan, atau waktu observasi yang tidak tersedia. Bukti dataset/provenance tidak menggantikan bukti kasus. Template reviewer/adjudikasi tetap mengikuti protokol gold set.

Dua reviewer manusia independen dan adjudikasi yang dibutuhkan adalah tindakan nyata. Sesuai jawaban pengguna, gunakan dahulu audit manusia yang sudah dipublikasikan dengan provenance asal. Tidak mengklaim anotasi baru oleh agent atau ketersediaan reviewer lokal. Gold set Indonesia tetap belum tersedia.

## Release gate dan keputusan

Policy disimpan pada `ml/policies/url-qr-release-gates.json`. Target usulan yang dibekukan untuk fase ini: lower bound Wilson 95% recall minimal 85% dan upper bound FPR maksimal 1%, didukung set evaluasi Indonesia dengan dua review, provenance, QA privasi, dan pemisahan domain/kampanye/waktu yang dapat dipertanggungjawabkan.

Ukuran awal untuk perencanaan final: minimal 1.000 phishing dan 3.000 benign; ini belum tersedia dan jumlah saja tidak membuktikan target. Pilot lebih kecil untuk memvalidasi proses. Bukti per segmen/domain, keterbatasan campaign, serta regresi terhadap baseline harus tetap diperiksa. Bukti yang hilang berarti pending; bukti angka yang gagal tetap failed. Evaluasi feed positif tidak menghasilkan FPR nol.

Runtime/API shadow boleh disiapkan dan diuji lokal. Gate tidak dapat dilewati hanya dengan environment flag. Skor tidak menjadi probability trafik atau jaminan keamanan. Tidak mengganti baseline/threshold setelah melihat hasil test.

## Kontrak inferensi shadow

- Satu input URL atau URL hasil decode QR; tidak berpura-pura melakukan decode gambar QR, memvalidasi QRIS, menganalisis APK, membuka URL, atau mengikuti redirect.
- Gunakan parser/feature encoder/scaler/kalibrator v6 yang sama. Verifikasi checksum artifact, source/schema, dependency dan save/reload parity. Joblib hanya berasal dari artifact training lokal tepercaya.
- `LOW` berarti indikator model rendah, bukan `SAFE`. Output menyertakan kebutuhan verifikasi, scope URL-only, versi, serta penjelasan Mode Manusia/Geek. Input unsupported dan kegagalan model tidak boleh diubah menjadi LOW.
- API tidak menggemakan URL, query, body request atau credential pada respons error, log, telemetry, maupun validasi schema. Validasi ukuran body dan input; schema memakai library mature.
- Seluruh respons tetap riset/shadow dan memerlukan tinjauan. Tidak menciptakan ukuran OOD/confidence atau kepastian label yang belum divalidasi.

## Monitoring dan integrasi bertahap

Monitoring hanya agregat: jumlah request, tipe URL/QR, status supported/unsupported/unavailable, risk band, latency bucket, dan versi model. Tidak menyimpan URL/domain/hash target, IP, user ID atau request body. Label manusia untuk quality monitoring diimpor lewat proses review terpisah; tanpa ground truth, precision/recall/FPR harus tidak tersedia.

Kontrak menghubungkan model ke pilar Recognize, penjelasan dual-mode, dan tindakan Share Card. Sandbox melindungi perangkat dan harus benar-benar terisolasi; UI simulasi bukan bukti isolasi. Kolektor redirect/halaman bukan bagian runtime URL-only dan tidak diimplementasikan sebelum desain worker/egress/SSRF, batas waktu, dan pengujian isolasi disetujui melalui bukti teknis. Agent tidak mengunjungi target dataset.

## Validasi dan catatan hasil

- Notebook audit dijalankan penuh; tidak menampilkan URL dataset ke output percakapan/notebook.
- Tes meaningful: parity runtime terhadap notebook/artifact nyata, unsupported input, error tanpa kebocoran, schema/body limit, URL/QR/HTTP-HTTPS, model hash/schema/version rejection, gate gagal tertutup, serta monitoring tidak menyimpan PII atau mengarang quality metrics.
- Jalankan Ruff/format, test Python yang relevan, pemeriksaan link dokumen dan checksum baseline. Jika tidak menyentuh frontend, tidak mengubah Next.js atau menjalankan format/build seluruh aplikasi.
- Setiap status akhir membedakan selesai otomatis, pending review manusia, failed gate, dan fitur yang belum diaktifkan. Tidak commit/push/deploy tanpa instruksi eksplisit.

## Hasil pengerjaan tahap ini

Bukti: [notebook yang dijalankan penuh](../guardian_lab_model_hardening.ipynb), [laporan agregat](../ml/reports/model-hardening-audit.json), [validasi runtime](../ml/reports/shadow-service-validation.json), dan [kontrak API beserta cara menjalankan](./shadow-api-contract.md).

| Bagian                     | Hasil aktual                                                                                  | Implikasi                                                                                                                           |
| -------------------------- | --------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------- |
| Audit development          | 84.000 URL tune; FN 17.501 dan FP 204 menurut label sumber                                    | Diagnosis pada data teramati, bukan accuracy test baru                                                                              |
| Representasi               | 33 representasi scheme-free memiliki label bertentangan pada 703.604 baris development        | Sedikitnya 33 kesalahan tidak dapat dihindari oleh classifier deterministik dengan representasi sama; konteks label harus diperiksa |
| Segmen struktur            | FPR private hosting 6,31% pada 824 benign; recall URL panjang 11,43% pada 315 phishing        | Hipotesis perbaikan; tidak mengubah skor melalui rule yang belum dievaluasi                                                         |
| Audit manusia terpublikasi | 200 kasus PhishVN, dua sheet reviewer dan adjudikasi penerbit diverifikasi SHA-256            | Bukti Vietnam teramati; tidak menggantikan gold set Indonesia                                                                       |
| Pencocokan bukti           | 57 exact canonical, 11 domain-only, 130 tidak cocok, 2 unsupported                            | Exact canonical memakai core tersanitasi; kecocokan query/waktu/halaman belum dibuktikan                                            |
| Usulan koreksi             | 3 exact canonical berverdict scam di luar scope biner; 2 berada di fit dan 1 di tune          | Usulan pemeriksaan semantik/temporal; nol relabel otomatis, nol perubahan data/model                                                |
| Paket diagnosis            | 159 kasus error dengan paket Reviewer A/B buta                                                | Paket disiapkan; tidak ada label baru yang dikarang                                                                                 |
| Pilot konteks Indonesia    | 73 kandidat, satu per domain, dari 103 kandidat token brand                                   | Belum berlabel, relevansi Indonesia dan QA privasi manusia belum terverifikasi; bukan final holdout                                 |
| Release gate               | 3 kriteria angka gagal dan 4 kelompok bukti pending                                           | Model tetap riset; tidak dipromosikan ke produksi                                                                                   |
| Runtime/API                | Adapter frozen v6, schema strict, URL/QR parity, human/geek, abstention, pemeriksaan checksum | Inferensi internal sudah dapat diuji dengan artifact asli; tidak mengaktifkan frontend                                              |
| Monitoring                 | Hitungan/status/risk band dan bucket latency agregat                                          | Precision/recall/FPR online tetap null tanpa ground truth                                                                           |

H0/H1, pencocokan bukti terpublikasi H2, evaluasi H3, dan implementasi lokal H4/H5 selesai. Anotasi pilot/gold set Indonesia belum selesai. H6 memiliki kontrak integrasi, sementara aktivasi publik dan kolektor redirect/HTML belum diimplementasikan. Tidak ada training ulang pada tahap ini: audit belum menghasilkan label terkoreksi yang sah atau bukti fitur baru untuk eksperimen berikutnya.

Notebook selesai dengan lima sel kode dieksekusi dan nol error. Seluruh 64 tes Python lulus tanpa skip pada lingkungan berartifact asli, termasuk parity prediksi 128 URL tune terhadap fungsi notebook v6, checksum/schema/dependency, ukuran body tanpa Content-Length, kegagalan inferensi tanpa skor LOW, serta monitoring agregat. Ruff check dan format check lulus. Checksum notebook/weights v3 dan v6 yang dilindungi tetap sama. Hasil tes implementasi ini bukan pengukuran accuracy baru.

Urutan eksperimen selanjutnya: verifikasi konteks tiga usulan out-of-scope dengan bukti penerbit, tetapkan kebijakan label/koreksi sebelum fitting baru, rancang fitur dari diagnosis development, lalu evaluasi pada holdout baru yang benar-benar independen. Benchmark yang sudah teramati tidak boleh dipakai memilih perubahan atau disebut test baru.
