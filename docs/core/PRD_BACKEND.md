# PRD Backend — Spesifikasi Implementasi

Dokumen ini menerjemahkan [PRD General](PRD_GENERAL.md) ke kebutuhan backend.
Ia tidak mendefinisikan ulang tujuan bisnis, role, scope, atau acceptance
criteria; setiap ID `FR` dan `AC` mengacu pada PRD General.

## 1. Tanggung jawab dan batas

Backend bertanggung jawab atas HTTP API, autentikasi, otorisasi, validasi,
aturan bisnis, transaksi, persistence, audit, dan error terstruktur. Backend
tidak bertanggung jawab atas UI atau keputusan bisnis yang belum disetujui.

Implementasi mengikuti [FOLDER_STRUCTURE](FOLDER_STRUCTURE.MD):
`routes -> services -> repositories -> core/database`. SQL hanya berada di
repository, transaksi dibuka oleh service, dan route memanggil satu use case service.

## 2. API requirements

- Base path: `/api/v1`; health check tersedia pada root dan prefix v1.
- Payload: JSON; waktu ISO 8601 dengan timezone.
- Auth: `Authorization: Bearer <access-token>` untuk endpoint terlindungi.
- Request ID: `X-Request-ID` dipertahankan atau dibuat server.
- Pagination: `limit` 1–200, default 50, dan `offset >= 0` bila endpoint mendukung.
- Kuantitas: string desimal yang dipetakan ke `Decimal`, bukan `float`.
- Error: `{ "error": { "code", "message", "details" } }`.
- Import item (`FR-MST-006`) dan import supplier (`FR-MST-007`) masing-masing menerima satu workbook `.xlsx` melalui `multipart/form-data`; batas yang
  disetujui adalah 1.000 baris data dan ukuran 5 MiB (`CONF-010`). Hasil per baris yang valid/tidak valid
  dikembalikan pada satu respons ringkasan.

Daftar endpoint aktual dan contoh payload berada di [API documentation](../API/README.md)
dan [API Contract](API_CONTRACT.md). Dokumen ini hanya menetapkan kebutuhan
implementasi, bukan menyalin seluruh katalog endpoint.

### 2.1 Import massal item (`FR-MST-006`)

| Method | Path | Permission | Kontrak |
| --- | --- | --- | --- |
| `GET` | `/api/v1/items/import-template` | `master:read` | Mengunduh workbook `.xlsx` dengan MIME type Excel dan nama file stabil. |
| `POST` | `/api/v1/items/import` | `master:manage` | Menerima satu file workbook `.xlsx` pada field `file` (`multipart/form-data`). |

Template memuat sheet `Items` dan `Referensi`. Header masing-masing berada pada
baris 1. Sheet `Items` memiliki kolom berurutan berikut.

| Header | Tipe sel | Wajib | Batas/validasi |
| --- | --- | --- | --- |
| `sku` | Teks | Ya | 1–64 karakter; unik tanpa membedakan kapitalisasi |
| `barcode` | Teks | Tidak | Kosong menjadi `null`; bila diisi, 1–64 karakter dan unik tanpa membedakan kapitalisasi |
| `name` | Teks | Ya | 1–200 karakter |
| `description` | Teks | Tidak | Kosong menjadi `null` |
| `category_name` | Teks | Ya | Maksimal 120 karakter; kategori ditemukan dan aktif |
| `uom_name` | Teks | Ya | Maksimal 60 karakter; nama cocok dengan tepat satu UoM aktif |
| `is_active` | Teks/boolean Excel | Tidak | `active`/`inactive` atau boolean; kosong berarti `true` |

Sheet `Referensi` memiliki header `category_name`, `uom_name`, `uom_code`, dan
berisi kategori serta UoM aktif saat template dibuat. Sheet ini memberi daftar
referensi dan dropdown, tetapi backend tidak mempercayai nilainya untuk
menentukan relasi. Backend mencocokkan nama kategori dan UoM ke database saat
import. Pencocokan case-insensitive setelah trim; nama yang cocok ke lebih dari
satu referensi ditolak dengan `VALIDATION_ERROR`. Untuk nama UoM ambigu, pesan
error menyertakan kode kandidat. Kategori dan UoM yang tidak ditemukan memakai
`NOT_FOUND`; referensi tunggal yang nonaktif memakai `INACTIVE_REFERENCE`.

