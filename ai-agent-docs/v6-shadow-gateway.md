# Gateway internal untuk frozen v6

Gateway baru memperkuat layanan internal shadow dengan key backend, kuota dan batas pekerjaan. Entry point: `guardian_ml.shadow_gateway:create_app`. Ia memuat primary service `guardian_ml.shadow_service:create_app` di dalam proses yang sama dan memakai binary/metadata v6 asli. Sejak instruksi pengguna 7 November 2026, [warning layanan adalah 0,5](v6-serving-threshold-0p5.md), HIGH tetap 0,9884744926236343. Tidak ada promosi model atau aktivasi publik; semua prediksi tetap `needs_review` dan `production_ready=false`.

## Menjalankan di lingkungan internal

Pasang Python 3.12 dan dependency terpin serta artifact seperti [panduan integrasi](web-integration-v6.md). Pada PowerShell, buat secret acak dalam environment proses tanpa mencetaknya:

```powershell
$env:GUARDIAN_SHADOW_GATEWAY_KEY = & .\ml\.venv\Scripts\python.exe -c "import secrets; print(secrets.token_urlsafe(48))"
.\ml\.venv\Scripts\python.exe -m uvicorn guardian_ml.shadow_gateway:create_app --factory --host 127.0.0.1 --port 8002 --no-access-log
```

Untuk Bash setelah environment aktif:

```bash
export GUARDIAN_SHADOW_GATEWAY_KEY="$(python -c 'import secrets; print(secrets.token_urlsafe(48))')"
python -m uvicorn guardian_ml.shadow_gateway:create_app --factory --host 127.0.0.1 --port 8002 --no-access-log
```

Pada deployment internal yang memakai beberapa service, simpan key yang sama dalam secret manager backend Python dan backend web. Key tidak masuk Git, log, browser atau variabel `NEXT_PUBLIC_*`. Key kosong, pendek, whitespace atau non-ASCII ditolak. `GUARDIAN_ML_MODE=production` tetap ditolak oleh primary service.

| Konfigurasi | Default | Makna |
| --- | ---: | --- |
| `GUARDIAN_GATEWAY_RPM` | 60 | refill token/menit global dalam satu proses |
| `GUARDIAN_GATEWAY_BURST` | 10 | kapasitas bucket |
| `GUARDIAN_GATEWAY_MAX_INFLIGHT` | 2 | prediksi aktif maksimum; tidak membuat antrean tanpa batas |
| `GUARDIAN_GATEWAY_TIMEOUT` | 5 detik | deadline respons setelah body diterima |

Body dibatasi 65.536 byte aktual termasuk chunked, dengan deadline 3 detik; URL schema tetap maksimum 16.384 karakter. Response dibatasi 65.536 byte. Konfigurasi di luar batas aman ditolak. Rate limit bersifat per proses/backend credential, bukan identitas IP/end-user; beberapa replica memerlukan gateway/kuota bersama di lapisan deployment. Backend web tetap memerlukan autentikasi/kuota penggunanya sendiri.

## Endpoint dan kontrak error

- `/live`: GET publik berisi liveness tetap, tanpa status model atau data target.
- `/health`, `/predict`, `/metrics`, `/openapi.json`: memerlukan `Authorization: Bearer <key>`.
- `/gateway-metrics`: GET terautentikasi untuk counters inflight/peak, status dan histogram latency. Tidak ada event per request, key, URL, IP atau user ID. Precision/recall/FPR online tetap null.

HTTP 401 (key), 408 (body timeout), 413 (ukuran), 429 (kuota), 503 (kapasitas/model/error), dan 504 (deadline inferensi) selalu tanpa model score atau risk band. Beberapa menyediakan Retry-After. Backend memperlakukan semuanya sebagai analisis belum tersedia/perlu verifikasi. Error gateway memakai envelope ringkas; caller memeriksa HTTP status sebelum membaca field prediksi lengkap.

