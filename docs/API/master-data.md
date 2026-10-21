# Manajemen Master Data (Kategori, UoM, Pemasok & Barang)

## 1. Informasi Umum

| Atribut | Keterangan |
| --- | --- |
| **Modul** | Manajemen Master Data (Kategori, Satuan Ukur/UoM, Pemasok/Supplier, dan Barang/Item) |
| **Base path** | `/api/v1/categories`, `/api/v1/uoms`, `/api/v1/suppliers`, `/api/v1/items` |
| **Rujukan PRD** | FR-02, FR-09, FR-11, Bagian 3.1 (Matriks Permission), 6.3 (Kuantitas & Desimal), 6.8 (Penonaktifan & Imutabilitas SKU), Lampiran A & B |
| **Status implementasi** | ✅ Sudah diimplementasikan dan diuji (`tests/test_rbac_scoping.py`) |
| **Kode sumber** | [routes/master.py](../../app/api/routes/master.py), [master_service.py](../../app/services/master_service.py), [master_repo.py](../../app/repositories/master_repo.py), [schemas/master.py](../../app/schemas/master.py) |
| **Tabel terkait** | `categories`, `uoms`, `suppliers`, `items`, `po_lines`, `purchase_orders`, `gr_lines`, `goods_receipts`, `stock_transfer_lines`, `stock_transfers`, `stock_opname_lines`, `stock_opnames`, `inventory_balances`, `stock_movements`, `audit_logs` |
| **Modul terkait** | [Autentikasi & Otorisasi](authentication.md), [Gudang & Lokasi Penyimpanan](warehouses.md), [Audit Log](audit-logs.md) |

---

## 2. Penjelasan Fitur

### 2.1 Tujuan

Modul Master Data menyediakan pengelolaan entitas referensi dasar yang digunakan di seluruh transaksi persediaan dan pembelian:

1. **Kategori (`categories`):** Pengelompokan barang berdasarkan jenis atau karakteristik.
2. **Satuan Ukur / *Unit of Measure* (`uoms`):** Satuan dasar barang beserta aturan apakah barang dalam satuan tersebut mengizinkan kuantitas pecahan/desimal (`allow_decimal`).
3. **Pemasok (`suppliers`):** Data rekanan pemasok untuk penerbitan *Purchase Order* (PO).
4. **Barang (`items`):** Data master SKU (*Stock Keeping Unit*) yang mengacu pada satu Kategori aktif dan satu UoM dasar aktif.

### 2.2 Alur Bisnis & Aturan Integritas Utama

* **Tanpa *Hard Delete* (Invarian 9 & PRD 6.8):** Tidak ada endpoint `DELETE` pada seluruh entitas master data. Penonaktifan dilakukan melalui `PATCH` dengan mengirimkan `{"is_active": false}`.
* **Perlindungan Penonaktifan (`409 ENTITY_IN_USE` — PRD 6.8):**
  * **Kategori & UoM:** Tidak dapat dinonaktifkan apabila masih dipakai oleh barang (`items`) yang berstatus `is_active = true`.
  * **Pemasok:** Tidak dapat dinonaktifkan apabila masih memiliki *Purchase Order* dengan status belum final (`DRAFT`, `ISSUED`, atau `PARTIALLY_RECEIVED`).
  * **Barang:** Tidak dapat dinonaktifkan apabila masih memiliki saldo fisik (`inventory_balances.qty_on_hand <> 0`) atau masih tercantum pada dokumen operasional yang belum final (PO `DRAFT`/`ISSUED`/`PARTIALLY_RECEIVED`, GR `DRAFT`, Transfer `DRAFT`/`APPROVED`/`SHIPPED`, atau Opname `DRAFT`/`IN_PROGRESS`/`WAITING_APPROVAL`).