SKU disimpan sebagai teks. Header harus sama persis dan berurutan, tanpa kolom
di luar template. Data item dimulai pada baris 2; baris kosong dilewati dan
nomor error menggunakan nomor baris workbook. Workbook tanpa sheet/header yang
tepat ditolak sebelum validasi data.

Untuk workbook yang dapat dibaca, `POST` mengembalikan `200 OK` dengan
`total_rows`, `imported_count`, `failed_count`, dan `errors[]`. Setiap error
memuat nomor baris Excel, field, kode katalog, dan pesan aman. Baris kosong
dilewati. `total_rows` menghitung baris data non-kosong, `imported_count`
menghitung item yang commit, dan `failed_count` menghitung baris dengan satu
atau lebih error. Baris valid diimpor meskipun baris lain gagal; respons tidak
mengandung data sukses sebelum transaksi commit. File rusak, sheet/header tidak
cocok, atau batas ukuran/baris yang disetujui terlampaui menghasilkan `422 VALIDATION_ERROR`
dan tidak menyimpan item. MIME type unduhan template adalah
`application/vnd.openxmlformats-officedocument.spreadsheetml.sheet`.

Contoh respons hasil parsial:

```json
{
  "total_rows": 12,
  "imported_count": 9,
  "failed_count": 3,
  "errors": [
    {
      "row": 4,
      "field": "sku",
      "code": "DUPLICATE",
      "message": "SKU sudah terdaftar."
    }
  ]
}
```

Service memvalidasi semua baris sebelum penyimpanan. Referensi dan SKU existing
diambil secara kelompok, bukan melalui query per baris. Insert menggunakan
operasi batch berparameter. Unique index SKU case-insensitive tetap menjadi
sumber kebenaran; konflik konkuren dilaporkan sebagai `DUPLICATE` di baris
terkait dan tidak menggagalkan insert valid lain. Item sukses dan satu event
`ITEM_CREATED` per item berada di satu transaksi. Kegagalan infrastruktur
membatalkan transaksi request. Tidak ada upsert atau pembuatan saldo.

Implementasi memakai `openpyxl` untuk workbook `.xlsx` dan `python-multipart`
untuk `multipart/form-data`; kedua dependensi telah disetujui dan tercantum pada
konfigurasi proyek.

### 2.2 Import massal supplier (`FR-MST-007`)

| Method | Path | Permission | Kontrak |
| --- | --- | --- | --- |
| `GET` | `/api/v1/suppliers/import-template` | `master:read` | Mengunduh template `.xlsx` bernama `template_import_supplier.xlsx`. |
| `POST` | `/api/v1/suppliers/import` | `master:manage` | Menerima satu workbook `.xlsx` di field `file` (`multipart/form-data`). |

Template memiliki satu sheet `Suppliers` dan header berurutan
`code`, `name`, `contact_person`, `phone`, `email`, `address`, `is_active`.
Batas field mengikuti `SupplierCreate`: kode 1–50, nama 1–150, contact person
maksimal 120, telepon maksimal 30, email maksimal 255, alamat maksimal 1.000.
Kode mengikuti format kode master. Telepon mengikuti `PHONE_REGEX` dan minimal
memiliki enam digit. Email divalidasi dengan `EMAIL_REGEX` dan dinormalisasi ke
huruf kecil. Field opsional kosong menjadi `null`; `is_active` menerima teks
`active`/`inactive` atau boolean Excel dan default `true`.

Kode supplier dicocokkan case-insensitive ke database. Kode berulang dalam
workbook menandai semua baris yang memakai kode tersebut sebagai `DUPLICATE`;
kode yang sudah ada atau konflik konkuren ditandai per baris. Baris valid lain
tetap dibuat. Parser memvalidasi workbook sebelum membuka transaksi; insert
batch dan event audit `SUPPLIER_CREATED` per baris berhasil berada pada satu
transaksi. Batas file dan data adalah 5 MiB dan 1.000 baris. File rusak,
header/sheet salah, dan batas terlampaui menghasilkan `422 VALIDATION_ERROR`
tanpa penyimpanan. Workbook yang terbaca menghasilkan ringkasan parsial
`total_rows`, `imported_count`, `failed_count`, dan `errors[]`.

