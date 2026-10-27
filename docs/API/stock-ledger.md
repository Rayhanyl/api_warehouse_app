# Saldo Stok & Buku Besar Pergerakan Stok (Stock & Ledger)

## 1. Informasi Umum

| Atribut | Keterangan |
| --- | --- |
| **Modul** | Saldo Stok (*Inventory Balances*), Stok Dalam Perjalanan (*In-Transit*), dan Buku Besar Pergerakan Stok (*Stock Movement Ledger*) |
| **Base path** | `/api/v1/stock` |
| **Rujukan PRD** | FR-03, FR-08, FR-11, Bagian 3.1 (Matriks Permission), 3.2 (*Warehouse Scoping*), 5.3 (*Movement Types*), 6.1 (Stok Negatif), 6.4 (Imutabilitas Ledger), 7.3 (Kinerja `< 200 ms`), 7.4 (Presisi Numerik), AC-01 s.d. AC-04, AC-08, AC-12, Lampiran A & B |
| **Status implementasi** | ✅ Sudah diimplementasikan dan diuji (`tests/test_rbac_scoping.py`, `tests/test_immutability.py`, `tests/test_goods_receipt.py`, `tests/test_stock_transfer.py`, `tests/test_stock_opname.py`) |
| **Kode sumber** | [routes/stock.py](../../app/api/routes/stock.py), [stock_service.py](../../app/services/stock_service.py), [inventory_service.py](../../app/services/inventory_service.py), [access_service.py](../../app/services/access_service.py), [inventory_repo.py](../../app/repositories/inventory_repo.py), [schemas/stock.py](../../app/schemas/stock.py) |
| **Tabel terkait** | `inventory_balances`, `stock_movements`, `stock_transfers`, `stock_transfer_lines`, `items`, `categories`, `uoms`, `warehouses`, `storage_locations`, `users` |
| **Modul terkait** | [Goods Receipt](goods-receipts.md), [Transfer Stok](stock-transfers.md), [Stock Opname](stock-opnames.md), [Gudang & Lokasi](warehouses.md) |

---

## 2. Penjelasan Fitur

### 2.1 Tujuan

Modul ini menyediakan endpoint **baca-saja (*read-only*)** untuk memantau posisi persediaan secara *real-time* beserta riwayat mutasi barang secara kronologis:

1. **Tampilan Saldo Stok (`inventory_balances` + *In-Transit* — FR-03):**
   * **Per Lokasi (`/balances` & `/by-location`):** Saldo aktual (`qty_on_hand`) dan stok dalam perjalanan (`qty_in_transit`) pada setiap kombinasi `(warehouse_id, location_id, item_id)`.
   * **Per Gudang (`/by-warehouse`):** Agregasi `qty_on_hand` dan `qty_in_transit` per `(warehouse_id, item_id)`.
   * **Ringkasan Lintas Gudang (`/summary`):** Agregasi `qty_on_hand` dan `qty_in_transit` per `item_id` di seluruh gudang.
2. **Buku Besar Pergerakan Stok (`/movements` & `/ledger` — FR-08):**
   * Catatan kronologis *append-only* atas seluruh penambahan dan pengurangan stok dari transaksi GR, Transfer Stok, dan Stock Opname.

### 2.2 Alur Bisnis & Invarian Inti Persediaan

* **Pintu Tunggal Perubahan Stok (`inventory_service.apply_movement` — AGENTS.MD Invarian 1):**
  * Tidak ada endpoint yang mengubah `inventory_balances` secara langsung. Seluruh perubahan saldo hanya terjadi melalui fungsi internal `inventory_service.apply_movement()` saat GR diposting (`IN_PURCHASE`), Transfer dikirim (`OUT_TRANSFER`), Transfer diterima (`IN_TRANSFER`), atau Stock Opname disetujui (`ADJUSTMENT_PLUS` / `ADJUSTMENT_MINUS`).
  * Setiap perubahan saldo wajib menghasilkan baris baru pada `stock_movements` dengan invarian `qty_after = qty_before + qty_change`, di mana `qty_after` baris terakhir untuk suatu `(warehouse_id, location_id, item_id)` selalu sama dengan `inventory_balances.qty_on_hand`.
* **Perhitungan Stok Dalam Perjalanan (`qty_in_transit` — FR-03):**
  * Dihitung secara dinamis dari jumlah `stock_transfer_lines.qty` pada dokumen Transfer yang berstatus **`SHIPPED`** (belum `RECEIVED`), dialokasikan pada gudang dan lokasi **tujuan** (`destination_warehouse_id`, `destination_location_id`).