* **Imutabilitas SKU & UoM Dasar Barang (`409 ENTITY_IN_USE` — FR-02 & PRD 6.8):**
  * Sebelum barang pernah dipakai di transaksi mana pun, `sku` dan `uom_id` masih dapat diperbarui.
  * Setelah barang tercatat pada `po_lines`, `stock_transfer_lines`, `stock_opname_lines`, `stock_movements`, atau memiliki `inventory_balances.qty_on_hand <> 0`, perubahan terhadap `sku` maupun `uom_id` ditolak dengan `409 ENTITY_IN_USE`.
* **Validasi Referensi Aktif (`422 INACTIVE_REFERENCE`):** Pembuatan atau pembaruan Barang wajib menunjuk `category_id` dan `uom_id` yang ada (`404 NOT_FOUND` bila tidak ditemukan) dan berstatus `is_active = true` (`422 INACTIVE_REFERENCE` bila nonaktif).
* **Jejak Audit Otomatis:** Setiap pembuatan, pembaruan, dan penonaktifan master data dicatat dalam satu transaksi yang sama ke tabel `audit_logs`.

---

## 3. Autentikasi dan Otorisasi

* **Autentikasi:** Wajib menyertakan header `Authorization: Bearer <access_token>`.
* **Permission:**
  * **`master:read`** — Untuk seluruh endpoint pembacaan daftar (`GET`) dan detail (`GET /{id}`). Berdasarkan *seed* awal Matriks 3.1 PRD, seluruh 5 peran (*Super Admin*, *Warehouse Manager*, *Purchasing Staff*, *Warehouse Staff*, dan *Auditor*) memiliki izin `master:read`.
  * **`master:manage`** — Untuk seluruh endpoint pembuatan (`POST`) dan pembaruan/penonaktifan (`PATCH /{id}`). Berdasarkan Matriks 3.1 PRD, izin ini dimiliki oleh **`Super Admin`**, **`Warehouse Manager`**, dan **`Purchasing Staff`**.
* **Warehouse Scoping:** Master data Kategori, UoM, Pemasok, dan Barang bersifat lintas-gudang (tidak bertanda `(g)` pada Matriks 3.1 PRD).

---

## 4. Ringkasan Endpoint

| # | Method | Endpoint | Fungsi | Auth | Permission |
| :-: | --- | --- | --- | --- | --- |
| 1 | GET | `/api/v1/categories` | Daftar kategori barang (paginasi, filter `is_active`, pencarian, urut) | Bearer | `master:read` |
| 2 | POST | `/api/v1/categories` | Buat kategori barang baru | Bearer | `master:manage` |
| 3 | GET | `/api/v1/categories/{category_id}` | Detail kategori berdasarkan ID | Bearer | `master:read` |
| 4 | PATCH | `/api/v1/categories/{category_id}` | Perbarui atau nonaktifkan kategori | Bearer | `master:manage` |
| 5 | GET | `/api/v1/uoms` | Daftar satuan ukur / UoM (paginasi, filter `is_active`, pencarian, urut) | Bearer | `master:read` |
| 6 | POST | `/api/v1/uoms` | Buat satuan ukur (UoM) baru | Bearer | `master:manage` |
| 7 | GET | `/api/v1/uoms/{uom_id}` | Detail satuan ukur (UoM) berdasarkan ID | Bearer | `master:read` |
| 8 | PATCH | `/api/v1/uoms/{uom_id}` | Perbarui atau nonaktifkan satuan ukur (UoM) | Bearer | `master:manage` |
| 9 | GET | `/api/v1/suppliers` | Daftar pemasok (paginasi, filter `is_active`, pencarian, urut) | Bearer | `master:read` |
| 10 | POST | `/api/v1/suppliers` | Buat pemasok baru | Bearer | `master:manage` |
| 11 | GET | `/api/v1/suppliers/{supplier_id}` | Detail pemasok berdasarkan ID | Bearer | `master:read` |
| 12 | PATCH | `/api/v1/suppliers/{supplier_id}` | Perbarui atau nonaktifkan pemasok | Bearer | `master:manage` |
| 13 | GET | `/api/v1/items` | Daftar barang / SKU (paginasi, filter kategori/UoM/aktif, pencarian, urut) | Bearer | `master:read` |
| 14 | POST | `/api/v1/items` | Buat barang (SKU) baru | Bearer | `master:manage` |
| 15 | GET | `/api/v1/items/{item_id}` | Detail barang (SKU) berdasarkan ID | Bearer | `master:read` |
| 16 | PATCH | `/api/v1/items/{item_id}` | Perbarui atau nonaktifkan barang (SKU) | Bearer | `master:manage` |

