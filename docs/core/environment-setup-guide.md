---
title: Panduan Setup Environment (Lokal, Server Development, Docker)
description: Cara menjalankan dan menguji frontend serta backend WMS pada skenario lokal dan server development hanya dengan mengganti konfigurasi environment
document_type: guide
status: draft
version: 1.0
last_updated: 2026-11-13
source_of_truth: true
---

# Panduan Setup Environment

Panduan ini adalah pemilik tunggal untuk cara menyambungkan frontend (`warehouse_app/`)
dan backend (`api_warehouse_app/`) pada berbagai lingkungan. Pergantian lingkungan
dilakukan **hanya lewat konfigurasi** (berkas environment atau variabel OS), tanpa
mengubah source code. Panduan deployment production ada di
[DEPLOYMENT_GUIDE_CICD.md](DEPLOYMENT_GUIDE_CICD.md); pengamanan server dan aplikasi di
[security-server-and-app.md](security-server-and-app.md).

Label status mengikuti [Documentation Standards](../STANDARDS/DOCUMENTATION_STANDARDS.md):
**Aktual** = sudah dijalankan dan diverifikasi pada 2026-11-13 di PC pengembangan;
**Belum Terverifikasi** = bergantung pada server yang belum tersedia untuk diuji.

## 1. Ringkasan skenario

| # | Skenario | Frontend | Backend | Database | Status |
| --- | --- | --- | --- | --- | --- |
| 1 | Pengembangan penuh lokal | `npm run dev` | `uvicorn` lokal | PostgreSQL lokal | Aktual |
| 2 | Frontend lokal, backend server development | `npm run dev:server` | server development | server development | Belum Terverifikasi |
| 3 | Backend lokal, database server development | `npm run dev` | `uvicorn` lokal dengan `ENV_FILE=.env.development` | server development lewat SSH tunnel | Belum Terverifikasi |
| 4 | Semua di Docker Compose lokal | `npm run dev` (atau compose FE) | container `api` | container `postgres` | Aktual (validasi konfigurasi compose) |
| 5 | Akses backend production dari PC | `npm run dev:server` + izin eksplisit | production | production | Diblokir secara default (lihat §8) |

> [!IMPORTANT]
> Sebelum 2026-11-13, `npm run dev` secara default memproksikan request ke backend
> **production**. Sekarang default adalah backend **lokal** (`http://localhost:8000`).
> Jika backend lokal belum berjalan, request API dari `npm run dev` akan gagal; ini
> disengaja agar data production tidak termodifikasi tanpa sengaja.

## 2. Prasyarat

- Node.js dan npm (untuk `warehouse_app/`), Python dan virtualenv `venv` (untuk `api_warehouse_app/`).
- PostgreSQL lokal dengan role `wms_owner`, `wms_app`, dan database `wms` / `wms_test`
  (langkah pembuatan database ada di `README.md` repositori backend).
- Simpan berkas `.env*` sebagai **UTF-8** (tanpa BOM bila memungkinkan). Backend toleran
  BOM, tetapi Vite tidak: BOM merusak baris pertama berkas `.env` frontend sehingga
  variabel pertama diabaikan tanpa pesan error. Gunakan editor kode (bukan Notepad lama)
  atau tulis berkas dengan `[IO.File]::WriteAllText(..., (New-Object Text.UTF8Encoding $false))`.

## 3. Berkas environment

### 3.1 Frontend (`warehouse_app/`, dimuat oleh Vite)

Prioritas Vite dari tertinggi ke terendah:
`variabel OS` > `.env.[mode].local` > `.env.[mode]` > `.env.local` > `.env`.

