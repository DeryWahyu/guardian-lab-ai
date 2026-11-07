# Evaluasi lanjutan frozen v6

Audit otomatis selesai untuk kesalahan, konflik representasi/label, hasil per kelompok dan trade-off threshold development. Verifikasi kebenaran label oleh manusia serta pengujian Indonesia independen masih menunggu kandidat dan hasil review nyata.

Tidak ada training atau perubahan threshold layanan. Semua cohort sudah pernah terpapar. Angka di bawah mengikuti label sumber, bukan penetapan label baru.

## Temuan utama

- Pada vendor, 1.142 dari 1.187 false negative (96,21%) berada di luar private hosting yang dikenali PSL. Recall kelompok ini 39,16% (735/1.877), dibanding private hosting 86,53% (289/334). Ini hubungan deskriptif; komposisi data berbeda dan penyebab kesalahan belum terverifikasi.
- URL panjang memang lemah pada tune (36/315 phishing tertangkap), tetapi hanya mencakup 279 dari 17.501 false negative tune. Pada vendor, hanya 5 dari 1.187 false negative berasal dari URL panjang. Perbaikan kelompok kecil ini saja tidak mengatasi sebagian besar phishing yang terlewat.
- Semua 33 konflik berasal dari PhiUSIIL dan berupa pasangan yang hanya berbeda HTTP/HTTPS: 33 HTTP berlabel phishing dan 33 HTTPS berlabel benign. V6 sengaja mengeluarkan scheme dari fitur, sehingga kedua anggota pasangan mendapat representasi sama. Ini membuktikan ambiguitas representasi terhadap label penerbit, bukan bukti label mana yang benar. [Rincian provenance](v6-label-conflict-provenance.json). Jumlah konflik ini tidak dengan sendirinya menjelaskan ribuan false negative.
- Kandidat mengalami regresi recall pada private hosting: vendor turun 5,09 percentage point (domain-bootstrap 95% [-7,927; -2,586]); feed positif turun 1,74 point (95% [-2,414; -1,050]). Interval ini bersifat eksplorasi setelah eksperimen dan belum dikoreksi untuk banyak perbandingan; keduanya memperkuat alasan mempertahankan v6 aktif.
- Pada tune, threshold sekitar 0,692713 menaikkan recall menjadi 59,70%, tetapi FPR menjadi 2,297% (1.228 FP), dibanding threshold aktif 42,69% dan 0,382% (204 FP). Kelima policy diagnostik belum mencapai recall 85%. Tidak disimpulkan bahwa semua threshold lain pasti gagal; tidak ada threshold baru yang diaktifkan.
- ECE tune 0,03089 dibanding vendor 0,15450. Perbedaan kalibrasi antarcohort ini menunjukkan keterbatasan memindahkan makna skor antar distribusi. Tanggal cache Phresh berakhir September 2025 dan DeepURLBench Maret 2023, sedangkan tiga sumber lain tidak memiliki tanggal kasus pada cache. Data ini tidak menyediakan benign Indonesia kontemporer 2026 yang terverifikasi.

Prioritas lanjutan berdasarkan audit ini adalah bukti label/URL baru untuk kelompok false negative yang dominan, pemeriksaan drift sumber/waktu, serta validasi dua kelas Indonesia yang dikunci. Vocabulary karakter tidak kosong pada seluruh cohort; ketiadaan vocabulary karakter bukan penjelasan umum yang didukung audit ini. Antrean error dan konflik yang sudah terpapar tidak menjadi final holdout baru.

## Kesalahan pada threshold warning asli

| Cohort | URL | TP | FN | FP | Precision | Recall | FPR |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| tune | 84,000 | 13037 | 17501 | 204 | 98.459% | 42.691% | 0.382% |
| vendor | 20,000 | 1024 | 1187 | 168 | 85.906% | 46.314% | 0.944% |
| community_positive | 9,269 | 4313 | 4956 | N/A | N/A | 46.531% | N/A |

## Pola false negative

Kelompok saling tumpang tindih. Share FN adalah proporsi seluruh phishing terlewat dalam cohort, bukan estimasi penyebab atau kepastian label. Perbandingan berikut bersifat eksplorasi setelah melihat eksperimen.