---

## 5. Detail Setiap Endpoint

### 5.1 Kategori (`/api/v1/categories`)

#### GET `/api/v1/categories` — Daftar Kategori
* **Autentikasi & Permission:** Bearer Token, `master:read`
* **Query Parameter:**
  * `limit` (integer, default `50`, rentang `1..200`)
  * `offset` (integer, default `0`, `>= 0`)
  * `is_active` (boolean, opsional) — Filter status aktif (`true`/`false`).
  * `search` (string, opsional) — Pencarian `ILIKE` pada `name` atau `description`.
  * `sort_by` (string, opsional, default `"id"`) — Whitelist: `"id"`, `"name"`, `"created_at"`.
  * `sort_dir` (string, opsional, default `"asc"`) — `"asc"` atau `"desc"`.
* **Response Berhasil (`200 OK` — `Page[CategoryOut]`):**
```json
{
  "items": [
    {
      "id": 1,
      "name": "Komponen Elektronik",
      "description": "IC, Resistor, Kapasitor",
      "is_active": true,
      "created_by": 3,
      "created_at": "2026-10-21T15:10:00.123456+07:00",
      "updated_at": "2026-10-21T15:10:00.123456+07:00"
    }
  ],
  "total": 1,
  "limit": 50,
  "offset": 0
}
```

#### POST `/api/v1/categories` — Buat Kategori Baru
* **Autentikasi & Permission:** Bearer Token, `master:manage`
* **Request Body (`CategoryCreate`):**
  * `name` (string, wajib, `1..120` karakter, di-*trim*, tidak boleh kosong/spasi saja, unik *case-insensitive*).
  * `description` (string | null, opsional).
  * `is_active` (boolean, opsional, default `true`).
* **Contoh Request:**
```json
{
  "name": "Komponen Elektronik",
  "description": "IC, Resistor, Kapasitor",
  "is_active": true
}
```
* **Response Berhasil:** `201 Created` (`CategoryOut`). Mencatat `CATEGORY_CREATED` pada `audit_logs`.
* **Kemungkinan Error:** `401 AUTH_TOKEN_INVALID`, `403 PERMISSION_DENIED`, `409 DUPLICATE` (nama kategori sudah terdaftar), `422 VALIDATION_ERROR`.

#### GET `/api/v1/categories/{category_id}` — Detail Kategori
* **Autentikasi & Permission:** Bearer Token, `master:read`
* **Response Berhasil:** `200 OK` (`CategoryOut`).
* **Kemungkinan Error:** `404 NOT_FOUND` (`details: {"category_id": ...}`).

#### PATCH `/api/v1/categories/{category_id}` — Perbarui / Nonaktifkan Kategori
* **Autentikasi & Permission:** Bearer Token, `master:manage`
* **Request Body (`CategoryUpdate`):** Seluruh field opsional (`name`, `description`, `is_active`).
* **Aturan Bisnis:**
  * Baris kategori dikunci dengan `SELECT ... FOR UPDATE`.
  * Jika `is_active` diubah dari `true` ke `false`, sistem memeriksa `master_repo.is_category_in_use()`. Bila masih ada `items` aktif yang memakai kategori ini, transaksi ditolak dengan `409 ENTITY_IN_USE`.
  * Mencatat `CATEGORY_DEACTIVATED` (bila dinonaktifkan) atau `CATEGORY_UPDATED` pada `audit_logs`.
