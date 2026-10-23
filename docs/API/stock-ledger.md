# Stok & Buku Besar Pergerakan Stok

## 1. Informasi Umum

| Atribut | Keterangan |
| --- | --- |
| **Modul** | Saldo Stok (*inventory balance*) dan Buku Besar Pergerakan Stok (*Stock Movement Ledger*) |
| **Base path** | `/api/v1/stock` |
| **Rujukan PRD** | FR-03, FR-08, FR-11, Bagian 3.1, 3.2, 5.3, 6.1, 6.4, 7.3, 7.4, Lampiran A & B |
| **Status** | Sudah diimplementasikan; saldo, ledger, dan scoping baca dicakup oleh `test_m4_inventory_apply_movement_concurrency_stock_views_and_ledger` di `tests/test_rbac_scoping.py`. |
| **Kode sumber** | [stock.py](../../app/api/routes/stock.py), [stock_service.py](../../app/services/stock_service.py), [inventory_repo.py](../../app/repositories/inventory_repo.py), [stock.py schema](../../app/schemas/stock.py) |
| **Tabel terkait** | `inventory_balances`, `stock_movements`, `stock_transfers`, `stock_transfer_lines`, `items`, `categories`, `uoms`, `warehouses`, `storage_locations`, `users` |
| **Modul terkait** | [Goods Receipt](goods-receipts.md), [Transfer Stok](stock-transfers.md), [Stock Opname](stock-opnames.md), [Gudang & Lokasi](warehouses.md) |

Modul ini hanya menyediakan pembacaan saldo dan ledger. Saldo aktual dibaca dari `inventory_balances`; barang dalam perjalanan dihitung dari baris Transfer berstatus `SHIPPED` dan dihitung pada gudang/lokasi tujuan. Perubahan saldo dilakukan oleh aksi operasional GR, Transfer, dan Opname, lalu dicatat sebagai pergerakan ledger.

Kuantitas dikirim sebagai string desimal dengan empat tempat, misalnya `"12.5000"`. Semua endpoint memakai pagination dengan `limit` bawaan 50, maksimum 200, dan `offset` bawaan 0.

## 2. Autentikasi, Permission, dan Warehouse Scoping

Semua endpoint memerlukan `Authorization: Bearer <access_token>`.

| Permission | Endpoint | Peran bawaan menurut Matriks 3.1 |
| --- | --- | --- |
| `stock:read` | Pembacaan saldo | Super Admin, Warehouse Manager, Purchasing Staff, Warehouse Staff, Auditor |
| `ledger:read` | Pembacaan ledger | Super Admin, Warehouse Manager, Warehouse Staff, Auditor |

Warehouse Staff hanya melihat saldo dan ledger di gudang yang ditugaskan. Tanpa `warehouse_id`, hasil dibatasi otomatis ke gudang tugasnya. Bila meminta `warehouse_id` di luar penugasan, API mengembalikan `403 WAREHOUSE_NOT_ASSIGNED`. Peran baca lain tidak dibatasi gudang. Permission diperiksa pada route, sedangkan scoping diterapkan service.

## 3. Ringkasan Endpoint

| Method | Endpoint | Fungsi | Permission |
| --- | --- | --- | --- |
| GET | `/api/v1/stock/balances` | Saldo per lokasi (alias `/by-location`) | `stock:read` |
| GET | `/api/v1/stock/by-location` | Saldo per lokasi | `stock:read` |
| GET | `/api/v1/stock/by-warehouse` | Saldo diagregasi per gudang dan barang | `stock:read` |
| GET | `/api/v1/stock/summary` | Saldo diagregasi lintas gudang per barang | `stock:read` |
| GET | `/api/v1/stock/movements` | Daftar pergerakan stok (alias `/ledger`) | `ledger:read` |
| GET | `/api/v1/stock/ledger` | Daftar ledger | `ledger:read` |

Alias pada baris pertama dan terakhir mengembalikan response dan menerima parameter yang sama.

## 4. Endpoint Saldo Stok

Ketiga bentuk tampilan saldo mengembalikan `200 OK` dengan format pagination:

```json
{
  "items": [],
  "total": 0,
  "limit": 50,
  "offset": 0
}
```

### 4.1 Parameter bersama

| Parameter | Tipe | Wajib | Default | Keterangan |
| --- | --- | --- | --- | --- |
| `limit` | integer | Tidak | `50` | Rentang `1..200`. |
| `offset` | integer | Tidak | `0` | Minimal `0`. |
| `warehouse_id` | integer | Tidak | – | Filter gudang. Warehouse Staff harus ditugaskan ke gudang tersebut. |
| `item_id` | integer | Tidak | – | Filter barang. |
| `category_id` | integer | Tidak | – | Filter kategori barang. |
| `search` | string | Tidak | – | Pencarian tidak peka huruf besar/kecil pada SKU atau nama barang. |
| `sort_by` | string | Tidak | endpoint-specific | Kolom pengurutan diambil dari whitelist per endpoint. |
| `sort_dir` | string | Tidak | `asc` | Arah `asc` atau `desc`. |

