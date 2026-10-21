# Manajemen Gudang & Lokasi Penyimpanan

## 1. Informasi Umum

| Atribut | Keterangan |
| --- | --- |
| **Modul** | Manajemen Gudang (*Warehouse*) dan Lokasi Penyimpanan (*Storage Location / Bin / Rack*) |
| **Base path** | `/api/v1/warehouses`, `/api/v1/locations` |
| **Rujukan PRD** | FR-02, FR-09, FR-11, Bagian 3.1 (Matriks Permission), 3.2 (*Warehouse Scoping*), 6.1 (Stok Negatif), 6.2 (Kepemilikan Lokasi), 6.8 (Penonaktifan Master Data), AC-05, AC-12, Lampiran A & B |
| **Status implementasi** | ✅ Sudah diimplementasikan dan diuji (`tests/test_rbac_scoping.py`) |
| **Kode sumber** | [routes/warehouses.py](../../app/api/routes/warehouses.py), [warehouse_service.py](../../app/services/warehouse_service.py), [access_service.py](../../app/services/access_service.py), [warehouse_repo.py](../../app/repositories/warehouse_repo.py), [schemas/warehouse.py](../../app/schemas/warehouse.py) |
| **Tabel terkait** | `warehouses`, `storage_locations`, `user_warehouses`, `inventory_balances`, `purchase_orders`, `goods_receipts`, `gr_lines`, `stock_transfers`, `stock_opnames`, `stock_opname_lines`, `audit_logs` |
| **Modul terkait** | [Autentikasi & Otorisasi](authentication.md), [Pengguna & RBAC](users.md), [Master Data](master-data.md), [Audit Log](audit-logs.md) |

---

## 2. Penjelasan Fitur

### 2.1 Tujuan

Modul ini mengelola struktur fisik penyimpanan barang dalam dua tingkatan:

1. **Gudang (`warehouses`):** Unit fasilitas gudang dengan kode unik, alamat, status aktif, serta kebijakan per-gudang apakah saldo stok negatif diizinkan (`allow_negative_stock`, bawaan `false`).
2. **Lokasi Penyimpanan (`storage_locations`):** Sub-unit penyimpanan (rak/bin/zona) yang berada di dalam satu gudang tertentu (`warehouse_id`), dengan kode lokasi yang unik per gudang (`UNIQUE (warehouse_id, code)`).

### 2.2 Alur Bisnis & Aturan Integritas Utama

* **Kebijakan Stok Negatif per Gudang (`allow_negative_stock` — FR-02 & PRD 6.1):**
  * Secara bawaan bernilai `false`. Hanya pengguna dengan izin `warehouse:manage` (*Super Admin*) yang dapat membuat gudang atau mengubah `allow_negative_stock`.
  * Setiap perubahan pada gudang (termasuk perubahan `allow_negative_stock`) wajib dicatat di `audit_logs` beserta `old_values` dan `new_values`.
* **Penegakan *Warehouse Scoping* pada Lokasi Penyimpanan (`403 WAREHOUSE_NOT_ASSIGNED` — PRD 3.1, 3.2 & AC-12):**
  * Aksi pengelolaan lokasi penyimpanan (`location:manage`) bertanda `(g)` pada Matriks 3.1 PRD.
  * Saat pengguna non-*Super Admin* (misalnya *Warehouse Manager*) membuat atau memperbarui lokasi penyimpanan, `warehouse_service` memanggil `access_service.ensure_warehouse_access(conn, actor, warehouse_id)`. Apabila pengguna tidak ditugaskan pada gudang pemilik lokasi tersebut, permintaan ditolak dengan HTTP `403` dan kode error `WAREHOUSE_NOT_ASSIGNED`.
