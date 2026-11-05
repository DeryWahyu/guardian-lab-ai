# Memakai Frozen v6 dari Backend Web

Kode dan hasil evaluasi ada di repository [DeryWahyu/guardian-lab-ai](https://github.com/DeryWahyu/guardian-lab-ai). Binary model tersedia terpisah pada [GitHub Release v6 shadow](https://github.com/DeryWahyu/guardian-lab-ai/releases/tag/v6-shadow-20261103), bersama metadata pembekuan asli. Dataset, environment dan arsip lokal tidak dibagikan.

## 1. Pasang layanan Python 3.12

Dari terminal di komputer/server pengembang:

```bash
git clone https://github.com/DeryWahyu/guardian-lab-ai.git
cd guardian-lab-ai
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -e "./ml[serve]"
python scripts/install_v6_model.py
python -m uvicorn guardian_ml.shadow_service:create_app --factory --host 127.0.0.1 --port 8001 --workers 1 --no-access-log
```

Di Windows gunakan `python -m venv .venv` dan `.venv\Scripts\Activate.ps1`, lalu perintah `python` berikutnya sama. Installer mengunduh ZIP dari release resmi, memverifikasi checksum ZIP serta dua anggotanya, dan menempatkannya sesuai manifest runtime. File yang sudah ada dengan isi berbeda tidak ditimpa. Jangan memuat joblib dari sumber pengguna atau sumber lain yang tidak tepercaya.

Jika ZIP sudah diunduh melalui browser, gunakan `python scripts/install_v6_model.py --archive "PATH/guardian-lab-v6-shadow.zip"`. Tidak perlu training ulang atau mengunduh dataset. `/health` harus menampilkan `model_available=true`; `production_ready=false` tetap merupakan status yang benar.

### Docker bersama Guardian Lab

Letakkan kedua checkout sebagai direktori sejajar `guardian-lab` dan `guardian-lab-ai`. Dari repo web, Compose `docker/docker-compose.dev.yml` membangun layanan `ml` menggunakan Dockerfile repo ini bersama Next dev, MySQL dan sandbox. Jalankan `docker compose --env-file .env -f docker/docker-compose.dev.yml up --build --watch` dari root repo web. Build memasang dependency terpin dan mengunduh paket v6 melalui installer resmi; build berhenti jika checksum atau guard ditolak. Konteks build hanya mengizinkan sumber runtime, policy, provenance, laporan agregat yang diperlukan health, serta installer. Dataset, environment, snapshot lokal dan binary dari host tidak disalin.

Model berjalan sebagai user non-root, satu worker, pada port internal 8001 tanpa port host atau access log. Healthcheck memeriksa ketersediaan model dalam mode shadow, bukan promosi produksi. Runtime tetap read-only dan hanya terhubung ke jaringan model privat; unduhan artifact hanya terjadi saat build. Compose mengatur backend Next ke `GUARDIAN_ML_URL=http://ml:8001`. Persiapan database, jaringan broker, perintah Compose, dan diagnosis aplikasi dijelaskan pada `ai-agent-docs/deployment.md` milik repo web.

Image ini tidak menjalankan training atau mengubah source yang diikat manifest. Artifact dan metadata hasil installer harus dapat dibaca user runtime; kepemilikan direktori artifact diatur saat build. Pengujian container/parity merupakan pemeriksaan terpisah dan tetap memerlukan cakupan yang disetujui saat dikerjakan melalui repo web.

Compose Watch memicu rebuild model untuk perubahan runtime yang diizinkan `.dockerignore`. Source website disinkronkan agar Next melakukan Fast Refresh; source Python memakai rebuild untuk mempertahankan guard artifact/dependency. Perubahan file yang diikat manifest tetap memerlukan pembaruan manifest yang sah dan verifikasi parity, bukan hot reload yang melewati checksum. Rebuild yang gagal dapat meninggalkan container lama tetap berjalan; periksa keluaran Watch. Rincian setup, environment, database dan perilaku Watch dimiliki panduan deployment repo web. Saat memakai stack ini, tidak perlu menjalankan Python atau Bun dev langsung di host.

## 2. Hubungkan backend web

Simpan alamat layanan sebagai konfigurasi server, misalnya `GUARDIAN_ML_URL=http://127.0.0.1:8001`. Frontend memanggil backend web milik aplikasi, lalu backend memanggil model. Alamat layanan tidak berasal dari input pengguna. Jika server terpisah, gunakan jaringan privat dan proteksi gateway sesuai lingkungan pengembang.

Implementasi Guardian Lab berada pada `lib/analysis/guardian-ml.ts`, `lib/investigations/receive-url.ts`, dan kontrak Zod `lib/validations/guardian-ml.ts` di repo web. Kedua jenis input memakai satu lifecycle investigasi: penerimaan serta `PROCESSING` ditransaksikan terlebih dahulu, panggilan model berlangsung di luar transaksi database, kemudian hasil terminal disimpan pada ID yang sama. Respons lengkap tervalidasi disimpan pada `technicalEvidence.urlModel`, termasuk skor asli, threshold, status riset, dan metadata artifact. Skor integer 0–100 hanya pembulatan untuk tampilan; kategori tetap mengikuti skor asli.

Sebelum pengiriman maupun penyimpanan, backend web menyaring URL melalui PII Scrubber dan sanitizer khusus yang menangani nilai sensitif path serta menghapus isi query/fragment. Keberadaan query/fragment dipertahankan sebagai penanda konteks. Path tanpa redaksi mempertahankan encoding aslinya. Target yang sudah dinonaktifkan atau didekode untuk tampilan tidak dipakai sebagai input model. Ini dapat mengubah skor untuk input sensitif, tetapi tidak mengubah preprocessing/representasi beku Python; sanitizer tetap heuristik. URL yang tidak dapat disanitasi ditolak tanpa menyimpan target asli.

Contoh pemanggilan dari backend JavaScript dengan `fetch`:

```javascript
// url harus sudah disanitasi di backend sebelum memanggil layanan.
export async function checkUrl(url, inputType = "URL") {
  const response = await fetch(`${process.env.GUARDIAN_ML_URL}/predict`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ url, input_type: inputType }),
    signal: AbortSignal.timeout(5000),
    cache: "no-store",
    redirect: "error",
  });
  const result = await response.json();
  if (!response.ok || result.status !== "complete") {
    return { status: result.status ?? "unavailable", needs_review: true };
  }
  return result;
}
```

Caller perlu menangani timeout/kegagalan jaringan sebagai unavailable/perlu verifikasi. Jangan mencatat URL, request body atau credential di log. Untuk QR, caller mendekode gambarnya terlebih dahulu dan mengirim URL dengan `input_type="QR"`. Payload QR non-URL tidak diberi hasil aman.

Contoh di atas hanya menunjukkan pemanggilan dasar. Adapter web aktif juga membatasi respons stream aktual 64 KiB, memvalidasi schema, provenance, pasangan HTTP/status dan konsistensi score/band/threshold. Kegagalan model atau respons rusak menghasilkan rekaman `UNAVAILABLE` tanpa skor; unsupported menghasilkan `FAILED` dengan ID. Web mengembalikan 201 setelah rekaman hasil selesai/unavailable tersimpan, atau 422 untuk input unsupported. Tidak ada retry otomatis atau pemrosesan ulang rekaman lama.

## 3. Tampilkan arti hasil dengan benar

- `risk_band` adalah LOW, MEDIUM atau HIGH berdasarkan threshold asli, bukan keputusan aman terkonfirmasi.
- Gunakan `human.title`, `human.explanation` dan `human.recommended_action` untuk tampilan biasa; `geek` menyimpan versi, scope dan threshold.
- LOW tetap berarti perlu verifikasi. HTTP 422/503 dan timeout tidak diubah menjadi LOW, skor nol atau SAFE.
- Respons tidak menggemakan URL. `model_score` merupakan skor kalibrasi riset, bukan probabilitas trafik Indonesia.
- Share Card dan snapshot komunitas mempertahankan status indikator riset/perlu verifikasi beserta versi model. Keterangan batas hasil tetap tampil di luar ringkasan yang dipotong. Snapshot komunitas tetap perlu consent dan moderasi; skor model bukan ground truth latihan.

Accuracy **93,23%** berasal dari holdout vendor 20.000 URL, dengan recall phishing **46,31%** dan FPR **0,944%**. Gold Indonesia belum tersedia dan model belum memenuhi gate produksi. Paket ini untuk riset nonkomersial/shadow. Integrasi fitur tersedia bagi akun web terverifikasi tanpa pembatasan admin, tetapi tidak mengubah `production_ready=false`; pengembangan dan validasi sebelum rilis tetap terpisah.

Kontrak field/status lengkap: [shadow-api-contract.md](shadow-api-contract.md). Hasil lengkap: [data-improvement-v6.json](../ml/reports/data-improvement-v6.json). Identitas paket: [v6-distribution.json](../ml/policies/v6-distribution.json).
