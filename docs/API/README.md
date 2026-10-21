# Dokumentasi API — Warehouse Management System (WMS)

Dokumentasi teknis REST API untuk aplikasi **Warehouse Management System (WMS)** berbasis **Python (FastAPI)** dan **PostgreSQL** (`psycopg` 3 tanpa ORM). Seluruh isi dokumentasi ini disusun berdasarkan **implementasi kode aktual**, **skema migrasi SQL (`001`–`008`)**, **pengujian otomatis (`pytest`)**, serta dokumen acuan [PRODUCT_REQUIREMENTS_DOCUMENT.MD](../core/PRODUCT_REQUIREMENTS_DOCUMENT.MD).

---

## 1. Gambaran Umum & Konvensi Global API

| Konvensi | Ketentuan Aktual di Kode |
| --- | --- |
| **Base URL** | `/api/v1` (seluruh modul bisnis; `/health` juga tersedia di root `/`) |
| **Format Data** | `application/json` |
| **Autentikasi** | Header `Authorization: Bearer <access_token>` (JWT HS256, umur bawaan 15 menit) |
| **Header Pelacakan** | `X-Request-ID` — dapat dikirim oleh klien; bila kosong, server otomatis membuat UUID v4 dan mengembalikannya di header response |
| **Format Waktu** | ISO 8601 dengan informasi zona waktu (`TIMESTAMPTZ`) |
| **Format Kuantitas** | `DecimalStr` — diserialisasi sebagai string desimal 4 angka di belakang koma (contoh: `"12.5000"`, lihat [`app/schemas/common.py`](../../app/schemas/common.py)) |
| **Format Pagination** | Query `limit` (bawaan `50`, rentang `1..200`) & `offset` (`>= 0`); response berbentuk `{ "items": [...], "total": n, "limit": n, "offset": n }` |

### Format Standar Response Error

Seluruh error bisnis (`DomainError`), error validasi request (`RequestValidationError`), dan error tak terduga dikembalikan dalam struktur JSON yang seragam oleh exception handler di [`app/main.py`](../../app/main.py):

```json
{
  "error": {
    "code": "PERMISSION_DENIED",
    "message": "Anda tidak memiliki izin 'user:manage' untuk melakukan aksi ini.",
    "details": {
      "required_permission": "user:manage"
    }
  }
}
```

### Katalog Kode Error yang Terdaftar (`app/core/exceptions.py`)

| Kode Error | HTTP Status | Kelas Exception | Status Pemakaian di Endpoint Saat Ini |
| --- | :---: | --- | --- |
| `AUTH_INVALID_CREDENTIALS` | 401 | `AuthInvalidCredentials` | Aktif (`/auth/login`, `/auth/change-password`) |
| `AUTH_TOKEN_INVALID` | 401 | `AuthTokenInvalid` | Aktif (`get_current_user`, `/auth/refresh`, `/auth/logout`) |
| `AUTH_TOO_MANY_ATTEMPTS` | 429 | `AuthTooManyAttempts` | Aktif (`/auth/login` saat akun terkunci) |
| `PERMISSION_DENIED` | 403 | `PermissionDenied` | Aktif (`require_permission`) |
| `WAREHOUSE_NOT_ASSIGNED` | 403 | `WarehouseNotAssigned` | Didefinisikan di `access_service.ensure_warehouse_access` (menunggu modul operasional M3–M7) |
| `NOT_FOUND` | 404 | `NotFoundError` | Aktif (`/users/*`) |
| `VALIDATION_ERROR` | 422 | `ValidationDomainError` & `RequestValidationError` | Aktif (validasi payload, pagination, sorting, kode permission) |
| `INVALID_LOCATION` | 422 | `InvalidLocationError` | Sudah didefinisikan (menunggu modul M3–M7) |
| `INACTIVE_REFERENCE` | 422 | `InactiveReferenceError` | Aktif (`/users` & `/users/{id}/warehouses` saat gudang nonaktif) |
| `DUPLICATE` | 409 | `DuplicateError` | Aktif (`/users` saat `username`/`email` duplikat) |
| `INVALID_STATE_TRANSITION` | 409 | `InvalidStateTransition` | Sudah didefinisikan (menunggu modul M5–M7) |
| `INSUFFICIENT_STOCK` | 409 | `InsufficientStock` | Sudah didefinisikan (menunggu modul M4–M6) |
| `OVER_RECEIPT` | 409 | `OverReceipt` | Sudah didefinisikan (menunggu modul M5) |
| `TRANSFER_QTY_EXCEEDS_SHIPPED` | 409 | `TransferQtyExceedsShipped` | Sudah didefinisikan (menunggu modul M6) |
| `LOCATION_FROZEN` | 409 | `LocationFrozen` | Sudah didefinisikan (menunggu modul M4–M7) |
| `ENTITY_IN_USE` | 409 | `EntityInUse` | Sudah didefinisikan (menunggu modul M3) |
| `INTERNAL_ERROR` | 500 | Handler `Exception` umum | Aktif (`app/main.py`) |

---

## 2. Daftar Modul & Status Implementasi