* **Perlindungan Penonaktifan (`409 ENTITY_IN_USE` — PRD 6.8):**
  * **Gudang:** Tidak dapat dinonaktifkan (`is_active: true -> false`) apabila masih memiliki saldo stok (`inventory_balances.qty_on_hand <> 0`) atau masih dirujuk oleh dokumen operasional yang belum final (PO `DRAFT`/`ISSUED`/`PARTIALLY_RECEIVED`, GR `DRAFT`, Transfer `DRAFT`/`APPROVED`/`SHIPPED`, atau Opname `DRAFT`/`IN_PROGRESS`/`WAITING_APPROVAL`).
  * **Lokasi Penyimpanan:** Tidak dapat dinonaktifkan apabila masih memiliki saldo stok (`qty_on_hand <> 0`), dipakai pada baris GR `DRAFT`, menjadi lokasi asal/tujuan Transfer `DRAFT`/`APPROVED`/`SHIPPED`, atau tercakup dalam sesi Opname yang belum final (`DRAFT`/`IN_PROGRESS`/`WAITING_APPROVAL`, termasuk Opname tingkat seluruh gudang di mana `stock_opnames.location_id IS NULL`).
* **Validasi Gudang Aktif (`422 INACTIVE_REFERENCE`):** Lokasi penyimpanan baru tidak dapat dibuat pada gudang yang berstatus `is_active = false`.

---

## 3. Autentikasi dan Otorisasi

* **Autentikasi:** Wajib menyertakan header `Authorization: Bearer <access_token>`.
* **Permission & Scoping:**

| Aksi | Permission | Peran Bawaan (Matriks 3.1) | Warehouse Scoping `(g)` |
| --- | --- | --- | --- |
| Membaca daftar & detail gudang / lokasi | `master:read` | Semua peran (*Super Admin*, *Warehouse Manager*, *Purchasing Staff*, *Warehouse Staff*, *Auditor*) | Tidak |
| Membuat & memperbarui gudang | `warehouse:manage` | *Super Admin* | Tidak |
| Membuat & memperbarui lokasi penyimpanan | `location:manage` | *Super Admin*, *Warehouse Manager* | **Ya** (`ensure_warehouse_access`) |

---

## 4. Ringkasan Endpoint

| # | Method | Endpoint | Fungsi | Auth | Permission |
| :-: | --- | --- | --- | --- | --- |
| 1 | GET | `/api/v1/warehouses` | Daftar gudang (paginasi, filter `is_active`, pencarian, urut) | Bearer | `master:read` |
| 2 | POST | `/api/v1/warehouses` | Buat gudang baru | Bearer | `warehouse:manage` |
| 3 | GET | `/api/v1/warehouses/{warehouse_id}` | Detail gudang berdasarkan ID | Bearer | `master:read` |
| 4 | PATCH | `/api/v1/warehouses/{warehouse_id}` | Perbarui atau nonaktifkan gudang (termasuk `allow_negative_stock`) | Bearer | `warehouse:manage` |
| 5 | GET | `/api/v1/warehouses/{warehouse_id}/locations` | Daftar lokasi penyimpanan milik suatu gudang | Bearer | `master:read` |
| 6 | POST | `/api/v1/warehouses/{warehouse_id}/locations` | Buat lokasi penyimpanan baru di dalam gudang tertentu | Bearer | `location:manage` `(g)` |
| 7 | GET | `/api/v1/locations` | Daftar seluruh lokasi penyimpanan (dapat difilter `warehouse_id`) | Bearer | `master:read` |
| 8 | POST | `/api/v1/locations` | Buat lokasi penyimpanan baru (menyertakan `warehouse_id` di body) | Bearer | `location:manage` `(g)` |
| 9 | GET | `/api/v1/locations/{location_id}` | Detail lokasi penyimpanan berdasarkan ID | Bearer | `master:read` |
| 10 | PATCH | `/api/v1/locations/{location_id}` | Perbarui atau nonaktifkan lokasi penyimpanan | Bearer | `location:manage` `(g)` |

---

## 5. Detail Setiap Endpoint

### 5.1 Gudang (`/api/v1/warehouses`)

#### GET `/api/v1/warehouses` — Daftar Gudang
* **Autentikasi & Permission:** Bearer Token, `master:read`
* **Query Parameter:**
  * `limit` (`1..200`, default `50`), `offset` (`>= 0`, default `0`)
  * `is_active` (boolean, opsional)
  * `search` (string, opsional) — Pencarian `ILIKE` pada `code`, `name`, atau `address`.
  * `sort_by` (string, default `"id"`) — Whitelist: `"id"`, `"code"`, `"name"`, `"created_at"`.
  * `sort_dir` (`"asc"` | `"desc"`, default `"asc"`).
