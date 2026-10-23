# Purchase Order (PO)

## 1. Informasi Umum

| Atribut | Keterangan |
| --- | --- |
| **Modul** | Purchase Order / Pesanan Pembelian |
| **Base path** | `/api/v1/purchase-orders` |
| **Rujukan PRD** | FR-04, FR-10, FR-11, Bagian 3.1, 5.1, 6.2, 6.3, 6.9, 8 (AC-01, AC-05, AC-12), Lampiran A & B |
| **Status** | Sudah diimplementasikan; siklus PO diuji di `tests/test_goods_receipt.py`, penerimaan parsial diuji pada AC-01. |
| **Kode sumber** | [purchase_orders.py](../../app/api/routes/purchase_orders.py), [po_service.py](../../app/services/po_service.py), [po_repo.py](../../app/repositories/po_repo.py), [purchase_order.py](../../app/schemas/purchase_order.py) |
| **Tabel terkait** | `purchase_orders`, `po_lines`, `suppliers`, `warehouses`, `items`, `uoms`, `goods_receipts`, `audit_logs`, `document_sequences` |
| **Modul terkait** | [Goods Receipt](goods-receipts.md), [Master Data](master-data.md), [Gudang & Lokasi](warehouses.md), [Audit Log](audit-logs.md) |

PO mencatat pemasok, gudang tujuan, tanggal pemesanan, catatan, dan baris barang. PO dibuat sebagai `DRAFT`; setelah diterbitkan, barang dapat diterima melalui Goods Receipt (GR). Posting GR memperbarui `qty_received` dan status PO secara otomatis.

## 2. Autentikasi dan Otorisasi

Semua endpoint memerlukan `Authorization: Bearer <access_token>`.

| Permission | Aksi | Peran bawaan menurut Matriks 3.1 |
| --- | --- | --- |
| `po:read` | Daftar dan baca detail PO | Super Admin, Warehouse Manager, Purchasing Staff, Warehouse Staff, Auditor |
| `po:create` | Buat/revisi PO `DRAFT`; batalkan PO `DRAFT` | Super Admin, Purchasing Staff |
| `po:issue` | Terbitkan PO | Super Admin, Purchasing Staff |
| `po:cancel` | Batalkan PO `ISSUED` | Super Admin, Purchasing Staff |
| `po:close` | Tutup PO | Super Admin, Warehouse Manager, Purchasing Staff |

Warehouse Staff hanya dapat membaca PO pada gudang yang ditugaskan. Daftar otomatis dibatasi; detail PO di gudang lain ditolak dengan `403 WAREHOUSE_NOT_ASSIGNED`. Pembacaan oleh peran lain tidak dibatasi penugasan. Aksi tulis PO tidak memakai warehouse scoping pada Matriks 3.1.

Endpoint pembatalan menerima `po:create` untuk PO `DRAFT` atau `po:cancel` untuk PO `ISSUED`. Service memeriksa permission yang sesuai status dokumen.

## 3. Siklus Status

| Status saat ini | Pemicu | Status berikutnya | Ketentuan |
| --- | --- | --- | --- |
| Baru | Buat PO | `DRAFT` | Pemasok dan gudang tujuan aktif. Baris boleh kosong saat penyusunan. |
| `DRAFT` | Terbitkan PO | `ISSUED` | Minimal satu baris; barang aktif dan kuantitas valid. |
| `DRAFT` | Batalkan PO | `CANCELLED` | Permission `po:create`. |
| `ISSUED` | Posting GR | `PARTIALLY_RECEIVED` | Sebagian kuantitas diterima dan masih ada sisa. |
| `ISSUED` atau `PARTIALLY_RECEIVED` | Posting GR | `RECEIVED` | Seluruh kuantitas PO telah diterima. |
| `ISSUED` | Batalkan PO | `CANCELLED` | Permission `po:cancel`; tidak boleh ada GR `DRAFT` atau `POSTED`. |
| `ISSUED` atau `PARTIALLY_RECEIVED` | Tutup PO | `CLOSED` | Permission `po:close`; tidak boleh ada GR `DRAFT`; alasan wajib. |