* **Kemungkinan Error:** `404 NOT_FOUND`, `409 DUPLICATE`, `409 ENTITY_IN_USE`, `422 VALIDATION_ERROR`.

---

### 5.2 Satuan Ukur / UoM (`/api/v1/uoms`)

#### GET `/api/v1/uoms` — Daftar UoM
* **Autentikasi & Permission:** Bearer Token, `master:read`
* **Query Parameter:**
  * `limit` (`1..200`, default `50`), `offset` (`>= 0`, default `0`)
  * `is_active` (boolean, opsional)
  * `search` (string, opsional) — Pencarian `ILIKE` pada `code` atau `name`.
  * `sort_by` (string, default `"id"`) — Whitelist: `"id"`, `"code"`, `"name"`, `"created_at"`.
  * `sort_dir` (`"asc"` | `"desc"`, default `"asc"`).
* **Response Berhasil (`200 OK` — `Page[UomOut]`):**
```json
{
  "items": [
    {
      "id": 1,
      "code": "PCS",
      "name": "Pieces",
      "allow_decimal": false,
      "is_active": true,
      "created_by": 3,
      "created_at": "2026-10-21T15:11:00.123456+07:00",
      "updated_at": "2026-10-21T15:11:00.123456+07:00"
    }
  ],
  "total": 1,
  "limit": 50,
  "offset": 0
}
```

#### POST `/api/v1/uoms` — Buat UoM Baru
* **Autentikasi & Permission:** Bearer Token, `master:manage`
* **Request Body (`UomCreate`):**
  * `code` (string, wajib, `1..20` karakter, unik *case-insensitive*).
  * `name` (string, wajib, `1..60` karakter).
  * `allow_decimal` (boolean, opsional, default `false` — menentukan apakah barang dengan UoM ini mengizinkan kuantitas desimal pada transaksi).
  * `is_active` (boolean, opsional, default `true`).
* **Contoh Request:**
```json
{
  "code": "KG",
  "name": "Kilogram",
  "allow_decimal": true,
  "is_active": true
}
```
* **Response Berhasil:** `201 Created` (`UomOut`). Mencatat `UOM_CREATED` pada `audit_logs`.
* **Kemungkinan Error:** `409 DUPLICATE` (kode UoM sudah ada), `422 VALIDATION_ERROR`.

#### GET `/api/v1/uoms/{uom_id}` — Detail UoM
* **Autentikasi & Permission:** Bearer Token, `master:read`
* **Response Berhasil:** `200 OK` (`UomOut`).
* **Kemungkinan Error:** `404 NOT_FOUND` (`details: {"uom_id": ...}`).

#### PATCH `/api/v1/uoms/{uom_id}` — Perbarui / Nonaktifkan UoM
* **Autentikasi & Permission:** Bearer Token, `master:manage`
* **Request Body (`UomUpdate`):** Seluruh field opsional (`code`, `name`, `allow_decimal`, `is_active`).
* **Aturan Bisnis:**
  * Jika dinonaktifkan (`is_active: true -> false`) saat masih dipakai oleh barang aktif, ditolak dengan `409 ENTITY_IN_USE`.
  * Mencatat `UOM_DEACTIVATED` atau `UOM_UPDATED` pada `audit_logs`.
* **Kemungkinan Error:** `404 NOT_FOUND`, `409 DUPLICATE`, `409 ENTITY_IN_USE`, `422 VALIDATION_ERROR`.

---

### 5.3 Pemasok / Supplier (`/api/v1/suppliers`)

#### GET `/api/v1/suppliers` — Daftar Pemasok
* **Autentikasi & Permission:** Bearer Token, `master:read`
* **Query Parameter:**
  * `limit` (`1..200`, default `50`), `offset` (`>= 0`, default `0`)
  * `is_active` (boolean, opsional)
  * `search` (string, opsional) — Pencarian `ILIKE` pada `code`, `name`, atau `contact_person`.
  * `sort_by` (string, default `"id"`) — Whitelist: `"id"`, `"code"`, `"name"`, `"created_at"`.
  * `sort_dir` (`"asc"` | `"desc"`, default `"asc"`).
