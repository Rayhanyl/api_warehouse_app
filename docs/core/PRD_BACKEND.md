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
- Import item menerima satu workbook `.xlsx` melalui `multipart/form-data`; batas yang
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

## 3. Arsitektur service dan persistence

### 3.1 Layer

| Layer | Tanggung jawab |
| --- | --- |
| Routes/dependencies | Parse request, permission dependency, panggil service |
| Services | Use case, aturan bisnis, transaction boundary, audit |
| Repositories | SQL berparameter, locking, query, dan persistence |
| Schemas | Bentuk request/response dan validasi format |
| Core | Config, pool, security, exception, request ID |

### 3.2 Transaksi dan locking

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

- Access token berlaku 15 menit; refresh token 7 hari.
- Refresh token disimpan sebagai hash, dirotasi, dan reuse token revoked
  mencabut seluruh sesi pengguna.
- Password menggunakan Argon2id.
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
| `FR-MST-001..006` | `MST-F01..F06` | `master_service`, `master_repo`, item import service/repository, category/uom/supplier/item routes | `AC-16`, `AC-19`, `AC-22`, `AC-30` |
| `FR-WHS-001..003` | `WHS-F01..F03` | `warehouse_service`, `warehouse_repo`, warehouse/location routes | `AC-12`, `AC-16`, `AC-20`, `AC-22` |
| `FR-INV-001..006` | `INV-F01..F06` | `inventory_service` (`apply_movement`), `stock_service`, `inventory_repo`, stock routes | `AC-02`, `AC-03`, `AC-04`, `AC-06`, `AC-08`, `AC-13`, `AC-16` |
| `FR-PUR-001..004` | `PUR-F01..F04` | `po_service` (`apply_receipt`), `po_repo`, PO routes | `AC-01`, `AC-13`, `AC-15`, `AC-16`, `AC-21`, `AC-22` |
| `FR-RCV-001..004` | `RCV-F01..F04` | `gr_service`, `gr_repo`, GR routes | `AC-01`, `AC-07`, `AC-12`, `AC-13`, `AC-15`, `AC-16`, `AC-21`, `AC-22` |
| `FR-TRF-001..005` | `TRF-F01..F05` | `transfer_service` (`in_transit`), `transfer_repo`, transfer routes | `AC-02`, `AC-03`, `AC-04`, `AC-06`, `AC-09`, `AC-12`, `AC-15`, `AC-16`, `AC-21`, `AC-22` |
| `FR-OPN-001..006` | `OPN-F01..F06` | `opname_service` (`is_location_frozen`), `opname_repo`, opname routes | `AC-04`, `AC-10`, `AC-12`, `AC-15`, `AC-16`, `AC-21`, `AC-22` |
| `FR-TNT-001..006` *(Fase 2 — M9)* | `TNT-F01..F06` | `tenant_service` (`ensure_tenant_active`, `check_quota`), `tenant_repo`, `routes/platform.py`, `routes/tenants.py`, context `current_tenant` | `AC-23`, `AC-24`, `AC-25`, `AC-27`, `AC-28`, `AC-29` |
| `FR-CFG-001..004` *(Fase 2 — M9)* | `CFG-F01..F04` | `setting_service` (`get_setting`), `setting_repo`, `routes/settings.py` | `AC-22`, `AC-26` |

Detail struktur file dan pola kode tetap berada di [FOLDER_STRUCTURE](FOLDER_STRUCTURE.MD).
