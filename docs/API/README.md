# Dokumentasi API — Warehouse Management System (WMS)

Dokumentasi teknis REST API untuk aplikasi **Warehouse Management System (WMS)** berbasis **Python (FastAPI)** dan **PostgreSQL** (`psycopg` 3 tanpa ORM). Seluruh isi dokumentasi ini disusun berdasarkan **implementasi kode aktual**, **skema migrasi SQL (`001`–`009`)**, **pengujian otomatis (`pytest`)**, serta dokumen acuan [PRD_GENERAL.md](../CORE/PRD_GENERAL.md).

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
| `WAREHOUSE_NOT_ASSIGNED` | 403 | `WarehouseNotAssigned` | Aktif pada pengelolaan lokasi serta aksi/data gudang terlingkup PO, GR, Transfer, dan Opname |
| `NOT_FOUND` | 404 | `NotFoundError` | Aktif pada master data, PO, GR, Transfer, Stock Opname, dan menu |
| `VALIDATION_ERROR` | 422 | `ValidationDomainError` & `RequestValidationError` | Aktif (payload, pagination, sorting, kuantitas, format email, aturan dokumen, dan hierarki menu) |
| `INVALID_LOCATION` | 422 | `InvalidLocationError` | Aktif (referensi lokasi tidak cocok, tidak ditemukan, atau tidak aktif pada operasi gudang) |
| `INACTIVE_REFERENCE` | 422 | `InactiveReferenceError` | Aktif pada master data, referensi dokumen PO/GR/Transfer/Opname, dan parent menu yang tidak aktif |
| `DUPLICATE` | 409 | `DuplicateError` | Aktif (`/users`, `/menus`, `/categories`, `/uoms`, `/suppliers`, `/items`, `/warehouses`, `/locations`) |
| `INVALID_STATE_TRANSITION` | 409 | `InvalidStateTransition` | Aktif (PO, GR, Transfer, Opname; status dokumen tidak sesuai aksi) |
| `INSUFFICIENT_STOCK` | 409 | `InsufficientStock` | Aktif (pengiriman Transfer saat stok tidak cukup dan stok negatif dilarang) |
| `OVER_RECEIPT` | 409 | `OverReceipt` | Aktif (posting GR melebihi sisa kuantitas PO) |
| `TRANSFER_QTY_EXCEEDS_SHIPPED` | 409 | `TransferQtyExceedsShipped` | Aktif (penerimaan Transfer melebihi jumlah dikirim) |
| `LOCATION_FROZEN` | 409 | `LocationFrozen` | Aktif saat sesi Opname membekukan lokasi yang akan dimutasi atau memiliki sesi tumpang tindih |
| `ENTITY_IN_USE` | 409 | `EntityInUse` | Aktif (`/menus/{id}` saat parent masih memiliki anak aktif; serta master data saat penonaktifan/perubahan ditolak karena masih digunakan) |
| `INTERNAL_ERROR` | 500 | Handler `Exception` umum | Aktif (`app/main.py`) |

---

## 2. Daftar Modul & Status Implementasi

Sesuai pentahapan di [`docs/CORE/FOLDER_STRUCTURE.MD`](../CORE/FOLDER_STRUCTURE.MD), berikut status setiap modul API di kode sumber saat ini:

