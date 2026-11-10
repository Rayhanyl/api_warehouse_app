# PRD Frontend — Spesifikasi Pengalaman Pengguna

Dokumen ini menerjemahkan [PRD General](PRD_GENERAL.md) ke kebutuhan frontend
dan menggunakan [API Contract](API_CONTRACT.md) serta [API documentation](../API/README.md)
sebagai kontrak integrasi. Frontend belum termasuk implementasi MVP pada
repository ini; seluruh status implementasi di bawah harus dibaca sebagai
spesifikasi target dan kebutuhan konfirmasi.

## 1. Tanggung jawab dan batas

Frontend bertanggung jawab atas navigasi, tampilan data, input pengguna,
permission-based UI, state request, dan feedback visual. Frontend tidak boleh
menanamkan aturan bisnis yang hanya boleh diputuskan backend, mengubah saldo
secara lokal sebagai sumber kebenaran, atau menampilkan fitur di luar scope.

## 2. Struktur informasi dan halaman

| Area | Halaman/fitur minimum |
| --- | --- |
| Authentication | Login, session refresh, logout, change password, profile |
| Administration | Users, roles/permissions, warehouse assignment, menu |
| Master | Categories, UoM, items (CRUD dan import massal), suppliers |
| Warehouse | Warehouses, storage locations |
| Inventory | Stock by location/warehouse, in-transit, movement ledger |
| Purchasing | PO list/detail/create/edit/issue/cancel/close |
| Receiving | GR list/detail/create/edit/post/cancel |
| Transfer | Transfer list/detail/create/approve/ship/receive/cancel |
| Opname | Session, snapshot, count input, approve/reject, adjustment |
| Audit | Audit log list dan filter |

Rute, label, dan navigasi final perlu konfirmasi produk/frontend; tabel di atas
adalah pemetaan langsung dari FR, bukan daftar endpoint baru.

## 3. UI/UX requirements

- Tampilkan status dokumen dan hanya aksi yang sah untuk status tersebut.
- Sembunyikan atau disable aksi berdasarkan permission dan warehouse assignment,
  tetapi tetap perlakukan backend sebagai enforcement utama.
- Form menampilkan field wajib, format kuantitas desimal, validasi referensi,
  dan konfirmasi untuk aksi yang mengubah status atau stok.
- Tabel mendukung pagination, filtering, sorting yang tersedia dari API.
- Setiap request memiliki loading state; hasil kosong memiliki empty state;
  error menampilkan pesan aman, kode error bila berguna, dan opsi retry.
- Perubahan stok dan status harus memberi feedback sukses/gagal yang jelas.
- Hindari menampilkan token, password, hash, SQL, atau stack trace.

### 3.1 Import massal item (`MST-F06`)

Pada halaman Master Data Barang, pengguna dengan `master:manage` dapat
mengunduh template Excel dan memilih satu workbook untuk diimpor. Unggahan
mengirim file ke backend; frontend tidak mengubah data item lokal sebagai
pengganti hasil server. Pengguna tanpa permission tidak melihat aksi impor.

Saat request berjalan, tampilkan loading state dan cegah submit berulang untuk
file yang sama. Setelah respons diterima, tampilkan `total_rows`, jumlah sukses
dan gagal, serta daftar error dengan nomor baris Excel, field, dan alasan.
Baris valid tetap ditampilkan sebagai berhasil meskipun ada baris gagal.
Workbook kosong menampilkan empty state; tipe/struktur/ukuran file yang ditolak
dan kegagalan server menampilkan error state yang aman.

Frontend menggunakan template dari endpoint backend apa adanya. Sheet `Items`
meminta `category_name` dan `uom_name`; pilihan dropdown dan daftar aktif
tersedia pada sheet `Referensi` (`category_name`, `uom_name`, `uom_code`).
Frontend tidak perlu mencari atau mengirim ID kategori/UoM. Hasil error dapat
menunjuk field `category_name` atau `uom_name`, termasuk nama yang ambigu.
Kolom `is_active` menerima `active`/`inactive` atau boolean Excel; kosong berarti
aktif.

### 3.2 Import massal supplier (`MST-F07`)

Pada halaman Master Data Supplier, pengguna dengan `master:manage` dapat
mengunduh template dari backend dan mengunggah workbook melalui endpoint import.
Template memiliki sheet `Suppliers`; frontend mengirim file apa adanya pada
field `file` dalam `multipart/form-data`. Setelah respons diterima, tampilkan
ringkasan total/sukses/gagal dan rincian error per baris. Kode duplikat dan
validasi field ditampilkan bersama nomor baris serta nama field. Nilai status
`active`/`inactive` dan boolean Excel didukung; field opsional kosong diterima.

## 4. Komponen dan state

Komponen bersama minimum: authenticated shell, navigation/menu tree, data table,
pagination controls, form fields untuk Decimal/date/reference, status badge,
confirmation dialog, error panel, loading indicator, dan empty state.

State minimum:

- session/access token dan user profile;
- permission serta menu hasil endpoint `my-menu`;
- resource list/detail dan pagination state;
- form draft, validation errors, submitting state;
- server error dan retry state.

Pilihan framework, library state management, dan strategi caching belum
ditentukan dan harus dicatat sebagai keputusan terpisah sebelum implementasi.

## 5. Integrasi API

Client harus mengikuti base path, header `Authorization`, `X-Request-ID`,
format Decimal string, pagination, status code, dan error envelope pada
[API Contract](API_CONTRACT.md). Endpoint aktual tidak boleh ditebak dari
desain UI; gunakan [API index](../API/README.md).

Alur request umum:

