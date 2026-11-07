# Memakai Frozen v6 dari Backend Web

Kode dan hasil evaluasi ada di repository [DeryWahyu/guardian-lab-ai](https://github.com/DeryWahyu/guardian-lab-ai). Binary model tersedia terpisah pada [GitHub Release v6 shadow](https://github.com/DeryWahyu/guardian-lab-ai/releases/tag/v6-shadow-20261103), bersama metadata pembekuan asli. Dataset, environment dan arsip lokal tidak dibagikan.

Untuk checkout yang sudah memuat gateway baru, integrasi backend disarankan melalui [gateway dengan autentikasi/kuota](v6-shadow-gateway.md). Source gateway saat ini berada pada branch pengembangan; artifact model tetap memakai release v6 yang sama. Langkah di bawah mempertahankan primary service asli untuk penggunaan internal langsung. Gateway memakai port 8002, memerlukan secret backend dan header Bearer, serta tetap `production_ready=false`.

## 1. Pasang layanan Python 3.12

Dari terminal di komputer/server pengembang:

```bash
git clone https://github.com/DeryWahyu/guardian-lab-ai.git
cd guardian-lab-ai
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -e "./ml[serve]"
python scripts/install_v6_model.py
python scripts/validate_v6.py
python -m uvicorn guardian_ml.shadow_service:create_app --factory --host 127.0.0.1 --port 8001 --no-access-log
```

Di Windows gunakan `python -m venv .venv` dan `.venv\Scripts\Activate.ps1`, lalu perintah `python` berikutnya sama. Installer mengunduh ZIP dari release resmi, memverifikasi checksum ZIP serta dua anggotanya, dan menempatkannya sesuai manifest runtime. File yang sudah ada dengan isi berbeda tidak ditimpa. Jangan memuat joblib dari sumber pengguna atau sumber lain yang tidak tepercaya.

Jika ZIP sudah diunduh melalui browser, gunakan `python scripts/install_v6_model.py --archive "PATH/guardian-lab-v6-shadow.zip"`. Tidak perlu training ulang atau mengunduh dataset. `/health` harus menampilkan `model_available=true`; `production_ready=false` tetap merupakan status yang benar.

Untuk menjalankan gateway, ikuti perintah pada [panduan gateway](v6-shadow-gateway.md), lalu gunakan `GUARDIAN_ML_URL=http://127.0.0.1:8002` dan key server `GUARDIAN_SHADOW_GATEWAY_KEY`. Gateway menampung primary service dalam proses yang sama; port primary tanpa gateway tidak perlu dibuka untuk integrasi ini.

## 2. Hubungkan backend web

Simpan alamat layanan sebagai konfigurasi server, misalnya `GUARDIAN_ML_URL=http://127.0.0.1:8001`. Frontend memanggil backend web milik aplikasi, lalu backend memanggil model. Alamat layanan tidak berasal dari input pengguna. Jika server terpisah, gunakan jaringan privat dan proteksi gateway sesuai lingkungan pengembang.

Contoh pemanggilan dari backend JavaScript dengan `fetch`:

```javascript
export async function checkUrl(url, inputType = "URL") {
  const response = await fetch(`${process.env.GUARDIAN_ML_URL}/predict`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ url, input_type: inputType }),
    signal: AbortSignal.timeout(5000),
  });
  const result = await response.json();
  if (!response.ok || result.status !== "complete") {
    return { status: result.status ?? "unavailable", needs_review: true };
  }
  return result;
}
```

Caller perlu menangani timeout/kegagalan jaringan sebagai unavailable/perlu verifikasi. Jangan mencatat URL, request body atau credential di log. Untuk QR, caller mendekode gambarnya terlebih dahulu dan mengirim URL dengan `input_type="QR"`. Payload QR non-URL tidak diberi hasil aman.

Contoh `fetch` di atas adalah pemanggilan langsung primary service internal. Untuk gateway, gunakan contoh server-side pada [panduan gateway](v6-shadow-gateway.md), dengan `Authorization: Bearer <key>` dan timeout client yang lebih besar daripada deadline gateway. HTTP 401/408/413/429/503/504 tidak menjadi LOW atau score nol. Key hanya disimpan pada backend; monitoring dan log tidak menyimpan body/URL/credential.

## 3. Tampilkan arti hasil dengan benar

- `risk_band` adalah LOW, MEDIUM atau HIGH berdasarkan threshold layanan aktif: warning 0,5 dan HIGH 0,9884744926236343. Gunakan `geek.thresholds`; `geek.frozen_thresholds` menyimpan ambang historis. Ini bukan keputusan aman terkonfirmasi. Lihat [kebijakan 7 November 2026](v6-serving-threshold-0p5.md).
- Gunakan `human.title`, `human.explanation` dan `human.recommended_action` untuk tampilan biasa; `geek` menyimpan versi, scope dan threshold.
- LOW tetap berarti perlu verifikasi. HTTP 422/503 dan timeout tidak diubah menjadi LOW, skor nol atau SAFE.
- Respons tidak menggemakan URL. `model_score` merupakan skor kalibrasi riset, bukan probabilitas trafik Indonesia.

Accuracy **93,23%** berasal dari holdout vendor 20.000 URL, dengan recall phishing **46,31%** dan FPR **0,944%**. Gold Indonesia belum tersedia dan model belum memenuhi gate produksi. Paket ini untuk riset nonkomersial/internal shadow; tidak mengaktifkan penggunaan publik atau mengubah status tersebut.

Kontrak field/status lengkap: [shadow-api-contract.md](shadow-api-contract.md). Hasil lengkap: [data-improvement-v6.json](../ml/reports/data-improvement-v6.json). Identitas paket: [v6-distribution.json](../ml/policies/v6-distribution.json).