* **Imutabilitas Buku Besar (`stock_movements` — PRD 6.4 & AC-08):**
  * Tabel `stock_movements` dilindungi oleh *trigger* PostgreSQL `trg_stock_movements_immutable` (`007_append_only_guards.sql`) yang menolak `UPDATE` dan `DELETE`, serta pencabutan hak `UPDATE, DELETE, TRUNCATE` dari role database aplikasi `wms_app`.

### 2.3 Jenis Pergerakan Stok (*Movement Types* — PRD 5.3)

| `movement_type` | Pemicu | Tanda `qty_change` | `reference_type` |
| --- | --- | --- | --- |
| `IN_PURCHASE` | Goods Receipt → `POSTED` | Positif (`+`) | `GOODS_RECEIPT` |
| `OUT_TRANSFER` | Stock Transfer → `SHIPPED` | Negatif (`-`) | `STOCK_TRANSFER` |
| `IN_TRANSFER` | Stock Transfer → `RECEIVED` (`qty_received > 0`) | Positif (`+`) | `STOCK_TRANSFER` |
| `ADJUSTMENT_PLUS` | Stock Opname → `COMPLETED` (`qty_variance > 0`) | Positif (`+`) | `STOCK_OPNAME` |
| `ADJUSTMENT_MINUS` | Stock Opname → `COMPLETED` (`qty_variance < 0`) | Negatif (`-`) | `STOCK_OPNAME` |

---

## 3. Autentikasi dan Otorisasi

* **Autentikasi:** Wajib menyertakan header `Authorization: Bearer <access_token>`.
* **Permission & Warehouse Scoping (Matriks 3.1 & PRD 3.2):**

| Permission | Endpoint | Peran Bawaan (Matriks 3.1) | Warehouse Scoping `(g)` |
| --- | --- | --- | --- |
| `stock:read` | `/balances`, `/by-location`, `/by-warehouse`, `/summary` | *Super Admin*, *Warehouse Manager*, *Purchasing Staff*, *Warehouse Staff*, *Auditor* | **Ya untuk Warehouse Staff** (otomatis difilter ke gudang yang ditugaskan; meminta `warehouse_id` di luar penugasan → `403 WAREHOUSE_NOT_ASSIGNED`). Peran lain tidak dibatasi. |
| `ledger:read` | `/movements`, `/ledger` | *Super Admin*, *Warehouse Manager*, *Warehouse Staff*, *Auditor* | **Ya untuk Warehouse Staff** (otomatis difilter ke gudang yang ditugaskan; meminta `warehouse_id` di luar penugasan → `403 WAREHOUSE_NOT_ASSIGNED`). Peran lain tidak dibatasi. |

---

## 4. Ringkasan Endpoint

| # | Method | Endpoint | Fungsi | Auth | Permission |
| :-: | --- | --- | --- | --- | --- |
| 1 | GET | `/api/v1/stock/balances` | Daftar saldo stok & *in-transit* per lokasi penyimpanan (alias `/by-location`) | Bearer | `stock:read` `(g)` |
| 2 | GET | `/api/v1/stock/by-location` | Daftar saldo stok & *in-transit* per lokasi penyimpanan | Bearer | `stock:read` `(g)` |
| 3 | GET | `/api/v1/stock/by-warehouse` | Daftar saldo stok & *in-transit* diagregasi per gudang dan barang | Bearer | `stock:read` `(g)` |
| 4 | GET | `/api/v1/stock/summary` | Ringkasan saldo stok & *in-transit* diagregasi lintas gudang per barang | Bearer | `stock:read` `(g)` |
| 5 | GET | `/api/v1/stock/movements` | Daftar buku besar pergerakan stok / *Stock Movement Ledger* (alias `/ledger`) | Bearer | `ledger:read` `(g)` |
| 6 | GET | `/api/v1/stock/ledger` | Daftar buku besar pergerakan stok / *Stock Movement Ledger* | Bearer | `ledger:read` `(g)` |

---

## 5. Detail Setiap Endpoint

### 5.1 GET `/api/v1/stock/balances` & GET `/api/v1/stock/by-location` — Saldo Stok per Lokasi

Mengambil daftar saldo stok aktual (`qty_on_hand`) dan stok dalam perjalanan (`qty_in_transit`) pada tingkat `(warehouse_id, location_id, item_id)`. Kedua path memanggil handler yang sama.

