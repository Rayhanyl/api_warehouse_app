# Goods Receipt (GR)

## 1. Informasi Umum

| Atribut | Keterangan |
| --- | --- |
| **Modul** | Goods Receipt / Penerimaan Barang dari Purchase Order |
| **Base path** | `/api/v1/goods-receipts` |
| **Rujukan PRD** | FR-05, Bagian 3.1, 3.2, 5.1, 6.2, 6.5, 6.6, 6.9, 8 (AC-01, AC-07, AC-12, AC-13), Lampiran A & B |
| **Status** | Sudah diimplementasikan; siklus, over-receipt, atomicity, scoping, dan konkurensi dicakup oleh test pada Bagian 8. |
| **Kode sumber** | [goods_receipts.py](../../app/api/routes/goods_receipts.py), [gr_service.py](../../app/services/gr_service.py), [gr_repo.py](../../app/repositories/gr_repo.py), [goods_receipt.py](../../app/schemas/goods_receipt.py) |
| **Modul terkait** | [Purchase Order](purchase-orders.md), [Stok & Buku Besar](stock-ledger.md), [Gudang & Lokasi](warehouses.md) |

GR mencatat jumlah barang yang diterima terhadap PO berstatus `ISSUED` atau `PARTIALLY_RECEIVED`. GR dibuat sebagai `DRAFT`; hanya aksi posting yang menambah saldo, mencatat ledger `IN_PURCHASE`, dan memperbarui kuantitas/status PO. Dokumen yang sudah `POSTED` tidak dapat direvisi atau dibatalkan.

## 2. Autentikasi, Permission, dan Scoping

Semua endpoint memerlukan `Authorization: Bearer <access_token>`.

| Permission | Aksi | Peran bawaan menurut Matriks 3.1 |
| --- | --- | --- |
| `gr:read` | Daftar dan baca detail GR | Super Admin, Warehouse Manager, Purchasing Staff, Warehouse Staff, Auditor |
| `gr:manage` | Buat, revisi, posting, atau batalkan GR | Super Admin, Warehouse Staff |

Warehouse Staff hanya dapat membaca GR pada gudang yang ditugaskan. Daftar otomatis dibatasi; detail dan semua aksi tulis memeriksa penugasan ke gudang PO. GR selalu memakai gudang tujuan yang tercatat di PO.

## 3. Siklus Status

| Status saat ini | Aksi | Status berikutnya | Ketentuan |
| --- | --- | --- | --- |
| Baru | Buat GR | `DRAFT` | PO harus `ISSUED` atau `PARTIALLY_RECEIVED`; baris boleh kosong saat penyusunan. |
| `DRAFT` | Revisi | `DRAFT` | PO terkait tetap dapat menerima barang. |
| `DRAFT` | Posting | `POSTED` | Minimal satu baris; PO dan baris PO dikunci, batas penerimaan dihitung ulang, lokasi aktif dan tidak dibekukan. |
| `DRAFT` | Batalkan | `CANCELLED` | Tidak ada mutasi stok. |

Status selain `DRAFT` tidak dapat diposting, direvisi, atau dibatalkan. Posting GR memperbarui status PO menjadi `PARTIALLY_RECEIVED` atau `RECEIVED` sesuai jumlah kumulatif. Kuantitas penerimaan kumulatif per baris PO tidak boleh melebihi kuantitas pesanan; hanya GR `POSTED` yang diperhitungkan. Seluruh perubahan posting berada dalam satu transaksi.

## 4. Ringkasan Endpoint

| Method | Endpoint | Fungsi | Permission |
| --- | --- | --- | --- |
| GET | `/api/v1/goods-receipts` | Daftar dan filter GR | `gr:read` |
| POST | `/api/v1/goods-receipts` | Buat GR `DRAFT` | `gr:manage` |
| GET | `/api/v1/goods-receipts/{gr_id}` | Baca GR dan barisnya | `gr:read` |
| PATCH | `/api/v1/goods-receipts/{gr_id}` | Revisi GR `DRAFT` | `gr:manage` |
| POST | `/api/v1/goods-receipts/{gr_id}/post` | Posting penerimaan | `gr:manage` |
| POST | `/api/v1/goods-receipts/{gr_id}/cancel` | Batalkan GR `DRAFT` | `gr:manage` |

