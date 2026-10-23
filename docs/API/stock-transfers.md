# Transfer Stok

## 1. Informasi Umum

| Atribut | Keterangan |
| --- | --- |
| **Modul** | Transfer Stok antar lokasi/gudang |
| **Base path** | `/api/v1/stock-transfers` |
| **Rujukan PRD** | FR-06, Bagian 3.1, 3.2, 5.1, 5.3, 6.1, 6.3, 6.5–6.7, 6.9, 8 (AC-02, AC-03, AC-06, AC-09, AC-12, AC-13), Lampiran A & B |
| **Status** | Sudah diimplementasikan; siklus, mutasi stok, scoping, selisih penerimaan, dan konkurensi dicakup oleh test pada Bagian 8. |
| **Kode sumber** | [stock_transfers.py](../../app/api/routes/stock_transfers.py), [transfer_service.py](../../app/services/transfer_service.py), [transfer_repo.py](../../app/repositories/transfer_repo.py), [stock_transfer.py](../../app/schemas/stock_transfer.py) |
| **Modul terkait** | [Stok & Buku Besar](stock-ledger.md), [Gudang & Lokasi](warehouses.md), [Audit Log](audit-logs.md) |

Transfer memindahkan stok dari satu lokasi asal ke satu lokasi tujuan melalui tiga tahap: persetujuan, pengiriman, dan penerimaan. Pengiriman mengurangi stok asal; penerimaan menambah stok tujuan sesuai jumlah yang benar-benar diterima. Perbedaan jumlah tidak dikembalikan ke gudang asal dan tidak menghasilkan pergerakan ledger.

## 2. Autentikasi, Permission, dan Warehouse Scoping

Semua endpoint memerlukan `Authorization: Bearer <access_token>`.

| Permission | Aksi | Peran bawaan menurut Matriks 3.1 |
| --- | --- | --- |
| `transfer:read` | Daftar dan baca detail | Super Admin, Warehouse Manager, Warehouse Staff, Auditor |
| `transfer:create` | Buat/revisi `DRAFT`; batalkan `DRAFT` | Super Admin, Warehouse Staff |
| `transfer:approve` | Setujui; batalkan `APPROVED` | Super Admin, Warehouse Manager |
| `transfer:ship` | Kirim dari lokasi asal | Super Admin, Warehouse Staff |
| `transfer:receive` | Terima di lokasi tujuan | Super Admin, Warehouse Staff |

Untuk operasi tulis, Warehouse Staff harus ditugaskan pada gudang asal saat membuat, merevisi, menyetujui, mengirim, atau membatalkan; penerima harus ditugaskan pada gudang tujuan. Untuk pembacaan, Warehouse Staff dapat melihat Transfer bila ditugaskan ke gudang asal atau tujuan. Filter `warehouse_id`, `source_warehouse_id`, atau `destination_warehouse_id` di luar penugasannya ditolak.

Pembatalan memakai `transfer:create` untuk status `DRAFT` dan `transfer:approve` untuk status `APPROVED`; izin yang benar diverifikasi kembali setelah dokumen dikunci.

## 3. Siklus Status dan Dampak Stok

| Status saat ini | Aksi | Status berikutnya | Dampak |
| --- | --- | --- | --- |
| Baru | Buat Transfer | `DRAFT` | Tidak ada mutasi stok. |
| `DRAFT` | Setujui | `APPROVED` | Minimal satu baris; belum ada mutasi stok. |
| `DRAFT` atau `APPROVED` | Batalkan | `CANCELLED` | Tidak ada mutasi stok; izin bergantung status. |
| `APPROVED` | Kirim | `SHIPPED` | Mengurangi saldo asal dan menulis `OUT_TRANSFER`; stok dalam perjalanan mulai dihitung. |
| `SHIPPED` | Terima | `RECEIVED` | Menambah saldo tujuan dan menulis `IN_TRANSFER` hanya sebesar `qty_received > 0`. |

