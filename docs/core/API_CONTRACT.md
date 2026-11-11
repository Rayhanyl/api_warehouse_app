# API Contract — Ringkasan CORE

Dokumen ini menetapkan batas kontrak API tingkat sistem tanpa menyalin detail
setiap endpoint. Detail operasional dan contoh request/response berada di
[API/README.md](../API/README.md) dan dokumen modul di folder tersebut.

## Kontrak global

- Base path modul: `/api/v1` (pengecualian: `GET /health` pada root).
- Format payload: JSON.
- Autentikasi: JWT HS256 melalui header `Authorization: Bearer <access-token>` (TTL 15 menit) dan refresh token melalui JSON body (TTL 7 hari).
- Waktu: ISO 8601 UTC dengan timezone (`TIMESTAMPTZ`).
- Kuantitas: string desimal pada JSON; penyimpanan PostgreSQL menggunakan `NUMERIC(18,4)`; tidak boleh menggunakan `float`.
- Pagination & Sorting:
  - Query parameter: `limit` (`1..200`, default `50`), `offset` (`>= 0`, default `0`), `sort_by` (hanya kolom pada whitelist endpoint), `sort_dir` (`asc` atau `desc`).
  - Envelope respons list: `{ "items": [...], "total": <int>, "limit": <int>, "offset": <int> }`.
- Action Endpoint: perubahan status dokumen hanya melalui `POST /api/v1/<resource>/{id}/<action>` sesuai matriks transisi `PRD_GENERAL.md` bagian 7.5; tidak ada endpoint update kolom `status` generik.
- Error: objek `{ "error": { "code": "<ERROR_CODE>", "message": "<pesan>", "details": { ... } } }`.
- Request ID: header `X-Request-ID` dipertahankan bila valid (`^[A-Za-z0-9._-]{1,128}$`) atau dibuat server (UUIDv4) pada setiap respons termasuk error.

## Import massal item (`FR-MST-006`)

- `GET /api/v1/items/import-template` memerlukan autentikasi dan permission
  `master:read`, lalu mengunduh workbook `.xlsx` dengan MIME type
  `application/vnd.openxmlformats-officedocument.spreadsheetml.sheet`. Sheet
  `Items` memiliki header `sku`, `barcode`, `name`, `description`, `category_name`,
  `uom_name`, `is_active`; sheet `Referensi` memiliki header
  `category_name`, `uom_name`, `uom_code` dan berisi pilihan master aktif.
- `POST /api/v1/items/import` memerlukan `master:manage` dan menerima tepat satu
  workbook `.xlsx` melalui `multipart/form-data`, field `file`.
- Dropdown kategori/UoM mengacu ke sheet `Referensi`. `barcode` bersifat opsional (teks 1–64 karakter bila diisi, unik case-insensitive). `is_active` menerima
  `active`/`inactive` atau boolean Excel; kosong berarti `true`.
- Batas yang disetujui adalah 5 MiB dan 1.000 baris data (`CONF-010`);
  baris kosong diabaikan.
- File yang terbaca menghasilkan `200 OK` dan JSON ringkasan berisi
  `total_rows`, `imported_count`, `failed_count`, serta `errors[]` dengan
  nomor baris Excel, `field`, `code`, dan pesan aman. Respons `200` dapat
  melaporkan hasil parsial; error per baris memakai kode katalog yang sudah
  ada, seperti `DUPLICATE`, `NOT_FOUND`, `INACTIVE_REFERENCE`, dan
  `VALIDATION_ERROR`. Nama kategori/UoM dicocokkan case-insensitive ke
  database; nama ambigu menghasilkan `VALIDATION_ERROR`, tanpa pemilihan
  otomatis. Pesan nama UoM ambigu menyertakan kode kandidat.
- `total_rows` menghitung baris data non-kosong, `imported_count` menghitung
  item yang commit, dan `failed_count` menghitung baris dengan satu atau lebih
  error. `errors[]` boleh memuat lebih dari satu kesalahan untuk satu baris.
- File rusak, sheet/header tidak sesuai, batas ukuran/baris terlampaui, atau
  bentuk request salah menghasilkan error envelope standar dengan
  `422 VALIDATION_ERROR`; file tersebut tidak membuat item.