Status tidak dapat diubah melalui `PATCH`. Transisi yang tidak diizinkan menghasilkan `409 INVALID_STATE_TRANSITION`. `RECEIVED`, `CLOSED`, dan `CANCELLED` adalah status akhir. PO `PARTIALLY_RECEIVED` tidak dapat dibatalkan, tetapi dapat ditutup bila sisa pesanan tidak dilanjutkan.

Penerimaan barang dan aturan *over-receipt* dilakukan melalui endpoint GR. Hanya GR `POSTED` yang menambah `qty_received`; jumlah kumulatif tidak boleh melampaui `qty_ordered`.

## 4. Ringkasan Endpoint

| Method | Endpoint | Fungsi | Permission |
| --- | --- | --- | --- |
| GET | `/api/v1/purchase-orders` | Daftar dan filter PO | `po:read` |
| POST | `/api/v1/purchase-orders` | Buat PO `DRAFT` | `po:create` |
| GET | `/api/v1/purchase-orders/{po_id}` | Baca PO dan barisnya | `po:read` |
| PATCH | `/api/v1/purchase-orders/{po_id}` | Revisi PO `DRAFT` | `po:create` |
| POST | `/api/v1/purchase-orders/{po_id}/issue` | Terbitkan PO | `po:issue` |
| POST | `/api/v1/purchase-orders/{po_id}/cancel` | Batalkan PO sesuai status | `po:create` atau `po:cancel` |
| POST | `/api/v1/purchase-orders/{po_id}/close` | Tutup PO | `po:close` |

## 5. Detail Endpoint

### 5.1 `GET /api/v1/purchase-orders` — Daftar PO

| Parameter | Tipe | Wajib | Default | Aturan |
| --- | --- | --- | --- | --- |
| `limit` | integer | Tidak | `50` | `1..200`. |
| `offset` | integer | Tidak | `0` | Minimal `0`. |
| `warehouse_id` | integer | Tidak | – | Filter gudang tujuan; Warehouse Staff hanya dapat meminta gudang yang ditugaskan. |
| `supplier_id` | integer | Tidak | – | Filter pemasok. |
| `status` | string | Tidak | – | Salah satu status pada Bagian 3. |
| `date_from`, `date_to` | date | Tidak | – | Filter tanggal pemesanan dalam format `YYYY-MM-DD`; tanggal awal tidak boleh melewati tanggal akhir. |
| `search` | string | Tidak | – | Pencarian pada nomor PO, kode/nama pemasok, atau catatan. |
| `sort_by` | string | Tidak | `id` | Whitelist: `id`, `po_number`, `order_date`, `status`, `created_at`. |
| `sort_dir` | string | Tidak | `desc` | `asc` atau `desc`. |

Urutan bawaan adalah `id DESC`. Response berbentuk `Page[PurchaseOrderSummaryOut]`; item daftar tidak menyertakan `lines`.

```json
{
  "items": [
    {
      "id": 14,
      "po_number": "PO-202610-0014",
      "supplier_id": 3,
      "supplier_code": "SUP-001",
      "supplier_name": "PT Sumber Jaya",
      "warehouse_id": 2,
      "warehouse_code": "WH-JKT",
      "warehouse_name": "Gudang Jakarta",
      "status": "ISSUED",
      "order_date": "2026-10-23",
      "notes": "Pengadaan Oktober",
      "line_count": 1,
      "issued_at": "2026-10-23T09:15:00+07:00",
      "issued_by": 8,
      "closed_reason": null,
      "closed_at": null,
      "closed_by": null,
      "created_by": 8,
      "created_at": "2026-10-23T09:00:00+07:00",
      "updated_at": "2026-10-23T09:15:00+07:00"
    }
  ],
  "total": 1,
  "limit": 50,
  "offset": 0
}
```