| Cohort | Kelompok | URL | Phishing | FN | Share seluruh FN | Recall | FPR |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| tune | root_path_yes | 47898 | 18438 | 10550 | 60.282% | 42.781% | 0.475% |
| tune | root_path_no | 36102 | 12100 | 6951 | 39.718% | 42.554% | 0.267% |
| tune | private_hosting_yes | 8212 | 7388 | 698 | 3.988% | 90.552% | 6.311% |
| tune | private_hosting_no | 75788 | 23150 | 16803 | 96.012% | 27.417% | 0.289% |
| tune | long_url_yes | 616 | 315 | 279 | 1.594% | 11.429% | 0.664% |
| tune | word_vector_empty_yes | 74 | 70 | 19 | 0.109% | 72.857% | 0.000% |
| tune | char_vector_empty_yes | 0 | 0 | 0 | 0.000% | N/A | N/A |
| tune | keyword_present_no | 78783 | 26455 | 16198 | 92.555% | 38.771% | 0.354% |
| vendor | root_path_yes | 7298 | 948 | 515 | 43.387% | 45.675% | 1.795% |
| vendor | root_path_no | 12702 | 1263 | 672 | 56.613% | 46.793% | 0.472% |
| vendor | private_hosting_yes | 1040 | 334 | 45 | 3.791% | 86.527% | 5.099% |
| vendor | private_hosting_no | 18960 | 1877 | 1142 | 96.209% | 39.158% | 0.773% |
| vendor | long_url_yes | 202 | 16 | 5 | 0.421% | 68.750% | 0.000% |
| vendor | word_vector_empty_yes | 1 | 0 | 0 | 0.000% | N/A | 0.000% |
| vendor | char_vector_empty_yes | 0 | 0 | 0 | 0.000% | N/A | N/A |
| vendor | keyword_present_no | 19294 | 1779 | 1048 | 88.290% | 41.091% | 0.908% |
| community_positive | root_path_yes | 4613 | 4613 | 1828 | 36.885% | 60.373% | N/A |
| community_positive | root_path_no | 4656 | 4656 | 3128 | 63.115% | 32.818% | N/A |
| community_positive | private_hosting_yes | 2757 | 2757 | 1040 | 20.985% | 62.278% | N/A |
| community_positive | private_hosting_no | 6512 | 6512 | 3916 | 79.015% | 39.865% | N/A |
| community_positive | long_url_yes | 6 | 6 | 4 | 0.081% | 33.333% | N/A |
| community_positive | word_vector_empty_yes | 7 | 7 | 1 | 0.020% | 85.714% | N/A |
| community_positive | char_vector_empty_yes | 0 | 0 | 0 | 0.000% | N/A | N/A |
| community_positive | keyword_present_no | 8618 | 8618 | 4663 | 94.088% | 45.892% | N/A |

Host/path, panjang, keyword, redaksi, vocabulary coverage dan `.id` hanya indikator struktur. Tidak ada inspeksi halaman atau bukti bahwa URL tertentu menargetkan Indonesia. Query/fragment asli sudah dibuang dan tidak dapat dipakai menjelaskan penyebab error.

## Konflik label

Ada 33 representasi development dengan label bertentangan (66 baris); distribusi per partisi: `{"calibration": 3, "fit": 20, "threshold": 3, "tune": 7}`. Konflik fit adalah subset yang dikarantina pada eksperimen sebelumnya.

Lintas sumber: 0; konflik dalam sumber: 33; core cache identik dengan label berbeda: 0; memuat placeholder redaksi: 0; lebih dari satu tanggal diketahui: 0.

Dua antrean review blind dan satu daftar koordinator disimpan hanya lokal di `ml/data/v6-diagnostic-evaluation`. Berisi locator hash cache tanpa URL target; label sumber dan prediksi tidak masuk antrean blind. Reviewer harus menggunakan bukti penerbit, mengisi label/uncertain/out_of_scope dan evidence_ref. Tidak ada label yang diubah atau reviewer yang dibuat otomatis.

## Perbandingan kelompok kandidat terhadap v6