Transfer hanya menerima satu kali penerimaan final; seluruh baris harus disertakan dalam request. Lokasi asal yang dibekukan menghalangi pengiriman dan lokasi tujuan yang dibekukan menghalangi penerimaan. Status `SHIPPED` menunjukkan barang dalam perjalanan, bukan saldo tersedia di lokasi tujuan.

## 4. Ringkasan Endpoint

| Method | Endpoint | Fungsi | Permission |
| --- | --- | --- | --- |
| GET | `/api/v1/stock-transfers` | Daftar dan filter Transfer | `transfer:read` |
| POST | `/api/v1/stock-transfers` | Buat Transfer `DRAFT` | `transfer:create` |
| GET | `/api/v1/stock-transfers/{transfer_id}` | Baca detail Transfer | `transfer:read` |
| PATCH | `/api/v1/stock-transfers/{transfer_id}` | Revisi Transfer `DRAFT` | `transfer:create` |
| POST | `/api/v1/stock-transfers/{transfer_id}/approve` | Setujui Transfer | `transfer:approve` |
| POST | `/api/v1/stock-transfers/{transfer_id}/ship` | Kirim Transfer | `transfer:ship` |
| POST | `/api/v1/stock-transfers/{transfer_id}/receive` | Catat penerimaan final | `transfer:receive` |
| POST | `/api/v1/stock-transfers/{transfer_id}/cancel` | Batalkan `DRAFT`/`APPROVED` | `transfer:create` atau `transfer:approve` |

## 5. Detail Endpoint

### 5.1 `GET /api/v1/stock-transfers` — Daftar Transfer

| Parameter | Tipe | Wajib | Default | Aturan |
| --- | --- | --- | --- | --- |
| `limit` | integer | Tidak | `50` | Rentang `1..200`. |
| `offset` | integer | Tidak | `0` | Minimal `0`. |
| `warehouse_id` | integer | Tidak | — | Filter Transfer yang gudang asal atau tujuannya sama dengan ID ini. |
| `source_warehouse_id` | integer | Tidak | — | Filter gudang asal. |
| `destination_warehouse_id` | integer | Tidak | — | Filter gudang tujuan. |
| `status` | string | Tidak | — | `DRAFT`, `APPROVED`, `SHIPPED`, `RECEIVED`, atau `CANCELLED`. |
| `date_from`, `date_to` | date | Tidak | — | Filter tanggal pembuatan, format `YYYY-MM-DD`; tanggal awal tidak boleh melewati tanggal akhir. |
| `search` | string | Tidak | — | Pencarian nomor Transfer atau catatan. |
| `sort_by` | string | Tidak | `id` | Whitelist: `id`, `transfer_number`, `status`, `created_at`, `shipped_at`, `received_at`. |
| `sort_dir` | string | Tidak | `desc` | `asc` atau `desc`. |

Response `200 OK` berbentuk `Page[StockTransferSummaryOut]` dengan `items`, `total`, `limit`, dan `offset`. Urutan bawaan `id DESC`; item list tidak memuat `lines`.

### 5.2 `POST /api/v1/stock-transfers` — Buat Transfer

Body:

| Field | Tipe | Wajib | Aturan |
| --- | --- | --- | --- |
| `source_warehouse_id`, `source_location_id` | integer | Ya | Gudang dan lokasi asal harus aktif; pengguna penulis harus ditugaskan ke gudang asal. |
| `destination_warehouse_id`, `destination_location_id` | integer | Ya | Gudang dan lokasi tujuan harus aktif serta cocok satu sama lain. |
| `notes` | string atau `null` | Tidak | Catatan header; teks kosong dinormalisasi menjadi `null`. |
| `lines` | array | Tidak | Bawaan `[]`; Transfer kosong dapat disimpan sebagai `DRAFT`, tetapi tidak dapat disetujui. |

