# Protokol v5 — Recall Phishing, False Alarm, dan Data Uji Baru

> Tanggal: 1 November 2026. Tahap awal: riset sumber dan pembekuan protokol sebelum fitting/prediksi data uji baru.

> **Hasil aktual:** v5 selesai; enam konfigurasi konvergen, tetapi repeat v3 tetap menang. Macro-source recall tune tetap 44,14%. Pada test baru DeepURLBench, recall 52,79% dan FPR 5,41%; pada 33 kasus manusia, 9/22 phishing tertangkap dan 0/11 benign salah ditandai. Batas atas Wilson FPR pada 11 benign tetap 25,88%, sehingga nol FP tidak membuktikan FPR rendah. Target peningkatan belum tercapai. Sebelas pemeriksaan inferensi/pembekuan lolos; [laporan aktual](../ml/reports/recall-improvement-v5.json) dan notebook dijalankan penuh tanpa error.

Test v5 kini telah teramati. Perbaikan data berikutnya harus memakai domain development yang tidak overlap dan holdout baru sesuai [protokol v6](./data-improvement-v6-plan.md). Jangan mengubah threshold v5 dari hasil tersebut.

## Tujuan dan batas

Meningkatkan recall phishing pada FPR rendah untuk URL dan URL hasil decode QR. Satu keluarga classifier tetap Logistic Regression. Baseline v3/v4 dipertahankan. V4 sudah menunjukkan perubahan bobot loss saja tidak memperbaiki objective validasi; v5 menguji representasi fitur, bukan mengulang pencarian bobot yang sama.

Tidak menjanjikan kenaikan hasil. Semua angka harus berasal dari eksekusi aktual. Dataset baru dan label yang diklaim lebih tepercaya harus diaudit terlebih dahulu; label model/LLM bukan ground truth. Tidak membuka target URL, mengeksekusi HTML, melakukan live DNS, mengirim baris dataset ke LLM, atau mengumpulkan PII asli.

## Fase A — Seleksi data uji sebelum model dibekukan

1. Gunakan sumber primer dengan versi/commit dan hak penggunaan yang jelas. Periksa file, schema, label mapping, jumlah kelas, provenance, metode verifikasi manusia/vendor, serta akses bukti. Klaim “manually verified” tanpa rincian tidak cukup untuk menyebut gold set.
2. Pisahkan phishing dari malware/scam/spam. Uncertain dan out-of-scope dikeluarkan dengan alasan sebelum prediksi, bukan diubah menjadi benign.
3. Sanitasi langsung di memori; persist hanya canonical core, label, group/hash, waktu/provenance yang aman. Jangan menyimpan raw URL atau bukti yang mengandung PII.
4. Deduplicate canonical, audit label konflik, dan keluarkan overlap URL/domain/tenant terhadap seluruh exposure tersimpan v1–v4. Catat campaign overlap yang belum dapat diverifikasi. Filter tidak boleh bergantung pada skor atau kesalahan model.
5. Label uji tidak dipakai untuk vocabulary, transformasi supervised, fitting, hyperparameter, kalibrasi, atau pemilihan threshold. Audit label boleh dilakukan tanpa prediksi; pembagian peran tetap dicatat secara jujur.
6. Bekukan manifest sumber dan subset uji sebelum scoring. Sumber baru berarti belum digunakan oleh eksperimen proyek; tahun publikasi bukan bukti tanggal pengumpulan atau independensi temporal.

Kandidat awal yang diperiksa: DeepURLBench, CompPhish, PhishBD_2026, Dataset_Phising dengan klaim manual, PhishMMF, serta audit manusia PhishVN. Ini daftar pemeriksaan, belum keputusan kelayakan. CompPhish/PhishBD dapat bercampur ancaman atau menggunakan label feed; audit PhishVN dapat overlap data lama. Sumber yang gagal tidak dipaksakan lolos.

Jika tidak ditemukan data yang cukup kuat, laporkan batas tersebut dan siapkan kandidat/anotasi sesuai [protokol gold set Indonesia](./indonesia-gold-set-plan.md). Jangan mengarang reviewer atau menyebut data otomatis sebagai gold. Eksperimen development tetap dapat berjalan sambil kebutuhan validasi yang belum terpenuhi dicatat.