Sesuai pentahapan di [`docs/core/FOLDER_STRUCTURE.MD`](../core/FOLDER_STRUCTURE.MD), berikut status setiap modul API di kode sumber saat ini:

| Modul / Domain Bisnis | Dokumen API | Status Implementasi | Ringkasan Fungsi |
| --- | --- | --- | --- |
| **Health Check** | [health.md](health.md) | ✅ **Aktif** (2 endpoint) | Pemeriksaan status layanan API dan konektivitas pool PostgreSQL. |
| **Autentikasi & Otorisasi** | [authentication.md](authentication.md) | ✅ **Aktif** (5 endpoint) | Login JWT, rotasi & deteksi penggunaan ulang *Refresh Token*, penguncian akun, logout, profil `/me`, dan ganti kata sandi. |
| **Pengguna, RBAC & Penugasan Gudang** | [users.md](users.md) | ✅ **Aktif** (9 endpoint) | CRUD pengguna, penonaktifan akun, daftar & pengaturan *role/permission*, serta penugasan gudang (*Warehouse Scoping*). |
| **Audit Log** | [audit-logs.md](audit-logs.md) | ✅ **Aktif** (1 endpoint) | Pembacaan jejak audit *append-only* dengan filter pengguna, aksi, entitas, dan rentang tanggal. |
| **Master Data** (`master.py`) | – | ⏳ **Belum Diimplementasikan** (Tahap M3) | Berkas `app/api/routes/master.py` masih kosong (0 byte). Mencakup Kategori, UoM, Barang, dan Pemasok (FR-02). |
| **Gudang & Lokasi** (`warehouses.py`) | – | ⏳ **Belum Diimplementasikan** (Tahap M3) | Berkas `app/api/routes/warehouses.py` masih kosong (0 byte). Mencakup Gudang & Lokasi Penyimpanan (FR-02). |
| **Stok & Buku Besar** (`stock.py`) | – | ⏳ **Belum Diimplementasikan** (Tahap M4) | Berkas `app/api/routes/stock.py` masih kosong (0 byte). Mencakup saldo stok, *in-transit*, dan *Stock Movement Ledger* (FR-03, FR-08). |
| **Purchase Order** (`purchase_orders.py`) | – | ⏳ **Belum Diimplementasikan** (Tahap M5) | Berkas `app/api/routes/purchase_orders.py` masih kosong (0 byte). Mencakup siklus PO (FR-04). |
| **Goods Receipt** (`goods_receipts.py`) | – | ⏳ **Belum Diimplementasikan** (Tahap M5) | Berkas `app/api/routes/goods_receipts.py` masih kosong (0 byte). Mencakup penerimaan barang dari PO (FR-05). |
| **Transfer Stok** (`stock_transfers.py`) | – | ⏳ **Belum Diimplementasikan** (Tahap M6) | Berkas `app/api/routes/stock_transfers.py` masih kosong (0 byte). Mencakup transfer dua tahap antar-gudang/lokasi (FR-06). |
| **Stock Opname** (`stock_opnames.py`) | – | ⏳ **Belum Diimplementasikan** (Tahap M7) | Berkas `app/api/routes/stock_opnames.py` masih kosong (0 byte). Mencakup sesi hitung fisik, pembekuan lokasi, dan penyesuaian stok (FR-07). |

> **Catatan:** Tabel database untuk seluruh modul M3–M7 sudah dibuat pada migrasi `002` s.d. `006`, namun lapisan *repository*, *service*, *schema*, dan *route* untuk modul-modul tersebut belum diimplementasikan.

---

## 3. Ringkasan Seluruh Endpoint yang Tersedia Saat Ini (17 Endpoint)