Path assignment yang terdeteksi berisi password/token/secret/identitas sensitif, termasuk beberapa encoding, menghasilkan HTTP 422 unsupported tanpa score/band. Ini abstention tambahan pada gateway untuk menutup keterbatasan secret pendek parser beku; tidak diam-diam mengubah input lalu mengklaim parity. Pendeteksian tetap heuristik, bukan anonimisasi atau deteksi seluruh PII. Cakupan URL yang dapat dianalisis berkurang. Query/fragment tetap diperlakukan sesuai parser/model asli.

## Integrasi backend Next.js

Atur `GUARDIAN_ML_URL=http://127.0.0.1:8002` dan `GUARDIAN_SHADOW_GATEWAY_KEY` pada environment server backend. Contoh server-side:

```javascript
export async function checkUrl(url, inputType = "URL") {
  const key = process.env.GUARDIAN_SHADOW_GATEWAY_KEY;
  if (!key) return { status: "unavailable", needs_review: true };
  try {
    const response = await fetch(`${process.env.GUARDIAN_ML_URL}/predict`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "Authorization": `Bearer ${key}`,
      },
      body: JSON.stringify({ url, input_type: inputType }),
      signal: AbortSignal.timeout(10000),
      cache: "no-store",
    });
    const result = await response.json();
    if (!response.ok || result.status !== "complete") {
      return { status: result.status ?? "unavailable", needs_review: true };
    }
    return result;
  } catch {
    return { status: "unavailable", needs_review: true };
  }
}
```

Pemanggilan ini hanya pada backend, dengan alamat model dari konfigurasi tepercaya. Caller QR mendekode gambar sendiri dan menghentikan payload non-URL. Untuk host berbeda, gunakan jaringan privat dan TLS/reverse proxy yang dikonfigurasi serta diuji; petunjuk ini tidak men-deploy server publik. Hasil LOW tetap memerlukan verifikasi dan tidak berarti SAFE.

## Batas timeout dan pengujian

Saat deadline berakhir, gateway mengembalikan 504 tetapi komputasi yang berjalan tetap memegang slot sampai selesai. Pembatalan klien tidak membebaskan slot lebih awal. Ini mencegah request timeout membuat jumlah komputasi aktif tak terbatas. Thread Python yang macet tidak dihentikan paksa; deployment memerlukan process supervision/isolasi worker, batas CPU/memori dan restart policy yang diuji.

[Load test lokal](../ml/reports/v6-shadow-gateway-load-test.json) memakai model asli dan URL sintetis: 100/100 request pada konkurensi 2 berhasil, p95 sekitar 17,8 ms; burst 160/konkurensi 16 menghasilkan 2 berhasil dan 158 busy dengan peak inference tetap 2. Seluruh prediksi berhasil mempunyai delta nol terhadap pemanggilan model langsung. Kuota benchmark dilonggarkan ke 10.000/menit, burst 1.000 agar pengujian mengukur kapasitas, bukan rate limiter. Angka ini adalah ASGI in-process di satu workstation, bukan benchmark jaringan/TLS atau SLA produksi.

Tes memeriksa kuota, autentikasi, privacy rejection, request lambat/chunked, error/response berlebih, cancellation, timeout threadpool nyata, dependency/source tampering dan parity artifact asli. [Manifest gateway](../ml/policies/shadow-gateway-manifest.json) mengikat source baru, dependency lengkap dan hash manifest layanan aktif `shadow-serving-manifest.json`. Source binding dan parent hash diperbarui pada perubahan kebijakan warning 0,5; laporan load test historis di atas tetap memakai policy historis. [Verifikasi kebijakan baru](v6-serving-threshold-0p5.md) mencatat parity dan load test ulang tanpa menimpa laporan historis. Perubahan source sengaja memerlukan pembaruan manifest serta pengujian parity/load baru; jangan melonggarkan guard agar mismatch diterima.

Kesiapan produksi tetap bergantung pada kualitas model, independent Indonesia gold dan reviewer nyata, hak penggunaan sumber hulu, serta pengujian deployment. [Hasil perbaikan dan hambatan](../ml/reports/v6-readiness-improvements.md) mencatat hasil negatif eksperimen private hosting dan sumber yang disaring.