* **Response Berhasil (`200 OK` — `Page[WarehouseOut]`):**
```json
{
  "items": [
    {
      "id": 1,
      "code": "WH-JKT-01",
      "name": "Gudang Utama Jakarta",
      "address": "Jl. Raya Cakung Cilincing",
      "allow_negative_stock": false,
      "is_active": true,
      "created_by": 1,
      "created_at": "2026-10-21T15:20:00.123456+07:00",
      "updated_at": "2026-10-21T15:20:00.123456+07:00"
    }
  ],
  "total": 1,
  "limit": 50,
  "offset": 0
}
```

#### POST `/api/v1/warehouses` — Buat Gudang Baru
* **Autentikasi & Permission:** Bearer Token, `warehouse:manage`
* **Request Body (`WarehouseCreate`):**
  * `code` (string, wajib, `1..50` karakter, unik *case-insensitive*).
  * `name` (string, wajib, `1..150` karakter).
  * `address` (string | null, opsional).
  * `allow_negative_stock` (boolean, opsional, default `false`).
  * `is_active` (boolean, opsional, default `true`).
* **Contoh Request:**
```json
{
  "code": "WH-JKT-01",
  "name": "Gudang Utama Jakarta",
  "address": "Jl. Raya Cakung Cilincing",
  "allow_negative_stock": false,
  "is_active": true
}
```
* **Response Berhasil:** `201 Created` (`WarehouseOut`). Mencatat `WAREHOUSE_CREATED` pada `audit_logs`.
* **Kemungkinan Error:** `401 AUTH_TOKEN_INVALID`, `403 PERMISSION_DENIED`, `409 DUPLICATE` (kode gudang sudah ada), `422 VALIDATION_ERROR`.

#### GET `/api/v1/warehouses/{warehouse_id}` — Detail Gudang
* **Autentikasi & Permission:** Bearer Token, `master:read`
* **Response Berhasil:** `200 OK` (`WarehouseOut`).
* **Kemungkinan Error:** `404 NOT_FOUND` (`details: {"warehouse_id": ...}`).

#### PATCH `/api/v1/warehouses/{warehouse_id}` — Perbarui / Nonaktifkan Gudang
* **Autentikasi & Permission:** Bearer Token, `warehouse:manage`
* **Request Body (`WarehouseUpdate`):** Seluruh field opsional (`code`, `name`, `address`, `allow_negative_stock`, `is_active`).
* **Aturan Bisnis:**
  * Baris gudang dikunci dengan `SELECT ... FOR UPDATE`.
  * Jika `is_active` diubah dari `true` ke `false`, sistem memeriksa `warehouse_repo.is_warehouse_in_use()`. Bila gudang masih memiliki saldo stok (`qty_on_hand <> 0`) atau dipakai pada dokumen belum final, ditolak dengan `409 ENTITY_IN_USE`.
  * Mencatat `WAREHOUSE_DEACTIVATED` atau `WAREHOUSE_UPDATED` (termasuk perubahan `allow_negative_stock`) pada `audit_logs`.
* **Kemungkinan Error:** `404 NOT_FOUND`, `409 DUPLICATE`, `409 ENTITY_IN_USE`, `422 VALIDATION_ERROR`.

---

### 5.2 Lokasi Penyimpanan (`/api/v1/warehouses/{warehouse_id}/locations` & `/api/v1/locations`)

Aplikasi menyediakan dua rute ekuivalen untuk membaca daftar dan membuat lokasi penyimpanan:
1. **Sub-resource gudang:** `GET / POST /api/v1/warehouses/{warehouse_id}/locations` (`warehouse_id` diambil dari path URL).
2. **Resource top-level:** `GET / POST /api/v1/locations` (`warehouse_id` dikirim sebagai query filter atau di dalam body JSON).