Setiap baris berisi `item_id` dan `qty`. Barang harus aktif, tidak boleh muncul lebih dari sekali, jumlah harus positif dengan maksimal empat tempat desimal, dan UoM dengan `allow_decimal: false` harus menggunakan bilangan bulat. Kuantitas dikirim sebagai string desimal atau integer; float ditolak. Lokasi asal dan tujuan yang sama persis tidak diizinkan.

Contoh:

```http
POST /api/v1/stock-transfers
Authorization: Bearer <ACCESS_TOKEN>
Content-Type: application/json
```

```json
{
  "source_warehouse_id": 2,
  "source_location_id": 7,
  "destination_warehouse_id": 4,
  "destination_location_id": 19,
  "notes": "Pemindahan stok ke cabang",
  "lines": [
    {"item_id": 17, "qty": "12.0000"}
  ]
}
```

Response `201 Created`, tipe `StockTransferOut`, status awal `DRAFT`. Nomor dibuat server dengan format `TRF-YYYYMM-NNNN`; kuantitas diserialisasi sebagai string desimal empat tempat.

### 5.3 `GET /api/v1/stock-transfers/{transfer_id}` — Detail Transfer

Response `200 OK`, tipe `StockTransferOut`: field ringkasan ditambah `lines`. Setiap baris memuat barang dan UoM, `qty`, serta `qty_received`, `qty_variance`, dan `variance_reason` setelah penerimaan. ID tidak ditemukan menghasilkan `404 NOT_FOUND`; Warehouse Staff yang tidak ditugaskan ke gudang asal maupun tujuan menerima `403 WAREHOUSE_NOT_ASSIGNED`.

### 5.4 `PATCH /api/v1/stock-transfers/{transfer_id}` — Revisi Transfer

Semua field pembuatan opsional. Field yang tidak dikirim tidak berubah. Jika `lines` dikirim, seluruh daftar baris diganti; `[]` mengosongkannya. Catatan dapat dikosongkan dengan string kosong; `null` mempertahankan nilai lama. Hanya `DRAFT` yang dapat direvisi. Validasi referensi, lokasi, item, UoM, dan kuantitas sama dengan pembuatan. Response sukses `200 OK`.

### 5.5 `POST /api/v1/stock-transfers/{transfer_id}/approve` — Setujui

Tanpa body. Hanya `DRAFT → APPROVED`; minimal satu baris diperlukan. Aksi memerlukan `transfer:approve` dan penugasan gudang asal untuk Warehouse Staff. Tidak mengubah saldo. Berhasil menghasilkan `200 OK` beserta `approved_by` dan `approved_at`.

### 5.6 `POST /api/v1/stock-transfers/{transfer_id}/ship` — Kirim

Tanpa body. Hanya `APPROVED → SHIPPED`; minimal satu baris diperlukan. Sistem memeriksa saldo terkunci dan menolak saldo negatif bila gudang tidak mengizinkannya. Lokasi asal harus tidak dibekukan. Pengiriman mengurangi stok melalui `OUT_TRANSFER` secara atomik dan menghasilkan `200 OK` beserta `shipped_by` dan `shipped_at`.

### 5.7 `POST /api/v1/stock-transfers/{transfer_id}/receive` — Terima

Request harus memuat seluruh baris Transfer tepat satu kali:

```json
{
  "lines": [
    {"line_id": 42, "qty_received": "11.0000", "variance_reason": "1 unit rusak saat perjalanan"}
  ]
}
```

`qty_received` harus berada pada rentang nol sampai `qty` yang dikirim. Bila kurang, `variance_reason` wajib diisi; kuantitas nol juga memerlukan alasan. Bila sama, alasan selisih disimpan sebagai `null`. Field `line_id` harus merujuk baris dalam Transfer ini, unik, dan seluruh ID baris wajib disertakan. Float ditolak dan aturan bilangan bulat UoM tetap berlaku.