### 2.3 Dukungan Barcode Barang & Lookup Scanner (`FR-MST-008`, `FR-INV-007`)

- **Skema Kolom & Pydantic:** Tabel `items` memiliki kolom `barcode VARCHAR(64) NULL`. Schema `ItemCreate`, `ItemUpdate`, dan `ItemOut` memuat atribut opsional `barcode: str | None = None` (maksimal 64 karakter, trim whitespace, case-insensitive uniqueness melalui indeks `uq_items_barcode_lower`).
- **Pencarian & Lookup Cepat:**
  - Endpoint `GET /api/v1/items` mendukung parameter `search` yang mencocokkan `sku`, `name`, maupun `barcode`, serta filter khusus `barcode` bila diperlukan.
  - Jika barcode tidak diisi saat pembuatan item, sistem mengizinkan nilai `null` (beberapa item dapat bernilai `barcode IS NULL`).
  - Lookup scanner: jika barcode dipindai, backend dapat mengembalikan entitas item yang cocok secara unik untuk digunakan auto-fill pada transaksi GR, Transfer, dan Opname.

### 2.4 Kelengkapan Kontrak Data Cetak Dokumen Fisik (`FR-RCV-005`, `FR-TRF-006`, `FR-MST-010`)

- Endpoint detail `GET /api/v1/goods-receipts/{id}` dan `GET /api/v1/stock-transfers/{id}` menjamin pengembalian data relasional lengkap tanpa truncate, mencakup:
  - Header: nomor dokumen, tanggal dokumen, nama & kode gudang (asal dan tujuan), data kontak supplier/pemasok, nama pembuat (`created_by_name`), pemeriksa, dan penyetuju.
  - Baris barang (*lines*): kode SKU, kode barcode (`item_barcode`), nama barang, kode UoM, kuantitas dikirim/dipesan, kuantitas diterima, kode rak/lokasi simpan (`location_code` & `location_name`), dan catatan per baris.
- Frontend memanfaatkan data lengkap tersebut untuk merender dokumen siap cetak (*print-ready layout* / `window.print()`) serta menyematkan grafik barcode SVG dokumen.

### 2.5 Pencarian Saldo Stok & Inspeksi Multi-SKU per Lokasi Rak / Gudang (`FR-WHS-004`, `FR-WHS-005`, `FR-INV-008`, `AC-34`, `AC-36`, `AC-37`)

- Endpoint `GET /api/v1/stock/by-location` (dan `/api/v1/stock/balances`) melalui `inventory_repo.list_stock_by_location` mendukung parameter `search` universal yang mencocokkan secara *case-insensitive* (`ILIKE`):
  - Identitas barang: `i.sku`, `i.name`, dan `i.barcode`.
  - Identitas lokasi rak: `sl.code` dan `sl.name`.
  - Identitas gudang: `w.code` dan `w.name`.
- Dengan perluasan query ini, ketika operator memindai **Barcode / QR Code Rak** (mis. `JKT-RAK-A1`) atau **QR Code Gudang** (mis. `WH-JKT-01`), backend mengembalikan seluruh daftar baris barang (*multi-SKU*) yang tersimpan pada rak atau gudang tersebut beserta `qty_on_hand` dan `qty_in_transit` dalam satu panggilan API terfilter sesuai *warehouse scoping* pengguna.

### 2.6 Endpoint API Dashboard Operasional (`FR-DSH-001`, `AC-38`)

| Method | Path | Permission | Kontrak |
| --- | --- | --- | --- |
| `GET` | `/api/v1/dashboard/summary` | User terautentikasi (`get_current_user`) | Mengembalikan ringkasan statistik stok, dokumen tertunda (action items), dan aktivitas terkini yang terisolasi sesuai penugasan gudang. |

