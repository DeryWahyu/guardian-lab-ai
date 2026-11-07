# Keandalan Frozen v6

Instruksi pengguna 7 November 2026 menetapkan [warning layanan 0,5](v6-serving-threshold-0p5.md), dengan HIGH tetap 0,9884744926236343. Skor, kalibrasi, binary, metadata training, manifest runtime historis dan hasil lama tetap utuh; `shadow-serving-manifest.json` mengikat kebijakan aktif dan source layanan saat ini. Kebijakan yang dipilih setelah benchmark teramati ini tidak menetapkan validasi independen atau readiness produksi. Verifikasi akhir mencatat 290 tes lulus dan score parity asli tetap identik.

API [shadow](shadow-api-contract.md) memuat artifact/threshold v6 asli dan tidak mengaktifkan penggunaan publik. [Audit agregat](../ml/reports/model-hardening-audit.json) tetap tersedia sebagai bukti historis.

Audit development memeriksa 84.000 URL tune dan bukti audit manusia PhishVN terpublikasi. Ditemukan 33 representasi dengan label bertentangan dan tiga kasus scam di luar scope yang memerlukan konteks. Tidak ada relabel otomatis. Pilot 73 kandidat berkonteks Indonesia belum memiliki label manusia terverifikasi; tidak dianggap gold set.

[Audit lanjutan 5 November 2026](../ml/reports/v6-diagnostic-evaluation.md) memeriksa false negative per struktur, konflik label, regresi kandidat per kelompok dan lima threshold development. [Provenance konflik](../ml/reports/v6-label-conflict-provenance.json) menunjukkan 33 pasangan HTTP/HTTPS dari PhiUSIIL yang berbeda label; sebab label dan konteks waktu/query tetap belum terverifikasi. Antrean review hash-only disiapkan lokal tanpa mengganti label. [Persiapan Indonesia](v6-indonesia-validation-readiness.md) mempertahankan kebutuhan kandidat baru, dua review manusia, QA dan final holdout terkunci.

Release gate membutuhkan bukti recall/FPR dengan ketidakpastian, dua reviewer manusia independen, provenance/hak penggunaan, QA privasi, audit kelompok/waktu/kampanye dan holdout Indonesia independen. Hasil v6 belum memenuhinya. Label vendor, feed positif atau skor model tidak menggantikan bukti manusia lokal.

Runtime harus menolak perubahan checksum/schema/dependency/PSL; perubahan source disengaja memerlukan pembaruan manifest serta parity terhadap referensi notebook training asli. Tes mencakup input unsupported, error tanpa URL/credential, body limit, URL/QR parity, dependency subset yang tidak dapat dikosongkan dan monitoring agregat.

LOW tidak berarti SAFE. Unsupported/unavailable tidak menghasilkan skor atau risk band. Monitoring hanya jumlah dan histogram latency; precision/recall/FPR online null sampai tersedia ground truth manusia. Tidak ada pencatatan target atau koneksi ke target.

Parser beku masih heuristik: nilai secret pendek dalam assignment path belum seluruhnya teredaksi. Perbaikan perlu representasi baru yang diuji dan tidak boleh menyamarkan perubahan sebagai parity dengan artifact lama. Cleanup hanya memisahkan v6 dari dependensi model lain; tidak mengubah parser, fitur atau bobot.

[Perbaikan 7 November 2026](../ml/reports/v6-readiness-improvements.md) menambahkan gateway internal opsional dengan manifest terpisah yang mengikat runtime asli, autentikasi backend, kuota/batas concurrency, timeout yang tetap menghitung komputasi aktif, serta abstention path assignment sensitif. Ini tidak mengubah representasi/threshold model asli. Real-artifact parity dan uji beban ASGI sintetis lulus; 274 tes teknis lulus. Eksperimen sumber yang disaring dan private-host LR expert tetap gagal guard atau mengalami regresi, sehingga tidak dipromosikan. Hak sumber hulu, independent Indonesia gold, reviewer nyata dan uji deployment tetap menjadi hambatan produksi.