## Fase B — Hipotesis model dan anggaran

### Keputusan sumber sebelum fitting

- **DeepURLBench:** benchmark eksternal baru untuk proyek, commit `bf17c3fef854ff0ea40bcf93e373fc2c6dc30081`. Gunakan delapan shard `urls_without_dns` dengan hash SHA-256 nama file terkecil, tanpa DNS atau fitur vendor sebagai input. Ambil hanya label `phishing`/`benign`; malware dikeluarkan. Label berdasarkan aturan konsensus vendor berbobot yang diterangkan penulis, bukan gold manusia. Benign karena tidak terdeteksi vendor masih berpotensi salah label. Lisensi CC BY-NC 4.0 membatasi penggunaan ke riset nonkomersial.
- **Audit manusia PhishVN:** commit `2bc80412a4b94ae546211e488ced996c8e0b78f1`, sheet A/B dan adjudikasi publik. Ambil kesepakatan/adjudikasi `phishing` atau `legitimate` dengan evidence `capture`, `archive`, `urlscan`, atau `registry`; evidence berbasis `name`/`none`, scam dan unsure tidak masuk binary test. Singkirkan overlap domain/URL lama. Audit awal menemukan 22 phishing dan 11 legitimate yang tidak cocok registry; ini pengujian tambahan kecil, belum cukup membuktikan FPR 1%. Sumber sama dengan PhishVN development; independensi sumber/kampanye tidak diklaim.
- **Tidak dipakai sebagai test primer:** CompPhish mencakup tautan malware; PhishBD mencampur feed rahasia dengan benign hasil injeksi ranking; PhishMMF berlabel email dan fitur LLM, bukan ground truth URL spesifik; Dataset_Phising mengklaim manual tetapi schema label numeric tidak menerangkan mapping kelas secara memadai dan tidak menyediakan audit independen. Jumlah/label tidak ditebak dari isi URL.

Untuk DeepURLBench, sanitasi dan kurasi seluruh delapan shard yang ditetapkan, buang konflik canonical sebelum prediksi, lalu ambil maksimal 10 URL per domain/tenant menurut hash digest dan maksimal 50.000 URL menurut digest terurut. Sampling ini tidak memakai skor atau label untuk menyeimbangkan kelas. Laporkan hitungan sebelum/sesudah setiap filter serta desain sampling; ini bukan sampel acak trafik. Manifest checksum source bytes dan subset dibekukan sebelum fitting/prediksi.

