# Hasil Tahap Persiapan Recall dan CNN v10

> 1 November 2026. [Protokol](./recall-cnn-v10-plan.md), [notebook](../guardian_lab_url_qr_recall_cnn_v10.ipynb), [status aktual](../ml/reports/recall-cnn-v10.json), [audit development](../ml/reports/development-error-audit-v10.json), [audit sumber](../ml/reports/data-source-audit-v10.json), [intake](../ml/reports/public-intake-v10.json).

## Status lima langkah

1. **Audit development selesai**, 84.545 tune URL; tidak memakai benchmark untuk diagnosis atau mengubah label.
2. **Tambahan publik dikurasi**, 4.472 URL, belum masuk fitting. Kekurangan positif baru tetap dilaporkan.
3. **Arsitektur/tokenizer CNN disiapkan dan diuji**, belum ada pelatihan dataset, optimizer run, checkpoint terlatih atau accuracy CNN.
4. **Perbandingan CNN-LR belum dijalankan**, menunggu training dan data gate yang sama; tidak ada threshold baru dari benchmark.
5. **Holdout temporal dua kelas belum tersedia**. Reserve berisi 913 benign historis dan dua phishing terbaru. Tidak memenuhi 400 benign terbaru dan 200 phishing yang dibekukan sebelum fitting. Gate training tetap gagal sesuai protokol; lima langkah belum dinyatakan selesai.

API internal tetap model v6 asli; model/notebook v3/v6/v7/v8/v9 dipertahankan. Tidak ada promosi produksi atau gold Indonesia yang dibuat otomatis. Jawaban pengguna atas akses data: lanjutkan sumber publik saja; tidak mengirim formulir, meminta identitas institusi, atau menghubungi penulis.

## Temuan development yang menjadi dasar perubahan

Kontrol memakai kebijakan threshold development v9 yang sebanding: v8 warning 0,9103663235299849 dan v6 kontrol 0,9286581321406272. Ini bukan perubahan threshold runtime v6 asli 0,904713285827399. Jumlah kelas tune: 30.884 phishing dan 53.661 benign.

| Slice development                                  |  Recall v8 |    FPR v8 | Dasar hitungan                                          |
| -------------------------------------------------- | ---------: | --------: | ------------------------------------------------------- |
| Seluruh tune                                       |     41,03% |    0,371% | 12.671 TP, 18.213 FN; 199 FP                            |
| Hosting bersama/private suffix                     |     90,02% | **5,82%** | 6.705/7.448 phishing; 48/825 benign salah ditandai      |
| Homepage                                           |     38,54% |    0,368% | 7.164/18.589 phishing; 109/29.643 benign salah ditandai |
| Tanpa keyword/brand/punycode/IP yang didefinisikan | **35,87%** |    0,325% | 9.381/26.155 phishing; 168/51.708 benign salah ditandai |

Sebanyak 16.774 FN masuk kelompok lexically_plain. Definisi tersebut bukan keputusan bahwa URL aman atau labelnya salah. Prioritas data adalah phishing yang tampak biasa dan benign pada hosting bersama; bukan menurunkan threshold secara global. Source guard tidak otomatis menjamin FPR rendah pada setiap subkelompok hosting.

Tanggal observasi development hilang pada **199.618/707.903** baris: PhiUSIIL, PhishVN core, Mendeley2020 dan TR-OP. Tanggal diketahui paling baru 7 September 2025 (Phresh); ini tidak membuktikan semua sumber lain lebih tua. Klaim temporal penuh tidak dapat dibuat hanya dari tanggal maksimum yang diketahui.

## Tambahan publik dan tingkat bukti

