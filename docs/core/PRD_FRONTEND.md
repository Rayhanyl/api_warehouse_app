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
| Master | Categories, UoM, items, suppliers |
| Warehouse | Warehouses, storage locations |
| Inventory | Stock by location/warehouse, in-transit, movement ledger |
| Purchasing | PO list/detail/create/edit/issue/cancel/close |
| Receiving | GR list/detail/create/edit/post/cancel |
| Transfer | Transfer list/detail/create/approve/ship/receive/cancel |
| Opname | Session, snapshot, count input, approve/reject, adjustment |
| Audit | Audit log list/detail/filter |

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

## 6. Pemetaan fitur dan data

| Fitur General | UI utama | Data/API yang dikonsumsi |
| --- | --- | --- |
| FR-01 | Auth/session | auth dan user |
| FR-02 | Master/warehouse | master dan warehouse |
| FR-03/08 | Inventory/ledger | stock dan movement |
| FR-04/05 | PO/GR | purchasing dan receiving |
| FR-06 | Transfer | transfer |
| FR-07 | Opname | opname |
| FR-09/10/11 | Audit, document number, list controls | audit, resource list, pagination |

## 7. Belum terdefinisi / perlu konfirmasi

- framework frontend, browser support, responsive/accessibility target;
- desain visual, bahasa UI final, timezone display, dan format tanggal;
- apakah frontend berada di repository terpisah;
- detail dashboard/reporting, karena reporting berada di luar MVP;
- strategi offline, optimistic update, dan caching.