- vendor, private_hosting: recall 86.527% menjadi 81.437%; FPR 5.099% menjadi 4.249%; 95% domain-bootstrap delta recall (percentage point) [-7.927, -2.586].
- vendor, long_url: recall 68.750% menjadi 68.750%; FPR 0.000% menjadi 0.000%; 95% domain-bootstrap delta recall (percentage point) [0.0, 0.0].
- vendor, punycode: recall 50.000% menjadi 50.000%; FPR 0.000% menjadi 5.263%; 95% domain-bootstrap delta recall (percentage point) [0.0, 0.0].
- community_positive, private_hosting: recall 62.278% menjadi 60.537%; FPR N/A menjadi N/A; 95% domain-bootstrap delta recall (percentage point) [-2.414, -1.05].
- community_positive, long_url: recall 33.333% menjadi 16.667%; FPR N/A menjadi N/A; 95% domain-bootstrap delta recall (percentage point) [-50.0, 0.0].
- community_positive, punycode: recall 0.000% menjadi 16.667%; FPR N/A menjadi N/A; 95% domain-bootstrap delta recall (percentage point) [0.0, 50.0].

## Threshold development

Setiap threshold dipilih hanya pada partisi threshold, kemudian dinilai pada tune yang terpisah domain/digest. Lima budget ditentukan sebelum scoring audit. Semua merupakan diagnostik; tidak ada policy yang dipilih untuk layanan atau dioptimalkan pada benchmark.

| Budget FPR per sumber, threshold partition | Threshold | Recall tune | FPR tune | Precision tune | FP tune | FN tune |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 0.1% | 0.988468765 | 17.319% | 0.028% | 99.717% | 15 | 25249 |
| 0.5% | 0.947446109 | 34.262% | 0.180% | 99.091% | 96 | 20075 |
| 1.0% | 0.904627780 | 42.698% | 0.382% | 98.460% | 204 | 17499 |
| 2.0% | 0.830207494 | 50.478% | 0.814% | 97.256% | 435 | 15123 |
| 5.0% | 0.692713125 | 59.696% | 2.297% | 93.689% | 1228 | 12308 |

FPR empiris partisi threshold tidak menjamin FPR di tune, sumber lain atau populasi. Skor/kalibrasi tetap mengacu pada campuran riset, bukan probabilitas trafik Indonesia. Counts, source rates, Wilson dan calibration bins tersedia dalam JSON.

## Kesiapan validasi Indonesia

Input aktual: `{"adjudication": 0, "candidates": 0, "reviewer_a": 0, "reviewer_b": 0}`. Belum ada holdout Indonesia dengan label dan identitas reviewer independen yang terverifikasi; metrik Indonesia tidak dihitung.

Rencana pengumpulan dan pembekuan ada di `ai-agent-docs/v6-indonesia-validation-readiness.md`. Minimum 1.000 phishing/3.000 benign dan dua reviewer adalah syarat awal, bukan bukti otomatis lolos. Pilot lama yang sudah terpapar tidak menjadi holdout baru.

## Reproduksi dan batas bukti

```powershell
ml/.venv/Scripts/python.exe scripts/evaluate_v6_diagnostics.py --output-stem ml/reports/v6-diagnostic-replay --review-dir ml/data/v6-diagnostic-replay
```

Memerlukan extra `quality`, cache v6 lokal dan kandidat eksperimen yang checksum/source-nya cocok. Output lengkap bersifat agregat; dataset/review queues tetap diabaikan Git. Guard runtime, 62 referensi sintetis dan registry exposure diperiksa sebelum/sesudah audit.

- This is an exploratory post-experiment audit; segments and previously exposed tune cannot establish fresh generalization.
- Source labels remain publisher labels unless real independent human evidence is supplied.
- Positive-only feeds cannot supply FPR, traffic precision or binary accuracy.
- Short URLs, root paths, missing vocabulary coverage or hosting flags are associations, not verified causes or labels.
- Original query/fragment content is unavailable; no claim about whether discarded context caused an error.
- No target visits, automatic relabeling, invented reviewers, model promotion or Indonesia validation claim.