Hanya `SHIPPED → RECEIVED`. Penerimaan memerlukan penugasan gudang tujuan dan lokasi tujuan yang aktif/tidak dibekukan. Saldo tujuan dan ledger `IN_TRANSFER` bertambah hanya sebesar kuantitas yang benar-benar diterima dan lebih dari nol. Selisih `qty - qty_received` dicatat pada baris Transfer; barang hilang/rusak tidak dikembalikan ke asal dan tidak membuat ledger. Penerimaan bersifat final dan atomik; response sukses `200 OK`.

### 5.8 `POST /api/v1/stock-transfers/{transfer_id}/cancel` — Batalkan

Tanpa body. `DRAFT` dibatalkan dengan `transfer:create`; `APPROVED` dengan `transfer:approve`. Kedua aksi mensyaratkan penugasan gudang asal untuk Warehouse Staff. `SHIPPED`, `RECEIVED`, atau `CANCELLED` tidak dapat dibatalkan. Berhasil menghasilkan `200 OK` dengan status `CANCELLED`.

## 6. Field Response

`StockTransferSummaryOut` memuat ID/nomor Transfer, ID/kode/nama gudang asal dan tujuan, ID/kode lokasi asal dan tujuan, `status`, `notes`, `line_count`, pelaku/waktu persetujuan, pengiriman, dan penerimaan, `created_by`, serta timestamp. Detail menambahkan `lines` berisi ID item/SKU/nama/UoM, `allow_decimal`, `qty`, `qty_received`, `qty_variance`, dan `variance_reason`. Field waktu memakai ISO 8601; kuantitas adalah string desimal empat tempat.

## 7. Error

Error mengikuti format umum `{ "error": { "code", "message", "details" } }`.

| HTTP | Kode | Kondisi umum |
| ---: | --- | --- |
| `401` | `AUTH_TOKEN_INVALID` | Token tidak ada atau tidak valid. |
| `403` | `PERMISSION_DENIED` | Permission tidak cukup, termasuk permission salah untuk pembatalan sesuai status. |
| `403` | `WAREHOUSE_NOT_ASSIGNED` | Pengguna Warehouse Staff tidak ditugaskan pada gudang yang diperlukan. |
| `404` | `NOT_FOUND` | Transfer, barang, lokasi, atau baris yang dirujuk tidak ditemukan. |
| `409` | `INVALID_STATE_TRANSITION` | Status Transfer tidak sesuai dengan aksi. |
| `409` | `INSUFFICIENT_STOCK` | Stok asal tidak mencukupi dan gudang melarang stok negatif. |
| `409` | `LOCATION_FROZEN` | Lokasi asal/tujuan sedang dibekukan oleh Opname. |
| `409` | `TRANSFER_QTY_EXCEEDS_SHIPPED` | `qty_received` lebih besar dari jumlah yang dikirim. |
| `422` | `INACTIVE_REFERENCE` | Barang atau referensi gudang tidak aktif. |
| `422` | `INVALID_LOCATION` | Lokasi tidak cocok dengan gudang yang dikirim atau tidak aktif. |
| `422` | `VALIDATION_ERROR` | Payload, filter, pagination, baris kosong/duplikat/hilang, UoM, kuantitas, atau alasan selisih tidak valid. |

## 8. Audit dan Pengujian

Aksi dicatat pada `audit_logs` dengan nama `TRANSFER_CREATED`, `TRANSFER_UPDATED`, `TRANSFER_APPROVED`, `TRANSFER_SHIPPED`, `TRANSFER_RECEIVED`, dan `TRANSFER_CANCELLED`. Test relevan: `test_ac02_negative_stock_prevention_and_allow_negative_stock_flag`, `test_ac03_inter_warehouse_transfer_consistency_in_transit_and_scoping`, `test_ac06_concurrent_ship_only_one_succeeds`, dan `test_ac09_transfer_receipt_variance_validation_and_accounting` di `tests/test_stock_transfer.py`; scoping gudang diverifikasi oleh `test_ac12_warehouse_scoping_assignment_and_access_enforcement` di `tests/test_rbac_scoping.py`.