* **HTTP Method & URL:** `GET /api/v1/stock/balances` atau `GET /api/v1/stock/by-location`
* **Autentikasi & Permission:** Bearer Token, `stock:read`

**Query Parameter**

| Parameter | Tipe | Wajib | Default | Aturan & Keterangan |
| --- | --- | --- | --- | --- |
| `limit` | integer | Tidak | `50` | Rentang `1..200`. |
| `offset` | integer | Tidak | `0` | Minimal `0`. |
| `warehouse_id` | integer | Tidak | `null` | Filter gudang (`403 WAREHOUSE_NOT_ASSIGNED` bila *Warehouse Staff* meminta gudang di luar penugasan). |
| `location_id` | integer | Tidak | `null` | Filter lokasi penyimpanan. |
| `item_id` | integer | Tidak | `null` | Filter ID barang. |
| `category_id` | integer | Tidak | `null` | Filter ID kategori barang. |
| `search` | string | Tidak | `null` | Pencarian `ILIKE` pada SKU atau nama barang. |
| `sort_by` | string | Tidak | `"item_id"` | Whitelist: `"warehouse_id"`, `"warehouse_code"`, `"location_id"`, `"location_code"`, `"item_id"`, `"item_sku"`, `"item_name"`, `"qty_on_hand"`, `"qty_in_transit"`. |
| `sort_dir` | string | Tidak | `"asc"` | `"asc"` atau `"desc"`. |

**Contoh Response Berhasil (`200 OK` — `Page[StockLocationBalanceOut]`)**

```json
{
  "items": [
    {
      "warehouse_id": 2,
      "warehouse_code": "WH-JKT",
      "warehouse_name": "Gudang Jakarta",
      "location_id": 7,
      "location_code": "A-01",
      "location_name": "Rak A01",
      "item_id": 17,
      "item_sku": "BRG-017",
      "item_name": "Kabel NYM",
      "category_id": 4,
      "category_name": "Kabel",
      "uom_id": 2,
      "uom_code": "MTR",
      "qty_on_hand": "80.0000",
      "qty_in_transit": "12.0000",
      "updated_at": "2026-10-23T09:15:00+07:00"
    }
  ],
  "total": 1,
  "limit": 50,
  "offset": 0
}
```

* **Kemungkinan Error:** `401 AUTH_TOKEN_INVALID`, `403 PERMISSION_DENIED`, `403 WAREHOUSE_NOT_ASSIGNED`, `422 VALIDATION_ERROR`.

---

### 5.2 GET `/api/v1/stock/by-warehouse` — Saldo Stok per Gudang

Mengambil saldo stok dan stok dalam perjalanan yang diagregasi per `(warehouse_id, item_id)` di seluruh lokasi dalam masing-masing gudang.

* **HTTP Method & URL:** `GET /api/v1/stock/by-warehouse`
* **Autentikasi & Permission:** Bearer Token, `stock:read`
* **Query Parameter:** `limit` (`1..200`, default `50`), `offset` (`>= 0`, default `0`), `warehouse_id`, `item_id`, `category_id`, `search`, `sort_by` (Whitelist: `"warehouse_id"`, `"warehouse_code"`, `"item_id"`, `"item_sku"`, `"item_name"`, `"qty_on_hand"`, `"qty_in_transit"`), `sort_dir` (`"asc"` | `"desc"`).

**Contoh Response Berhasil (`200 OK` — `Page[StockWarehouseBalanceOut]`)**

```json
{
  "items": [
    {
      "warehouse_id": 2,
      "warehouse_code": "WH-JKT",
      "warehouse_name": "Gudang Jakarta",
      "item_id": 17,
      "item_sku": "BRG-017",
      "item_name": "Kabel NYM",
      "category_id": 4,
      "category_name": "Kabel",
      "uom_id": 2,
      "uom_code": "MTR",
      "qty_on_hand": "80.0000",
      "qty_in_transit": "12.0000"
    }
  ],
  "total": 1,
  "limit": 50,
  "offset": 0
}
```

* **Kemungkinan Error:** `401 AUTH_TOKEN_INVALID`, `403 PERMISSION_DENIED`, `403 WAREHOUSE_NOT_ASSIGNED`, `422 VALIDATION_ERROR`.

---

### 5.3 GET `/api/v1/stock/summary` — Ringkasan Saldo Stok Lintas Gudang

Mengambil total saldo stok (`qty_on_hand`) dan stok dalam perjalanan (`qty_in_transit`) yang diagregasi lintas gudang per `item_id`.