## 5. Detail Endpoint

### 5.1 `GET /api/v1/goods-receipts` — Daftar GR

| Parameter | Tipe | Wajib | Default | Aturan |
| --- | --- | --- | --- | --- |
| `limit` | integer | Tidak | `50` | Rentang `1..200`. |
| `offset` | integer | Tidak | `0` | Minimal `0`. |
| `warehouse_id` | integer | Tidak | — | Filter gudang PO; Warehouse Staff hanya dapat meminta gudang tugasnya. |
| `po_id` | integer | Tidak | — | Filter berdasarkan PO. |
| `status` | string | Tidak | — | `DRAFT`, `POSTED`, atau `CANCELLED`. |
| `date_from`, `date_to` | date | Tidak | — | Filter `received_date`, format `YYYY-MM-DD`; tanggal awal tidak boleh melewati tanggal akhir. |
| `search` | string | Tidak | — | Pencarian nomor GR, PO, pemasok, atau catatan. |
| `sort_by` | string | Tidak | `id` | Whitelist: `id`, `gr_number`, `received_date`, `status`, `created_at`. |
| `sort_dir` | string | Tidak | `desc` | `asc` atau `desc`. |

Response `200 OK` berbentuk `Page[GoodsReceiptSummaryOut]` dengan `items`, `total`, `limit`, dan `offset`. Urutan bawaan `id DESC`; item list tidak memuat array `lines`.

### 5.2 `POST /api/v1/goods-receipts` — Buat GR

Body:

| Field | Tipe | Wajib | Aturan |
| --- | --- | --- | --- |
| `po_id` | integer | Ya | PO harus ada, aktif gudangnya, dan berstatus `ISSUED` atau `PARTIALLY_RECEIVED`. |
| `received_date` | date | Ya | Format `YYYY-MM-DD`; bulan tanggal menjadi bagian nomor GR. |
| `notes` | string atau `null` | Tidak | Catatan header; teks kosong dinormalisasi menjadi `null`. |
| `lines` | array | Tidak | Bawaan `[]`; GR kosong dapat disimpan, tetapi tidak dapat diposting. |

Setiap baris berisi `po_line_id`, `location_id`, `qty_received`, dan `notes` opsional. Baris PO harus termasuk dalam PO tersebut; lokasi harus aktif dan berada pada gudang PO. Kombinasi `po_line_id` dan `location_id` tidak boleh berulang di GR yang sama. Kuantitas harus positif, maksimal empat angka desimal, dan dikirim sebagai string desimal atau integer (float ditolak). Untuk barang dengan `allow_decimal: false`, jumlah harus bulat. Batas over-receipt diperiksa saat penyimpanan dan diperiksa ulang secara terkunci saat posting.

Contoh:

```http
POST /api/v1/goods-receipts
Authorization: Bearer <ACCESS_TOKEN>
Content-Type: application/json
```

```json
{
  "po_id": 14,
  "received_date": "2026-10-23",
  "notes": "Penerimaan tahap pertama",
  "lines": [
    {"po_line_id": 31, "location_id": 7, "qty_received": "10.0000", "notes": "Kondisi baik"}
  ]
}
```

Response `201 Created`, tipe `GoodsReceiptOut`, dengan status awal `DRAFT`. Nomor GR dibuat server dalam format `GR-YYYYMM-NNNN`. Kuantitas response berupa string desimal empat tempat.

### 5.3 `GET /api/v1/goods-receipts/{gr_id}` — Detail GR

Response `200 OK`, tipe `GoodsReceiptOut`: field ringkasan ditambah `lines`. Setiap baris menyertakan ID GR/PO/baris PO/barang/UoM/lokasi, `qty_received`, catatan, pembuat, dan waktu. ID yang tidak ditemukan menghasilkan `404 NOT_FOUND`.

