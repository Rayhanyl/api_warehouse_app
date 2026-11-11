# PRD Frontend — Spesifikasi Pengalaman Pengguna

Dokumen ini menerjemahkan [PRD General](PRD_GENERAL.md) ke kebutuhan frontend
dan menggunakan [API Contract](API_CONTRACT.md) serta [API documentation](../API/README.md)
sebagai kontrak integrasi. Frontend dikembangkan pada folder `warehouse_app/`
(React 19 + TypeScript + Vite + Tailwind CSS v4) dan terhubung langsung ke REST API
backend di `api_warehouse_app/`.

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
meminta `sku`, `barcode` (opsional), `name`, `description` (opsional), `category_name`, `uom_name`, dan `is_active`; pilihan dropdown dan daftar aktif
tersedia pada sheet `Referensi` (`category_name`, `uom_name`, `uom_code`).
Frontend tidak perlu mencari atau mengirim ID kategori/UoM. Hasil error dapat
menunjuk field `sku`, `barcode`, `category_name`, atau `uom_name`, termasuk nama yang ambigu.
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

### 3.3 Cetak Dokumen Fisik: Surat Jalan & Bukti Penerimaan Barang (`RCV-F05`, `TRF-F06`, `AC-32`)

Untuk memenuhi kebutuhan legalitas pengiriman jalan raya dan SOP serah terima fisik pada toko cabang dan mitra B2B:
- **Pendekatan Layout Cetak:** Menggunakan template cetak berbasis CSS `@media print` murni. Saat pengguna menekan tombol "Cetak Dokumen" pada modal detail dokumen, aplikasi membuka dialog cetak peramban (`window.print()`). Template dirancang presisi untuk format kertas A4 maupun continuous form / printer thermal, dengan elemen antarmuka web (tombol, modal, sidebar) otomatis disembunyikan saat mencetak.
- **Surat Jalan Transfer (`TRF-F06`):**
  - Kop perusahaan / nama toko cabang pengirim.
  - Metadata: Nomor Transfer (`TR-YYYYMMDD-XXXX`), Tanggal Kirim, Gudang & Lokasi Asal, Gudang & Lokasi Tujuan, dan Catatan Pengiriman.
  - Tabel Rincian: No, SKU, Barcode, Nama Barang, Satuan (UoM), Qty Kirim, Kolom Checklist Fisik Penerimaan Cabang, Catatan Kondisi.
  - 3 Blok Tanda Tangan Fisik:
    1. *Disiapkan Oleh:* Staf Gudang Pengirim.
    2. *Dibawa Oleh:* Sopir / Kurir Ekspedisi (wajib disertai kolom isian No. Polisi Kendaraan & Nama Terang).
    3. *Diterima Oleh:* Staf / Kepala Toko Cabang Penerima.
- **Bukti Penerimaan Barang / GRN (`RCV-F05`):**
  - Kop organisasi, Nomor Dokumen GRN (`GR-YYYYMMDD-XXXX`), Nomor PO Referensi, Nama Pemasok, Gudang Penerima, dan Tanggal Penerimaan.
  - Tabel Barang: No, SKU, Barcode, Nama Barang, Satuan, Lokasi Simpan (*Rak/Bin*), Qty Dipesan, Qty Diterima, Catatan.
  - 3 Blok Tanda Tangan Fisik:
    1. *Diserahkan Oleh:* Pemasok / Pengantar Barang.
    2. *Diperiksa Oleh:* Checker / Staf Penerimaan Gudang.
    3. *Disetujui Oleh:* Warehouse Manager / Supervisor.

### 3.4 Integrasi Barcode & QR Scanner (`MST-F08`, `MST-F09`, `INV-F07`, `INV-F08`, `AC-33`, `AC-34`)

Untuk mendukung kecepatan operasional toko cabang dan kasir retail:
- **Form Master Data Barang & Generator Otomatis (`MST-F08`, `MST-F09`):** Form penambahan/pengubahan barang menyediakan input teks `Barcode` opsional (maks 64 karakter) di samping kode SKU. Tersedia dua pilihan pengisian:
  1. *Barcode Pabrik:* Operator dapat mengetik manual atau menekan tombol **"Pindai"** (kamera/scanner gun) untuk memasukkan barcode fisik bawaan produk dari supplier/pabrikan.
  2. *Auto-Generate Barcode WMS:* Untuk produk non-barcode (barang curah, *repack*, atau *private label*), tersedia tombol **"Generate Barcode"** yang menghasilkan barcode unik standar EAN-13 internal (prefix GS1 `200..299` dengan modulo-10 check digit) atau format Code-128 berbasis penomoran unik WMS.
