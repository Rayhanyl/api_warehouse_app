# Stock Opname

## 1. Informasi Umum

| Atribut | Keterangan |
| --- | --- |
| **Modul** | Stock Opname / Rekonsiliasi Stok Fisik |
| **Base path** | `/api/v1/stock-opnames` |
| **Rujukan PRD** | FR-07, FR-08, FR-10, FR-11, Bagian 3.1, 3.2, 5.1, 5.3, 6.5, 6.6, 6.9, 8 (AC-04, AC-05, AC-07, AC-10, AC-12, AC-13), Lampiran A & B |
| **Status** | Sudah diimplementasikan; rekonsiliasi dan pembekuan lokasi diuji oleh test di Bagian 9. |
| **Kode sumber** | [stock_opnames.py](../../app/api/routes/stock_opnames.py), [opname_service.py](../../app/services/opname_service.py), [opname_repo.py](../../app/repositories/opname_repo.py), [stock_opname.py](../../app/schemas/stock_opname.py) |
| **Modul terkait** | [Stok & Buku Besar](stock-ledger.md), [Gudang & Lokasi](warehouses.md), [Audit Log](audit-logs.md) |

Satu sesi Opname berlaku untuk satu gudang, dengan cakupan satu lokasi atau seluruh gudang jika `location_id` tidak diisi. Saat sesi dimulai, sistem mengambil snapshot saldo menjadi `qty_system` dan membekukan cakupan tersebut. Setelah penghitungan diajukan dan disetujui, saldo disesuaikan dengan hitung fisik; koreksi dicatat pada ledger sebagai `ADJUSTMENT_PLUS` atau `ADJUSTMENT_MINUS`.

## 2. Autentikasi, Permission, dan Scoping

Semua endpoint memerlukan `Authorization: Bearer <access_token>`.

| Permission | Aksi | Peran bawaan menurut Matriks 3.1 |
| --- | --- | --- |
| `opname:read` | Daftar dan baca detail Opname | Super Admin, Warehouse Manager, Warehouse Staff, Auditor |
| `opname:manage` | Buat, revisi `DRAFT`, mulai, dan batalkan sesi | Super Admin, Warehouse Manager |
| `opname:count` | Input hitung fisik dan ajukan persetujuan | Super Admin, Warehouse Staff |
| `opname:approve` | Setujui atau tolak hasil hitung | Super Admin, Warehouse Manager |

Warehouse Staff hanya dapat membaca sesi pada gudang yang ditugaskan. Operasi tulis memeriksa penugasan gudang pada sesi. Warehouse Manager dapat membaca seluruh gudang, tetapi aksi pengelolaan/persetujuan dibatasi ke gudang yang ditugaskan. Auditor hanya memiliki akses baca.

## 3. Siklus Status dan Pembekuan Lokasi

| Status saat ini | Aksi | Status berikutnya | Ketentuan dan dampak |
| --- | --- | --- | --- |
| Baru | Buat sesi | `DRAFT` | Gudang aktif; cakupan lokasi opsional. |
| `DRAFT` | Revisi | `DRAFT` | Lokasi dan catatan dapat diubah. |
| `DRAFT` | Mulai | `IN_PROGRESS` | Lokasi aktif dikunci; tidak boleh tumpang tindih dengan sesi aktif lain. Snapshot saldo dicatat dan lokasi dibekukan. |
| `DRAFT` | Batalkan | `CANCELLED` | Tidak ada perubahan saldo. |
| `IN_PROGRESS` | Input hitung | `IN_PROGRESS` | Isi hasil hitung pada baris snapshot atau tambahkan barang fisik yang ditemukan. |
| `IN_PROGRESS` | Ajukan | `WAITING_APPROVAL` | Semua baris harus memiliki `qty_physical`; pembekuan tetap berlaku. |
| `IN_PROGRESS` | Batalkan | `CANCELLED` | Pembekuan dilepas; saldo tidak berubah. |
| `WAITING_APPROVAL` | Setujui | `COMPLETED` | Saldo disesuaikan secara atomik; pembekuan dilepas. |
| `WAITING_APPROVAL` | Tolak | `IN_PROGRESS` | Alasan wajib; sesi kembali untuk dihitung/revisi, pembekuan tetap berlaku. |