### 5.2 `POST /api/v1/purchase-orders` — Buat PO

Body:

| Field | Tipe | Wajib | Aturan |
| --- | --- | --- | --- |
| `supplier_id` | integer | Ya | Pemasok harus ada dan aktif. |
| `warehouse_id` | integer | Ya | Gudang tujuan harus ada dan aktif. |
| `order_date` | date | Ya | Format `YYYY-MM-DD`; bulan tanggal ini dipakai pada nomor PO. |
| `notes` | string atau `null` | Tidak | Catatan header; string kosong dinormalisasi menjadi `null`. |
| `lines` | array | Tidak | Bawaan `[]`; PO kosong dapat disimpan sebagai `DRAFT`, tetapi tidak dapat diterbitkan. |

Setiap baris menerima `item_id` (integer), `qty_ordered` (string desimal atau integer), dan `notes` (string/null). Barang harus ada dan aktif; barang yang sama tidak boleh muncul lebih dari sekali pada satu PO. Kuantitas harus lebih dari nol dan maksimal empat tempat desimal. Float JSON ditolak. Bila UoM barang memiliki `allow_decimal: false`, kuantitas harus bilangan bulat.

Contoh:

```http
POST /api/v1/purchase-orders
Authorization: Bearer <ACCESS_TOKEN>
Content-Type: application/json
```

```json
{
  "supplier_id": 3,
  "warehouse_id": 2,
  "order_date": "2026-10-23",
  "notes": "Pengadaan Oktober",
  "lines": [
    {"item_id": 17, "qty_ordered": "25", "notes": "Kirim utuh bila tersedia"},
    {"item_id": 21, "qty_ordered": "12.5000"}
  ]
}
```

Response `201 Created`, tipe `PurchaseOrderOut`, status awal `DRAFT`. Nomor dibuat server dengan format `PO-YYYYMM-NNNN`, unik, dan tidak digunakan ulang setelah pembatalan. Nilai kuantitas response berupa string desimal empat tempat, misalnya `"25.0000"`.

### 5.3 `GET /api/v1/purchase-orders/{po_id}` — Detail PO

Response `200 OK`, tipe `PurchaseOrderOut`: field ringkasan ditambah array `lines`. Setiap baris memuat `id`, `po_id`, `item_id`, `item_sku`, `item_name`, `uom_id`, `uom_code`, `allow_decimal`, `qty_ordered`, `qty_received`, `notes`, `created_by`, `created_at`, dan `updated_at`. ID yang tidak ditemukan menghasilkan `404 NOT_FOUND`; Warehouse Staff yang tidak ditugaskan menghasilkan `403 WAREHOUSE_NOT_ASSIGNED`.

### 5.4 `PATCH /api/v1/purchase-orders/{po_id}` — Revisi PO

Semua field berikut opsional: `supplier_id`, `warehouse_id`, `order_date`, `notes`, dan `lines`. Field yang dihilangkan tidak berubah. Jika `lines` dikirim, seluruh baris diganti dengan array tersebut; `[]` menghapus semua baris selama PO masih `DRAFT`. Gunakan string kosong untuk mengosongkan catatan; nilai `null` berarti tidak mengubahnya.

Referensi aktif, duplikasi barang, presisi kuantitas, dan aturan UoM divalidasi seperti pada pembuatan. Berhasil menghasilkan `200 OK` dengan detail PO terbaru. PO selain `DRAFT` ditolak dengan `409 INVALID_STATE_TRANSITION`.

### 5.5 `POST /api/v1/purchase-orders/{po_id}/issue` — Terbitkan PO

Tanpa body. Hanya `DRAFT → ISSUED`. Sistem memvalidasi kembali pemasok dan gudang aktif, minimal satu baris, status aktif barang, kuantitas, serta aturan UoM. Berhasil menghasilkan `200 OK` dengan `issued_at`, `issued_by`, dan status `ISSUED`. PO kosong atau baris tidak valid menghasilkan `422 VALIDATION_ERROR`; referensi tidak aktif menghasilkan `422 INACTIVE_REFERENCE`.

