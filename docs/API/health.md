# Pemeriksaan Kesehatan Layanan (Health Check)

## 1. Informasi Umum

| Atribut | Keterangan |
| --- | --- |
| **Modul** | Health Check |
| **Endpoint** | `/health` dan `/api/v1/health` |
| **Rujukan PRD** | FR-01 (pengecualian Bearer Token), Bagian 7.6 (Operasional & Kualitas), Lampiran B |
| **Status implementasi** | ✅ Sudah diimplementasikan dan diverifikasi |
| **Kode sumber** | [routes/health.py](../../app/api/routes/health.py), [database.py](../../app/core/database.py), [schemas/common.py](../../app/schemas/common.py), [main.py](../../app/main.py) |

---

## 2. Penjelasan Fitur

Endpoint ini digunakan oleh *load balancer*, orkestrator container (Docker/Kubernetes), maupun operator untuk memeriksa apakah proses FastAPI hidup dan apakah *connection pool* PostgreSQL dapat mengeksekusi query (`SELECT 1 AS ok`).

Router `health.router` didaftarkan pada dua path sekaligus di [`app/main.py`](../../app/main.py):
1. `GET /health` (sesuai PRD 7.6).
2. `GET /api/v1/health` (di bawah base path `/api/v1` sesuai Lampiran B PRD).

Keduanya memanggil fungsi handler yang sama dan mengembalikan payload yang identik.

---

## 3. Autentikasi dan Otorisasi

* **Autentikasi:** Tidak diperlukan (sesuai PRD FR-01: *"Seluruh endpoint selain `login`, `refresh`, dan `health` mewajibkan Bearer Token"*).
* **Permission:** Tidak diperlukan.

---

## 4. Ringkasan Endpoint

| Method | Endpoint | Fungsi | Auth | Permission |
| --- | --- | --- | --- | --- |
| GET | `/health` | Memeriksa status layanan API dan koneksi database | Tidak | – |
| GET | `/api/v1/health` | Alias pemeriksaan kesehatan di bawah prefix `/api/v1` | Tidak | – |

---

## 5. Detail Setiap Endpoint

### GET `/health` & GET `/api/v1/health`

* **HTTP Method & URL:** `GET /health` atau `GET /api/v1/health`
* **Autentikasi & Permission:** Publik (tanpa token)
* **Path / Query Parameter:** Tidak ada
* **Request Body:** Tidak ada

**Contoh Response Berhasil (`200 OK` — `HealthResponse`)**

```json
{
  "status": "ok",
  "service": "WMS REST API",
  "version": "2.0.0",
  "database": "connected"
}
```

| Field | Tipe | Nilai yang Mungkin | Keterangan |
| --- | --- | --- | --- |
| `status` | string | `"ok"` \| `"degraded"` | `"ok"` bila query `SELECT 1 AS ok` mengembalikan `1`; `"degraded"` bila tidak. |
| `service` | string | `"WMS REST API"` | Nilai `settings.app_name`. |
| `version` | string | `"2.0.0"` | Nilai `settings.app_version`. |
| `database` | string | `"connected"` \| `"disconnected"` | Status konektivitas ke PostgreSQL. |

**Kemungkinan Kondisi Degraded (`200 OK` — `HealthResponse`)**

Apabila *connection pool* belum diinisialisasi atau gagal memperoleh koneksi ke PostgreSQL (misalnya layanan database mati atau melempar `OperationalError` / `PoolTimeout`), fungsi `check_pool_health()` menangkap exception tersebut dan mengembalikan:

```json
{
  "status": "degraded",
  "service": "WMS REST API",
  "version": "2.0.0",
  "database": "disconnected"
}
```

---

## 6. Relasi dan Ketergantungan

* Menggunakan fungsi `check_pool_health()` dari [`app/core/database.py`](../../app/core/database.py) yang mengambil koneksi dari `psycopg_pool.ConnectionPool`, menjalankan `check_db_health(conn)` (`SELECT 1 AS ok`), serta menangani kegagalan koneksi secara aman.
* Setiap respons juga menerima header `X-Request-ID` dari middleware di `app/main.py`.

---

## 7. Contoh Penggunaan (cURL)

```bash
curl -i http://localhost:8000/health
curl -i http://localhost:8000/api/v1/health
```

---

## 8. Catatan dan Status Verifikasi

| # | Status | Catatan |
| --- | --- | --- |
| 1 | ✅ Terverifikasi | Kedua path `/health` dan `/api/v1/health` telah diuji terhadap PostgreSQL aktif dan mengembalikan `200 OK` beserta header `X-Request-ID`. |
| 2 | ✅ Terverifikasi | Apabila database tidak dapat dihubungi atau *pool* melempar `PsycopgError` / `PoolTimeout` / `OSError`, `check_pool_health()` menangkap exception tersebut dan mengembalikan `status: "degraded", database: "disconnected"` tanpa melempar HTTP `500 INTERNAL_ERROR`. |