1. login memperoleh session;
2. client memuat profile dan menu terfilter;
3. client memanggil resource sesuai permission;
4. `401` memicu refresh sekali lalu retry request;
5. refresh gagal mengakhiri session;
6. `403`, `409`, dan `422` ditampilkan sebagai feedback domain/validasi;
7. `5xx` ditampilkan sebagai error umum tanpa detail internal.

### 5.1 Kontrak pohon menu navigasi dan allowlist icon (`IAM-F08`)

- Endpoint `GET /api/v1/menus/my-menu` mengembalikan struktur pohon (`MenuTreeOut`) dengan atribut: `id`, `code`, `name`, `path`, `icon`, `parent_id`, `sort_order`, `permission_code`, `is_active`, dan `children` (tanpa properti `short_name`).
- Komponen sidebar memetakan nilai string `icon` ke komponen icon melalui *allowlist* statis (dengan *fallback icon* bila nilai tidak dikenali). Daftar 19 nama icon canonical yang di-seed pada `db/migrations/009_create_menu_tables.sql` adalah:
  `layout-dashboard`, `database`, `warehouse`, `boxes`, `shopping-cart`, `arrow-left-right`, `clipboard-check`, `shield`, `folder-tree`, `scale`, `truck`, `package`, `building-2`, `map-pin`, `layers`, `bar-chart-3`, `book-open`, `file-text`, `package-check`, `users`, `key-round`, `menu`, `scroll-text`.

## 6. Pemetaan fitur dan data

| Modul / Requirement PRD General | Feature ID | UI utama | Data/API yang dikonsumsi | AC terkait |
| --- | --- | --- | --- | --- |
| `FR-PLT-001..004` | `PLT-F01..F04` | Nomor dokumen read-only, kontrol list/pagination/filter/sort, error state | query params list, error envelope, `X-Request-ID`, health | `AC-15`, `AC-16`, `AC-17` |
| `FR-IAM-001..009` | `IAM-F01..F09` | Login, session refresh, profil, ganti password, manajemen user/role/assignment, sidebar menu dinamis | auth, user, role/permission, warehouse assignment, `my-menu` | `AC-05`, `AC-11`, `AC-12`, `AC-14` |
| `FR-AUD-002` | `AUD-F02` | Penelusuran dan filter daftar audit log (`old_values`/`new_values`) | audit log list (`GET /api/v1/audit-logs`) | `AC-16`, `AC-22` |
| `FR-MST-001..005` | `MST-F01..F05` | Layar CRUD dan aktivasi/deaktivasi kategori, UoM, item, supplier | master data CRUD dan list | `AC-16`, `AC-19` |
| `FR-MST-006` | `MST-F06` | Aksi unduh template, unggah workbook, ringkasan hasil dan tabel error per baris | `GET /api/v1/items/import-template`, `POST /api/v1/items/import` | `AC-30` |
| `FR-MST-007` | `MST-F07` | Aksi unduh template supplier, unggah workbook, ringkasan hasil dan tabel error per baris | `GET /api/v1/suppliers/import-template`, `POST /api/v1/suppliers/import` | `AC-31` |
| `FR-WHS-001..003` | `WHS-F01..F03` | Layar CRUD warehouse, pengaturan `allow_negative_stock`, lokasi penyimpanan | warehouse dan storage location CRUD/list | `AC-12`, `AC-16`, `AC-20` |
| `FR-INV-001..003` | `INV-F01..F03` | Saldo per lokasi, per gudang, ringkasan, in-transit, dan movement ledger | stock balances, by-warehouse, summary, movements | `AC-03`, `AC-12`, `AC-16` |
| `FR-PUR-001..003` | `PUR-F01..F03` | Daftar/detail PO, form draft, aksi issue/cancel/close, progres fulfillment | purchase order CRUD, list, dan action endpoints | `AC-01`, `AC-15`, `AC-16`, `AC-21` |
| `FR-RCV-001..004` | `RCV-F01..F04` | Daftar/detail GR, form penerimaan dari PO, aksi post dan cancel draft | goods receipt CRUD, list, dan action endpoints | `AC-01`, `AC-07`, `AC-12`, `AC-13`, `AC-21` |
| `FR-TRF-001..005` | `TRF-F01..F05` | Daftar/detail transfer, form draft, approve, ship, receive (beserta alasan selisih), cancel | stock transfer CRUD, list, dan action endpoints | `AC-02`, `AC-03`, `AC-06`, `AC-09`, `AC-12`, `AC-21` |
| `FR-OPN-001..006` | `OPN-F01..F06` | Sesi opname, indikator lokasi beku, input count fisik, submit, approve/reject | stock opname CRUD, list, count lines, dan action endpoints | `AC-04`, `AC-10`, `AC-12`, `AC-21` |
| `FR-TNT-001..006` *(Fase 2 — M9)* | `TNT-F01..F06` | Input `tenant_slug` pada login tenant, panel `Platform Admin` (daftar/provisioning/status/kuota tenant), serta layar profil & penggunaan kuota bagi `Super Admin` tenant | `/api/v1/auth/login` (`tenant_slug`), `/api/v1/platform/*`, `/api/v1/tenant/profile` | `AC-23`, `AC-24`, `AC-25`, `AC-27`, `AC-28`, `AC-29` |
| `FR-CFG-001..004` *(Fase 2 — M9)* | `CFG-F01..F04` | Layar pengaturan tenant dan override pengaturan per gudang beserta indikator sumber pewarisan nilai | `/api/v1/settings`, `/api/v1/warehouses/{id}/settings` | `AC-26` |

## 7. Belum terdefinisi / perlu konfirmasi

- framework frontend, browser support, responsive/accessibility target;
- desain visual, bahasa UI final, timezone display, dan format tanggal;
- apakah frontend berada di repository terpisah;
- detail dashboard/reporting, karena reporting berada di luar MVP;
- strategi offline, optimistic update, dan caching.