* **Response Berhasil (`200 OK` — `Page[SupplierOut]`):**
```json
{
  "items": [
    {
      "id": 1,
      "code": "SUP-ELK-01",
      "name": "PT Nusantara Elektronik",
      "contact_person": "Hendra",
      "phone": "021-5551234",
      "email": "sales@nusantara.co.id",
      "address": "Kawasan Industri Jababeka",
      "is_active": true,
      "created_by": 3,
      "created_at": "2026-10-21T15:12:00.123456+07:00",
      "updated_at": "2026-10-21T15:12:00.123456+07:00"
    }
  ],
  "total": 1,
  "limit": 50,
  "offset": 0
}
```

#### POST `/api/v1/suppliers` — Buat Pemasok Baru
* **Autentikasi & Permission:** Bearer Token, `master:manage`
* **Request Body (`SupplierCreate`):**
  * `code` (string, wajib, `1..50` karakter, unik *case-insensitive*).
  * `name` (string, wajib, `1..150` karakter).
  * `contact_person` (string | null, opsional, maks `120` karakter).
  * `phone` (string | null, opsional, maks `30` karakter).
  * `email` (string | null, opsional, maks `255` karakter, divalidasi dengan `EMAIL_REGEX` dan dinormalisasi ke huruf kecil).
  * `address` (string | null, opsional).
  * `is_active` (boolean, opsional, default `true`).
* **Response Berhasil:** `201 Created` (`SupplierOut`). Mencatat `SUPPLIER_CREATED` pada `audit_logs`.
* **Kemungkinan Error:** `409 DUPLICATE` (kode pemasok sudah ada), `422 VALIDATION_ERROR` (termasuk format email tidak valid).

#### GET `/api/v1/suppliers/{supplier_id}` — Detail Pemasok
* **Autentikasi & Permission:** Bearer Token, `master:read`
* **Response Berhasil:** `200 OK` (`SupplierOut`).
* **Kemungkinan Error:** `404 NOT_FOUND` (`details: {"supplier_id": ...}`).

#### PATCH `/api/v1/suppliers/{supplier_id}` — Perbarui / Nonaktifkan Pemasok
* **Autentikasi & Permission:** Bearer Token, `master:manage`
* **Request Body (`SupplierUpdate`):** Seluruh field opsional (`code`, `name`, `contact_person`, `phone`, `email`, `address`, `is_active`).
* **Aturan Bisnis:**
  * Sesuai PRD 6.8, pemasok tidak dapat dinonaktifkan (`is_active: true -> false`) apabila masih memiliki *Purchase Order* dengan status `DRAFT`, `ISSUED`, atau `PARTIALLY_RECEIVED` (`409 ENTITY_IN_USE`).
  * Mencatat `SUPPLIER_DEACTIVATED` atau `SUPPLIER_UPDATED` pada `audit_logs`.
* **Kemungkinan Error:** `404 NOT_FOUND`, `409 DUPLICATE`, `409 ENTITY_IN_USE`, `422 VALIDATION_ERROR`.

---

### 5.4 Barang / Item (`/api/v1/items`)

#### GET `/api/v1/items` — Daftar Barang
* **Autentikasi & Permission:** Bearer Token, `master:read`
* **Query Parameter:**
  * `limit` (`1..200`, default `50`), `offset` (`>= 0`, default `0`)
  * `category_id` (integer, opsional) — Filter berdasarkan ID kategori.
  * `uom_id` (integer, opsional) — Filter berdasarkan ID satuan ukur.
  * `is_active` (boolean, opsional) — Filter status aktif.
  * `search` (string, opsional) — Pencarian `ILIKE` pada `sku`, `name`, atau `description`.
  * `sort_by` (string, default `"id"`) — Whitelist: `"id"`, `"sku"`, `"name"`, `"created_at"`.
  * `sort_dir` (`"asc"` | `"desc"`, default `"asc"`).