#### GET `/api/v1/warehouses/{warehouse_id}/locations` — Daftar Lokasi pada Satu Gudang
* **Autentikasi & Permission:** Bearer Token, `master:read`
* **Path Parameter:** `warehouse_id` (integer, wajib — diverifikasi keberadaannya; jika gudang tidak ada, mengembalikan `404 NOT_FOUND`).
* **Query Parameter:** `limit` (`1..200`, default `50`), `offset` (`>= 0`, default `0`), `is_active` (boolean, opsional), `search` (string, opsional — `ILIKE` pada `code` atau `name`), `sort_by` (`"id"`, `"code"`, `"name"`, `"warehouse_id"`, `"created_at"`), `sort_dir` (`"asc"` | `"desc"`).
* **Response Berhasil (`200 OK` — `Page[StorageLocationOut]`):**
```json
{
  "items": [
    {
      "id": 1,
      "warehouse_id": 1,
      "warehouse_code": "WH-JKT-01",
      "warehouse_name": "Gudang Utama Jakarta",
      "code": "A-01-01",
      "name": "Rak A Baris 1",
      "is_active": true,
      "created_by": 1,
      "created_at": "2026-10-21T15:25:00.123456+07:00",
      "updated_at": "2026-10-21T15:25:00.123456+07:00"
    }
  ],
  "total": 1,
  "limit": 50,
  "offset": 0
}
```

#### POST `/api/v1/warehouses/{warehouse_id}/locations` — Buat Lokasi pada Gudang Tertentu
* **Autentikasi & Permission:** Bearer Token, `location:manage` + **Warehouse Scoping `(g)`** pada `warehouse_id`.
* **Request Body (`WarehouseLocationCreate`):**
  * `code` (string, wajib, `1..50` karakter, unik per gudang *case-insensitive*).
  * `name` (string, wajib, `1..120` karakter).
  * `is_active` (boolean, opsional, default `true`).
* **Contoh Request:**
```json
{
  "code": "BIN-A01",
  "name": "Bin A01",
  "is_active": true
}
```
* **Response Berhasil:** `201 Created` (`StorageLocationOut`). Mencatat `LOCATION_CREATED` pada `audit_logs`.
* **Kemungkinan Error:**
  * `403 PERMISSION_DENIED` — Tidak memiliki izin `location:manage`.
  * `403 WAREHOUSE_NOT_ASSIGNED` — Pengguna (non-*Super Admin*) tidak ditugaskan ke `warehouse_id`.
  * `404 NOT_FOUND` — Gudang `warehouse_id` tidak ditemukan.
  * `409 DUPLICATE` — Kode lokasi sudah ada di gudang tersebut.
  * `422 INACTIVE_REFERENCE` — Gudang `warehouse_id` berstatus tidak aktif (`is_active = false`).
  * `422 VALIDATION_ERROR` — Payload tidak valid.

#### GET `/api/v1/locations` — Daftar Seluruh Lokasi Penyimpanan
* **Autentikasi & Permission:** Bearer Token, `master:read`
* **Query Parameter:** Sama dengan `GET /api/v1/warehouses/{warehouse_id}/locations`, ditambah query opsional `warehouse_id` (integer).
* **Response Berhasil:** `200 OK` (`Page[StorageLocationOut]`).

#### POST `/api/v1/locations` — Buat Lokasi Penyimpanan (Top-Level)
* **Autentikasi & Permission:** Bearer Token, `location:manage` + **Warehouse Scoping `(g)`** pada `payload.warehouse_id`.
* **Request Body (`StorageLocationCreate`):**
  * `warehouse_id` (integer, wajib).
  * `code` (string, wajib, `1..50` karakter).
  * `name` (string, wajib, `1..120` karakter).
  * `is_active` (boolean, opsional, default `true`).
* **Contoh Request:**
```json
{
  "warehouse_id": 1,
  "code": "A-01-01",
  "name": "Rak A Baris 1",
  "is_active": true
}
```
* **Response Berhasil & Error:** Identik dengan `POST /api/v1/warehouses/{warehouse_id}/locations`.

#### GET `/api/v1/locations/{location_id}` — Detail Lokasi Penyimpanan
* **Autentikasi & Permission:** Bearer Token, `master:read`
* **Response Berhasil:** `200 OK` (`StorageLocationOut`).
* **Kemungkinan Error:** `404 NOT_FOUND` (`details: {"location_id": ...}`).