| Modul / Domain Bisnis | Dokumen API | Status Implementasi | Ringkasan Fungsi |
| --- | --- | --- | --- |
| **Health Check** | [health.md](health.md) | ✅ **Aktif** (2 endpoint) | Pemeriksaan status layanan API dan konektivitas pool PostgreSQL. |
| **Autentikasi & Otorisasi** | [authentication.md](authentication.md) | ✅ **Aktif** (5 endpoint) | Login JWT, rotasi & deteksi penggunaan ulang *Refresh Token*, penguncian akun, logout, profil `/me`, dan ganti kata sandi. |
| **Pengguna, RBAC & Penugasan Gudang** | [users.md](users.md) | ✅ **Aktif** (9 endpoint) | CRUD pengguna, penonaktifan akun, daftar & pengaturan *role/permission*, serta penugasan gudang (*Warehouse Scoping*). |
| **Menu Navigasi Dinamis** | [menus.md](menus.md) | ✅ **Aktif** (5 endpoint) | Pohon menu terfilter permission pengguna dan administrasi menu tanpa hard delete (FR-01, AC-14). |
| **Master Data** (`master.py`) | [master-data.md](master-data.md) | ✅ **Aktif** (16 endpoint) | CRUD Kategori, Satuan Ukur (UoM + `allow_decimal`), Pemasok, dan Barang (SKU), beserta perlindungan `ENTITY_IN_USE` dan imutabilitas SKU/UoM dasar (FR-02). |
| **Gudang & Lokasi** (`warehouses.py`) | [warehouses.md](warehouses.md) | ✅ **Aktif** (10 endpoint) | CRUD Gudang (`allow_negative_stock`) & Lokasi Penyimpanan (*Bin/Rack*) dengan penegakan *Warehouse Scoping* (`location:manage`) dan perlindungan `ENTITY_IN_USE` (FR-02). |
| **Audit Log** | [audit-logs.md](audit-logs.md) | ✅ **Aktif** (1 endpoint) | Pembacaan jejak audit *append-only* dengan filter pengguna, aksi, entitas, dan rentang tanggal. |
| **Stok & Buku Besar** (`stock.py`) | [stock-ledger.md](stock-ledger.md) | ✅ **Aktif** (6 path) | Baca saldo per lokasi, gudang, dan agregat lintas gudang; barang dalam perjalanan; serta Stock Movement Ledger (FR-03, FR-08). |
| **Purchase Order** (`purchase_orders.py`) | [purchase-orders.md](purchase-orders.md) | ✅ **Aktif** (7 endpoint) | Pembuatan, revisi `DRAFT`, penerbitan, pembatalan, penutupan, daftar/detail PO, dan pemenuhan otomatis melalui GR (FR-04). |
| **Goods Receipt** (`goods_receipts.py`) | [goods-receipts.md](goods-receipts.md) | ✅ **Aktif** (6 endpoint) | Penerimaan PO sebagai draft, revisi, posting stok/ledger dan pemenuhan PO, atau pembatalan (FR-05). |
| **Transfer Stok** (`stock_transfers.py`) | [stock-transfers.md](stock-transfers.md) | ✅ **Aktif** (8 endpoint) | Draft, persetujuan, pengiriman, penerimaan final dengan pencatatan selisih, serta pembatalan (FR-06). |
| **Stock Opname** (`stock_opnames.py`) | [stock-opnames.md](stock-opnames.md) | ✅ **Aktif** (12 path/method) | Sesi opname per gudang/lokasi, snapshot dan pembekuan, input hitung, persetujuan/penolakan, serta penyesuaian stok (FR-07). |

> **Catatan:** Modul operasional M5–M7 (Goods Receipt, Transfer Stok, dan Stock Opname) sudah aktif.

---