Satu lokasi tidak dapat berada dalam lebih dari satu sesi aktif (`IN_PROGRESS` atau `WAITING_APPROVAL`). Selama cakupan dibekukan, posting GR ke lokasi, pengiriman Transfer dari lokasi, dan penerimaan Transfer ke lokasi ditolak dengan `409 LOCATION_FROZEN`. Pembekuan dilepas saat sesi `COMPLETED` atau `CANCELLED`.

## 4. Ringkasan Endpoint

| Method | Endpoint | Fungsi | Permission |
| --- | --- | --- | --- |
| GET | `/api/v1/stock-opnames` | Daftar dan filter sesi | `opname:read` |
| POST | `/api/v1/stock-opnames` | Buat sesi `DRAFT` | `opname:manage` |
| GET | `/api/v1/stock-opnames/{opname_id}` | Baca detail dan baris hitung | `opname:read` |
| PATCH | `/api/v1/stock-opnames/{opname_id}` | Revisi sesi `DRAFT` | `opname:manage` |
| POST | `/api/v1/stock-opnames/{opname_id}/start` | Ambil snapshot dan mulai pembekuan | `opname:manage` |
| POST | `/api/v1/stock-opnames/{opname_id}/count` | Input atau revisi hasil hitung | `opname:count` |
| POST | `/api/v1/stock-opnames/{opname_id}/lines` | Alias input hasil hitung | `opname:count` |
| PUT | `/api/v1/stock-opnames/{opname_id}/lines` | Alias input hasil hitung | `opname:count` |
| POST | `/api/v1/stock-opnames/{opname_id}/submit` | Ajukan untuk persetujuan | `opname:count` |
| POST | `/api/v1/stock-opnames/{opname_id}/approve` | Setujui dan terapkan selisih | `opname:approve` |
| POST | `/api/v1/stock-opnames/{opname_id}/reject` | Tolak dan kembalikan ke hitung | `opname:approve` |
| POST | `/api/v1/stock-opnames/{opname_id}/cancel` | Batalkan `DRAFT`/`IN_PROGRESS` | `opname:manage` |

## 5. Detail Endpoint

### 5.1 `GET /api/v1/stock-opnames` — Daftar sesi

| Parameter | Tipe | Wajib | Default | Aturan |
| --- | --- | --- | --- | --- |
| `limit` | integer | Tidak | `50` | Rentang `1..200`. |
| `offset` | integer | Tidak | `0` | Minimal `0`. |
| `warehouse_id` | integer | Tidak | — | Filter gudang; Warehouse Staff hanya dapat meminta gudang tugasnya. |
| `location_id` | integer | Tidak | — | Filter cakupan lokasi spesifik. |
| `status` | string | Tidak | — | `DRAFT`, `IN_PROGRESS`, `WAITING_APPROVAL`, `COMPLETED`, atau `CANCELLED`. |
| `date_from`, `date_to` | date | Tidak | — | Filter tanggal pembuatan UTC, format `YYYY-MM-DD`; tanggal awal tidak boleh melewati tanggal akhir. |
| `search` | string | Tidak | — | Pencarian nomor Opname atau catatan. |
| `sort_by` | string | Tidak | `id` | Whitelist: `id`, `opname_number`, `status`, `created_at`, `started_at`, `approved_at`. |
| `sort_dir` | string | Tidak | `desc` | `asc` atau `desc`. |

Response `200 OK` berbentuk `Page[StockOpnameSummaryOut]` (`items`, `total`, `limit`, `offset`). Item list tidak menyertakan array `lines`.

### 5.2 `POST /api/v1/stock-opnames` — Buat sesi

Body:

| Field | Tipe | Wajib | Aturan |
| --- | --- | --- | --- |
| `warehouse_id` | integer | Ya | Gudang harus ada dan aktif; Warehouse Manager harus ditugaskan ke gudang ini. |
| `location_id` | integer atau `null` | Tidak | Jika diisi, lokasi harus aktif dan milik gudang; jika tidak diisi, cakupan seluruh gudang. |
| `notes` | string atau `null` | Tidak | Catatan sesi; teks kosong dinormalisasi menjadi `null`. |

Contoh:

```http
POST /api/v1/stock-opnames
Authorization: Bearer <ACCESS_TOKEN>
Content-Type: application/json
```

```json
{
  "warehouse_id": 2,
  "location_id": 7,
  "notes": "Opname bulanan lokasi A-01"
}
```

Response `201 Created`, tipe `StockOpnameOut`, status awal `DRAFT`, nomor format `OPN-YYYYMM-NNNN`. Nomor dibuat server dan nomor sesi yang dibatalkan tidak digunakan ulang.