- **Aturan Warehouse Scoping (`BR-GLB-007`):**
  - Jika pengguna memiliki peran `Super Admin` atau `Auditor`, query menghitung agregat lintas seluruh gudang aktif (`warehouse_id IS NULL` filter).
  - Jika pengguna memiliki peran operasional (`Warehouse Manager`, `Warehouse Staff`, `Purchasing Staff`), query membatasi perhitungan hanya pada `warehouse_id` yang terdaftar di `user_warehouses` pengguna. Jika pengguna tidak memiliki penugasan gudang, metrik stok dan dokumen bernilai 0 / list kosong.
- **Payload Respons (`DashboardSummaryOut`):**
  - `stock_summary`:
    - `total_active_items`: int (jumlah SKU barang aktif).
    - `total_qty_on_hand`: string desimal `NUMERIC(18,4)` (total saldo fisik tersimpan).
    - `total_qty_in_transit`: string desimal `NUMERIC(18,4)` (total barang dalam perjalanan transfer).
    - `low_stock_items_count`: int (jumlah barang dengan saldo on-hand <= 0 atau mendekati minimum).
  - `pending_actions`:
    - `pending_po_receipt_count`: int (jumlah PO `ISSUED` / `PARTIALLY_RECEIVED` yang menunggu penerimaan).
    - `draft_gr_count`: int (jumlah GR `DRAFT` yang belum diposting).
    - `pending_transfer_ship_count`: int (jumlah Transfer `APPROVED` yang menunggu pengiriman).
    - `pending_transfer_receive_count`: int (jumlah Transfer `SHIPPED` yang menunggu penerimaan cabang).
    - `active_opname_count`: int (jumlah sesi Opname `IN_PROGRESS` / `WAITING_APPROVAL` yang sedang membekukan lokasi).
  - `recent_activities`: list 5–10 pergerakan mutasi stok (`stock_movements`) atau dokumen terakhir (waktu, tipe, nomor referensi, nama barang, jumlah perubahan, nama aktor).
  - `assigned_warehouses`: list ringkas gudang aktif yang dievaluasi (`id`, `code`, `name`).

## 3. Arsitektur service, spesifikasi teknis, dan persistence

### 3.1 Spesifikasi teknologi & dependensi backend (`api_warehouse_app/`)

- **Runtime & Framework:** Python `3.12+`, FastAPI (`>=0.115`), Uvicorn (`uvicorn[standard]`).
- **Database Driver & Pool:** PostgreSQL `16+` diakses langsung melalui `psycopg[binary,pool]` v3 (`ConnectionPool` sinkron dengan `autocommit=True` dan `row_factory=dict_row`, tanpa ORM).
- **Validasi & Konfigurasi:** Pydantic v2 (`>=2.9`) dan `pydantic-settings` (`app/core/config.py`). Seluruh kuantitas menggunakan `Decimal` (`NUMERIC(18,4)`) yang diserialisasi sebagai string desimal.
- **Keamanan & Kriptografi:** `argon2-cffi` (hashing password Argon2id), `PyJWT` (`HS256` access token 15 menit, refresh token 7 hari disimpan sebagai SHA-256 hash di tabel `refresh_tokens`).
- **Pemrosesan File Excel:** `openpyxl` dan `python-multipart` untuk unduh template dan impor massal workbook `.xlsx`.
- **Migrasi Skema (`db/migrations/`):** Runner SQL *forward-only* (`db/migrate.py`) yang mengelola migrasi `001_create_auth_tables.sql` s.d. `012_add_barcode_to_items.sql` menggunakan koneksi pemilik skema (`MIGRATION_DATABASE_URL`), sementara aplikasi berjalan dengan role terbatas `wms_app` (`DATABASE_URL`).

### 3.2 Layer