## 3. Ringkasan Endpoint Utama yang Didokumentasikan (87 entri)

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
| 17 | GET | `/api/v1/categories` | Daftar kategori barang (paginasi, filter, pencarian) | Bearer | `master:read` | [master-data.md](master-data.md#get-apiv1categories--daftar-kategori) |
| 18 | POST | `/api/v1/categories` | Buat kategori barang baru | Bearer | `master:manage` | [master-data.md](master-data.md#post-apiv1categories--buat-kategori-baru) |
| 19 | GET | `/api/v1/categories/{category_id}` | Detail kategori barang berdasarkan ID | Bearer | `master:read` | [master-data.md](master-data.md#get-apiv1categoriescategory_id--detail-kategori) |
| 20 | PATCH | `/api/v1/categories/{category_id}` | Perbarui atau nonaktifkan kategori barang | Bearer | `master:manage` | [master-data.md](master-data.md#patch-apiv1categoriescategory_id--perbarui--nonaktifkan-kategori) |
| 21 | GET | `/api/v1/uoms` | Daftar satuan ukur / UoM (paginasi, filter, pencarian) | Bearer | `master:read` | [master-data.md](master-data.md#get-apiv1uoms--daftar-uom) |
| 22 | POST | `/api/v1/uoms` | Buat satuan ukur (UoM) baru | Bearer | `master:manage` | [master-data.md](master-data.md#post-apiv1uoms--buat-uom-baru) |
| 23 | GET | `/api/v1/uoms/{uom_id}` | Detail satuan ukur (UoM) berdasarkan ID | Bearer | `master:read` | [master-data.md](master-data.md#get-apiv1uomsuom_id--detail-uom) |
| 24 | PATCH | `/api/v1/uoms/{uom_id}` | Perbarui atau nonaktifkan satuan ukur (UoM) | Bearer | `master:manage` | [master-data.md](master-data.md#patch-apiv1uomsuom_id--perbarui--nonaktifkan-uom) |
| 25 | GET | `/api/v1/suppliers` | Daftar pemasok (paginasi, filter, pencarian) | Bearer | `master:read` | [master-data.md](master-data.md#get-apiv1suppliers--daftar-pemasok) |
| 26 | POST | `/api/v1/suppliers` | Buat pemasok baru | Bearer | `master:manage` | [master-data.md](master-data.md#post-apiv1suppliers--buat-pemasok-baru) |
| 27 | GET | `/api/v1/suppliers/{supplier_id}` | Detail pemasok berdasarkan ID | Bearer | `master:read` | [master-data.md](master-data.md#get-apiv1supplierssupplier_id--detail-pemasok) |
| 28 | PATCH | `/api/v1/suppliers/{supplier_id}` | Perbarui atau nonaktifkan pemasok | Bearer | `master:manage` | [master-data.md](master-data.md#patch-apiv1supplierssupplier_id--perbarui--nonaktifkan-pemasok) |
| 29 | GET | `/api/v1/items` | Daftar barang / SKU (paginasi, filter kategori/UoM, pencarian) | Bearer | `master:read` | [master-data.md](master-data.md#get-apiv1items--daftar-barang) |
| 30 | POST | `/api/v1/items` | Buat barang (SKU) baru | Bearer | `master:manage` | [master-data.md](master-data.md#post-apiv1items--buat-barang-baru) |
| 31 | GET | `/api/v1/items/{item_id}` | Detail barang (SKU) berdasarkan ID | Bearer | `master:read` | [master-data.md](master-data.md#get-apiv1itemsitem_id--detail-barang) |
| 32 | PATCH | `/api/v1/items/{item_id}` | Perbarui atau nonaktifkan barang (SKU) | Bearer | `master:manage` | [master-data.md](master-data.md#patch-apiv1itemsitem_id--perbarui--nonaktifkan-barang) |
| 33 | GET | `/api/v1/items/import-template` | Unduh template Excel import barang | Bearer | `master:read` | [master-data.md](master-data.md#get-apiv1itemsimport-template--unduh-template-import-barang) |
| 34 | POST | `/api/v1/items/import` | Import item massal dari workbook Excel | Bearer | `master:manage` | [master-data.md](master-data.md#post-apiv1itemsimport--import-barang-massal) |
| 35 | GET | `/api/v1/warehouses` | Daftar gudang (paginasi, filter, purpose, pencarian) | Bearer | `master:read` `(g)` | [warehouses.md](warehouses.md#get-apiv1warehouses--daftar-gudang) |
| 36 | POST | `/api/v1/warehouses` | Buat gudang baru | Bearer | `warehouse:manage` | [warehouses.md](warehouses.md#post-apiv1warehouses--buat-gudang-baru) |
| 37 | GET | `/api/v1/warehouses/{warehouse_id}` | Detail gudang berdasarkan ID | Bearer | `master:read` `(g)` | [warehouses.md](warehouses.md#get-apiv1warehouseswarehouse_id--detail-gudang) |
| 38 | PATCH | `/api/v1/warehouses/{warehouse_id}` | Perbarui atau nonaktifkan gudang | Bearer | `warehouse:manage` | [warehouses.md](warehouses.md#patch-apiv1warehouseswarehouse_id--perbarui--nonaktifkan-gudang) |
| 39 | GET | `/api/v1/warehouses/{warehouse_id}/locations` | Daftar lokasi penyimpanan pada satu gudang | Bearer | `master:read` `(g)` | [warehouses.md](warehouses.md#get-apiv1warehouseswarehouse_idlocations--daftar-lokasi-pada-satu-gudang) |
| 40 | POST | `/api/v1/warehouses/{warehouse_id}/locations` | Buat lokasi penyimpanan pada gudang tertentu | Bearer | `location:manage` `(g)` | [warehouses.md](warehouses.md#post-apiv1warehouseswarehouse_idlocations--buat-lokasi-pada-gudang-tertentu) |
| 41 | GET | `/api/v1/locations` | Daftar seluruh lokasi penyimpanan (filter `warehouse_id`, `purpose`) | Bearer | `master:read` `(g)` | [warehouses.md](warehouses.md#get-apiv1locations--daftar-seluruh-lokasi-penyimpanan) |
| 42 | POST | `/api/v1/locations` | Buat lokasi penyimpanan (dengan `warehouse_id` di body) | Bearer | `location:manage` `(g)` | [warehouses.md](warehouses.md#post-apiv1locations--buat-lokasi-penyimpanan-top-level) |
| 43 | GET | `/api/v1/locations/{location_id}` | Detail lokasi penyimpanan berdasarkan ID | Bearer | `master:read` `(g)` | [warehouses.md](warehouses.md#get-apiv1locationslocation_id--detail-lokasi-penyimpanan) |
| 44 | PATCH | `/api/v1/locations/{location_id}` | Perbarui atau nonaktifkan lokasi penyimpanan | Bearer | `location:manage` `(g)` | [warehouses.md](warehouses.md#patch-apiv1locationslocation_id--perbarui--nonaktifkan-lokasi-penyimpanan) |
| 45 | GET | `/api/v1/audit-logs` | Daftar jejak audit (paginasi & filter) | Bearer | `audit:read` | [audit-logs.md](audit-logs.md#get-apiv1audit-logs--daftar-audit-log) |
| 46 | GET | `/api/v1/purchase-orders` | Daftar PO (filter, pencarian, pagination) | Bearer | `po:read` `(g)` | [purchase-orders.md](purchase-orders.md#51-get-apiv1purchase-orders--daftar-po) |
| 47 | POST | `/api/v1/purchase-orders` | Buat PO berstatus `DRAFT` | Bearer | `po:create` `(g)` | [purchase-orders.md](purchase-orders.md#52-post-apiv1purchase-orders--buat-po) |
| 48 | GET | `/api/v1/purchase-orders/{po_id}` | Detail PO dan barisnya | Bearer | `po:read` `(g)` | [purchase-orders.md](purchase-orders.md#53-get-apiv1purchase-orderspo_id--detail-po) |
| 49 | PATCH | `/api/v1/purchase-orders/{po_id}` | Revisi header/baris PO `DRAFT` | Bearer | `po:create` `(g)` | [purchase-orders.md](purchase-orders.md#54-patch-apiv1purchase-orderspo_id--revisi-po) |
| 50 | POST | `/api/v1/purchase-orders/{po_id}/issue` | Terbitkan PO | Bearer | `po:issue` `(g)` | [purchase-orders.md](purchase-orders.md#55-post-apiv1purchase-orderspo_idissue--terbitkan-po) |
| 51 | POST | `/api/v1/purchase-orders/{po_id}/cancel` | Batalkan PO sesuai status | Bearer | `po:create` / `po:cancel` `(g)` | [purchase-orders.md](purchase-orders.md#56-post-apiv1purchase-orderspo_idcancel--batalkan-po) |
| 52 | POST | `/api/v1/purchase-orders/{po_id}/close` | Tutup PO dengan alasan | Bearer | `po:close` `(g)` | [purchase-orders.md](purchase-orders.md#57-post-apiv1purchase-orderspo_idclose--tutup-po) |
| 53 | GET | `/api/v1/stock/balances` | Saldo stok per lokasi (alias `by-location`) | Bearer | `stock:read` `(g)` | [stock-ledger.md](stock-ledger.md#51-get-apiv1stockbalances--get-apiv1stockby-location--saldo-stok-per-lokasi) |
| 54 | GET | `/api/v1/stock/by-location` | Saldo stok per lokasi | Bearer | `stock:read` `(g)` | [stock-ledger.md](stock-ledger.md#51-get-apiv1stockbalances--get-apiv1stockby-location--saldo-stok-per-lokasi) |
| 55 | GET | `/api/v1/stock/by-warehouse` | Saldo diagregasi per gudang dan barang | Bearer | `stock:read` `(g)` | [stock-ledger.md](stock-ledger.md#52-get-apiv1stockby-warehouse--saldo-stok-per-gudang) |
| 56 | GET | `/api/v1/stock/summary` | Saldo diagregasi lintas gudang per barang | Bearer | `stock:read` `(g)` | [stock-ledger.md](stock-ledger.md#53-get-apiv1stocksummary--ringkasan-saldo-stok-lintas-gudang) |
| 57 | GET | `/api/v1/stock/movements` | Daftar Stock Movement Ledger (alias `ledger`) | Bearer | `ledger:read` `(g)` | [stock-ledger.md](stock-ledger.md#54-get-apiv1stockledger--get-apiv1stockmovements--buku-besar-pergerakan-stok) |
| 58 | GET | `/api/v1/stock/ledger` | Daftar Stock Movement Ledger | Bearer | `ledger:read` `(g)` | [stock-ledger.md](stock-ledger.md#54-get-apiv1stockledger--get-apiv1stockmovements--buku-besar-pergerakan-stok) |
| 59 | GET | `/api/v1/goods-receipts` | Daftar dan filter Goods Receipt | Bearer | `gr:read` `(g)` | [goods-receipts.md](goods-receipts.md#51-get-apiv1goods-receipts--daftar-gr) |
| 60 | POST | `/api/v1/goods-receipts` | Buat GR berstatus `DRAFT` | Bearer | `gr:manage` `(g)` | [goods-receipts.md](goods-receipts.md#52-post-apiv1goods-receipts--buat-gr) |
| 61 | GET | `/api/v1/goods-receipts/{gr_id}` | Detail GR dan baris penerimaan | Bearer | `gr:read` `(g)` | [goods-receipts.md](goods-receipts.md#53-get-apiv1goods-receiptsgr_id--detail-gr) |
| 62 | PATCH | `/api/v1/goods-receipts/{gr_id}` | Revisi GR `DRAFT` | Bearer | `gr:manage` `(g)` | [goods-receipts.md](goods-receipts.md#54-patch-apiv1goods-receiptsgr_id--revisi-gr) |
| 63 | POST | `/api/v1/goods-receipts/{gr_id}/post` | Posting penerimaan dan mutasi stok | Bearer | `gr:manage` `(g)` | [goods-receipts.md](goods-receipts.md#55-post-apiv1goods-receiptsgr_idpost--posting-gr) |
| 64 | POST | `/api/v1/goods-receipts/{gr_id}/cancel` | Batalkan GR `DRAFT` | Bearer | `gr:manage` `(g)` | [goods-receipts.md](goods-receipts.md#56-post-apiv1goods-receiptsgr_idcancel--batalkan-gr) |
| 65 | GET | `/api/v1/stock-transfers` | Daftar dan filter Transfer Stok | Bearer | `transfer:read` `(g)` | [stock-transfers.md](stock-transfers.md#51-get-apiv1stock-transfers--daftar-transfer) |
| 66 | POST | `/api/v1/stock-transfers` | Buat Transfer berstatus `DRAFT` | Bearer | `transfer:create` `(g asal)` | [stock-transfers.md](stock-transfers.md#52-post-apiv1stock-transfers--buat-transfer) |
| 67 | GET | `/api/v1/stock-transfers/{transfer_id}` | Detail Transfer dan baris | Bearer | `transfer:read` `(g)` | [stock-transfers.md](stock-transfers.md#53-get-apiv1stock-transferstransfer_id--detail-transfer) |
| 68 | PATCH | `/api/v1/stock-transfers/{transfer_id}` | Revisi Transfer `DRAFT` | Bearer | `transfer:create` `(g asal)` | [stock-transfers.md](stock-transfers.md#54-patch-apiv1stock-transferstransfer_id--revisi-transfer) |
| 69 | POST | `/api/v1/stock-transfers/{transfer_id}/approve` | Setujui Transfer | Bearer | `transfer:approve` `(g asal)` | [stock-transfers.md](stock-transfers.md#55-post-apiv1stock-transferstransfer_idapprove--setujui) |
| 70 | POST | `/api/v1/stock-transfers/{transfer_id}/ship` | Kirim dan kurangi saldo gudang asal | Bearer | `transfer:ship` `(g asal)` | [stock-transfers.md](stock-transfers.md#56-post-apiv1stock-transferstransfer_idship--kirim) |
| 71 | POST | `/api/v1/stock-transfers/{transfer_id}/receive` | Catat penerimaan final dan selisih | Bearer | `transfer:receive` `(g tujuan)` | [stock-transfers.md](stock-transfers.md#57-post-apiv1stock-transferstransfer_idreceive--terima) |
| 72 | POST | `/api/v1/stock-transfers/{transfer_id}/cancel` | Batalkan Transfer `DRAFT`/`APPROVED` | Bearer | `transfer:create` / `transfer:approve` `(g asal)` | [stock-transfers.md](stock-transfers.md#58-post-apiv1stock-transferstransfer_idcancel--batalkan) |
| 73 | GET | `/api/v1/stock-opnames` | Daftar dan filter sesi Stock Opname | Bearer | `opname:read` `(g)` | [stock-opnames.md](stock-opnames.md#51-get-apiv1stock-opnames--daftar-sesi) |
| 74 | POST | `/api/v1/stock-opnames` | Buat sesi `DRAFT` | Bearer | `opname:manage` `(g)` | [stock-opnames.md](stock-opnames.md#52-post-apiv1stock-opnames--buat-sesi) |
| 75 | GET | `/api/v1/stock-opnames/{opname_id}` | Detail sesi dan baris hitung | Bearer | `opname:read` `(g)` | [stock-opnames.md](stock-opnames.md#53-get-apiv1stock-opnamesopname_id--detail-sesi) |
| 76 | PATCH | `/api/v1/stock-opnames/{opname_id}` | Revisi sesi `DRAFT` | Bearer | `opname:manage` `(g)` | [stock-opnames.md](stock-opnames.md#54-patch-apiv1stock-opnamesopname_id--revisi-sesi) |
| 77 | POST | `/api/v1/stock-opnames/{opname_id}/start` | Ambil snapshot dan mulai sesi | Bearer | `opname:manage` `(g)` | [stock-opnames.md](stock-opnames.md#55-post-apiv1stock-opnamesopname_idstart--mulai-sesi) |
| 78 | POST | `/api/v1/stock-opnames/{opname_id}/count` | Input atau revisi hasil hitung | Bearer | `opname:count` `(g)` | [stock-opnames.md](stock-opnames.md#56-input-hasil-hitung--post-opname_idcount) |
| 79 | POST | `/api/v1/stock-opnames/{opname_id}/submit` | Ajukan hasil hitung | Bearer | `opname:count` `(g)` | [stock-opnames.md](stock-opnames.md#57-post-apiv1stock-opnamesopname_idsubmit--ajukan-persetujuan) |
| 80 | POST | `/api/v1/stock-opnames/{opname_id}/approve` | Setujui dan terapkan selisih | Bearer | `opname:approve` `(g)` | [stock-opnames.md](stock-opnames.md#58-post-apiv1stock-opnamesopname_idapprove--setujui) |
| 81 | POST | `/api/v1/stock-opnames/{opname_id}/reject` | Tolak dan minta hitung ulang | Bearer | `opname:approve` `(g)` | [stock-opnames.md](stock-opnames.md#59-post-apiv1stock-opnamesopname_idreject--tolak) |
| 82 | POST | `/api/v1/stock-opnames/{opname_id}/cancel` | Batalkan sesi `DRAFT`/`IN_PROGRESS` | Bearer | `opname:manage` `(g)` | [stock-opnames.md](stock-opnames.md#510-post-apiv1stock-opnamesopname_idcancel--batalkan) |
| 83 | GET | `/api/v1/menus/my-menu` | Ambil pohon menu aktif sesuai permission pengguna | Bearer | – (autentikasi saja) | [menus.md](menus.md#41-mengambil-pohon-menu-pengguna) |
| 84 | GET | `/api/v1/menus` | Daftar katalog menu (pagination, filter, pencarian, sorting) | Bearer | `user:manage` | [menus.md](menus.md#42-membaca-katalog-menu) |
| 85 | POST | `/api/v1/menus` | Buat menu navigasi | Bearer | `user:manage` | [menus.md](menus.md#43-membuat-menu) |
| 86 | GET | `/api/v1/menus/{menu_id}` | Detail menu berdasarkan ID | Bearer | `user:manage` | [menus.md](menus.md#44-membaca-detail-menu) |
| 87 | PATCH | `/api/v1/menus/{menu_id}` | Ubah atau nonaktifkan menu | Bearer | `user:manage` | [menus.md](menus.md#45-memperbarui-atau-menonaktifkan-menu) |
---

## 4. Ringkasan Status Verifikasi & Perbaikan Temuan

Seluruh temuan hasil tinjauan silang antara kode aktual, skema database, pengujian, dan PRD telah diperbaiki dan diverifikasi dengan pengujian otomatis (`pytest`):

1. **Kredensial & Rahasia Wajib dari Lingkungan (`app/core/config.py`)** — ✅ **Terverifikasi** ([authentication.md](authentication.md#8-catatan-dan-status-verifikasi)):
   * Atribut `database_url` dan `jwt_secret` (minimal 32 karakter) pada `Settings` kini diwajibkan tanpa nilai *fallback* statis di kode sumber, selaras dengan PRD 7.2 dan AGENTS.MD §6.
2. **Pencegahan Penguncian Diri (*Self-Lockout*) Super Admin & Validasi Email** — ✅ **Terverifikasi** ([users.md](users.md#8-catatan-dan-status-verifikasi)):
   * `PATCH /api/v1/users/{id}` menolak penonaktifan akun sendiri (`is_active: false`) dan perubahan peran sendiri (`role_id`) dengan `422 VALIDATION_ERROR`.
   * `PUT /api/v1/users/roles/{role_id}/permissions` menolak pencabutan izin `user:manage` dari peran `Super Admin` dengan `422 VALIDATION_ERROR`.
   * Pembuatan dan pembaruan pengguna serta pemasok memvalidasi format alamat email (`EMAIL_REGEX`).
3. **Validasi Proxy Tepercaya pada Header `X-Forwarded-For`** — ✅ **Terverifikasi** ([authentication.md](authentication.md#8-catatan-dan-status-verifikasi)):
   * `get_client_ip()` hanya mempercayai header `X-Forwarded-For` apabila alamat IP koneksi langsung (`request.client.host`) terdaftar di `TRUSTED_PROXY_IPS`.
4. **Ketahanan `GET /health` Saat Database Tidak Dapat Dihubungi** — ✅ **Terverifikasi** ([health.md](health.md#8-catatan-dan-status-verifikasi)):
   * `check_pool_health()` menangkap kegagalan koneksi pool (`PsycopgError`, `PoolTimeout`, `OSError`) sehingga endpoint tetap mengembalikan respons terstruktur `status: "degraded", database: "disconnected"` tanpa melempar `500 INTERNAL_ERROR`.
5. **Pengujian Otomatis Imutabilitas (`tests/test_immutability.py` — AC-08)** — ✅ **Terverifikasi** ([audit-logs.md](audit-logs.md#8-catatan-dan-status-verifikasi)):
   * Skenario pengujian `test_ac08_immutability_stock_movements_and_audit_logs` telah diimplementasikan dan lulus terhadap role aplikasi (`wms_app`) maupun pemilik tabel (*table owner*).
6. **Master Data, Gudang, Lokasi Penyimpanan & Penegakan `ENTITY_IN_USE` / `WAREHOUSE_NOT_ASSIGNED` (Tahap M3)** — ✅ **Terverifikasi** ([master-data.md](master-data.md#8-catatan-dan-status-verifikasi), [warehouses.md](warehouses.md#8-catatan-dan-status-verifikasi)):
   * Seluruh 26 endpoint pada `master.py` dan `warehouses.py` telah diimplementasikan dan diuji di `tests/test_rbac_scoping.py` (`test_ac12_warehouse_scoping_assignment_and_access_enforcement` dan `test_master_data_and_warehouse_crud_deactivation_and_sku_immutability`).
   * Penonaktifan entitas yang masih bersaldo atau dipakai pada dokumen belum final ditolak dengan `409 ENTITY_IN_USE`, perubahan SKU/UoM barang setelah bertransaksi ditolak dengan `409 ENTITY_IN_USE`, dan pengelolaan lokasi pada gudang yang tidak ditugaskan ditolak dengan `403 WAREHOUSE_NOT_ASSIGNED`.
7. **Verifikasi Akhir M8 & Fase 1 — Seluruh AC-01 sampai AC-22 Lulus Penuh** — ✅ **34 Test Lulus 100%**:
   * Seluruh 34 skenario pengujian otomatis lulus terhadap database PostgreSQL sungguhan (`wms_test`).
   * Menguji penuh seluruh AC-01 s.d. AC-22:
     * AC-01: Partial & Over-Receipt pada Goods Receipt
     * AC-02: Pencegahan Saldo Negatif & Pembekuan Stok Opname
     * AC-03: Konsistensi Transfer Antar-Gudang & Perhitungan In-Transit
     * AC-04: Rekonsiliasi Stock Opname & Buku Besar Selisih
     * AC-05: Penegakan RBAC & Audit Log Perubahan Hak Akses
     * AC-06: Konkurensi Pengiriman Transfer Stok
     * AC-07: Atomisitas Transaksi & Rollback Total saat Kegagalan
     * AC-08: Imutabilitas Append-Only Tabel `stock_movements` & `audit_logs`
     * AC-09: Penerimaan Transfer & Validasi Alasan Selisih
     * AC-10: Pembekuan Lokasi (*Location Freeze*) saat Opname Berlangsung
     * AC-11: Rotasi Refresh Token, Deteksi Pemakaian Ulang, & Logout
     * AC-12: Penegakan Penugasan Gudang (*Warehouse Scoping*) untuk Staff, Manager, dan Purchasing
     * AC-13: Konkurensi Posting GR & Pencegahan Double Posting
     * AC-14: Pohon Menu Dinamis & Otomasi Hirarki Permission
     * AC-15: Konkurensi Penomoran Dokumen Atomik & Rollover Bulanan
     * AC-16: Paginasi, Whitelist Pengurutan, & Format Desimal String NUMERIC(18,4)
     * AC-17: Korelasi Header `X-Request-ID`, Sanitasi Karakter, & Endpoint `/health`
     * AC-18: Runner Migrasi Forward-Only, Pencatatan `schema_migrations`, & Idempotensi
     * AC-19: Imutabilitas Master Data (SKU, allow_decimal UoM) & `ENTITY_IN_USE`
     * AC-20: Validasi Kepemilikan Lokasi Gudang & Audit Perubahan `allow_negative_stock`
     * AC-21: Penolakan Transisi Status Dokumen di Luar FSM (`INVALID_STATE_TRANSITION`)
     * AC-22: Kelengkapan Audit Log, Sanitasi Rahasia/Password, & Otorisasi Pembacaan
8. **Validasi `X-Request-ID` (PRD 7.6)** — ✅ **Terverifikasi** (`tests/test_request_id.py`, `tests/test_ac15_to_ac22.py`): nilai aman hingga 128 karakter dipertahankan; nilai dengan karakter di luar whitelist atau panjang berlebih diganti dengan UUID agar tidak masuk ke log mentah.
9. **Menu navigasi dinamis (FR-01, AC-14)** — ✅ **Terverifikasi** (`tests/test_menus.py`): pohon menu tersaring menurut permission, parent tanpa anak terlihat disembunyikan, operasi katalog dibatasi `user:manage`, audit log tercatat, dan parent aktif tidak dapat dinonaktifkan selama memiliki anak aktif.