* **Response Berhasil (`200 OK` — `Page[ItemOut]`):** Mengembalikan data barang beserta hasil `JOIN` kategori (`category_name`) dan UoM (`uom_code`, `uom_name`, `allow_decimal`).
```json
{
  "items": [
    {
      "id": 1,
      "sku": "ELK-MCU-001",
      "name": "Microcontroller ESP32",
      "description": "Dual-core Wi-Fi & BLE MCU",
      "category_id": 1,
      "category_name": "Komponen Elektronik",
      "uom_id": 1,
      "uom_code": "PCS",
      "uom_name": "Pieces",
      "allow_decimal": false,
      "is_active": true,
      "created_by": 3,
      "created_at": "2026-10-21T15:15:00.123456+07:00",
      "updated_at": "2026-10-21T15:15:00.123456+07:00"
    }
  ],
  "total": 1,
  "limit": 50,
  "offset": 0
}
```

#### POST `/api/v1/items` — Buat Barang Baru
* **Autentikasi & Permission:** Bearer Token, `master:manage`
* **Request Body (`ItemCreate`):**
  * `sku` (string, wajib, `1..64` karakter, unik *case-insensitive*).
  * `name` (string, wajib, `1..200` karakter).
  * `description` (string | null, opsional).
  * `category_id` (integer, wajib — harus merujuk ke kategori yang ada dan `is_active = true`).
  * `uom_id` (integer, wajib — harus merujuk ke UoM yang ada dan `is_active = true`).
  * `is_active` (boolean, opsional, default `true`).
* **Contoh Request:**
```json
{
  "sku": "ELK-MCU-001",
  "name": "Microcontroller ESP32",
  "description": "Dual-core Wi-Fi & BLE MCU",
  "category_id": 1,
  "uom_id": 1,
  "is_active": true
}
```
* **Response Berhasil:** `201 Created` (`ItemOut`). Mencatat `ITEM_CREATED` pada `audit_logs`.
* **Kemungkinan Error:**
  * `404 NOT_FOUND` — `category_id` atau `uom_id` tidak ditemukan.
  * `409 DUPLICATE` — `sku` sudah terdaftar.
  * `422 INACTIVE_REFERENCE` — Kategori atau UoM yang dipilih berstatus tidak aktif (`is_active = false`).
  * `422 VALIDATION_ERROR` — Payload tidak valid.

#### GET `/api/v1/items/{item_id}` — Detail Barang
* **Autentikasi & Permission:** Bearer Token, `master:read`
* **Response Berhasil:** `200 OK` (`ItemOut`).
* **Kemungkinan Error:** `404 NOT_FOUND` (`details: {"item_id": ...}`).

#### PATCH `/api/v1/items/{item_id}` — Perbarui / Nonaktifkan Barang
* **Autentikasi & Permission:** Bearer Token, `master:manage`
* **Request Body (`ItemUpdate`):** Seluruh field opsional (`sku`, `name`, `description`, `category_id`, `uom_id`, `is_active`).
* **Aturan Bisnis:**
  * **Imutabilitas SKU & UoM Dasar:** Apabila `sku` atau `uom_id` diubah ke nilai baru, sistem memeriksa `master_repo.is_item_used_in_transactions()`. Jika barang sudah pernah tercatat di `po_lines`, `stock_transfer_lines`, `stock_opname_lines`, `stock_movements`, atau memiliki `inventory_balances.qty_on_hand <> 0`, perubahan ditolak dengan `409 ENTITY_IN_USE`.
  * **Validasi Referensi:** Perubahan `category_id` atau `uom_id` wajib menunjuk entitas yang ada (`404 NOT_FOUND`) dan aktif (`422 INACTIVE_REFERENCE`).
  * **Penonaktifan (`is_active: true -> false`):** Ditolak dengan `409 ENTITY_IN_USE` apabila barang masih memiliki `qty_on_hand <> 0` di `inventory_balances` atau tercantum pada dokumen PO/GR/Transfer/Opname yang belum berstatus final (`master_repo.is_item_in_use()`).
  * Mencatat `ITEM_DEACTIVATED` atau `ITEM_UPDATED` pada `audit_logs`.