| Layer | Lokasi Folder | Tanggung jawab |
| --- | --- | --- |
| Routes/dependencies | `app/api/routes/`, `app/api/deps.py` | Parse request, `require_permission`, panggil tepat satu fungsi service |
| Services | `app/services/` | Use case, aturan bisnis, `ensure_warehouse_access`, transaction boundary (`with conn.transaction():`), audit |
| Repositories | `app/repositories/` | Satu-satunya pemilik string SQL berparameter, row locking (`FOR UPDATE`/`FOR SHARE`), dan persistence |
| Schemas | `app/schemas/` | Bentuk request/response Pydantic (`XxxCreate`, `XxxUpdate`, `XxxOut`, `Page[T]`) |
| Core & Utils | `app/core/`, `app/utils/` | Config, connection pool, security, `DomainError`, middleware `X-Request-ID`, whitelist pagination/sort |

### 3.3 Transaksi dan locking

Satu aksi bisnis adalah satu transaksi yang mencakup status dokumen, saldo,
ledger, dan audit. Lock ordering: header dokumen, PO terkait, lokasi terurut,
lalu saldo terurut `(warehouse_id, location_id, item_id)`. Saldo dibuat dengan
`INSERT ... ON CONFLICT DO NOTHING` sebelum `FOR UPDATE`.

Seluruh perubahan saldo melewati `inventory_service.apply_movement()`.

## 4. Business logic dan validasi

- Verifikasi user aktif, role, dan permission dari database pada setiap request.
- Terapkan warehouse scoping melalui service, bukan middleware.
- Validasi state transition hanya pada endpoint aksi yang sah.
- Tolak referensi tidak aktif, lokasi yang tidak cocok, duplicate, dan entity in use
  sesuai katalog error.
- Hitung ulang over-receipt setelah PO line dikunci; hanya GR `POSTED` dihitung.
- Tolak stok negatif setelah saldo dikunci jika `allow_negative_stock = FALSE`.
- Tolak operasi pada lokasi frozen, kecuali adjustment opname yang diizinkan.
- Gunakan movement type hanya `IN_PURCHASE`, `OUT_TRANSFER`, `IN_TRANSFER`,
  `ADJUSTMENT_PLUS`, dan `ADJUSTMENT_MINUS`.

## 5. Authentication dan authorization

- Access token berlaku 15 menit (dikembalikan di payload JSON dan disimpan di memori aplikasi).
- Refresh token berlaku 7 hari, disimpan sebagai hash di database, dirotasi pada setiap pemanggilan `/api/v1/auth/refresh`, dan reuse token yang telah revoked mencabut seluruh sesi aktif pengguna.
- **Penyimpanan & Pengiriman Refresh Token Berbasis Cookie (`CONF-008`, `SEC-F01`):**
  - Pada `POST /api/v1/auth/login` dan `POST /api/v1/auth/refresh`, server menyetel header `Set-Cookie` dengan atribut: `refresh_token=<token>; HttpOnly; SameSite=Lax; Path=/api/v1/auth; Max-Age=604800` (flag `Secure` aktif pada environment produksi HTTPS).
  - Pada `POST /api/v1/auth/refresh`, server memprioritaskan pembacaan refresh token dari cookie peramban `request.cookies.get("refresh_token")` (dengan fallback ke JSON body untuk klien API/CLI otomatis).
  - Pada `POST /api/v1/auth/logout`, server menghapus cookie melalui `Set-Cookie: refresh_token=; Max-Age=0; Path=/api/v1/auth; ...` dan mencabut sesi di tabel database.
  - CORS middleware pada backend dikonfigurasi dengan `allow_credentials=True` dan whitelist origin frontend yang terdaftar.
- Password menggunakan Argon2id (`argon2-cffi`).
- Akun dikunci setelah lima kegagalan login sesuai aturan produk.
- Permission berasal dari role/database, bukan dipercaya dari claim token saja.

### 5.1 Arsitektur konteks Multi-Tenant & RLS pada Fase 2 (M9)

Karena `ConnectionPool` (`psycopg_pool`) berjalan dengan `autocommit=True` dan endpoint pembacaan (`GET`) tidak membuka blok `with conn.transaction():`, implementasi Fase 2 (M9) wajib mematuhi aturan propagasi konteks tenant berikut:

1. **Pengaturan dan Pembersihan Variabel Sesi PostgreSQL (`app.current_tenant_id`):**
   - Jangan menggunakan `SET LOCAL` di luar blok transaksi pada koneksi `autocommit=True` (karena nilai langsung hilang setelah statement `SET LOCAL` selesai).
   - Gunakan `SELECT set_config('app.current_tenant_id', %s, false)` saat dependency autentikasi tenant mengaktifkan konteks request, **DAN wajib** mengeksekusi `RESET app.current_tenant_id; RESET app.current_scope;` pada blok `finally` di `get_db()` serta pada callback `reset` milik `ConnectionPool` sebelum koneksi dikembalikan ke pool (mencegah *session variable bleed* lintas request).
2. **Resolusi Konteks Pra-Autentikasi (`login` dan `refresh`):**
   - Pada `POST /api/v1/auth/login`: service membaca tabel `tenants` berdasarkan `tenant_slug` (tabel `tenants` tidak dibatasi RLS tenant), memverifikasi status tenant melalui `ensure_tenant_active`, lalu menyetel `app.current_tenant_id` sebelum melakukan query ke tabel `users`.
   - Pada `POST /api/v1/auth/refresh`: resolusi `token_hash` pada `refresh_tokens` menetapkan `tenant_id` sesi terkait terlebih dahulu, memverifikasi `ensure_tenant_active`, lalu menyetel `app.current_tenant_id` sebelum memuat profil dan permission `users`.
3. **Pemisahan Scope Token (`scope: "tenant"` vs `scope: "platform"`):**
   - Dependency `get_current_user` menolak token dengan `scope != "tenant"`.
   - Dependency `require_platform_admin` hanya menerima token dengan `scope == "platform"` yang diverifikasi terhadap tabel `platform_admins`.
4. **Konvensi Penamaan File Modul Fase 2 (M9):**
   - Mengikuti pola `FOLDER_STRUCTURE.MD`: route ditempatkan di `app/api/routes/tenants.py`, `app/api/routes/platform.py`, dan `app/api/routes/settings.py` (tanpa akhiran `_routes`); service di `app/services/tenant_service.py` dan `app/services/setting_service.py`; repository di `app/repositories/tenant_repo.py` dan `app/repositories/setting_repo.py`.

## 6. Error handling dan observability

Gunakan `DomainError` dan kode katalog yang sudah ada: auth, permission,
warehouse assignment, not found, validation, duplicate, invalid state,
insufficient stock, over-receipt, frozen location, entity in use, dan internal
error. Jangan membocorkan SQL, stack trace, struktur tabel, password, hash,
atau token. Audit mencatat aksi dan nilai bisnis yang aman tanpa secret.

## 7. Integrasi dan operasional

Backend menggunakan PostgreSQL melalui `psycopg` 3/`psycopg_pool` sinkron,
tanpa ORM, migration SQL forward-only, dan role aplikasi `wms_app`. Tidak ada
Redis, queue, worker, atau integrasi eksternal dalam MVP.

## 8. Traceability backend