### 5.4 `PATCH /api/v1/goods-receipts/{gr_id}` — Revisi GR

Semua field opsional: `received_date`, `notes`, dan `lines`. Field yang tidak dikirim tidak berubah. Jika `lines` dikirim, seluruh baris diganti; `[]` mengosongkan baris. Untuk mengosongkan catatan kirim string kosong; `null` mempertahankan nilai lama. Hanya GR `DRAFT` dengan PO yang masih dapat menerima barang yang dapat direvisi. Validasi baris mengikuti aturan pada Bagian 5.2. Response sukses `200 OK` dengan detail terbaru.

### 5.5 `POST /api/v1/goods-receipts/{gr_id}/post` — Posting GR

Tanpa body. Hanya `DRAFT → POSTED`. Posting menambah saldo lokasi melalui pergerakan `IN_PURCHASE`, menambah `qty_received` pada baris PO, memperbarui status PO, dan mencatat audit secara atomik. Minimal satu baris wajib ada. Lokasi yang sedang dibekukan oleh sesi Opname tidak dapat menerima GR. Berhasil menghasilkan `200 OK` dengan detail GR dan `posted_at/posted_by`.

### 5.6 `POST /api/v1/goods-receipts/{gr_id}/cancel` — Batalkan GR

Tanpa body. Hanya GR `DRAFT` yang dapat dibatalkan; GR `POSTED` bersifat final. Berhasil menghasilkan `200 OK` dengan status `CANCELLED`; aksi ini tidak mengubah saldo atau ledger.

## 6. Field Response

`GoodsReceiptSummaryOut` memuat `id`, `gr_number`, `po_id`, `po_number`, ID/kode/nama pemasok dan gudang, `status`, `received_date`, `notes`, `line_count`, `posted_at`, `posted_by`, `created_by`, `created_at`, dan `updated_at`. Detail menambahkan `lines`; field waktu memakai ISO 8601 dan kuantitas berupa string desimal empat tempat.

## 7. Error

Error mengikuti format umum `{ "error": { "code", "message", "details" } }`.

| HTTP | Kode | Kondisi umum |
| ---: | --- | --- |
| `401` | `AUTH_TOKEN_INVALID` | Token tidak ada atau tidak valid. |
| `403` | `PERMISSION_DENIED` | Permission tidak cukup. |
| `403` | `WAREHOUSE_NOT_ASSIGNED` | Warehouse Staff tidak ditugaskan pada gudang PO. |
| `404` | `NOT_FOUND` | GR, PO, baris PO, barang, atau lokasi yang dirujuk tidak ditemukan. |
| `409` | `INVALID_STATE_TRANSITION` | PO/GR tidak berada pada status yang dapat menerima aksi. |
| `409` | `OVER_RECEIPT` | Total penerimaan akan melampaui kuantitas pada baris PO. |
| `409` | `LOCATION_FROZEN` | Lokasi tujuan dibekukan oleh Opname yang berjalan/menunggu persetujuan. |
| `422` | `INACTIVE_REFERENCE` | Gudang atau barang tidak aktif. |
| `422` | `INVALID_LOCATION` | Lokasi bukan milik gudang PO atau tidak aktif. |
| `422` | `VALIDATION_ERROR` | Payload, filter, pagination, baris kosong saat posting, duplikasi pasangan baris/lokasi, UoM, atau kuantitas tidak valid. |

## 8. Audit dan Pengujian

Aksi dicatat pada `audit_logs` sebagai `GR_CREATED`, `GR_UPDATED`, `GR_POSTED`, dan `GR_CANCELLED`. Test relevan di `tests/test_goods_receipt.py`: `test_purchase_order_lifecycle_validations_rbac_and_audit`, `test_ac01_partial_receipt_over_receipt_and_po_fulfillment` (AC-01), `test_ac07_gr_post_transaction_atomicity_rollback_on_failure` (AC-07), dan `test_ac13_concurrent_gr_post_prevents_double_posting` (AC-13).
