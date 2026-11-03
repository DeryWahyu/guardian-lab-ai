# Validasi Indonesia untuk v6

Status: belum ada gold set Indonesia yang terverifikasi dan belum ada evaluasi lokal independen. Model tunggal adalah frozen v6; pemilihannya tidak memenuhi release gate.

Kandidat perlu berasal dari sumber publik dengan provenance, waktu observasi dan hak penggunaan yang jelas. Dua reviewer manusia independen menilai relevansi Indonesia dan label URL-only, kemudian konflik diadjudikasi. Jangan membuat nama reviewer, mengisi review otomatis, memakai LLM sebagai ground truth atau mengunjungi target dari mesin lokal.

Pisahkan holdout sebelum fitting/seleksi/kalibrasi/threshold. Periksa canonical URL, registered domain/private tenant, waktu dan kampanye terhadap exposure lama. Registry exposure lokal dipertahankan setelah cleanup; benchmark yang pernah dilihat tidak kembali independen karena model lain dihapus.

Template kosong tetap ada di [ml/templates](../ml/templates/). Minimum pada [release policy](../ml/policies/url-qr-release-gates.json) adalah 1.000 phishing dan 3.000 benign, dua reviewer, lower Wilson recall 85% dan upper Wilson FPR 1%, beserta audit lain. Minimum jumlah saja tidak meluluskan gate. Data positif saja, historical domain negatives, `.id` atau nama brand tidak cukup.