| Berkas | Di-commit | Fungsi |
| --- | --- | --- |
| `.env.example` | Ya | Template dan penjelasan seluruh variabel |
| `.env.development` | Ya | Default aman untuk `npm run dev`: proxy ke backend lokal. Tanpa kredensial |
| `.env.dev-server.example` | Ya | Template untuk `npm run dev:server` |
| `.env.dev-server` | Tidak | Salinan template berisi URL backend server development |
| `.env.development.local`, `.env.dev-server.local` | Tidak | Override pribadi developer (pola `*.local`) |
| `.env`, `.env.local` | Tidak | Hanya berlaku bila tidak ditimpa berkas mode di atas |

> [!WARNING]
> `.env.development` **menimpa** `.env` dan `.env.local` saat `npm run dev`. Untuk
> mengubah URL secara pribadi, gunakan `.env.development.local`, bukan `.env.local`.

| Variabel | Dibaca oleh | Keterangan |
| --- | --- | --- |
| `VITE_API_BASE_URL` | Browser (`src/lib/api-client.ts`) | `/api/v1` = lewat proxy Vite (disarankan). URL absolut = langsung ke backend; `/api/v1` ditambahkan otomatis |
| `VITE_DEV_PROXY_TARGET` | `vite.config.ts` (hanya dev server) | Tujuan proxy `/api`. Default `http://localhost:8000` |
| `VITE_ALLOW_PRODUCTION_PROXY` | `vite.config.ts` | `true` mengizinkan target berupa host production (lihat §8) |

Semua variabel berawalan `VITE_` masuk ke bundle browser. Jangan menaruh secret di sana.

### 3.2 Backend (`api_warehouse_app/`, dimuat oleh `app/core/env_files.py`)

Aturan pemilihan berkas (dipakai bersama oleh aplikasi, `python -m db.migrate`, `pytest`,
dan seluruh skrip di `scripts/`):

1. Jika variabel OS `ENV_FILE` diisi, **hanya** berkas itu yang dipakai. Path relatif
   dihitung dari root repositori backend. Bila berkas tidak ada, proses berhenti dengan
   pesan jelas (tidak diam-diam memakai konfigurasi lain).
2. Jika tidak, `.env` dimuat lalu `.env.local` (menimpa `.env` bila ada).
3. Variabel OS yang sudah diset selalu menang atas isi berkas.

| Berkas | Di-commit | Fungsi |
| --- | --- | --- |
| `.env.example` | Ya | Template backend lokal + PostgreSQL lokal. Salin menjadi `.env` |
| `.env.development.example` | Ya | Template backend lokal ke database server development. Salin menjadi `.env.development` |
| `.env.docker.example` | Ya | Template Docker Compose. Salin menjadi `.env.docker` |
| `.env`, `.env.local`, `.env.development`, `.env.docker` | Tidak | Konfigurasi aktif (dilindungi `.gitignore`) |

Variabel utama (daftar lengkap beserta komentar ada di `.env.example`):

| Variabel | Keterangan |
| --- | --- |
| `APP_ENV` | `local`, `development`, `staging`, atau `production`. Nilai lain ditolak saat startup. Dipakai sebagai label lingkungan (juga untuk notifikasi pada Tahap 13) |
| `DATABASE_URL` | Koneksi runtime aplikasi (role `wms_app`) |
| `MIGRATION_DATABASE_URL` | Koneksi migrasi (role `wms_owner`) |
| `TEST_DATABASE_URL` | Pytest hanya berjalan jika nama databasenya `wms_test` |
| `JWT_SECRET` | Minimal 32 karakter; buat dengan `python -c "import secrets; print(secrets.token_hex(32))"` |
| `FRONTEND_ORIGINS` | Daftar origin CORS (JSON array) |
| `COOKIE_SECURE`, `COOKIE_SAMESITE` | Lokal: `False` / `lax`. Production lintas domain: `True` / `none` |

**Guard production:** jika `APP_ENV=production`, aplikasi menolak start bila
`COOKIE_SECURE=False` atau `JWT_SECRET` masih berisi placeholder dari berkas contoh.