- Sheet referensi hanya panduan dan bukan sumber ID; backend menyelesaikan
  `category_id` dan `uom_id` dari data master terkini.
- Semua baris valid yang berhasil dibuat dan audit `ITEM_CREATED` commit dalam
  satu transaksi. Kegagalan infrastruktur me-rollback seluruh insert request.
  Duplikasi SKU concurrent dilaporkan per baris dan tidak menghentikan baris
  valid lainnya.
- Endpoint tidak menambah kode error global, tabel, atau kolom. Parser XLSX dan
  penerimaan multipart memakai dependensi `openpyxl` dan `python-multipart` yang
  telah disetujui.

## Import massal supplier (`FR-MST-007`)

- `GET /api/v1/suppliers/import-template` memerlukan `master:read` dan
  mengunduh workbook `.xlsx` bernama `template_import_supplier.xlsx`, dengan
  satu sheet `Suppliers` dan header `code`, `name`, `contact_person`, `phone`,
  `email`, `address`, `is_active`.
- `POST /api/v1/suppliers/import` memerlukan `master:manage` dan menerima satu
  file di field `file` (`multipart/form-data`). Batasnya 5 MiB dan 1.000 baris
  data; baris kosong dilewati.
- Kolom mengikuti aturan `SupplierCreate`: code 1–50 karakter, name 1–150,
  contact person 120, phone 30, email 255, address 1.000. Format code, phone,
  dan email divalidasi; email dinormalisasi ke huruf kecil. `is_active` menerima
  `active`/`inactive` atau boolean Excel, kosong berarti `true`.
- File yang terbaca menghasilkan `200 OK` dan ringkasan parsial
  `total_rows`, `imported_count`, `failed_count`, serta `errors[]` dengan nomor
  baris Excel, `field`, `code`, dan pesan aman. Kode duplikat dalam file,
  database, atau request konkuren dilaporkan sebagai `DUPLICATE`; seluruh baris
  yang mengulang kode di dalam file gagal, sedangkan baris valid lain tetap
  dapat dibuat.
- Workbook rusak, header/sheet salah, atau batas terlampaui menghasilkan
  `422 VALIDATION_ERROR` tanpa insert. Pembuatan supplier dan audit
  `SUPPLIER_CREATED` commit dalam satu transaksi. Endpoint tidak menambah kode
  error, tabel, atau kolom.

## Barcode barang, generator otomatis, dan lookup scanner (`FR-MST-008`, `FR-MST-009`, `FR-INV-007`, `FR-INV-008`, `AC-33`, `AC-34`)

- Pembuatan dan pembaruan item (`POST /api/v1/items`, `PATCH /api/v1/items/{id}`) menerima field opsional `barcode` (string teks maks 64 karakter, null jika tidak ada).
- Field `barcode` mendukung fleksibilitas operasional:
  1. *Barcode Pabrik:* Diinput manual atau dipindai langsung dari kemasan fisik pabrikan via barcode gun/kamera.
  2. *Auto-Generate Barcode WMS (`FR-MST-009`):* Untuk produk non-barcode (*re-pack*, curah, *private label*), form menyediakan generator barcode internal otomatis berstandar EAN-13 GS1 Internal (prefix `200`..`299` + checksum) atau Code-128 unik.
- Keunikan `barcode` dijaga secara case-insensitive (`uq_items_barcode_lower`); duplikasi nilai non-null ditolak dengan `409 DUPLICATE`.
- Endpoint pencarian `GET /api/v1/items` mendukung parameter `search` dan `barcode` untuk auto-matching barang pada transaksi operasional (GR, Transfer, Opname).
- **Pindai Cek Barang & Posisi Rak Gudang (`FR-INV-008`, `AC-34`):**
  - Pemindaian barcode produk fisik di lantai gudang memanggil `GET /api/v1/stock/by-location?search=<barcode_or_sku>` untuk mengembalikan sebaran rak gudang aktual (`location_code`, `location_name`, `warehouse_name`, `qty_on_hand`, `qty_in_transit`).
  - Digabungkan dengan profil master barang (`GET /api/v1/items?barcode=<barcode>` atau hasil pencarian) ke dalam modal `StockLookupModal` untuk menampilkan kartu identitas barang dan posisi rak secara instan.
