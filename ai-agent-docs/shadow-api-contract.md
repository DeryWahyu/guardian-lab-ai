# Kontrak API Internal Shadow URL/QR

> Versi: `shadow-v6-1`. Runtime: frozen Logistic Regression v6, kebijakan layanan `v6-user-warning-0.5-20261107`.
> Status: implementasi lokal riset; warning layanan 0,5 sesuai instruksi pengguna 7 November 2026, tanpa aktivasi publik atau perubahan model.

[Keputusan model utama sementara](./selected-model-v6.md) menetapkan v6 sebagai fokus saat ini. Runtime memakai artifact v6 asli, dengan warning layanan **`0.5`** dan high **`0.9884744926236343`** dari `decision_policy` dalam `shadow-serving-manifest.json`. Metadata training dan field `thresholds` historis manifest tetap warning `0.904713285827399`. [Perubahan kebijakan](v6-serving-threshold-0p5.md) mengikuti pilihan pengguna setelah diagnosis benchmark teramati; ini belum menjadi validasi independen.

## Menjalankan dan memeriksa

Dari root `guardian_lab_ai`, gunakan Python 3.12 dan dependency ML yang dipin. Dependency layanan ditambahkan sebagai extra terpisah:

```powershell
ml/.venv/Scripts/python.exe -m pip install -e "./ml[test,dev,serve]"
ml/.venv/Scripts/python.exe -m pytest ml/tests -q
ml/.venv/Scripts/python.exe -m uvicorn guardian_ml.shadow_service:create_app --factory --host 127.0.0.1 --port 8001 --no-access-log
```

Binding localhost dan access log dinonaktifkan untuk jalur pengujian internal ini. Jangan meneruskan URL pada query/path endpoint layanan. Mode selain `shadow` ditolak; environment flag tidak memberikan bukti bahwa release gate terpenuhi. Tidak ada proses server publik yang diluncurkan oleh pengerjaan ini; smoke test memakai ASGI TestClient dalam proses.

Artifact lokal diperlukan. Manifest `ml/policies/shadow-serving-manifest.json` mengikat checksum binary, metadata pembekuan, kode training, source runtime, feature schema, PSL offline dan hash manifest runtime historis yang tetap utuh. Perubahan runtime yang disengaja harus memperbarui manifest dan menjalankan tes parity; jangan menonaktifkan guard karena checksum berbeda. Joblib hanya berasal dari training lokal tepercaya.

## Endpoint

| Endpoint        | Method | Kegunaan                                                                         |
| --------------- | ------ | -------------------------------------------------------------------------------- |
| `/health`       | GET    | Ketersediaan model untuk shadow dan hasil release gate; `production_ready=false` |
| `/predict`      | POST   | Indikator URL-only untuk URL langsung atau URL yang sudah didekode dari QR       |
| `/metrics`      | GET    | Counts dan histogram latency agregat; tidak memuat target/IP/user ID             |
| `/openapi.json` | GET    | Schema request/response untuk pengembang internal                                |

Layanan tidak menyediakan lookup reputasi, pengambilan halaman, redirect, DNS, decode gambar QR, validasi QRIS, atau classifier APK. URL target diperlakukan sebagai teks, bukan tujuan koneksi jaringan.

### Request predict

```json
{
  "url": "https://example.org/login",
  "input_type": "URL"
}
```

`input_type` adalah `URL` atau `QR`; QR berarti caller sudah mendekode gambar menjadi URL. Schema strict dan menolak field tambahan. URL maksimal 16.384 karakter, body UTF-8 JSON maksimal 65.536 byte termasuk request chunked. Credential asli tidak diperlukan dan tidak boleh digunakan dalam pengujian.

### Makna respons

- `mode=shadow`, `decision=needs_review`, `needs_further_review=true`, `production_ready=false` pada semua respons analisis.
- `status=complete` hanya berarti classifier menyelesaikan perhitungan. `risk_band=LOW|MEDIUM|HIGH` memakai kebijakan layanan aktif: LOW jika skor <0,5; MEDIUM jika 0,5 <= skor <0,9884744926236343; HIGH mulai 0,9884744926236343. LOW bukan SAFE.
- `model_score` adalah keluaran kalibrasi pada campuran data riset. Ia tidak diklaim sebagai probability trafik Indonesia atau jaminan bahwa target aman/berbahaya.
- `human` berisi penjelasan Bahasa Manusia dan aksi perlu verifikasi. `geek` memuat scope, versi, hash artifact, schema fitur dan context flags. `thresholds` adalah ambang layanan aktif; `frozen_thresholds` adalah ambang training historis; `decision_policy_version` membedakan keduanya.
- Context flags untuk query/fragment yang dikeluarkan, placeholder redaksi, private hosting tenant, punycode, dan URL panjang mendeskripsikan kebutuhan konteks. Flag tidak mengubah skor atau menetapkan label phishing.
- Respons tidak menggemakan URL, host, path, hash target, query, fragment, credential, maupun body request. Metadata hash yang ditampilkan adalah hash artifact model, bukan hash input.