### 5.3 `GET /api/v1/stock-opnames/{opname_id}` — Detail sesi

Response `200 OK`, tipe `StockOpnameOut`: field ringkasan ditambah `lines`. Baris memuat lokasi, barang, UoM, `qty_system`, `qty_physical`, `qty_variance`, penghitung/waktu hitung, catatan, dan timestamp. ID tidak ditemukan menghasilkan `404 NOT_FOUND`.

### 5.4 `PATCH /api/v1/stock-opnames/{opname_id}` — Revisi sesi

Body menerima `location_id`, `clear_location`, dan `notes`, semuanya opsional; hanya sesi `DRAFT` dapat direvisi. Untuk mengubah lokasi, kirim `location_id`. Untuk mengubah cakupan menjadi seluruh gudang, kirim `"clear_location": true`. Jika `clear_location` bernilai true, nilai `location_id` diabaikan. Field catatan yang tidak dikirim tetap; kirim string kosong untuk mengosongkannya. Response sukses `200 OK`.

### 5.5 `POST /api/v1/stock-opnames/{opname_id}/start` — Mulai sesi

Tanpa body. Hanya `DRAFT → IN_PROGRESS`. Sistem mengunci lokasi dalam cakupan, memeriksa sesi aktif yang tumpang tindih, lalu mengambil snapshot `qty_system` dari saldo saat ini. Lokasi harus aktif dan setidaknya ada satu lokasi aktif dalam cakupan. Sesi yang tumpang tindih ditolak dengan `409 LOCATION_FROZEN`. Berhasil menghasilkan `200 OK` dengan `started_at`, `started_by`, dan baris snapshot.

### 5.6 Input hasil hitung — `POST .../{opname_id}/count`, `POST .../{opname_id}/lines`, `PUT .../{opname_id}/lines`

Ketiga path/method adalah alias yang memanggil operasi input hitung yang sama. Hanya sesi `IN_PROGRESS` yang dapat menerima input. Body memuat array `lines` minimal satu elemen. Setiap elemen:

| Field | Tipe | Ketentuan |
| --- | --- | --- |
| `line_id` | integer atau `null` | Untuk memperbarui baris snapshot yang sudah ada. |
| `location_id` | integer atau `null` | Dipakai bersama `item_id` untuk barang/lokasi baru; boleh dihilangkan bila sesi dibatasi ke satu lokasi. |
| `item_id` | integer atau `null` | Dipakai bersama `location_id` untuk menambahkan barang fisik yang ditemukan. |
| `qty_physical` | string desimal atau integer | Wajib; nilai `≥ 0`, maksimum empat tempat desimal; float ditolak. |
| `notes` | string atau `null` | Catatan hasil hitung. |

Setiap elemen harus menggunakan `line_id` atau pasangan `location_id` + `item_id`. Pasangan baru harus berada dalam cakupan sesi; barang dan lokasi harus aktif. Jika barang belum memiliki baris saldo, `qty_system` awalnya `0.0000`. Barang dengan UoM `allow_decimal: false` harus dihitung dalam bilangan bulat. Hasil dapat dikirim bertahap sebelum diajukan. Response `200 OK` berisi sesi dan baris terbaru.

Contoh:

```json
{
  "lines": [
    {"line_id": 81, "qty_physical": "97.0000", "notes": "Tiga unit tidak ditemukan"},
    {"location_id": 7, "item_id": 24, "qty_physical": "5", "notes": "Barang ditemukan saat hitung"}
  ]
}
```

### 5.7 `POST /api/v1/stock-opnames/{opname_id}/submit` — Ajukan persetujuan

Tanpa body. Hanya `IN_PROGRESS → WAITING_APPROVAL`. Semua baris harus sudah memiliki `qty_physical`; jika masih ada yang belum dihitung, API menolak dengan `422 VALIDATION_ERROR` dan mencantumkan ID baris. Pembekuan tetap aktif selama menunggu persetujuan.

### 5.8 `POST /api/v1/stock-opnames/{opname_id}/approve` — Setujui

