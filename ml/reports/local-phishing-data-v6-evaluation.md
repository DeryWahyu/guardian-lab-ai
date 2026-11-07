# Frozen v6: evaluasi phishing_data.csv

Dataset: 11,481 baris; phishing 5,741, legitimate 5,740.
Dapat dinilai: 11,241 (97.91%); unsupported: 240 tanpa score/band.
Hanya kolom URL digunakan; 87 fitur tambahan diabaikan. Tidak ada training atau perubahan threshold.
Threshold warning asli: `0.904713285827399`; MEDIUM/HIGH dihitung positif.

| Populasi | N | Accuracy | Precision | Recall phishing | FPR | Brier | ECE |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Semua baris didukung (diagnostik, termasuk duplikat) | 11,241 | 74.98% | 99.23% | 49.33% | 0.37% | 0.061419 | 0.065751 |
| Representasi unik tanpa konflik label | 7,413 | 76.73% | 99.33% | 50.76% | 0.31% | 0.058447 | 0.064890 |
| Unik, tanpa overlap URL/domain paparan lokal sebelumnya | 0 | N/A | N/A | N/A | N/A | N/A | N/A |

Confusion matrix seluruh baris didukung: TN=5,712, FP=21, FN=2,791, TP=2,717.
Interval Wilson accuracy 95% (asumsi baris independen): 74.18%–75.78%; duplikat dan korelasi domain membatasi tafsirnya.
Duplikat URL mentah: 3,481 baris. Konflik representasi model: 1 representasi/6 baris; label tidak diubah.
Overlap URL atau domain dengan paparan sebelumnya: 11,241/11,241 baris didukung.

Ketidakpastian domain, metrik kalibrasi, dua threshold asli, cakupan, hash sumber dan verifikasi tersimpan dalam JSON pendamping.
Provenance penerbit/lisensi/tanggal/review manusia belum diverifikasi. Hasil ini bukan validasi manusia Indonesia atau bukti kesiapan produksi. LOW tidak menjamin aman; production_ready=false.

Artifact SHA-256: `f332bcbf7665955677e17daa73c487a7e1572a18d7f465b87e73caaa72e06319`.
Dataset SHA-256: `d0cae5023a83e8325b4c5829e5556d5a7bcc149a9ed75555a972964b1360ccdf`.
Seluruh input supported dicatat sebagai hash-only exposure sidecar; registry lama tidak diubah. Tidak ada URL/core/baris dataset dipersistensikan atau dikirim ke LLM, dan akses jaringan diblok selama evaluasi.