Jika `sort_by` tidak diberikan, urutan bawaan adalah ID barang menaik.

### 4.2 `GET /api/v1/stock/balances` dan `GET /api/v1/stock/by-location`

Saldo per kombinasi gudang, lokasi, dan barang. Selain parameter bersama, tersedia `location_id` untuk membatasi hasil ke lokasi tertentu.

Whitelist `sort_by`: `warehouse_id`, `warehouse_code`, `location_id`, `location_code`, `item_id`, `item_sku`, `item_name`, `qty_on_hand`, `qty_in_transit`.

Field setiap item (`StockLocationBalanceOut`):

| Field | Tipe JSON | Keterangan |
| --- | --- | --- |
| `warehouse_id`, `location_id`, `item_id`, `category_id`, `uom_id` | integer | Identitas gudang, lokasi, barang, kategori, dan UoM. |
| `warehouse_code`, `warehouse_name`, `location_code`, `location_name` | string | Identitas yang dapat dibaca untuk gudang dan lokasi. |
| `item_sku`, `item_name`, `category_name`, `uom_code` | string | Identitas barang, kategori, dan satuan dasar. |
| `qty_on_hand` | string desimal | Saldo aktual pada lokasi. |
| `qty_in_transit` | string desimal | Kuantitas Transfer berstatus `SHIPPED` menuju lokasi ini. |
| `updated_at` | datetime atau `null` | Waktu saldo terakhir berubah; dapat `null` bila baris hanya muncul karena barang dalam perjalanan. |

Contoh item:

```json
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
```

### 4.3 `GET /api/v1/stock/by-warehouse`

Menggabungkan saldo dari seluruh lokasi dalam setiap gudang, per barang. `qty_in_transit` dijumlahkan untuk Transfer yang menuju gudang tersebut. Menerima parameter bersama kecuali `location_id`.

Whitelist `sort_by`: `warehouse_id`, `warehouse_code`, `item_id`, `item_sku`, `item_name`, `qty_on_hand`, `qty_in_transit`.

Setiap item (`StockWarehouseBalanceOut`) memuat `warehouse_id`, `warehouse_code`, `warehouse_name`, `item_id`, `item_sku`, `item_name`, `category_id`, `category_name`, `uom_id`, `uom_code`, `qty_on_hand`, dan `qty_in_transit`.

### 4.4 `GET /api/v1/stock/summary`

Menjumlahkan saldo dan barang dalam perjalanan lintas gudang per barang. Bila `warehouse_id` dikirim, kedua jumlah dibatasi pada gudang tersebut. Menerima parameter bersama kecuali `location_id`.

Whitelist `sort_by`: `item_id`, `item_sku`, `item_name`, `qty_on_hand`, `qty_in_transit`.

Setiap item (`StockSummaryOut`) memuat `item_id`, `item_sku`, `item_name`, `category_id`, `category_name`, `uom_id`, `uom_code`, `qty_on_hand`, dan `qty_in_transit`.

Contoh pemanggilan:

```http
GET /api/v1/stock/by-warehouse?warehouse_id=2&category_id=4&limit=25&sort_by=qty_on_hand&sort_dir=desc
Authorization: Bearer <ACCESS_TOKEN>
```

Baris hasil berasal dari saldo yang tersedia atau Transfer aktif berstatus `SHIPPED`; barang tanpa saldo dan tanpa barang dalam perjalanan tidak muncul sebagai baris nol.

## 5. Buku Besar Pergerakan Stok

### `GET /api/v1/stock/ledger` dan `GET /api/v1/stock/movements`

Kedua path adalah alias untuk daftar ledger yang sama. Endpoint memerlukan `ledger:read` dan mengembalikan `200 OK` dalam format pagination. Filter waktu mendukung rentang; `date_from` tidak boleh lebih besar dari `date_to`. Pagination tetap berlaku, dengan maksimum 200 baris per halaman.