* **HTTP Method & URL:** `GET /api/v1/stock/summary`
* **Autentikasi & Permission:** Bearer Token, `stock:read`
* **Query Parameter:** `limit` (`1..200`, default `50`), `offset` (`>= 0`, default `0`), `warehouse_id` (opsional — membatasi agregasi pada gudang tertentu), `item_id`, `category_id`, `search`, `sort_by` (Whitelist: `"item_id"`, `"item_sku"`, `"item_name"`, `"qty_on_hand"`, `"qty_in_transit"`), `sort_dir` (`"asc"` | `"desc"`).

**Contoh Response Berhasil (`200 OK` — `Page[StockSummaryOut]`)**

```json
{
  "items": [
    {
      "item_id": 17,
      "item_sku": "BRG-017",
      "item_name": "Kabel NYM",
      "category_id": 4,
      "category_name": "Kabel",
      "uom_id": 2,
      "uom_code": "MTR",
      "qty_on_hand": "120.0000",
      "qty_in_transit": "12.0000"
    }
  ],
  "total": 1,
  "limit": 50,
  "offset": 0
}
```

* **Kemungkinan Error:** `401 AUTH_TOKEN_INVALID`, `403 PERMISSION_DENIED`, `403 WAREHOUSE_NOT_ASSIGNED`, `422 VALIDATION_ERROR`.

---

### 5.4 GET `/api/v1/stock/ledger` & GET `/api/v1/stock/movements` — Buku Besar Pergerakan Stok

Mengambil daftar riwayat mutasi stok (`stock_movements`) secara kronologis dengan dukungan filter rentang waktu dan pagination (FR-08 & FR-11). Kedua path adalah alias untuk handler yang sama.

* **HTTP Method & URL:** `GET /api/v1/stock/ledger` atau `GET /api/v1/stock/movements`
* **Autentikasi & Permission:** Bearer Token, `ledger:read`

**Query Parameter**

| Parameter | Tipe | Wajib | Default | Aturan & Keterangan |
| --- | --- | --- | --- | --- |
| `limit` | integer | Tidak | `50` | Rentang `1..200`. |
| `offset` | integer | Tidak | `0` | Minimal `0`. |
| `warehouse_id` | integer | Tidak | `null` | Filter gudang (`403 WAREHOUSE_NOT_ASSIGNED` bila *Warehouse Staff* meminta gudang di luar penugasan). |
| `location_id` | integer | Tidak | `null` | Filter lokasi penyimpanan. |
| `item_id` | integer | Tidak | `null` | Filter ID barang. |
| `movement_type` | string | Tidak | `null` | Salah satu dari: `IN_PURCHASE`, `OUT_TRANSFER`, `IN_TRANSFER`, `ADJUSTMENT_PLUS`, `ADJUSTMENT_MINUS`. |
| `reference_type` | string | Tidak | `null` | Salah satu dari: `GOODS_RECEIPT`, `STOCK_TRANSFER`, `STOCK_OPNAME`. |
| `reference_id` | integer | Tidak | `null` | Filter ID dokumen sumber. |
| `date_from` | datetime (ISO 8601) | Tidak | `null` | Batas awal waktu mutasi (`created_at >= date_from`). |
| `date_to` | datetime (ISO 8601) | Tidak | `null` | Batas akhir waktu mutasi (`created_at <= date_to`). Tidak boleh `< date_from`. |
| `sort_by` | string | Tidak | `"id"` | Whitelist: `"id"`, `"created_at"`, `"movement_type"`, `"warehouse_id"`, `"item_id"`. |
| `sort_dir` | string | Tidak | `"desc"` | `"asc"` atau `"desc"`. |

**Contoh Response Berhasil (`200 OK` — `Page[StockMovementOut]`)**

```json
{
  "items": [
    {
      "id": 105,
      "movement_type": "IN_PURCHASE",
      "warehouse_id": 2,
      "warehouse_code": "WH-JKT",
      "warehouse_name": "Gudang Jakarta",
      "location_id": 7,
      "location_code": "A-01",
      "location_name": "Rak A01",
      "item_id": 17,
      "item_sku": "BRG-017",
      "item_name": "Kabel NYM",
      "uom_code": "MTR",
      "qty_before": "60.0000",
      "qty_change": "20.0000",
      "qty_after": "80.0000",
      "reference_type": "GOODS_RECEIPT",
      "reference_id": 31,
      "notes": null,
      "created_by": 8,
      "created_by_username": "warehouse.staff",
      "created_at": "2026-10-23T09:15:00+07:00"
    }
  ],
  "total": 1,
  "limit": 50,
  "offset": 0
}
```