#### PATCH `/api/v1/locations/{location_id}` — Perbarui / Nonaktifkan Lokasi Penyimpanan
* **Autentikasi & Permission:** Bearer Token, `location:manage` + **Warehouse Scoping `(g)`** pada gudang pemilik lokasi.
* **Request Body (`StorageLocationUpdate`):** Seluruh field opsional (`code`, `name`, `is_active`). Kepemilikan gudang (`warehouse_id`) bersifat tetap dan tidak dapat dipindahkan.
* **Aturan Bisnis:**
  * Baris lokasi dikunci dengan `SELECT ... FOR UPDATE`.
  * Memeriksa `access_service.ensure_warehouse_access(conn, actor, existing["warehouse_id"])` (`403 WAREHOUSE_NOT_ASSIGNED` bila tidak ditugaskan).
  * Jika `is_active` diubah dari `true` ke `false`, sistem memeriksa `warehouse_repo.is_location_in_use()`. Bila lokasi masih bersaldo `<> 0` atau dipakai pada dokumen belum final, ditolak dengan `409 ENTITY_IN_USE`.
  * Mencatat `LOCATION_DEACTIVATED` atau `LOCATION_UPDATED` pada `audit_logs`.
* **Kemungkinan Error:** `403 PERMISSION_DENIED`, `403 WAREHOUSE_NOT_ASSIGNED`, `404 NOT_FOUND`, `409 DUPLICATE`, `409 ENTITY_IN_USE`, `422 VALIDATION_ERROR`.

---

## 6. Relasi dan Ketergantungan

| Tabel | Kunci & Constraint Utama (`002_create_master_tables.sql`) | Relasi & Dampak |
| --- | --- | --- |
| `warehouses` | `pk_warehouses (id)`, `uq_warehouses_code (code)` | Dirujuk oleh `storage_locations`, `user_warehouses`, `inventory_balances`, `stock_movements`, `purchase_orders`, `goods_receipts`, `stock_transfers`, `stock_opnames`. |
| `storage_locations` | `pk_storage_locations (id)`, `uq_storage_locations_warehouse_code (warehouse_id, code)`, `uq_storage_locations_id_warehouse (id, warehouse_id)` | Constraint unik komposit `(id, warehouse_id)` menjadi target *Composite Foreign Key* dari tabel `inventory_balances`, `stock_movements`, `stock_transfers`, `stock_opnames`, dan `stock_opname_lines` untuk menjamin di level database bahwa lokasi pasti milik gudang yang dirujuk (PRD 6.2 & 7.5). |

Alur lapisan: `routes/warehouses.py` → `warehouse_service.py` (`with conn.transaction():` + `access_service.ensure_warehouse_access()` + `audit_service.record()`) → `warehouse_repo.py` → PostgreSQL.

---

## 7. Contoh Penggunaan (cURL)

```bash
BASE=http://localhost:8000/api/v1

# 1. Buat Gudang Baru (Super Admin)
curl -s -X POST "$BASE/warehouses" \
  -H "Authorization: Bearer <SUPERADMIN_TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{"code":"WH-JKT-01","name":"Gudang Utama Jakarta","allow_negative_stock":false}'

# 2. Buat Lokasi Penyimpanan melalui sub-resource gudang (Warehouse Manager yang ditugaskan)
curl -s -X POST "$BASE/warehouses/1/locations" \
  -H "Authorization: Bearer <MANAGER_TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{"code":"BIN-A01","name":"Bin A01"}'

# 3. Ambil daftar lokasi pada Gudang 1
curl -s "$BASE/warehouses/1/locations?is_active=true" \
  -H "Authorization: Bearer <ACCESS_TOKEN>"

# 4. Perbarui nama lokasi penyimpanan
curl -s -X PATCH "$BASE/locations/1" \
  -H "Authorization: Bearer <MANAGER_TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{"name":"Bin A01 - Zona Cepat"}'
```

---

## 8. Catatan dan Status Verifikasi

| # | Status | Catatan |
| --- | --- | --- |
| 1 | ✅ Terverifikasi | Penegakan *Warehouse Scoping* (`403 WAREHOUSE_NOT_ASSIGNED`) pada endpoint pembuatan dan pembaruan lokasi penyimpanan telah diuji secara otomatis di `test_ac12_warehouse_scoping_assignment_and_access_enforcement` (`tests/test_rbac_scoping.py` — **AC-12**). |
| 2 | ✅ Terverifikasi | Pencatatan audit log atas perubahan `allow_negative_stock` pada gudang serta penolakan penonaktifan gudang/lokasi yang sedang digunakan (`409 ENTITY_IN_USE`) telah diuji di `test_master_data_and_warehouse_crud_deactivation_and_sku_immutability`. |