- **Dukungan Hardware Barcode Gun (USB/Bluetooth):** Menggunakan hook kustom `useBarcodeScanner` yang mendengarkan event keyboard global dengan ambang buffer ketukan sangat cepat (10–50 ms antar karakter) dan mendeteksi terminasi `Enter`. Saat barcode terbaca, hook secara otomatis memicu pencarian barang atau pengisian baris dokumen tanpa mengharuskan kursor berada di input tertentu.
- **Dukungan Kamera Web (Mobile / Tablet Toko Cabang):** Komponen modal pemindai kamera interaktif (memanfaatkan API native `BarcodeDetector` / `getUserMedia`) yang dapat dipicu melalui tombol ikon barcode di form. Kamera membaca kode 1D (EAN-13, UPC, Code 128) maupun 2D (QR Code).
- **Titik Otomasi Pemindaian:**
  1. *Goods Receipt:* Menembak barcode kemasan barang langsung mencocokkan baris PO dan menambahkan kuantitas terima (+1 atau mengalokasikan lokasi aktif).
  2. *Stock Transfer:* Scan barang saat verifikasi packing (gudang asal) dan unboxing serah terima (gudang cabang).
  3. *Stock Opname:* Scan barcode barang untuk mengakumulasi hitungan fisik (+1) pada baris snapshot maupun menambahkannya ke daftar temuan.
  4. *Katalog Stok:* Scan barcode langsung memfilter kartu stok barang terkait.
- **Pindai Cek Barang & Posisi Rak Gudang (`INV-F08`, `AC-34`):** Tombol cepat di Topbar Navigasi / Header dan halaman stok yang membuka `StockLookupModal`. Operator gudang cukup men-scan barcode barang fisik di lantai gudang, dan sistem seketika memuat kartu ringkasan barang (SKU, nama, barcode, kategori, UoM, total stok) dan tabel sebaran posisi fisik rak di seluruh gudang (`warehouse_name`, `location_code`, `location_name`, `qty_on_hand`, `qty_in_transit`).
- **Visualisasi Gambar Barcode SVG & Cetak Label Stiker Fisik (`MST-F10`, `AC-35`):**
  - Komponen `BarcodeVisual` merender kode `barcode` atau `sku` menjadi grafik vektor `<svg>` 1D berstandar **EAN-13** (bila 13 digit valid) atau **Code-128B** (untuk SKU/alfanumerik) secara instan di browser tanpa menyimpan file gambar di database.
  - Pratinjau visual barcode tampil langsung di `StockFormDialog` (saat mengetik/generate barcode) dan `StockDetailDialog`.
  - `StockDetailDialog` menyediakan aksi **"Cetak Label Barcode"** dengan layout stiker thermal standar (`50x30 mm`) yang siap ditempel pada kemasan fisik barang.
  - Dokumen cetak Bukti Penerimaan Barang (`GoodsReceiptPrintSheet`) dan Surat Jalan Transfer (`StockTransferPrintSheet`) turut menampilkan barcode visual dokumen untuk mempercepat proses verifikasi scan.
- **Barcode Lokasi Rak & Gudang serta Inspeksi Isi Rak Multi-Barang (`WHS-F04` / `LOC-F03`, `AC-36`):**
  - Modal detail Lokasi Penyimpanan (`StorageLocationDetailDialog`) dan Gudang (`WarehouseDetailDialog`) menampilkan visualisasi barcode Code-128 untuk `location.code` dan `warehouse.code` beserta tombol **"Cetak Label Rak"** / **"Cetak Label Gudang"**.
  - `StockLookupModal` mendukung deteksi cerdas dua arah (*Dual-Mode Lookup*):
    1. **Mode Barang (Scan SKU / Barcode Produk):** Menampilkan identitas barang dan tabel sebaran di rak mana saja barang tersebut berada.
    2. **Mode Lokasi Rak / Gudang (Scan Barcode Rak `JKT-RAK-A1` atau Gudang `WH-JKT-01`):** Menampilkan Kartu Identitas Rak/Gudang (jumlah macam SKU barang di rak tersebut, total unit fisik, dan stok in-transit) beserta tabel rincian seluruh macam barang yang tersimpan di lokasi tersebut.

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