| Parameter | Tipe | Wajib | Default | Keterangan |
| --- | --- | --- | --- | --- |
| `limit` | integer | Tidak | `50` | Rentang `1..200`. |
| `offset` | integer | Tidak | `0` | Minimal `0`. |
| `warehouse_id` | integer | Tidak | – | Filter gudang; diterapkan juga untuk warehouse scoping. |
| `location_id` | integer | Tidak | – | Filter lokasi. |
| `item_id` | integer | Tidak | – | Filter barang. |
| `movement_type` | string | Tidak | – | Salah satu tipe pada Bagian 6. |
| `reference_type` | string | Tidak | – | Salah satu tipe referensi pada Bagian 6. |
| `reference_id` | integer | Tidak | – | ID dokumen sumber. |
| `date_from` | datetime | Tidak | – | Batas awal inklusif, `created_at >= date_from`; kirim ISO 8601 dengan zona waktu. |
| `date_to` | datetime | Tidak | – | Batas akhir inklusif, `created_at <= date_to`; kirim ISO 8601 dengan zona waktu. |
| `sort_by` | string | Tidak | `id` | Whitelist: `id`, `created_at`, `movement_type`, `warehouse_id`, `item_id`. |
| `sort_dir` | string | Tidak | `desc` | Arah `asc` atau `desc`. |

Urutan bawaan adalah `id DESC`. Tipe pergerakan yang diterima: `IN_PURCHASE`, `OUT_TRANSFER`, `IN_TRANSFER`, `ADJUSTMENT_PLUS`, `ADJUSTMENT_MINUS`. Tipe referensi: `GOODS_RECEIPT`, `STOCK_TRANSFER`, `STOCK_OPNAME`.

Setiap item (`StockMovementOut`) memuat `id`, `movement_type`, `warehouse_id`, `warehouse_code`, `warehouse_name`, `location_id`, `location_code`, `location_name`, `item_id`, `item_sku`, `item_name`, `uom_code`, `qty_before`, `qty_change`, `qty_after`, `reference_type`, `reference_id`, `notes`, `created_by`, `created_by_username`, dan `created_at`.

Contoh request:

```http
GET /api/v1/stock/ledger?warehouse_id=2&item_id=17&date_from=2026-10-01T00:00:00%2B07:00&date_to=2026-10-31T23:59:59%2B07:00&limit=50
Authorization: Bearer <ACCESS_TOKEN>
```

Contoh response:

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

Ledger adalah append-only dan hanya dibaca melalui endpoint ini. Pergerakan mengikuti invariant `qty_after = qty_before + qty_change`; jumlah positif menambah saldo dan jumlah negatif mengurangi saldo. Endpoint ini tidak menyediakan operasi penulisan, pembaruan, atau penghapusan.

## 6. Jenis Pergerakan

| `movement_type` | Pemicu | Arah `qty_change` | `reference_type` |
| --- | --- | --- | --- |
| `IN_PURCHASE` | GR diposting | Positif | `GOODS_RECEIPT` |
| `OUT_TRANSFER` | Transfer dikirim (`SHIPPED`) | Negatif | `STOCK_TRANSFER` |
| `IN_TRANSFER` | Transfer diterima (`RECEIVED`) | Positif | `STOCK_TRANSFER` |
| `ADJUSTMENT_PLUS` | Opname selesai, selisih positif | Positif | `STOCK_OPNAME` |
| `ADJUSTMENT_MINUS` | Opname selesai, selisih negatif | Negatif | `STOCK_OPNAME` |

Penerimaan Transfer dengan selisih hanya menambah stok tujuan sebesar kuantitas yang diterima; selisih tidak menghasilkan baris ledger tambahan. Lihat dokumentasi atau endpoint Transfer untuk detail siklusnya.

## 7. Error

Error memakai format umum `{ "error": { "code", "message", "details" } }`.

| HTTP | Kode | Kondisi umum |
| ---: | --- | --- |
| `401` | `AUTH_TOKEN_INVALID` | Token tidak ada atau tidak valid. |
| `403` | `PERMISSION_DENIED` | Tidak memiliki `stock:read` atau `ledger:read`. |
| `403` | `WAREHOUSE_NOT_ASSIGNED` | Warehouse Staff meminta gudang di luar penugasan. |
| `422` | `VALIDATION_ERROR` | Pagination/sorting salah, tanggal tidak valid/terbalik, atau tipe pergerakan/referensi tidak dikenal. |

## 8. Catatan Implementasi & Verifikasi

Tipe kuantitas response menggunakan `DecimalStr` agar presisi tetap terjaga pada JSON. Query ledger menggunakan pagination dan filter tanggal sesuai FR-11. Indeks stok dan ledger dibuat pada migrasi `003_create_inventory_tables.sql`; pemeriksaan M8 pada data benchmark 10.000 saldo dan 1.000.000 baris ledger dicatat di [ringkasan dokumentasi API](README.md#4-ringkasan-status-verifikasi--perbaikan-temuan).

Pembacaan dan scoping saldo/ledger diuji oleh `test_m4_inventory_apply_movement_concurrency_stock_views_and_ledger` di `tests/test_rbac_scoping.py`. Perilaku mutasi dan konsistensi ledger juga diliputi test AC GR, Transfer, Opname, dan imutabilitas.