- **Visualisasi Barcode Vektor & Cetak Label Stiker (`FR-MST-010`, `AC-35`):**
  - Database hanya menyimpan string `barcode` dan `sku`; gambar batang barcode (`<svg>` EAN-13 / Code-128) dirender secara deterministik *on-the-fly* di sisi klien (frontend) baik untuk pratinjau layar maupun pencetakan stiker fisik (`50x30 mm`).

## Kontrak cetak dokumen fisik (`FR-RCV-005`, `FR-TRF-006`, `AC-32`)

- Endpoint `GET /api/v1/goods-receipts/{id}` dan `GET /api/v1/stock-transfers/{id}` mengembalikan data relasional lengkap (header, rincian lines dengan SKU, barcode, nama barang, UoM, lokasi rak, kuantitas, catatan, dan nama pengguna penandatangan) yang siap dikonsumsi langsung oleh komponen cetak frontend (`@media print` / `window.print()`).
- Dokumen fisik Surat Jalan (`TRF-F06`) dan Bukti Penerimaan Barang (`RCV-F05`) tidak memerlukan endpoint biner PDF tambahan pada backend; rendering cetak dan penyimpanan ke PDF ditangani secara presisi pada layer antarmuka pengguna.

## Katalog kode error resmi

Seluruh kode error bisnis (`DomainError` pada `app/core/exceptions.py`) dan handler
umum (`app/main.py`) mengikuti katalog tunggal berikut:

| Kode Error | HTTP Status | Kelas Exception / Handler | Kondisi Penggunaan |
| --- | :---: | --- | --- |
| `AUTH_INVALID_CREDENTIALS` | 401 | `AuthInvalidCredentials` | Username atau kata sandi salah saat login atau ganti kata sandi |
| `AUTH_TOKEN_INVALID` | 401 | `AuthTokenInvalid` | Access/refresh token tidak valid, kedaluwarsa, dicabut, reuse terdeteksi, atau akun nonaktif |
| `AUTH_TOO_MANY_ATTEMPTS` | 429 | `AuthTooManyAttempts` | Akun sedang terkunci sementara karena >= 5 kali gagal login berturut-turut |
| `PERMISSION_DENIED` | 403 | `PermissionDenied` | Peran pengguna tidak memiliki permission untuk endpoint atau aksi tersebut |
| `WAREHOUSE_NOT_ASSIGNED` | 403 | `WarehouseNotAssigned` | Pengguna tidak ditugaskan ke gudang yang menjadi cakupan operasi `(g)` |
| `NOT_FOUND` | 404 | `NotFoundError` | Entitas master, pengguna, menu, lokasi, atau dokumen transaksi tidak ditemukan |
| `VALIDATION_ERROR` | 422 | `ValidationDomainError` / `RequestValidationError` | Kegagalan validasi skema request, parameter query/sort/pagination, kuantitas desimal pada UoM integer, atau aturan input domain |
| `INVALID_LOCATION` | 422 | `InvalidLocationError` | Lokasi penyimpanan tidak ditemukan, tidak aktif, atau bukan milik gudang yang direferensikan |
| `INACTIVE_REFERENCE` | 422 | `InactiveReferenceError` | Referensi master data, gudang, atau parent menu yang dipilih berstatus tidak aktif |
| `DUPLICATE` | 409 | `DuplicateError` | Pelanggaran keunikan kode, nama kategori, SKU, username, atau email |
| `INVALID_STATE_TRANSITION` | 409 | `InvalidStateTransition` | Aksi status dokumen tidak sesuai status awal atau kondisi wajib pada matriks transisi bagian 7.5 |
| `INSUFFICIENT_STOCK` | 409 | `InsufficientStock` | Saldo stok tidak mencukupi saat `allow_negative_stock = false` |
| `OVER_RECEIPT` | 409 | `OverReceipt` | Kuantitas penerimaan GR melebihi sisa `qty_ordered - qty_received` pada baris PO |
| `TRANSFER_QTY_EXCEEDS_SHIPPED` | 409 | `TransferQtyExceedsShipped` | Kuantitas `qty_received` pada penerimaan Transfer melebihi `qty` yang dikirim |
| `LOCATION_FROZEN` | 409 | `LocationFrozen` | Lokasi sedang dibekukan oleh sesi Stock Opname aktif (`IN_PROGRESS` atau `WAITING_APPROVAL`) |
| `ENTITY_IN_USE` | 409 | `EntityInUse` | Entitas tidak dapat dinonaktifkan atau diubah atribut kuncinya (`sku`, `uom_id`, `allow_decimal`) karena sedang direferensikan saldo/transaksi/item/anak menu aktif |
| `INTERNAL_ERROR` | 500 | Handler `Exception` umum | Kesalahan internal tak terduga (detail teknis tidak diekspos ke klien) |