| Modul / Requirement PRD General | Feature ID | Komponen backend | AC terkait |
| --- | --- | --- | --- |
| `FR-PLT-001..005` | `PLT-F01..F05` | `numbering_service`, `utils/pagination`, `core/exceptions`, `core/middleware`, health route, `db/migrate` | `AC-15` s.d. `AC-18` |
| `FR-IAM-001..009` | `IAM-F01..F09` | `auth_service`, `user_service`, `access_service`, `menu_service`, auth/user/menu routes & dependencies | `AC-05`, `AC-11`, `AC-12`, `AC-14` |
| `FR-AUD-001..002` | `AUD-F01..F02` | `audit_service`, `audit_repo`, audit routes | `AC-05`, `AC-07`, `AC-08`, `AC-16`, `AC-22` |
| `FR-MST-001..010` | `MST-F01..F10` | `master_service`, `master_repo`, item import (termasuk kolom `barcode`) dan supplier import service/repository, category/uom/supplier/item routes (kolom & indeks `uq_items_barcode_lower` pada `012_add_barcode_to_items.sql`) | `AC-16`, `AC-19`, `AC-22`, `AC-30`, `AC-31`, `AC-33`, `AC-34`, `AC-35` |
| `FR-WHS-001..005` | `WHS-F01..F05` (`LOC-F03..F04`) | `warehouse_service`, `warehouse_repo`, warehouse/location routes, perluasan pencarian kode/nama lokasi rak & gudang pada saldo stok (`inventory_repo.list_stock_by_location`) | `AC-12`, `AC-16`, `AC-20`, `AC-22`, `AC-36`, `AC-37` |
| `FR-INV-001..008` | `INV-F01..F08` | `inventory_service` (`apply_movement`), `stock_service`, `inventory_repo`, stock routes, barcode/QR scanner lookup barang & inspeksi multi-SKU posisi rak/gudang | `AC-02`, `AC-03`, `AC-04`, `AC-06`, `AC-08`, `AC-13`, `AC-16`, `AC-33`, `AC-34`, `AC-36`, `AC-37` |
| `FR-PUR-001..004` | `PUR-F01..F04` | `po_service` (`apply_receipt`), `po_repo`, PO routes | `AC-01`, `AC-13`, `AC-15`, `AC-16`, `AC-21`, `AC-22` |
| `FR-RCV-001..005` | `RCV-F01..F05` | `gr_service`, `gr_repo`, GR routes, penyediaan payload cetak GRN lengkap beserta barcode | `AC-01`, `AC-07`, `AC-12`, `AC-13`, `AC-15`, `AC-16`, `AC-21`, `AC-22`, `AC-32`, `AC-35` |
| `FR-TRF-001..006` | `TRF-F01..F06` | `transfer_service` (`in_transit`), `transfer_repo`, transfer routes, penyediaan payload cetak Surat Jalan lengkap beserta barcode | `AC-02`, `AC-03`, `AC-04`, `AC-06`, `AC-09`, `AC-12`, `AC-15`, `AC-16`, `AC-21`, `AC-22`, `AC-32`, `AC-35` |
| `FR-OPN-001..006` | `OPN-F01..F06` | `opname_service` (`is_location_frozen`), `opname_repo`, opname routes | `AC-04`, `AC-10`, `AC-12`, `AC-15`, `AC-16`, `AC-21`, `AC-22` |
| `FR-DSH-001` | `DSH-F01` | `dashboard_service`, `dashboard_repo`, `routes/dashboard.py` (agregasi metrik stok, dokumen tertunda, & aktivitas terkini ter-scope) | `AC-12`, `AC-38` |
| `FR-TNT-001..006` *(Fase 2 — M9)* | `TNT-F01..F06` | `tenant_service` (`ensure_tenant_active`, `check_quota`), `tenant_repo`, `routes/platform.py`, `routes/tenants.py`, context `current_tenant` | `AC-23`, `AC-24`, `AC-25`, `AC-27`, `AC-28`, `AC-29` |
| `FR-CFG-001..004` *(Fase 2 — M9)* | `CFG-F01..F04` | `setting_service` (`get_setting`), `setting_repo`, `routes/settings.py` | `AC-22`, `AC-26` |

## 9. Status implementasi & pengujian backend saat ini

- **Lokasi & repositori:** Backend aktif berada di folder `api_warehouse_app/` berdampingan dengan `warehouse_app/`.
- **Cakupan modul terimplementasi (Fase 1):** Seluruh modul Fase 1 (`PLT`, `IAM`, `AUD`, `MST` termasuk import massal item/supplier & barcode item, `WHS` termasuk pencarian lokasi rak/gudang, `INV`, `PUR`, `RCV`, `TRF`, `OPN`) beserta migrasi `001` s.d. `012` telah diimplementasikan penuh.
- **Verifikasi pengujian (`tests/`):** Seluruh 49 pengujian integrasi `pytest` terhadap PostgreSQL `wms_test` sungguhan lulus 100% (`AC-01` s.d. `AC-22`, `AC-30`, `AC-31`, `AC-32`, `AC-33`, `AC-36`). Detail struktur file dan pola kode terdapat pada [FOLDER_STRUCTURE](FOLDER_STRUCTURE.MD).