Pilihan teknologi dan arsitektur state yang diterapkan pada `warehouse_app/`:
- **Framework & Build:** React `19.3.1`, Vite `8`, TypeScript `5.9.3`, Tailwind CSS `4.3.3`, shadcn/ui.
- **Routing:** React Router `7` (`createBrowserRouter`) dengan layout `AppShell`, `Sidebar`, `PageHeader`, dan guard `ProtectedRoute`.
- **Server State & Caching:** TanStack Query `5` (`@tanstack/react-query`) untuk query caching, deduplikasi request, dan mutasi data terkelola.
- **Client Session State:** Zustand `5` (`features/auth/store.ts`) untuk sesi login dan profil pengguna aktif.
- **Form & Validasi:** React Hook Form + Zod (`@hookform/resolvers/zod`).
- **Data Table:** TanStack Table (`@tanstack/react-table`) dengan dukungan pagination, sorting, dan filtering.
- **HTTP Client & Autentikasi:** Axios (`lib/api-client.ts`) dengan `baseURL: /api/v1`, injeksi otomatis header `Authorization: Bearer <access_token>`, dan interceptor response `401` yang memicu pembaruan token via `POST /api/v1/auth/refresh`.
- **Penyimpanan Token:** `localStorage` (`wms.frontend.auth.refresh-token`) dengan sinkronisasi multi-tab melalui `BroadcastChannel` dan event storage.

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
- Komponen sidebar memetakan nilai string `icon` ke komponen icon melalui *allowlist* statis (dengan *fallback icon* bila nilai tidak dikenali). Daftar 23 nama icon canonical yang di-seed pada `db/migrations/009_create_menu_tables.sql` dan didukung frontend adalah:
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
| `FR-MST-008` | `MST-F08` | Field input barcode pada form barang dan pencarian barang via barcode | CRUD item & filter `search`/`barcode` | `AC-33` |
| `FR-MST-009` | `MST-F09` | Tombol auto-generate barcode internal (EAN-13 GS1 `200..299` / Code-128) pada form barang | form dialog item (`StockFormDialog`) | `AC-33` |
| `FR-WHS-001..003` | `WHS-F01..F03` | Layar CRUD warehouse, pengaturan `allow_negative_stock`, lokasi penyimpanan | warehouse dan storage location CRUD/list | `AC-12`, `AC-16`, `AC-20` |
| `FR-INV-001..003` | `INV-F01..F03` | Saldo per lokasi, per gudang, ringkasan, in-transit, dan movement ledger | stock balances, by-warehouse, summary, movements | `AC-03`, `AC-12`, `AC-16` |
| `FR-INV-007` | `INV-F07` | Hook pemindai scanner hardware & modal scanner kamera web pada form operasional | lookup barcode item dan lokasi | `AC-33` |
| `FR-INV-008` | `INV-F08` | Shortcut pemindai Topbar & modal lookup posisi rak & saldo barang (`StockLookupModal`) | `GET /api/v1/stock/by-location?search=` | `AC-34` |
| `FR-PUR-001..003` | `PUR-F01..F03` | Daftar/detail PO, form draft, aksi issue/cancel/close, progres fulfillment | purchase order CRUD, list, dan action endpoints | `AC-01`, `AC-15`, `AC-16`, `AC-21` |
| `FR-RCV-001..004` | `RCV-F01..F04` | Daftar/detail GR, form penerimaan dari PO, aksi post dan cancel draft | goods receipt CRUD, list, dan action endpoints | `AC-01`, `AC-07`, `AC-12`, `AC-13`, `AC-21` |
| `FR-RCV-005` | `RCV-F05` | Tombol dan layout cetak Bukti Penerimaan Barang (GRN) siap cetak/PDF | detail GR (`GET /api/v1/goods-receipts/{id}`) | `AC-32` |
| `FR-TRF-001..005` | `TRF-F01..F05` | Daftar/detail transfer, form draft, approve, ship, receive (beserta alasan selisih), cancel | stock transfer CRUD, list, dan action endpoints | `AC-02`, `AC-03`, `AC-06`, `AC-09`, `AC-12`, `AC-21` |
| `FR-TRF-006` | `TRF-F06` | Tombol dan layout cetak Surat Jalan Transfer (Delivery Note) siap cetak/PDF | detail transfer (`GET /api/v1/stock-transfers/{id}`) | `AC-32` |
| `FR-OPN-001..006` | `OPN-F01..F06` | Sesi opname, indikator lokasi beku, input count fisik, submit, approve/reject | stock opname CRUD, list, count lines, dan action endpoints | `AC-04`, `AC-10`, `AC-12`, `AC-21` |
| `FR-TNT-001..006` *(Fase 2 — M9)* | `TNT-F01..F06` | Input `tenant_slug` pada login tenant, panel `Platform Admin` (daftar/provisioning/status/kuota tenant), serta layar profil & penggunaan kuota bagi `Super Admin` tenant | `/api/v1/auth/login` (`tenant_slug`), `/api/v1/platform/*`, `/api/v1/tenant/profile` | `AC-23`, `AC-24`, `AC-25`, `AC-27`, `AC-28`, `AC-29` |
| `FR-CFG-001..004` *(Fase 2 — M9)* | `CFG-F01..F04` | Layar pengaturan tenant dan override pengaturan per gudang beserta indikator sumber pewarisan nilai | `/api/v1/settings`, `/api/v1/warehouses/{id}/settings` | `AC-26` |