Rujukan primer: [paper DeepURLBench](https://arxiv.org/html/2501.00356v1), [dataset dan lisensi](https://github.com/deepinstinct-algo/DeepURLBench), [rubric audit PhishVN](https://github.com/vuthainguyen1602/phishvn/blob/2bc80412a4b94ae546211e488ced996c8e0b78f1/docs/verify/CODEBOOK.md). Verifikasi yang dilakukan tim penerbit dicatat sebagai provenance, bukan diklaim sebagai review baru oleh agent.

Data development tetap cache v3 dengan checksum terverifikasi: fit 432.793, tune 64.000, calibration 30.104, threshold 31.707. Tidak memasukkan data uji baru ke development. Source weighting akar rasio tetap seperti baseline agar pengaruh perubahan fitur dapat dibandingkan.

Enam konfigurasi yang direncanakan, satu classifier akhir:

| Kandidat         | Representasi                                            |   C |
| ---------------- | ------------------------------------------------------- | --: |
| `repeat_v3`      | Encoder v3 tanpa perubahan                              |   2 |
| `nb_rich_c05`    | Encoder v3 + supervised log-count-ratio pada fitur teks | 0,5 |
| `nb_rich_c2`     | Encoder v3 + supervised log-count-ratio pada fitur teks |   2 |
| `nb_rich_c8`     | Encoder v3 + supervised log-count-ratio pada fitur teks |   8 |
| `field_aware_c2` | Char TF-IDF host/path terpisah + numeric scheme-free    |   2 |
| `field_aware_c8` | Char TF-IDF host/path terpisah + numeric scheme-free    |   8 |

Transformasi log-count-ratio mengikuti hipotesis NB-SVM untuk teks: rasio statistik kelas dihitung **hanya dari fit**, dengan smoothing, lalu dipakai untuk transformasi fit/tune/inferensi yang sama. Model akhir tetap Logistic Regression, bukan ensemble voting. Parameter rinci dan implementasi final dibekukan dalam manifest notebook sebelum fitting.

Parameter final: alpha=1, rasio log berbobot source weights fit dan dibatasi ke [-4,4], hanya dimensi teks yang diberi rasio; dimensi numeric memakai faktor 1. Seluruh vektor hasil transformasi dinormalisasi L2. Ini adaptasi proyek dari [log-count-ratio NB-SVM](https://aclanthology.org/P12-2018/), bukan klaim mereproduksi hasil paper pada phishing. Field-aware memakai host char (2,5) maksimal 60.000 fitur dan path char (2,5) maksimal 80.000, min_df=4, sublinear TF, float32. Vocabulary memakai sampling fit seimbang per sumber yang sama batasnya dengan v3 (maksimum 60.000 per sumber dan 150.000 total); scaler numeric fit v3 dipakai kembali karena fit partition tidak berubah. Bobot host/path 0,7/0,7 dan numeric 0,2, lalu normalisasi L2.

Representasi field-aware membedakan sinyal hostname dan path; semua vocabulary/scaler baru dipelajari dari fit saja. Tidak memakai HTTPS sebagai fitur, query/fragment yang mengandung data pribadi, target brand dari metadata label, source ID, atau informasi yang tidak tersedia saat inferensi.

## Fase C — Aturan seleksi dan pembekuan

- Solver liblinear, seed 20261101, max_iter 300, tol 0,0001. Kandidat tidak konvergen tidak boleh menang.
- Pada tune, pilih macro-source recall terbesar dengan operating point yang memenuhi FPR empiris maksimal 1% di setiap sumber, lalu minimum-source recall, lalu AP. Bandingkan dengan repeat v3. Tidak memilih model dari accuracy test.
- Satu pemenang dikalibrasi sigmoid pada calibration; slope harus positif dan kalibrator konvergen.
- Warning/HIGH dipilih hanya dari threshold partition dengan target FPR empiris per sumber 1%/0,1%. Laporkan keterbatasan dukungan kelas dan interval; angka target bukan jaminan trafik.
- Simpan model, checksum, versi, manifest representasi, konfigurasi, dan threshold sebelum prediksi data uji baru. Tidak mengubah model/threshold setelah melihat hasil uji.

## Fase D — Evaluasi dan keputusan

Laporkan baseline dan kandidat pada sampel baru yang sama: recall, FPR, precision, accuracy/balanced accuracy, F1, AP, Brier/log loss, confusion matrix, dukungan kelas/domain, coverage/rejection, Wilson row-IID dan bootstrap domain berpasangan. Benchmark lama tetap diberi label teramati, bukan independent test baru.

Perbaikan development hanya diklaim dari tune sebagai hasil seleksi yang optimistis. Keberhasilan pada data baru memerlukan recall meningkat dengan ketidakpastian yang memadai dan FPR tetap rendah; trade-off atau regresi harus tetap terlihat. Tujuan recall 85%/FPR 1% dari rencana gold set adalah target, bukan hasil yang boleh diasumsikan tercapai.

Tidak melakukan promosi produksi otomatis. Jika data uji kecil/tidak cukup tepercaya atau interval tidak mendukung, keputusan validasi tetap belum meyakinkan. Validasi Indonesia memerlukan bukti konteks Indonesia; dataset Bangladesh/Vietnam/internasional tidak diganti namanya menjadi Indonesia.

## Deliverable

Notebook v5 berisi audit, fitting aktual, seleksi, kalibrasi, pembekuan, evaluasi dan inferensi URL/QR. Run baru terisolasi di `ml/runs/notebook-tfidf-logistic-v5/`; data tersanitasi dan artifact tetap lokal. Dokumen ini dan laporan agregat memuat hasil serta keterbatasan tanpa URL target atau identitas pribadi.