Karakter khusus pada password di dalam URL database harus di-URL-encode
(`@` menjadi `%40`, `#` menjadi `%23`, `!` menjadi `%21`).

## 4. Skenario 1: pengembangan penuh lokal

```powershell
# Backend
cd api_warehouse_app
Copy-Item .env.example .env        # isi password database dan JWT_SECRET
.\venv\Scripts\python.exe -m db.migrate
.\venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8000

# Frontend (terminal lain)
cd warehouse_app
npm install
npm run dev                         # memakai .env.development -> proxy ke http://localhost:8000
```

Verifikasi (hasil yang diharapkan: `database: connected`):

```powershell
Invoke-WebRequest http://localhost:5173/api/v1/health -UseBasicParsing | Select-Object -ExpandProperty Content
```

Log Vite menampilkan baris `[wms] mode "development": request /api diteruskan ke http://localhost:8000`.
Browser mengakses `/api/v1` pada origin Vite sehingga tidak ada masalah CORS maupun
pemblokiran cookie lintas-origin.

## 5. Skenario 2: frontend lokal, backend server development

Prasyarat: tim memiliki backend server development yang terpisah dari production
(database dan secret berbeda).

```powershell
cd warehouse_app
Copy-Item .env.dev-server.example .env.dev-server
# Ubah VITE_DEV_PROXY_TARGET menjadi URL backend server development
npm run dev:server
```

Request tetap lewat proxy Vite, jadi backend server development tidak perlu mendaftarkan
origin PC Anda di `FRONTEND_ORIGINS`. Cookie refresh dari server HTTPS memakai atribut
`Secure`; Chrome dan Firefox menerimanya pada `http://localhost`, Safari tidak, sehingga
sesi login tidak bertahan setelah reload di Safari (**Belum Terverifikasi** terhadap server
development sungguhan).

## 6. Skenario 3: backend lokal, database server development

Port PostgreSQL di server hanya terbuka pada `127.0.0.1` (lihat
[security-server-and-app.md](security-server-and-app.md)), jadi gunakan SSH tunnel:

```powershell
# Terminal 1: biarkan terbuka
ssh -N -L 15432:127.0.0.1:5432 <user>@<host-server-development>

# Terminal 2
cd api_warehouse_app
Copy-Item .env.development.example .env.development   # isi password dan JWT_SECRET
$env:ENV_FILE = ".env.development"
.\venv\Scripts\python.exe -m db.migrate
.\venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8000
```

`ENV_FILE` berlaku untuk terminal tersebut saja. Hapus dengan `Remove-Item Env:\ENV_FILE`
untuk kembali ke `.env`. Jangan pernah mengarahkan berkas ini ke database production;
nama database development sengaja berbeda (`wms_development`).

## 7. Skenario 4: Docker Compose lokal

```powershell
cd api_warehouse_app
Copy-Item .env.docker.example .env.docker   # isi SEMUA variabel; password pada URL harus sama dengan POSTGRES_PASSWORD
docker compose up --build
```

Perilaku yang perlu diketahui:

- `.env.docker` adalah satu-satunya sumber konfigurasi container `postgres` dan `api`.
  Compose menolak berjalan bila berkas tidak ada.
- Dalam container, host database adalah nama service `postgres`, bukan `localhost`.
- Port database hanya dipublikasikan ke `127.0.0.1`.
- File `docker-compose.yml` ini khusus pengembangan (volume kode dan `--reload`). Jangan
  dipakai di server; production memakai `docker-compose.prod.yml` dari
  [DEPLOYMENT_GUIDE_CICD.md](DEPLOYMENT_GUIDE_CICD.md).

## 8. Skenario 5: akses backend production

Default diblokir. Jika `VITE_DEV_PROXY_TARGET` berisi host production, `npm run dev:server`
berhenti dengan pesan error. Aktifkan hanya untuk kebutuhan khusus yang telah diizinkan:

```ini
# warehouse_app/.env.dev-server.local  (tidak di-commit)
VITE_DEV_PROXY_TARGET=https://<host-backend-production>
VITE_ALLOW_PRODUCTION_PROXY=true
```

Gunakan akun dengan hak akses terendah yang cukup (idealnya baca saja) dan jangan
menjalankan operasi tulis dari lingkungan lokal.

## 9. Pengujian per skenario

| Skenario | Perintah | Catatan |
| --- | --- | --- |
| Backend (semua skenario) | `.\venv\Scripts\python.exe -m pytest` | Selalu ke database `wms_test`; guard di `tests/conftest.py` menolak nama lain |
| Frontend | `npm run test` lalu `npm run build` | Tidak membutuhkan backend |
| Konfigurasi environment | `pytest tests/test_config_environment.py` | Pemilihan `ENV_FILE`, BOM, guard production |
| Koneksi frontend ke backend | `Invoke-WebRequest http://localhost:5173/api/v1/health` | Harus mengembalikan `database: connected` |
| Kebersihan repositori dari secret | `git status` dan `git check-ignore -v .env .env.development` | Semua berkas `.env*` aktif harus muncul sebagai ignored |

## 10. Mengganti environment (ringkasan)

| Ingin | Lakukan | Mengubah source? |
| --- | --- | --- |
| Frontend ke backend lokal | `npm run dev` | Tidak |
| Frontend ke server development | `npm run dev:server` dengan `.env.dev-server` | Tidak |
| Pindah target tanpa menyentuh berkas | `$env:VITE_DEV_PROXY_TARGET="http://localhost:9000"; npm run dev` | Tidak |
| Backend ke database lain | `$env:ENV_FILE=".env.development"` atau edit `.env` | Tidak |
| Kembali ke default | `Remove-Item Env:\ENV_FILE` | Tidak |

## 11. Troubleshooting

| Gejala | Penyebab | Solusi |
| --- | --- | --- |
| `ENV_FILE menunjuk ke berkas yang tidak ditemukan` | Nama berkas salah atau belum disalin dari template | Periksa nama dan lokasi (relatif ke root backend) |
| `Konfigurasi production tidak aman` saat start | `APP_ENV=production` dengan `COOKIE_SECURE=False` atau `JWT_SECRET` placeholder | Perbaiki nilai di `.env.production` server |
| Frontend tetap memanggil target lama | Variabel pertama di berkas `.env` ber-BOM, atau berkas yang salah menimpa | Simpan tanpa BOM; ingat `.env.development` menimpa `.env` |
| `ECONNREFUSED` / 500 pada `/api/...` di `npm run dev` | Backend lokal belum berjalan | Jalankan backend (skenario 1) |
| Dev server berhenti dengan pesan "backend PRODUCTION" | Target menunjuk host production | Gunakan target lain, atau izin eksplisit pada §8 |
| Sesi hilang setelah reload | Cookie `Secure` pada HTTP di browser tertentu (Safari), atau `withCredentials` tidak aktif | Gunakan Chrome/Firefox; pastikan lewat proxy Vite |
| Container `api` tidak bisa terhubung ke database | Host pada URL masih `localhost` | Gunakan host `postgres` pada `.env.docker` |
| CORS error saat `VITE_API_BASE_URL` berupa URL absolut | Origin tidak ada di `FRONTEND_ORIGINS` | Tambahkan origin, atau gunakan `/api/v1` lewat proxy |

## 12. Keamanan

- Jangan commit `.env`, `.env.*` aktif, password, token, atau API key. Pola `.gitignore`
  kedua repositori sudah menutup berkas tersebut; hanya berkas `*.example` dan
  `.env.development` frontend (tanpa kredensial) yang boleh di-commit.
- Template hanya boleh berisi placeholder. Jangan menulis nilai asli di dokumen mana pun.
- Gunakan `JWT_SECRET` dan password database yang **berbeda** untuk setiap lingkungan.