Tanpa body. Hanya `WAITING_APPROVAL → COMPLETED`. Untuk setiap baris, sistem menghitung `qty_variance = qty_physical - qty_system`. Baris dengan selisih positif membuat pergerakan `ADJUSTMENT_PLUS`; selisih negatif membuat `ADJUSTMENT_MINUS`; selisih nol tidak menghasilkan ledger. Saldo diselaraskan ke hitung fisik, sesi ditandai selesai, dan pembekuan dilepas dalam transaksi atomik. Response `200 OK` menyertakan `approved_by` dan `approved_at`.

### 5.9 `POST /api/v1/stock-opnames/{opname_id}/reject` — Tolak

Body wajib:

```json
{"rejection_reason": "Hitung ulang rak A-01 untuk SKU yang berbeda"}
```

Alasan tidak boleh kosong setelah spasi tepi dihapus. Hanya `WAITING_APPROVAL → IN_PROGRESS`; hasil dapat diperbaiki dan diajukan ulang. Tidak ada penyesuaian saldo saat penolakan, dan lokasi tetap dibekukan. Response `200 OK`.

### 5.10 `POST /api/v1/stock-opnames/{opname_id}/cancel` — Batalkan

Tanpa body. Hanya status `DRAFT` atau `IN_PROGRESS` yang dapat dibatalkan. Pembatalan dari `IN_PROGRESS` melepaskan pembekuan tanpa mengubah saldo. Sesi `WAITING_APPROVAL`, `COMPLETED`, dan `CANCELLED` tidak dapat dibatalkan. Response `200 OK` dengan status `CANCELLED`.

## 6. Field Response

`StockOpnameSummaryOut` berisi ID/nomor, gudang, cakupan lokasi opsional, status, catatan, jumlah baris, timestamp/pelaku mulai, ajukan, dan persetujuan, alasan penolakan, pembuat, serta timestamp. Detail menambahkan `lines` yang memuat identitas lokasi dan barang/UoM, `qty_system`, `qty_physical`, `qty_variance`, penghitung dan waktu hitung. Waktu memakai ISO 8601; kuantitas diserialisasi sebagai string desimal empat tempat. Sebelum dihitung, `qty_physical` dan `qty_variance` dapat bernilai `null`.

## 7. Error

Error mengikuti format umum `{ "error": { "code", "message", "details" } }`.

| HTTP | Kode | Kondisi umum |
| ---: | --- | --- |
| `401` | `AUTH_TOKEN_INVALID` | Token tidak ada atau tidak valid. |
| `403` | `PERMISSION_DENIED` | Permission tidak cukup untuk operasi. |
| `403` | `WAREHOUSE_NOT_ASSIGNED` | Pengguna tidak ditugaskan ke gudang sesi. |
| `404` | `NOT_FOUND` | Sesi, baris hitung, barang, gudang, atau lokasi tidak ditemukan. |
| `409` | `INVALID_STATE_TRANSITION` | Status sesi tidak mengizinkan aksi yang diminta. |
| `409` | `LOCATION_FROZEN` | Cakupan tumpang tindih dengan sesi Opname aktif lain; kode ini juga dipakai operasi stok yang menyentuh lokasi beku. |
| `422` | `INACTIVE_REFERENCE` | Gudang atau barang tidak aktif. |
| `422` | `INVALID_LOCATION` | Lokasi tidak aktif, bukan milik gudang sesi, atau di luar cakupan. |
| `422` | `VALIDATION_ERROR` | Filter/pagination, baris input, kuantitas, UoM, baris belum dihitung, atau alasan penolakan tidak valid. |

## 8. Audit dan Dampak Ledger

Aksi sesi dicatat pada `audit_logs`: `OPNAME_CREATED`, `OPNAME_UPDATED`, `OPNAME_STARTED`, `OPNAME_COUNTED`, `OPNAME_SUBMITTED`, `OPNAME_APPROVED`, `OPNAME_REJECTED`, dan `OPNAME_CANCELLED`. Penyesuaian stok terjadi hanya saat persetujuan dan menggunakan referensi `STOCK_OPNAME`; baris tanpa selisih tidak menghasilkan pergerakan stok.

## 9. Pengujian

Skenario utama di `tests/test_stock_opname.py`: `test_ac04_stock_opname_reconciliation_variance_and_zero_variance_no_ledger` (AC-04) dan `test_ac10_location_freeze_during_opname_and_unfreeze_on_complete_or_cancel` (AC-10). Pengujian tersebut memeriksa penyesuaian plus/minus, tidak adanya ledger untuk selisih nol, pembekuan saat sesi aktif, serta pelepasan pembekuan saat selesai atau dibatalkan.
