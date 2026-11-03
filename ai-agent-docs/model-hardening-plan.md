# Keandalan Frozen v6

API [shadow](shadow-api-contract.md) memuat artifact/threshold v6 asli dan tidak mengaktifkan penggunaan publik. [Audit agregat](../ml/reports/model-hardening-audit.json) tetap tersedia sebagai bukti historis.

Audit development memeriksa 84.000 URL tune dan bukti audit manusia PhishVN terpublikasi. Ditemukan 33 representasi dengan label bertentangan dan tiga kasus scam di luar scope yang memerlukan konteks. Tidak ada relabel otomatis. Pilot 73 kandidat berkonteks Indonesia belum memiliki label manusia terverifikasi; tidak dianggap gold set.

Release gate membutuhkan bukti recall/FPR dengan ketidakpastian, dua reviewer manusia independen, provenance/hak penggunaan, QA privasi, audit kelompok/waktu/kampanye dan holdout Indonesia independen. Hasil v6 belum memenuhinya. Label vendor, feed positif atau skor model tidak menggantikan bukti manusia lokal.

Runtime harus menolak perubahan checksum/schema/dependency/PSL; perubahan source disengaja memerlukan pembaruan manifest serta parity terhadap referensi notebook training asli. Tes mencakup input unsupported, error tanpa URL/credential, body limit, URL/QR parity, dependency subset yang tidak dapat dikosongkan dan monitoring agregat.

LOW tidak berarti SAFE. Unsupported/unavailable tidak menghasilkan skor atau risk band. Monitoring hanya jumlah dan histogram latency; precision/recall/FPR online null sampai tersedia ground truth manusia. Tidak ada pencatatan target atau koneksi ke target.

Parser beku masih heuristik: nilai secret pendek dalam assignment path belum seluruhnya teredaksi. Perbaikan perlu representasi baru yang diuji dan tidak boleh menyamarkan perubahan sebagai parity dengan artifact lama. Cleanup hanya memisahkan v6 dari dependensi model lain; tidak mengubah parser, fitur atau bobot.