### Tambahan kontrak dan kode error pada Fase 2 (M9 — Multi-Tenant SaaS)

Pada saat Fase 2 (M9) diimplementasikan, kontrak API diperluas dengan ketentuan berikut:

1. **Kontrak Autentikasi Tenant vs Platform Admin:**
   - `POST /api/v1/auth/login` menerima `{ "tenant_slug": "<slug>", "username": "<user>", "password": "<pass>" }` dan menerbitkan JWT dengan klaim `{ "sub": "<user_id>", "tenant_id": <int>, "scope": "tenant", "jti": "<uuid>", "iat": <int>, "exp": <int> }`.
   - `POST /api/v1/platform/auth/login` menerima `{ "username": "<admin>", "password": "<pass>" }` (tanpa `tenant_slug`) dan menerbitkan JWT dengan klaim `{ "sub": "<admin_id>", "tenant_id": null, "scope": "platform", "jti": "<uuid>", "iat": <int>, "exp": <int> }`.
2. **Endpoint Baru Fase 2 (M9):**
   - Platform Admin (`/api/v1/platform/*`): `POST /api/v1/platform/auth/login`, `POST /api/v1/platform/auth/refresh`, `POST /api/v1/platform/auth/logout`, `GET /api/v1/platform/plans`, `GET /api/v1/platform/tenants`, `POST /api/v1/platform/tenants`, `GET /api/v1/platform/tenants/{tenant_id}`, `PATCH /api/v1/platform/tenants/{tenant_id}`, `POST /api/v1/platform/tenants/{tenant_id}/activate`, `POST /api/v1/platform/tenants/{tenant_id}/suspend`, `POST /api/v1/platform/tenants/{tenant_id}/deactivate`.
   - Tenant Profile & Settings (`/api/v1/tenant/*` & `/api/v1/settings`): `GET /api/v1/tenant/profile`, `PATCH /api/v1/tenant/profile`, `GET /api/v1/settings`, `PUT /api/v1/settings`, `GET /api/v1/warehouses/{warehouse_id}/settings`, `PUT /api/v1/warehouses/{warehouse_id}/settings`.
3. **Kode Error Tambahan Fase 2 (M9):**
   - `TENANT_SUSPENDED` (HTTP 403): Tenant berstatus `SUSPENDED` atau `DEACTIVATED`.
   - `TENANT_NOT_FOUND` (HTTP 404): `tenant_slug` atau `tenant_id` tidak ditemukan.
   - `QUOTA_EXCEEDED` (HTTP 409): Penambahan/pengaktifan gudang, pengguna aktif, atau barang aktif melampaui batas kuota paket (`plans`) tenant.

## Ownership

CORE hanya menetapkan prinsip dan katalog kontrak. Route dan schema aktual
menentukan bentuk endpoint; repository tidak boleh menjadi sumber kontrak HTTP.
Jika implementasi berbeda dari PRD, catat di
[Documentation Audit](DOCUMENTATION_AUDIT.md) dan dokumentasikan perilaku aktual
di [API/README.md](../API/README.md).

## Rujukan

- Kebutuhan dan acceptance criteria:
  [PRD_GENERAL.md](PRD_GENERAL.md).
- Kebutuhan backend:
  [PRD_BACKEND.md](PRD_BACKEND.md).
- Struktur layer:
  [FOLDER_STRUCTURE.MD](FOLDER_STRUCTURE.MD).
- Detail endpoint:
  [API/README.md](../API/README.md).