[IOBHunter penulis NDSS 2026](https://github.com/dpliu/iobhunter-dataset/tree/4267788db6b73a0d30c99f53a72a2addcc47994b) menyediakan FQDN false positive yang diterima peneliti Palo Alto Networks dan bersih menurut snapshot vendor. Label dipakai sebagai **benign domain historis**, diproyeksikan hanya ke root URL; tidak diwariskan ke path arbitrer. Rilis tidak memuat komentar pengguna atau PII reviewer. Tidak menggunakan keluaran sistem LLM IOBHunter sebagai label baru.

CSV memiliki 4.841 baris, **4.809 accepted=yes dan 32 accepted=no**, berbeda dari pernyataan README bahwa semuanya yes. Ke-32 kasus tidak diterima itu dikarantina; tidak diubah menjadi benign. Dari kandidat diterima, 216 overlap URL/domain lama dan 16 unsupported/privacy-rejected dikeluarkan, lalu duplikat dan cap domain diterapkan. Tersisa **4.469 benign**. Tanggal review asli 2019-2024 dipertahankan; tanggal kompilasi VT/publikasi paper tidak dipakai untuk menjadikannya gold 2026. Lisensi eksplisit tidak tersedia: tidak meredistribusikan baris atau mengklaim izin produksi.

[PhishTank verified-online](https://www.phishtank.org/developer_info.php) hanya memberi positif yang diverifikasi komunitas. Dari 51.780 baris feed, 3.681 memenuhi verified/online dan rentang submission/verification 1 September 2026 sampai waktu intake. Sebanyak 3.160 overlap URL/domain exposure lama dan 518 unsupported/privacy-rejected dikeluarkan. Tersisa **tiga phishing** baru. Tidak memakai ketiadaan deteksi sebagai label benign atau mengarang FPR dari feed ini.

| Role        | Benign IOB historis | Phishing terbaru | Status                                              |
| ----------- | ------------------: | ---------------: | --------------------------------------------------- |
| Fit         |               2.257 |                0 | Disiapkan, belum dilatih                            |
| Tune        |                 428 |                0 | Development tambahan                                |
| Calibration |                 446 |                0 | Terpisah dari fitting                               |
| Threshold   |                 425 |                1 | Terpisah dari kalibrasi                             |
| Reserve     |                 913 |                2 | Dua challenge terbatas, bukan primary temporal gold |

Role dipilih dari hash domain sebelum scoring; tidak memindahkan tiga kasus phishing agar angka fit terlihat lebih besar. Total intake unik sebelum cap **4.489**; 17 kelebihan cap tetap tercatat exposure. Tidak ada prediksi model pada data baru. **Data tambahan tidak berarti jumlah training model lama berubah**: belum ada baris v10 yang masuk optimizer.

## Penelusuran holdout dan batas akses

Sepuluh sumber primer diperiksa; ini bukan klaim telah meninjau seluruh internet. PhiShark2026 memiliki koleksi 2026, tetapi URL/metadata memerlukan persetujuan institusional dan DUA. Pengguna belum memiliki akses; tidak mengajukan permohonan atas namanya. IOB adalah data historis; PhishTank hanya positif. Tidak menggabungkan dua sumber satu kelas lalu mengklaim accuracy temporal yang valid.

Dataset Zenodo 23477065 diperiksa melalui ZIP range terbatas: 21.318 entry, dua header CSV, sekitar 3,03 MB transfer. Header tidak memuat tanggal observasi dan label benign berasal dari Tranco tanpa audit kasus yang tersedia; tidak mengunduh seluruh ZIP 4,5 GB. URL-Phish v2 dan CompPhish v3 terbit 2026 tetapi data dikumpulkan 2024-2025. PhishBD2026 tidak merilis atribusi per-provider/timestamp kasus yang diperlukan. PhreshPhish terbaru masih commit yang sama dengan sumber lama. Audit PhishVN tetap 200 domain, sedangkan tambahan 21 adjudikasi QR memiliki label inert/app-download/abuse yang tidak identik dengan klasifikasi phishing URL. Artefak IPFS WWW2026 menyediakan kode kolektor, bukan tabel publik dua kelas bertanggal yang langsung dapat dipakai; kolektor tidak dijalankan.

## Kesiapan teknis CNN

PyTorch **2.11.0+cpu** tersedia; GPU CUDA tidak tersedia. Dependency opsional `cnn` dipin ke torch 2.11.0. Arsitektur percobaan kecil memiliki **18.193 parameter**, embedding byte deterministik, tiga Conv1d, padding mask dan head classifier. HTTP/HTTPS menerima token identik; URL hasil QR melewati canonical core yang sama. Query/fragment tidak masuk tokenizer. Ada token CUT untuk pemotongan head/tail; ini bukan kompresi SVD.

Audit panjang dilakukan **hanya pada 535.504 fit v8**: median 30, p99 110, p99,9 201, maksimum 4.183 karakter scheme-free. Sebanyak 46 URL melampaui 512 dan 14 melampaui 1.024; pemotongan tetap harus dilaporkan bila konfigurasi 512 digunakan. Ini persiapan konfigurasi, bukan hasil eksperimen CNN.

Tes arsitektur menggunakan fixture sintetis dalam memori, memeriksa scheme parity, pelestarian tail/CUT, padding invariance, finite output, backward gradient dan roundtrip `state_dict` dengan `weights_only=True`. Tidak melatih classifier pada data proyek, menyimpan checkpoint random sebagai model, atau menampilkan skor random sebagai accuracy.

## Exposure, integritas dan pekerjaan yang masih diperlukan

Registry diperbarui setelah checksum intake dan protokol audit tervalidasi: **17 cache, 1.158.886 hash URL unik, 747.365 hash domain/tenant unik**, tanpa run belum terdaftar. V9 didaftarkan sebagai verified data reuse, v10 sebagai completed intake tanpa training. Snapshot registry sebelum intake dipertahankan; semua 4.489 core baru tercakup, termasuk reserve dan yang melewati cap. Template anotasi Indonesia tetap kosong; tidak ada reviewer atau gold lokal rekaan.

Untuk membuka training, masih diperlukan holdout dengan benign serta phishing dari periode observasi baru, label/evidence yang dapat ditelusuri, domain di luar development/exposure sebelum intake, dan dukungan kelas memadai. Setelah tersedia, bekukan manifest holdout serta addendum konfigurasi sebelum fitting; latih CNN dan LR pada fit identik, pilih hanya dari development, kalibrasi/threshold terpisah, kemudian buka holdout satu kali. Accuracy CNN saat ini **tidak tersedia**.

## Verifikasi tahap persiapan

Notebook v10 selesai Run All **enam sel kode tanpa error**, dengan status data gate gagal secara eksplisit; notebook registry/anotasi delapan sel kode tanpa error. **89 tes lulus tanpa skip** (30,07 detik), Ruff check dan format 52 berkas lulus. Seluruh 4.489 URL intake beserta domainnya diperiksa tidak ada pada snapshot registry sebelum intake. Checksum model/notebook beku dan manifest shadow tetap cocok. [Laporan validasi](../ml/reports/recall-cnn-validation-v10.json) membedakan pengujian arsitektur dari training atau peningkatan accuracy.

Environment baru memerlukan `ml/.venv/Scripts/python.exe -m pip install -e "./ml[test,dev,research,cnn]"`; dependency CPU torch 2.11.0 sudah tersedia pada mesin pengerjaan. Cache input lokal yang terikat manifest diperlukan untuk replay.