* **Kemungkinan Error:** `404 NOT_FOUND`, `409 DUPLICATE`, `409 ENTITY_IN_USE`, `422 INACTIVE_REFERENCE`, `422 VALIDATION_ERROR`.

---

## 6. Relasi dan Ketergantungan

| Tabel | Kunci & Constraint Utama (`002_create_master_tables.sql`) | Relasi & Dampak |
| --- | --- | --- |
| `categories` | `pk_categories (id)`, `uq_categories_name (name)` | Dirujuk oleh `items.category_id` (`ON DELETE RESTRICT`). |
| `uoms` | `pk_uoms (id)`, `uq_uoms_code (code)` | Dirujuk oleh `items.uom_id` (`ON DELETE RESTRICT`). Menyimpan atribut `allow_decimal`. |
| `suppliers` | `pk_suppliers (id)`, `uq_suppliers_code (code)` | Dirujuk oleh `purchase_orders.supplier_id` (`ON DELETE RESTRICT`). |
| `items` | `pk_items (id)`, `uq_items_sku (sku)` | Dirujuk oleh `inventory_balances`, `stock_movements`, `po_lines`, `stock_transfer_lines`, `stock_opname_lines` (`ON DELETE RESTRICT`). |

Alur lapisan: `routes/master.py` → `master_service.py` (`with conn.transaction():` + `audit_service.record()`) → `master_repo.py` → PostgreSQL.

---

## 7. Contoh Penggunaan (cURL)

```bash
BASE=http://localhost:8000/api/v1

# 1. Buat Kategori
curl -s -X POST "$BASE/categories" \
  -H "Authorization: Bearer <ACCESS_TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{"name":"Komponen Elektronik","description":"IC, Resistor, Kapasitor"}'

# 2. Buat UoM
curl -s -X POST "$BASE/uoms" \
  -H "Authorization: Bearer <ACCESS_TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{"code":"PCS","name":"Pieces","allow_decimal":false}'

# 3. Buat Pemasok
curl -s -X POST "$BASE/suppliers" \
  -H "Authorization: Bearer <ACCESS_TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{"code":"SUP-ELK-01","name":"PT Nusantara Elektronik","email":"sales@nusantara.co.id"}'

# 4. Buat Barang (SKU)
curl -s -X POST "$BASE/items" \
  -H "Authorization: Bearer <ACCESS_TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{"sku":"ELK-MCU-001","name":"Microcontroller ESP32","category_id":1,"uom_id":1}'

# 5. Cari Barang berdasarkan kategori & kata kunci
curl -s "$BASE/items?category_id=1&search=ESP32" \
  -H "Authorization: Bearer <ACCESS_TOKEN>"
```

---

## 8. Catatan dan Status Verifikasi

| # | Status | Catatan |
| --- | --- | --- |
| 1 | ✅ Terverifikasi | Seluruh 16 endpoint Master Data (`categories`, `uoms`, `suppliers`, `items`) telah diuji secara otomatis di `test_master_data_and_warehouse_crud_deactivation_and_sku_immutability` (`tests/test_rbac_scoping.py`). |
| 2 | ✅ Terverifikasi | Aturan penolakan penonaktifan (`409 ENTITY_IN_USE`), penolakan referensi nonaktif (`422 INACTIVE_REFERENCE`), dan imutabilitas SKU setelah dipakai pada transaksi (`409 ENTITY_IN_USE`) telah diverifikasi terhadap PostgreSQL sungguhan. |