* **Kemungkinan Error:** `401 AUTH_TOKEN_INVALID`, `403 PERMISSION_DENIED`, `403 WAREHOUSE_NOT_ASSIGNED`, `422 VALIDATION_ERROR`.

---

## 6. Relasi dan Ketergantungan

| Objek / Tabel | Kunci, Constraint & Indeks Utama (`003_create_inventory_tables.sql`) | Relasi & Dampak |
| --- | --- | --- |
| `inventory_balances` | `pk_inventory_balances (id)`, `uq_inventory_balances_warehouse_location_item (warehouse_id, location_id, item_id)`, `fk_inventory_balances_location_warehouse (location_id, warehouse_id)`, `ix_inventory_balances_warehouse_item`, `ix_inventory_balances_item_id` | Dibuat otomatis (`INSERT ... ON CONFLICT DO NOTHING`) dan dikunci (`SELECT ... FOR UPDATE`) oleh `inventory_service.apply_movement()`. Tidak memasang `CHECK (qty_on_hand >= 0)` di tabel karena kebijakan `allow_negative_stock` bersifat per gudang (PRD 6.1). |
| `stock_movements` | `pk_stock_movements (id)`, `fk_stock_movements_location_warehouse (location_id, warehouse_id)`, `ck_stock_movements_qty_balance (qty_after = qty_before + qty_change)`, `ck_stock_movements_direction`, `ix_stock_movements_warehouse_item_created`, `ix_stock_movements_created_at` | Bersifat *append-only* (dilindungi trigger `trg_stock_movements_immutable` pada `007_append_only_guards.sql`). Indeks komposit mendukung pembacaan cepat dengan filter gudang, barang, dan rentang tanggal (PRD 7.3). |

Alur lapisan pembacaan: `routes/stock.py` → `stock_service.py` (`access_service.resolve_read_warehouse_scope`) → `inventory_repo.py` → PostgreSQL.

---

## 7. Contoh Penggunaan (cURL)

```bash
BASE=http://localhost:8000/api/v1

# 1. Baca saldo stok per lokasi pada Gudang 2
curl -s "$BASE/stock/by-location?warehouse_id=2&limit=50" \
  -H "Authorization: Bearer <ACCESS_TOKEN>"

# 2. Baca saldo stok diagregasi per gudang untuk kategori tertentu
curl -s "$BASE/stock/by-warehouse?warehouse_id=2&category_id=4&sort_by=qty_on_hand&sort_dir=desc" \
  -H "Authorization: Bearer <ACCESS_TOKEN>"

# 3. Baca ringkasan stok lintas gudang dengan pencarian SKU/nama barang
curl -s "$BASE/stock/summary?search=BRG-017" \
  -H "Authorization: Bearer <ACCESS_TOKEN>"

# 4. Baca Stock Movement Ledger dengan filter gudang dan rentang tanggal
curl -s "$BASE/stock/ledger?warehouse_id=2&date_from=2026-10-01T00:00:00Z&date_to=2026-10-31T23:59:59Z&limit=50" \
  -H "Authorization: Bearer <ACCESS_TOKEN>"
```

---

## 8. Catatan dan Status Verifikasi

| # | Status | Catatan |
| --- | --- | --- |
| 1 | ✅ Terverifikasi | Konkurensi penguncian baris pada `inventory_service.apply_movement()`, tampilan saldo per lokasi/gudang/summary, perhitungan `qty_in_transit`, pembacaan ledger, serta *Warehouse Scoping* untuk *Warehouse Staff* telah diuji di `test_m4_inventory_apply_movement_concurrency_stock_views_and_ledger` (`tests/test_rbac_scoping.py`). |
| 2 | ✅ Terverifikasi | Imutabilitas tabel `stock_movements` terhadap operasi `UPDATE` dan `DELETE` (baik oleh role aplikasi `wms_app` maupun pemilik tabel) telah diuji di `test_ac08_immutability_stock_movements_and_audit_logs` (`tests/test_immutability.py` — **AC-08**). |
| 3 | ✅ Terverifikasi | Benchmark lokal M8 menggunakan `EXPLAIN ANALYZE` pada 10.000 baris saldo/barang dan 1.000.000 baris `stock_movements` mencatat waktu eksekusi di bawah target 200 ms (`5,550 ms` untuk halaman saldo per lokasi, `0,105 ms` untuk halaman ledger 50 baris, dan `122,527 ms` untuk hitung ledger rentang 30 hari setelah `VACUUM (ANALYZE)`). |