### 5.6 `POST /api/v1/purchase-orders/{po_id}/cancel` — Batalkan PO

Tanpa body. PO `DRAFT` dibatalkan dengan `po:create`. PO `ISSUED` dibatalkan dengan `po:cancel` hanya bila tidak memiliki GR `DRAFT` maupun `POSTED`. Status lain atau GR penghalang menghasilkan `409 INVALID_STATE_TRANSITION`. Berhasil menghasilkan `200 OK` dengan status `CANCELLED`.

### 5.7 `POST /api/v1/purchase-orders/{po_id}/close` — Tutup PO

Wajib permission `po:close`. Hanya PO `ISSUED` atau `PARTIALLY_RECEIVED` tanpa GR `DRAFT` yang dapat ditutup. GR `POSTED` tidak menghalangi penutupan. Alasan wajib tidak kosong setelah spasi tepi dihapus.

```json
{"closed_reason": "Sisa pesanan tidak dilanjutkan sesuai kesepakatan pemasok"}
```

Berhasil menghasilkan `200 OK` dengan status `CLOSED`, `closed_reason`, `closed_at`, dan `closed_by`.

## 6. Field Response

### `PurchaseOrderSummaryOut`

Mencakup `id`, `po_number`, `supplier_id`, `supplier_code`, `supplier_name`, `warehouse_id`, `warehouse_code`, `warehouse_name`, `status`, `order_date`, `notes`, `line_count`, `issued_at`, `issued_by`, `closed_reason`, `closed_at`, `closed_by`, `created_by`, `created_at`, dan `updated_at`. Field waktu bertipe ISO 8601 dengan zona waktu; field yang belum berlaku bernilai `null`.

### `POLineOut`

Mencakup `id`, `po_id`, `item_id`, `item_sku`, `item_name`, `uom_id`, `uom_code`, `allow_decimal`, `qty_ordered`, `qty_received`, `notes`, `created_by`, `created_at`, dan `updated_at`. Kuantitas diserialisasi sebagai string desimal empat tempat.

## 7. Error

Error mengikuti format umum `{ "error": { "code", "message", "details" } }`.

| HTTP | Kode | Kondisi umum |
| ---: | --- | --- |
| `401` | `AUTH_TOKEN_INVALID` | Token tidak ada atau tidak valid. |
| `403` | `PERMISSION_DENIED` | Permission tidak cukup; termasuk permission yang salah untuk membatalkan sesuai status PO. |
| `403` | `WAREHOUSE_NOT_ASSIGNED` | Warehouse Staff membaca PO di luar penugasan. |
| `404` | `NOT_FOUND` | PO, pemasok, gudang, atau barang tidak ditemukan. |
| `409` | `INVALID_STATE_TRANSITION` | Revisi/aksi status tidak sesuai status PO atau terhalang GR. |
| `422` | `INACTIVE_REFERENCE` | Pemasok, gudang, atau barang tidak aktif. |
| `422` | `VALIDATION_ERROR` | Payload/filter/pagination tidak valid, duplikasi barang, kuantitas tidak valid, PO tanpa baris diterbitkan, atau alasan tutup kosong. |

## 8. Audit dan Pengujian

Pembuatan, revisi, penerbitan, pembatalan, dan penutupan dicatat pada `audit_logs` dengan aksi `PO_CREATED`, `PO_UPDATED`, `PO_ISSUED`, `PO_CANCELLED`, dan `PO_CLOSED`. Siklus PO, validasi, hak akses, warehouse scoping baca, serta audit diuji oleh `test_purchase_order_lifecycle_validations_rbac_and_audit`. Penerimaan parsial, over-receipt, dan pemenuhan PO diuji oleh `test_ac01_partial_receipt_over_receipt_and_po_fulfillment` (**AC-01**).