## 7. Status implementasi & batasan saat ini

- **Lokasi & repositori:** Frontend aktif dikembangkan di folder `warehouse_app/` (berdampingan dengan `api_warehouse_app/` dalam satu workspace monorepo).
- **Fondasi teknologi yang telah diputuskan:** React 19, TypeScript, Vite, Tailwind CSS v4, shadcn/ui, TanStack Query v5, Zustand v5, Axios dengan interceptor auto-refresh token JWT, dan penyimpanan refresh token di `localStorage` dengan sinkronisasi multi-tab.
- **Bahasa & tanggal:** Antarmuka utama berbahasa Indonesia, format tanggal menggunakan standar lokal `Intl.DateTimeFormat("id-ID")` dan pustaka `date-fns`.
- **Halaman & alur yang telah tersedia:** Landing page publik (`/`), Login (`/login`), Dashboard (`/dashboard`), Profil & ganti password (`/profile`), Administrasi Pengguna/Role/Menu (`/admin/*`), Master Data Kategori/UoM/Pemasok/Barang/Gudang/Lokasi (`/master/*`), Saldo Stok & Ledger (`/stock/*`), Purchase Order (`/purchase-orders/*`), Goods Receipt (`/goods-receipts/*`), Stock Transfer (`/stock-transfers/*`), Stock Opname (`/stock-opnames/*`), dan Audit Log (`/audit-logs`).
- **Import massal di frontend:** Import massal item (`MST-F06`) telah diintegrasikan (`StockImportDialog.tsx`), sedangkan import massal supplier (`MST-F07`) menggunakan kontrak backend yang sama dan siap dipasang pada dialog pemasok.
- **Fitur Retail & Toko Cabang (Fase 1):** Fitur cetak fisik Surat Jalan (`TRF-F06`), Bukti Penerimaan Barang GRN (`RCV-F05`), serta pemindaian Barcode/QR (`MST-F08`, `INV-F07`) disetujui masuk ke dalam rilis Fase 1 sebelum transisi multi-tenant.
- **Batasan di luar MVP (Fase 2 & Fase 3):**
  - Modul Multi-Tenant SaaS (UI pemilihan tenant/slug login tenant dan panel Platform Admin) akan dikembangkan pada Fase 2 (M9).
  - Modul Goods Issue (`ISS`) dan Pelaporan Analitik Lengkap (`RPT`) direncanakan pada Fase 3 (M10).
  - Dukungan Progressive Web App (PWA) / mode offline sepenuhnya belum masuk dalam cakupan baseline Fase 1.