| HTTP | Status/makna                                                                         |
| ---- | ------------------------------------------------------------------------------------ |
| 200  | `complete`, indikator riset dan tetap perlu verifikasi                               |
| 400  | JSON tidak dapat dibaca, pesan tetap tanpa input                                     |
| 413  | Body melewati batas aktual, termasuk tanpa Content-Length                            |
| 415  | Content-Type bukan application/json                                                  |
| 422  | Schema invalid atau input URL unsupported; unsupported tidak memiliki skor/risk band |
| 503  | Model tidak tersedia/guard gagal; skor dan risk band tidak tersedia                  |

Kesalahan tidak menjadi skor nol atau LOW. Traceback/debug/body error framework tidak diekspos ke caller. Log akses Uvicorn harus tetap nonaktif pada perintah internal di atas.

## Monitoring dan ground truth

Monitoring in-memory menyimpan jumlah request per status/input type/risk band dan histogram durasi. Tidak ada event individu, URL/domain/hash target, IP, user ID, body, atau credential yang dipersistensikan. Metrics online precision/recall/FPR bernilai `null` sampai ada proses ground truth manusia yang benar-benar selesai; skor dan feedback otomatis tidak menjadi label.

Audit kualitas offline ada di [laporan audit v6](../ml/reports/model-hardening-audit.json). Audit manusia PhishVN adalah bukti penerbit, bukan anotasi baru oleh agent dan bukan dataset Indonesia.

[Validasi v6](../ml/reports/v6-only-validation.json) memeriksa artifact asli dan replay dua holdout v6. [Referensi sintetis](../ml/provenance/v6-runtime-reference.json) berasal dari notebook training asli sebelum cleanup; tes tidak memerlukan notebook atau model lama. Smoke test TestClient bukan benchmark latency deployment atau accuracy trafik.

## Batas integrasi aplikasi Guardian Lab

1. Caller frontend tetap memakai backend aplikasi; alamat model internal berasal dari konfigurasi server tepercaya dan tidak boleh berasal dari URL pengguna.
2. Pertahankan provenance URL/QR. QR non-URL harus dihentikan sebagai unsupported, dan QRIS merchant tidak diberi klaim autentik.
3. Sanitasi dan privacy policy berlaku sebelum pencatatan riwayat/forensic log atau pengiriman narasi ke LLM. Respons API ini tidak mengandung target yang perlu diteruskan ke LLM.
4. Peta `human`/`geek` ke dua mode antarmuka. `unavailable`/`unsupported`/timeout tetap perlu pemeriksaan; tidak menampilkan SAFE atau kepastian keamanan.
5. Proteksi sandbox hanya ditawarkan bila isolasi backend sudah terbukti, termasuk timeout 180 detik dan auto-destroy. UI simulasi bukan bukti isolasi. Layanan ini tidak memberikan URL sandbox atau menjalankan target.
6. Share Card harus mengikuti tingkat bukti: indikator/perlu verifikasi tidak diubah menjadi tuduhan phishing yang sudah terkonfirmasi.
7. Sebelum aktivasi publik, selesaikan release gate, autentikasi/quota gateway, privacy logging, dan pengujian integrasi nyata. Tidak ada rute/frontend aplikasi yang diaktifkan oleh tahap shadow ini.

Sinyal redirect/HTML memerlukan desain worker dan uji isolasi terpisah. Saat ini kolektor tersebut tidak diimplementasikan dan agent tidak mengunjungi target dataset. Panduan keamanan jaringan: [OWASP SSRF prevention](https://cheatsheetseries.owasp.org/cheatsheets/Server_Side_Request_Forgery_Prevention_Cheat_Sheet.html). Implementasi request/schema memakai [FastAPI](https://fastapi.tiangolo.com/tutorial/handling-errors/) dan [Pydantic](https://pydantic.dev/docs/validation/latest/concepts/models/).


Notebook utama mandiri: [guardian_lab_url_qr_v6.ipynb](../guardian_lab_url_qr_v6.ipynb). Loader memeriksa subset dependency inferensi lengkap yang versinya cocok dengan metadata training asli; tooling training/evaluasi yang tidak dipakai layanan tidak wajib dipasang. Binary, metadata training dan threshold historis tetap utuh; warning layanan aktif 0,5 dicatat terpisah.