| # | Method | Endpoint | Fungsi | Auth | Permission | Dokumen |
| :-: | --- | --- | --- | --- | --- | --- |
| 1 | GET | `/health` | Pemeriksaan kesehatan layanan & koneksi DB | Tidak | – | [health.md](health.md) |
| 2 | GET | `/api/v1/health` | Pemeriksaan kesehatan layanan (prefix v1) | Tidak | – | [health.md](health.md) |
| 3 | POST | `/api/v1/auth/login` | Login pengguna & terbitkan pasangan token | Tidak | – | [authentication.md](authentication.md#post-apiv1authlogin--login) |
| 4 | POST | `/api/v1/auth/refresh` | Rotasi *Refresh Token* & terbitkan token baru | Tidak (token di body) | – | [authentication.md](authentication.md#post-apiv1authrefresh--rotasi-refresh-token) |
| 5 | POST | `/api/v1/auth/logout` | Cabut *Refresh Token* sesi saat ini | Bearer | – | [authentication.md](authentication.md#post-apiv1authlogout--logout) |
| 6 | GET | `/api/v1/auth/me` | Ambil profil, permission, & gudang pengguna aktif | Bearer | – | [authentication.md](authentication.md#get-apiv1authme--profil-pengguna-aktif) |
| 7 | POST | `/api/v1/auth/change-password` | Ganti kata sandi sendiri & cabut seluruh sesi | Bearer | – | [authentication.md](authentication.md#post-apiv1authchange-password--ganti-kata-sandi-sendiri) |
| 8 | GET | `/api/v1/users` | Daftar pengguna (paginasi, filter, pencarian) | Bearer | `user:manage` | [users.md](users.md#get-apiv1users--daftar-pengguna) |
| 9 | POST | `/api/v1/users` | Buat pengguna baru (+ penugasan gudang awal) | Bearer | `user:manage` | [users.md](users.md#post-apiv1users--buat-pengguna-baru) |
| 10 | GET | `/api/v1/users/roles` | Daftar seluruh peran beserta kode permission | Bearer | `user:manage` | [users.md](users.md#get-apiv1usersroles--daftar-peran) |
| 11 | GET | `/api/v1/users/permissions` | Daftar seluruh 24 kode permission sistem | Bearer | `user:manage` | [users.md](users.md#get-apiv1userspermissions--daftar-kode-permission) |
| 12 | PUT | `/api/v1/users/roles/{role_id}/permissions` | Atur ulang daftar permission untuk suatu peran | Bearer | `user:manage` | [users.md](users.md#put-apiv1usersrolesrole_idpermissions--atur-permission-untuk-peran) |
| 13 | GET | `/api/v1/users/{user_id}` | Detail pengguna berdasarkan ID | Bearer | `user:manage` | [users.md](users.md#get-apiv1usersuser_id--detail-pengguna) |
| 14 | PATCH | `/api/v1/users/{user_id}` | Perbarui data / nonaktifkan pengguna | Bearer | `user:manage` | [users.md](users.md#patch-apiv1usersuser_id--perbarui--nonaktifkan-pengguna) |
| 15 | GET | `/api/v1/users/{user_id}/warehouses` | Daftar gudang yang ditugaskan ke pengguna | Bearer | `user:manage` | [users.md](users.md#get-apiv1usersuser_idwarehouses--daftar-gudang-yang-ditugaskan-ke-pengguna) |
| 16 | PUT | `/api/v1/users/{user_id}/warehouses` | Ganti daftar gudang yang ditugaskan ke pengguna | Bearer | `user:manage` | [users.md](users.md#put-apiv1usersuser_idwarehouses--atur-penugasan-gudang) |
| 17 | GET | `/api/v1/audit-logs` | Daftar jejak audit (paginasi & filter) | Bearer | `audit:read` | [audit-logs.md](audit-logs.md#get-apiv1audit-logs--daftar-audit-log) |

---

## 4. Ringkasan Status Verifikasi & Perbaikan Temuan

Seluruh temuan hasil tinjauan silang antara kode aktual, skema database, pengujian, dan PRD telah diperbaiki dan diverifikasi dengan pengujian otomatis (`pytest`):

1. **Kredensial & Rahasia Wajib dari Lingkungan (`app/core/config.py`)** — ✅ **Terverifikasi** ([authentication.md](authentication.md#8-catatan-dan-status-verifikasi)):
   * Atribut `database_url` dan `jwt_secret` (minimal 32 karakter) pada `Settings` kini diwajibkan tanpa nilai *fallback* statis di kode sumber, selaras dengan PRD 7.2 dan AGENTS.md §6.
2. **Pencegahan Penguncian Diri (*Self-Lockout*) Super Admin & Validasi Email** — ✅ **Terverifikasi** ([users.md](users.md#8-catatan-dan-status-verifikasi)):
   * `PATCH /api/v1/users/{id}` menolak penonaktifan akun sendiri (`is_active: false`) dan perubahan peran sendiri (`role_id`) dengan `422 VALIDATION_ERROR`.
   * `PUT /api/v1/users/roles/{role_id}/permissions` menolak pencabutan izin `user:manage` dari peran `Super Admin` dengan `422 VALIDATION_ERROR`.
   * Pembuatan dan pembaruan pengguna memvalidasi format alamat email (`EMAIL_REGEX`).
3. **Validasi Proxy Tepercaya pada Header `X-Forwarded-For`** — ✅ **Terverifikasi** ([authentication.md](authentication.md#8-catatan-dan-status-verifikasi)):
   * `get_client_ip()` hanya mempercayai header `X-Forwarded-For` apabila alamat IP koneksi langsung (`request.client.host`) terdaftar di `TRUSTED_PROXY_IPS`.
4. **Ketahanan `GET /health` Saat Database Tidak Dapat Dihubungi** — ✅ **Terverifikasi** ([health.md](health.md#8-catatan-dan-status-verifikasi)):
   * `check_pool_health()` menangkap kegagalan koneksi pool (`PsycopgError`, `PoolTimeout`, `OSError`) sehingga endpoint tetap mengembalikan respons terstruktur `status: "degraded", database: "disconnected"` tanpa melempar `500 INTERNAL_ERROR`.
5. **Pengujian Otomatis Imutabilitas (`tests/test_immutability.py` — AC-08)** — ✅ **Terverifikasi** ([audit-logs.md](audit-logs.md#8-catatan-dan-status-verifikasi)):
   * Skenario pengujian `test_ac08_immutability_stock_movements_and_audit_logs` telah diimplementasikan dan lulus terhadap role aplikasi (`wms_app`) maupun pemilik tabel (*table owner*).


