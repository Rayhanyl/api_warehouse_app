# Product Requirements Document (PRD) Frontend WMS

| Atribut | Nilai |
|---|---|
| Produk | Warehouse Management System (WMS) Frontend |
| Versi dokumen | 1.1 |
| Status | Draft acuan frontend — telah direview terhadap implementasi backend |
| Platform | React SPA untuk browser desktop dan mobile |
| Backend | FastAPI REST API, PostgreSQL, JWT |
| Baseline stack | React 19.3.1, Vite 8, TypeScript 5 |

Dokumen ini menerjemahkan kebutuhan bisnis dan kontrak API WMS menjadi
kebutuhan implementasi frontend. Dokumen ini tidak mengubah aturan backend dan
tidak memperkenalkan endpoint baru.

---

## 1. Status informasi dan sumber acuan

### 1.1 Terkonfirmasi

Hal berikut dikonfirmasi oleh PRD backend dan dokumentasi API:

- WMS mengelola master data, stok multi-gudang, PO, GR, transfer, opname,
  stock ledger, audit log, auth, RBAC, warehouse scoping, dan menu dinamis.
- Backend memiliki lima role bawaan: `Super Admin`, `Warehouse Manager`,
  `Purchasing Staff`, `Warehouse Staff`, dan `Auditor`.
- Access token berumur pendek digunakan pada header `Authorization`; refresh token
  dirotasi melalui body request.
- Daftar permission dan menu dikirim oleh backend; frontend tidak boleh
  menganggap menu tersembunyi sebagai pengganti otorisasi server.
- Endpoint daftar yang memang paginated memakai response
  `{items, total, limit, offset}` dengan `limit` 1–200 (default 50).
  Pengecualian yang dikembalikan sebagai array langsung adalah
  `/auth/me`, `/menus/my-menu`, `/users/roles`, `/users/permissions`, dan
  endpoint assignment warehouse.
- Kuantitas memakai presisi maksimal empat angka desimal dan aturan
  `allow_decimal` pada UoM.
- Tidak ada lot/batch, serial number, inventory costing, stock reservation,
  goods issue, retur, reversal GR, konversi UoM, atau penerimaan transfer
  bertahap pada MVP.

### 1.2 Asumsi implementasi frontend

Asumsi berikut diperlukan untuk membangun UI, tetapi bukan aturan bisnis baru:

- `/api/v1` menjadi prefix API dan base URL berasal dari `VITE_API_BASE_URL`.
- Frontend menggunakan TanStack Query untuk request, cache, invalidasi, dan
  mutation state.
- Filter/pagination disimpan pada URL search params agar dapat di-refresh dan
  dibagikan.
- Komponen UI mengikuti [DESIGN.MD](./DESIGN.MD), termasuk konsep
  “Warehouse Control Tower”.
- Ikon menu dari API dipetakan ke allowlist ikon Lucide; nama ikon yang tidak
  dikenal memakai fallback yang aman.

### 1.3 Klarifikasi yang masih diperlukan

Hal berikut harus dikonfirmasi sebelum implementasi final:

1. Apakah ada SLA frontend, target browser minimum, dan target ukuran bundle
   yang lebih ketat dari PRD backend?
**Fakta yang tidak lagi menjadi klarifikasi:** backend menyediakan `GET /health`
dan `/api/v1/health`; role resmi pada seed/backend adalah `Auditor`. Kontrak
refresh saat ini hanya menerima `refresh_token` di JSON body, sehingga
HttpOnly-cookie tidak dapat digunakan tanpa perubahan backend. Landing page
menggunakan content JSON statis. Dashboard operasional ditunda; MVP memakai
dashboard informatif berbasis teks. Untuk MVP, access token disimpan di memory
melalui Zustand dan refresh token disimpan melalui `LocalStorageRepository`.

---

## 2. Product Overview

### 2.1 Tujuan

Frontend harus memberikan satu workspace yang memungkinkan pengguna:

1. melihat posisi stok per item, gudang, lokasi, dan in-transit;
2. menjalankan transaksi PO, GR, transfer, dan opname sesuai state machine;
3. memahami tindakan yang tersedia berdasarkan permission dan gudang yang
   ditugaskan;
4. menemukan kegagalan validasi secara jelas tanpa kehilangan input;
5. menelusuri perubahan melalui stock ledger dan audit log.

Landing page, bila diaktifkan, menjelaskan manfaat WMS dan mengarahkan pengguna
ke login atau CTA bisnis. Landing page tidak boleh menampilkan data operasional
terproteksi.

### 2.2 Target pengguna

| Pengguna | Kebutuhan frontend utama |
|---|---|
| Super Admin | Pengguna, role/permission, assignment, menu, seluruh data |
| Warehouse Manager | Lokasi, approval transfer/opname, PO close, monitoring |
| Purchasing Staff | Master data pembelian, pembuatan dan lifecycle PO |
| Warehouse Staff | GR, transfer fisik, penghitungan opname pada gudang yang ditugaskan |
| Auditor | Read-only master, dokumen, stok, ledger, dan audit log |

### 2.3 Ruang lingkup frontend

**In scope:**

- public landing page statis berbasis JSON;
- login, refresh, logout, profil, ganti password;
- route protection, permission-aware action, dan warehouse context;
- dynamic menu dari `GET /api/v1/menus/my-menu`;
- dashboard informatif berbasis teks dan navigasi ke pekerjaan operasional;
- CRUD/update sesuai endpoint master data;
- lifecycle PO, GR, transfer, dan opname;
- tampilan stok, in-transit, ledger, dan audit log;
- loading, error, empty, pagination, filter, form validation, toast;
- testing, accessibility, dan development setup; Docker frontend hanya bila
  service frontend disepakati.

**Out of scope:**

- implementasi atau perubahan backend;
- barcode scanner dan integrasi ERP;
- notifikasi email/WhatsApp;
- costing, lot/batch, serial, reservation, goods issue, retur, reversal GR;
- approval PO multi-level;
- offline transaction dan conflict resolution offline.

---

## 3. Feature Requirements

Prioritas: **P0** wajib untuk MVP, **P1** penting setelah alur inti stabil,
**P2** enhancement yang tidak boleh memblokir transaksi utama.

### FR-01 — Authentication dan session (P0)

Pengguna dapat login, mempertahankan session melalui refresh token, logout,
melihat profil, dan mengganti password sendiri.

**Endpoint terkonfirmasi:**

- `POST /api/v1/auth/login`
- `POST /api/v1/auth/refresh`
- `POST /api/v1/auth/logout`
- `GET /api/v1/auth/me`
- `POST /api/v1/auth/change-password`

**Acceptance criteria:**

- form login memvalidasi username 1–64 karakter dan password 1–255 karakter;
- login sukses menyimpan access token di memory dan refresh token melalui
  `LocalStorageRepository`, lalu mengambil profil/permission/gudang;
- access token dikirim sebagai `Bearer` pada request terproteksi;
- refresh memakai refresh token pada JSON body dan mengganti token lama secara
  atomik setelah response berhasil;
- `AUTH_INVALID_CREDENTIALS`, `AUTH_TOO_MANY_ATTEMPTS`, dan `401` ditampilkan
  dengan pesan yang dapat dipahami tanpa membocorkan detail sensitif;
- logout mengirim refresh token ke backend bila tersedia, lalu selalu
  membersihkan cache sensitif, session memory, dan storage token;
- expired/invalid session tidak meninggalkan layar yang membutuhkan auth.

### FR-02 — Dynamic navigation dan authorization UI (P0)

Frontend merender pohon menu dari backend dan menggunakan permission sebagai
petunjuk visibilitas UI.

**Endpoint terkonfirmasi:**

- `GET /api/v1/menus/my-menu`
- endpoint administrasi menu hanya untuk `user:manage`.

**Acceptance criteria:**

- hanya menu aktif dan menu yang terlihat untuk permission user yang dirender;
- parent tanpa child yang terlihat tidak dirender;
- `sort_order` lalu `id` dihormati;
- `path` menu dipetakan ke route yang terdaftar;
- ikon tidak dikenal memakai fallback dan tidak membuat navigasi gagal;
- direct URL tetap divalidasi oleh route guard dan server, bukan hanya menu.

### FR-03 — Informational Dashboard MVP (P0)

Dashboard MVP hanya berisi teks informatif statis untuk membantu orientasi
pengguna. Dashboard tidak mengambil data dari API dan tidak menampilkan KPI,
chart, alert count, work queue, atau recent activity.

**Acceptance criteria:**

- route `/dashboard` dapat dibuka oleh pengguna terautentikasi;
- halaman memiliki judul, deskripsi singkat, dan teks pengantar penggunaan WMS;
- seluruh teks dashboard tidak mengklaim angka, status operasional, atau data
  yang berasal dari backend;
- halaman tidak membuat request dashboard atau agregasi bisnis;
- halaman memiliki state loading/error hanya bila diperlukan oleh mekanisme
  route/content loading, bukan karena request data operasional;
- implementasi dashboard dapat dikembangkan menjadi dashboard operasional pada
  fase berikutnya tanpa mengubah alur landing page.

### FR-04 — Master data (P0)

Frontend mengelola kategori, UoM, supplier, item, warehouse, dan storage
location sesuai endpoint backend.

**Endpoint terkonfirmasi:**

- `/api/v1/categories`
- `/api/v1/uoms`
- `/api/v1/suppliers`
- `/api/v1/items`
- `GET/POST /api/v1/warehouses`
- `GET/PATCH /api/v1/warehouses/{warehouse_id}`
- `/api/v1/warehouses/{warehouse_id}/locations`
- `/api/v1/locations`

**Acceptance criteria:**

- daftar mendukung pagination, search, filter `is_active`, dan sorting sesuai
  whitelist backend;
- create/update memakai schema yang sama dengan kontrak backend;
- tidak ada tombol hard delete;
- penonaktifan memakai `PATCH` dan menjelaskan dampaknya;an dampaknya;
- `DUPLICATE`, `ENTITY_IN_USE`, `INACTIVE_REFERENCE`, `NOT_FOUND`, dan
  `WAREHOUSE_NOT_ASSIGNED` ditampilkan sebagai feedback kontekstual;
- item menghormati category/UoM aktif dan aturan `allow_decimal`;
- pengelolaan location memeriksa warehouse scope.

### FR-05 — Stock balance dan stock ledger (P0)

Pengguna berhak dapat membaca saldo, in-transit, agregasi gudang, ringkasan item,
dan riwayat movement.

**Endpoint terkonfirmasi:**

- `GET /api/v1/stock/balances`
- `GET /api/v1/stock/by-location`
- `GET /api/v1/stock/by-warehouse`
- `GET /api/v1/stock/summary`
- `GET /api/v1/stock/movements`
- `GET /api/v1/stock/ledger`

**Acceptance criteria:**

- qty on hand dan in-transit memakai format presisi dan UoM yang sesuai;
- pengguna dapat memfilter warehouse, location, item, category, dan search
  sesuai endpoint;
- movement menampilkan type, qty before/change/after, reference, waktu, dan
  konteks lokasi jika tersedia dalam response;
- angka tidak dihitung dengan floating-point JavaScript;
- pagination dan sorting mengikuti whitelist API;
- ledger ditampilkan read-only dan tidak menyediakan edit/delete.

### FR-06 — Purchase Order (P0)

Pengguna berwenang dapat membuat dan menjalankan lifecycle PO:
`DRAFT → ISSUED → PARTIALLY_RECEIVED/RECEIVED → CLOSED`, atau `CANCELLED`
sesuai state machine backend.

**Endpoint terkonfirmasi:**

- `GET/POST /api/v1/purchase-orders`
- `GET/PATCH /api/v1/purchase-orders/{po_id}`
- `POST /{po_id}/issue`
- `POST /{po_id}/cancel`
- `POST /{po_id}/close`

**Acceptance criteria:**

- form line mencegah item duplikat dalam satu PO;
- qty `> 0`, maksimal 4 desimal, dan mengikuti `allow_decimal`;
- PO baru menampilkan nomor dari response, bukan membuat nomor di frontend;
- aksi hanya tersedia jika status dan permission cocok;
- issue memperingatkan bila line kosong atau referensi tidak aktif;
- close mewajibkan `closed_reason`;
- status akibat GR ditampilkan sebagai server result;
- `INVALID_STATE_TRANSITION` dan validation error
  tidak menghapus draft pengguna.

### FR-07 — Goods Receipt (P0)

Warehouse Staff membuat, mengubah, mem-post, atau membatalkan GR berdasarkan PO
`ISSUED`/`PARTIALLY_RECEIVED`.

**Endpoint terkonfirmasi:**

- `GET/POST /api/v1/goods-receipts`
- `GET/PATCH /api/v1/goods-receipts/{gr_id}`
- `POST /{gr_id}/post`
- `POST /{gr_id}/cancel`

**Acceptance criteria:**

- hanya PO yang dapat diterima menurut response backend yang dapat dipilih;
- setiap line memilih lokasi aktif yang tidak dibekukan;
- posting menampilkan konfirmasi bahwa stok dan PO akan berubah;
- `OVER_RECEIPT`, `LOCATION_FROZEN`, dan `INVALID_STATE_TRANSITION` dijelaskan
  tanpa mengklaim transaksi berhasil;
- tombol post disabled selama request dan dapat dicoba ulang setelah error;
- setelah post sukses, invalidate GR, PO, stock, dan ledger yang terkait;
- frontend tidak menyediakan reversal untuk GR `POSTED`.

### FR-08 — Stock Transfer (P0)

Frontend mendukung dua tahap fisik:
`DRAFT → APPROVED → SHIPPED → RECEIVED`, dengan pembatalan sesuai status.

**Endpoint terkonfirmasi:**

- `GET/POST /api/v1/stock-transfers`
- `GET/PATCH /api/v1/stock-transfers/{transfer_id}`
- `POST /{transfer_id}/approve`
- `POST /{transfer_id}/ship`
- `POST /{transfer_id}/receive`
- `POST /{transfer_id}/cancel`

**Acceptance criteria:**

- source dan destination location tidak boleh sama;
- qty line positif dan mengikuti presisi UoM;
- approve hanya tersedia bagi permission/warehouse asal yang sesuai;
- ship menampilkan risiko `INSUFFICIENT_STOCK` dan tidak menjanjikan stok
  berkurang sebelum response sukses;
- receive adalah aksi final satu kali;
- `qty_received <= qty`; jika lebih kecil termasuk nol, `variance_reason` wajib;
- selisih ditampilkan jelas dan tidak dijelaskan sebagai pengembalian otomatis;
- invalidate stock, ledger, dan transfer query setelah setiap mutasi sukses.

### FR-09 — Stock Opname (P0)

Frontend mendukung sesi opname per lokasi atau seluruh lokasi aktif dalam gudang:
`DRAFT → IN_PROGRESS → WAITING_APPROVAL → COMPLETED`, dengan reject kembali ke
`IN_PROGRESS` dan cancel sesuai state.

**Endpoint terkonfirmasi:**

- `GET/POST /api/v1/stock-opnames`
- `GET/PATCH /api/v1/stock-opnames/{opname_id}`
- `POST /{opname_id}/start`
- `POST /{opname_id}/count`
- `POST /{opname_id}/lines`
- `PUT /{opname_id}/lines`
- `POST /{opname_id}/submit`
- `POST /{opname_id}/approve`
- `POST /{opname_id}/reject`
- `POST /{opname_id}/cancel`

**Acceptance criteria:**

- start menjelaskan bahwa lokasi akan dibekukan;
- snapshot `qty_system` ditampilkan sebagai nilai server dan tidak diedit;
- setiap line memerlukan `qty_physical >= 0`;
- item fisik baru dapat dicatat dengan qty system nol jika diizinkan schema;
- submit hanya tersedia setelah semua line memiliki count;
- approval menampilkan ringkasan variance plus/minus;
- reject mengirim `rejection_reason` dan mengembalikan sesi ke counting;
- selama freeze, UI menjelaskan bahwa GR/ship/receive terkait dapat ditolak;
- saldo awal hanya menggunakan mekanisme opname yang didukung backend.

### FR-10 — User, RBAC, dan assignment (P1)

Pengguna dengan `user:manage` (umumnya Super Admin) mengelola user,
role/permission, menu administrasi, dan warehouse assignment. Role resmi
backend adalah `Auditor`, bukan “Auditor/Viewer”.

**Endpoint terkonfirmasi:**

- `GET/POST /api/v1/users`
- `GET/PATCH /api/v1/users/{user_id}`
- `GET/PUT /api/v1/users/{user_id}/warehouses`
- `GET /api/v1/users/roles`
- `GET /api/v1/users/permissions`
- `PUT /api/v1/users/roles/{role_id}/permissions`

**Acceptance criteria:**

- hanya `user:manage` dapat mengakses route;
- password tidak pernah ditampilkan atau dipersist di state UI;
- role dan assignment hanya memilih warehouse aktif;
- perubahan role/status/password menjelaskan bahwa session/token dapat berubah;
- deactivation adalah soft deactivate, bukan hard delete;
- list mendukung filter `role_id`, `is_active`, `search`, dan sorting sesuai API;
- password hanya berada di form sementara, tidak disimpan dalam cache atau
  response UI.

### FR-11 — Audit log (P1)

Auditor dan Super Admin dapat membaca audit log append-only.

**Endpoint terkonfirmasi:** `GET /api/v1/audit-logs`.

**Acceptance criteria:**

- hanya permission `audit:read`;
- filter `user_id`, `action`, `entity_type`, `entity_id`, `date_from`,
  `date_to`, pagination, dan sorting mengikuti API; tidak ada filter `search`
  generik pada endpoint ini;
- actor, action, entity, timestamp, old/new values ditampilkan dengan aman;
- token/password/sensitive values tidak dirender;
- tidak ada create/update/delete control;
- detail JSON dapat dibaca pada dialog/drawer tanpa merusak tabel.

### FR-12 — Landing page statis (P0)

Landing page publik adalah fokus utama MVP frontend. Seluruh konten landing page
bersifat statis dan dibaca dari kumpulan file JSON terpusat; komponen UI tidak
boleh menyimpan copy, daftar fitur, proof point, atau konfigurasi section secara
hard-coded.

**Acceptance criteria:**

- dapat dibuka tanpa token;
- CTA login mengarah ke route login;
- tidak memuat data gudang atau data user;
- responsive, accessible, dan konsisten dengan [DESIGN.MD](./DESIGN.MD);
- klaim hanya berasal dari kemampuan backend yang terkonfirmasi.
- seluruh data yang dirender dapat ditelusuri ke file JSON pada
  `src/content/landing/`;
- perubahan copy atau urutan section dapat dilakukan dengan mengubah JSON,
  tanpa mengubah komponen presentasi;
- schema TypeScript/Zod memvalidasi bentuk data JSON saat development dan test;
- jika data JSON invalid, build/test gagal secara eksplisit, bukan menampilkan
  konten fallback yang menyesatkan.

---

## 4. User Flow

### 4.1 Flow landing page dan login

```text
Landing (baca JSON statis)
  → CTA login
  → login
  → token response
  → /auth/me
  → /menus/my-menu
  → halaman pertama yang tersedia dari menu
  → detail/form
  → mutation
  → toast + query invalidation
  → detail/list terbaru
```

Setelah autentikasi, pengguna diarahkan ke `/dashboard` yang berisi teks
informatif statis. Dari sana pengguna dapat menuju route operasional pertama
yang tersedia dan diizinkan berdasarkan menu/permission backend.

### 4.2 PO sampai stok

```text
PO list → Create DRAFT → tambah lines → Issue
  → GR list → Create berdasarkan PO → pilih lokasi/qty
  → Post GR → saldo bertambah + PO status diperbarui
  → Stock/ledger melihat IN_PURCHASE
```

PO dengan penerimaan bertahap tetap menunggu status dari backend; frontend tidak
menghitung status final sebagai sumber kebenaran.

### 4.3 Transfer

```text
Transfer list → Create DRAFT
  → Approve oleh manager asal
  → Ship oleh operator asal
  → status SHIPPED/in-transit
  → Receive oleh operator tujuan
  → input qty_received/variance_reason
  → RECEIVED + stock/ledger updated
```

### 4.4 Opname

```text
Opname list → Create DRAFT → Start
  → snapshot + location freeze
  → Count lines
  → Submit
  → Approve → COMPLETED + adjustment
             ↘ Reject(reason) → IN_PROGRESS
```

### 4.5 Session expiry

```text
Request 401
  → coba refresh sekali dengan mutex
  → simpan pasangan token baru
  → ulangi request asli
  → jika gagal: clear session + redirect login
```

Request refresh tidak boleh memicu loop interceptor tanpa batas.

---

## 5. Page dan Route Specification

Path berikut adalah kontrak navigasi frontend. Permission di tabel adalah
minimum UI guard; server tetap menjadi otoritas final.

| Route | Access | Komponen utama | Kondisi wajib |
|---|---|---|---|
| `/` | publik | landing page berbasis JSON statis | content schema valid, loading/error build-time |
| `/login` | publik | login form | validation, 401, lockout |
| `/dashboard` | authenticated | judul, teks orientasi, dan shortcut menu | tidak ada request KPI/agregasi; teks statis |
| `/master/categories` | `master:read` | filter + data table | manage action hanya `master:manage` |
| `/master/uoms` | `master:read` | table + form | `allow_decimal` |
| `/master/suppliers` | `master:read` | table + form | `ENTITY_IN_USE` |
| `/master/items` | `master:read` | table + form | active refs, precision |
| `/warehouses` | `master:read` | table; create/edit dialog | mutation memerlukan `warehouse:manage` |
| `/warehouses/:warehouseId/locations` | `master:read` | location table/form | mutation memerlukan `location:manage`; scope + frozen/use errors |
| `/stock` | `stock:read` | balance filters/table | location/warehouse/summary views |
| `/stock/ledger` | `ledger:read` | movement table/detail | read-only |
| `/purchase-orders` | `po:read` | PO table/filter | status/date/supplier/warehouse |
| `/purchase-orders/new` | `po:create` | PO form | draft line validation |
| `/purchase-orders/:poId` | `po:read` | detail/lines/activity | state actions |
| `/goods-receipts` | `gr:read` | GR table/filter | warehouse/PO/status/date |
| `/goods-receipts/new` | `gr:manage` | GR form | PO/location/over-receipt |
| `/goods-receipts/:grId` | `gr:read` | detail/lines/activity | post/cancel |
| `/stock-transfers` | `transfer:read` | transfer table/filter | source/destination/status |
| `/stock-transfers/new` | `transfer:create` | transfer form | source != destination |
| `/stock-transfers/:transferId` | `transfer:read` | detail + lifecycle actions | scoped action |
| `/stock-opnames` | `opname:read` | session table/filter | warehouse/location/status |
| `/stock-opnames/new` | `opname:manage` | session form | scope |
| `/stock-opnames/:opnameId` | `opname:read` | snapshot/count/approval UI | freeze, count, variance |
| `/users` | `user:manage` | user table/form | role/status/search |
| `/users/:userId` | `user:manage` | profile/assignment | no secrets |
| `/menus` | `user:manage` | menu administration table/form | active state, hierarchy, permission |
| `/profile` | authenticated | profile read-only + change-password form | session expiry, password validation |
| `/audit-logs` | `audit:read` | filterable audit table | read-only, sensitive masking |

404, unauthorized, forbidden, dan backend error pages harus punya jalur kembali
ke landing page, `/dashboard`, halaman operasional pertama yang diizinkan, atau
halaman sebelumnya.

---

## 6. API Integration

### 6.1 HTTP client

`src/lib/api-client.ts` menyediakan Axios instance dengan:

- `baseURL` dari `VITE_API_BASE_URL`;
- `Content-Type: application/json`;
- bearer access token;
- normalisasi error response;
- request ID bila dikirim backend; backend mengizinkan header `X-Request-ID` dan
  mengekspos response header tersebut untuk dibaca browser;
- interceptor refresh yang hanya mencoba sekali per request.

Frontend tidak boleh mengirim password, access token, atau refresh token ke log.
Untuk development Docker, backend mengizinkan origin `http://localhost:5173`
melalui `FRONTEND_ORIGINS`. CORS menggunakan allowlist origin eksplisit,
mengizinkan method API (`GET`, `POST`, `PATCH`, `PUT`, `OPTIONS`) dan header
`Authorization`, `Content-Type`, serta `X-Request-ID`. Backend saat ini tidak
menggunakan cookie credential sehingga `allow_credentials` tetap `false`.

### 6.2 Response dan error

Response sukses memakai body yang dideskripsikan pada dokumen API. Error backend
berbentuk objek `error` dengan `code`, `message`, dan optional `details`.

Pemetaan minimum:

| HTTP/code | Perilaku UI |
|---|---|
| `401 AUTH_TOKEN_INVALID` | refresh sekali; jika gagal clear session |
| `403 PERMISSION_DENIED` | forbidden state, bukan retry |
| `403 WAREHOUSE_NOT_ASSIGNED` | tampilkan scope warehouse yang diizinkan jika detail tersedia |
| `404 NOT_FOUND` | not-found state atau kembali ke list |
| `409 DUPLICATE` | tampilkan field/entity conflict |
| `409 ENTITY_IN_USE` | jelaskan referensi aktif yang menghalangi |
| `409 INVALID_STATE_TRANSITION` | refetch detail dan tampilkan status terbaru |
| `409 OVER_RECEIPT` | tandai line yang melampaui sisa PO |
| `409 INSUFFICIENT_STOCK` | tampilkan saldo tidak cukup dan jangan retry otomatis |
| `409 LOCATION_FROZEN` | arahkan ke konteks opname |
| `422 INVALID_LOCATION` | tandai lokasi yang tidak cocok/tidak aktif |
| `422 INACTIVE_REFERENCE` | minta pengguna memilih referensi aktif |
| `409 TRANSFER_QTY_EXCEEDS_SHIPPED` | tandai line penerimaan yang melebihi qty dikirim |
| `422 VALIDATION_ERROR` | map field/detail ke form |
| `429 AUTH_TOO_MANY_ATTEMPTS` | tampilkan lockout time bila tersedia |
| `500 INTERNAL_ERROR` | pesan generik + request ID bila ada; jangan tampilkan detail internal |
| `5xx/network` | error state + retry terbatas |

### 6.3 Query, cache, dan invalidation

Setiap feature memiliki query key sendiri, misalnya:

```text
["purchase-orders", "list", params]
["purchase-orders", "detail", poId]
["stock", "by-location", params]
```

Aturan:

- `staleTime` default 30 detik untuk data operasional;
- detail transaksi memakai query terpisah dari list;
- mutation tidak mengubah cache secara spekulatif untuk posting stok;
- sukses GR menginvalidasi GR detail/list, PO terkait, stock, ledger;
- sukses transfer menginvalidasi transfer, stock, ledger;
- sukses opname menginvalidasi opname, stock, ledger;
- create/update master menginvalidasi list dan detail entity;
- navigasi kembali tidak boleh menghidupkan request identik tanpa kebutuhan.

### 6.4 Pagination, filter, sorting

Gunakan `limit` maksimum 200 sesuai kontrak API. Default UI boleh 50.
`offset`, search, filters, `sort_by`, dan `sort_dir`:

- divalidasi sebelum request;
- diserialisasi ke URL;
- dipertahankan saat back/forward;
- di-reset ke offset nol ketika filter utama berubah;
- tidak memakai sorting kolom yang tidak diizinkan backend.

---

## 7. UI/UX Requirements

Implementasi wajib mengikuti [DESIGN.MD](./DESIGN.MD).

### 7.1 Landing page

- gunakan alur naratif statis dari `src/content/landing/`, bukan query API;
- section, heading, body copy, proof point, workflow, CTA, dan footer dirender
  dari content loader tervalidasi;
- perubahan JSON tidak boleh memerlukan perubahan pada komponen section;
- state error content harus ditangani pada build/test, bukan dengan fallback
  copy yang tidak ditinjau.

### 7.2 Operational pages

- gunakan struktur “control tower”: alert → KPI actionable → work queue →
  activity/trend hanya bila halaman operasional dan endpoint terkait tersedia;
- sidebar `ink-950`, canvas `#F7F8F5`, primary teal, warning amber;
- tidak menggunakan card identik tanpa keputusan yang dihasilkan;
- status selalu memiliki label teks, bukan warna saja;
- angka memakai tabular numerals dan unit.

### 7.3 Form

- label selalu terlihat dan terhubung ke input;
- section form panjang memakai heading, bukan accordion berlebihan;
- sticky summary untuk PO, GR, transfer, opname di desktop;
- destructive/business-impact action memakai dialog konfirmasi;
- mutation mempertahankan input jika gagal;
- error field dekat input dan ringkasan error di atas form.

### 7.4 Tabel

- identifier di kolom pertama;
- angka rata kanan;
- status dekat identifier;
- pagination menampilkan rentang dan total;
- mobile memprioritaskan identifier/status/action dan memindahkan detail ke
  drawer;
- tabel ledger dan audit read-only.

### 7.5 State

- initial load: skeleton yang menyerupai bentuk akhir;
- refetch: data lama dipertahankan dan indikator kecil ditampilkan;
- empty: jelaskan konteks dan next action;
- error: pesan manusiawi, request ID bila ada, retry kontekstual;
- toast hanya untuk feedback singkat, bukan satu-satunya tempat error penting.

### 7.6 Accessibility

- WCAG kontras minimal sesuai DESIGN;
- keyboard focus jelas;
- dialog focus trap dan restore focus;
- target sentuh minimal 44px;
- status tidak hanya memakai warna;
- tabel memakai header semantik;
- `aria-live` untuk hasil mutation penting;
- uji zoom 200%, keyboard, mobile, dan screen reader dasar.

---

## 8. State Management

| State | Owner | Aturan |
|---|---|---|
| PO/GR/transfer/opname/stock/user list | TanStack Query | cache berdasarkan query key |
| Entity detail | TanStack Query | invalidasi setelah mutation |
| Access token/session context | Zustand (memory) | access token tidak dipersist; session profile, permission, dan warehouse IDs dapat di-reset saat logout/refresh gagal |
| Refresh token | `LocalStorageRepository` melalui auth/token manager | key `wms.frontend.auth.refresh-token`; hanya dikirim sebagai JSON body ke `/auth/refresh` dan `/auth/logout`; tidak pernah dilog atau dimasukkan ke URL |
| Sidebar collapsed/theme | Zustand atau local React | bukan data server; persist melalui storage adapter bila diperlukan |
| Form draft | React Hook Form | jangan duplikasi ke global store |
| Dialog/tab/row selection | local React | reset saat entity berubah |
| Filter/pagination/sort | URL search params | sumber state navigasi |
| Decimal calculation | local/form helper + Decimal.js | jangan `parseFloat` |
| Landing content | imported JSON + typed content loader | statis, read-only, bukan state server |
| Frontend persistence MVP | storage adapter dengan implementasi `localStorage` | gunakan interface agar implementasi API dapat menggantikan adapter tanpa mengubah komponen |

Zustand tidak boleh menjadi cache kedua untuk data API.

### 8.1 Storage abstraction

Semua kebutuhan penyimpanan frontend yang perlu bertahan antar-refresh harus
melewati interface repository/adapter, bukan memanggil `window.localStorage`
langsung dari komponen. Implementasi MVP:

```text
StorageRepository
├── get<T>(key)
├── set<T>(key, value)
├── remove(key)
└── clear(scope)

LocalStorageRepository implements StorageRepository
ApiStorageRepository (future; tidak diimplementasikan pada MVP)
```

Adapter wajib menangani JSON serialization, key namespace aplikasi, data yang
hilang, dan kegagalan akses storage secara eksplisit. Token, password, dan
refresh token tidak boleh ditulis ke log. Untuk MVP, `LocalStorageRepository`
adalah keputusan penyimpanan refresh token karena backend mengharuskan token
tersebut dikirim melalui JSON body. Access token tetap memory-only.

`localStorage` dapat dibaca JavaScript sehingga refresh token berisiko terekspos
oleh XSS. Implementasi wajib menghindari `dangerouslySetInnerHTML`, memakai
rendering yang aman, tidak memuat script pihak ketiga yang tidak diperlukan,
dan tidak menyimpan password. Migrasi ke HttpOnly cookie nantinya hanya boleh
mengubah token manager, adapter, dan konfigurasi Axios; komponen UI tidak boleh
bergantung pada detail penyimpanan token.

---

## 9. Form dan Data Validation

### 9.1 Prinsip

- schema Zod mencerminkan batas field backend, bukan menggantikan validasi
  backend;
- trim input teks sebelum submit jika kontrak menyatakan trim;
- ID dikirim sebagai integer sesuai schema;
- tanggal memakai format API (`YYYY-MM-DD` atau ISO 8601 sesuai endpoint);
- date display memakai `date-fns`, tetapi payload tidak boleh berubah timezone
  secara tidak sengaja;
- decimal dikirim sebagai string/format yang diterima schema backend, setelah
  dihitung dengan Decimal.js;
- `allow_decimal=false` memblokir pecahan dengan pesan yang jelas.

### 9.2 Validasi domain minimum

- unique line item pada PO;
- qty PO/GR/transfer > 0;
- qty physical opname >= 0;
- source location != destination location;
- transfer received tidak boleh > shipped;
- `variance_reason` wajib jika qty received < qty;
- `closed_reason` wajib saat close PO;
- `rejection_reason` wajib saat reject opname;
- referensi category/UoM/item/supplier/warehouse/location harus aktif bila
  aturan backend mensyaratkannya.

### 9.3 Server sebagai sumber kebenaran

Validasi frontend adalah feedback awal. Setelah submit, response backend tetap
menjadi sumber kebenaran. Jika terjadi konflik state atau duplicate karena user
lain, refetch entity dan jangan menimpa data baru dengan draft lama.

---

## 10. Authentication dan Authorization

### 10.1 Login dan refresh

1. Submit login.
2. Simpan `access_token` hanya di memory/Zustand.
3. Simpan `refresh_token` melalui `LocalStorageRepository` dengan key
   `wms.frontend.auth.refresh-token`.
4. Panggil `/auth/me`.
5. Panggil `/menus/my-menu`.
6. Route ke `/dashboard`, lalu pengguna dapat memilih menu/halaman operasional
   yang terlihat dan diizinkan.

Access token memiliki umur bawaan 15 menit dan refresh token 7 hari menurut
dokumentasi backend; frontend harus membaca `expires_in`/`access_expires_at` bila
dibutuhkan, bukan meng-hardcode expiry lain.

Saat request terproteksi menerima `401 AUTH_TOKEN_INVALID`, Axios interceptor
menjalankan satu refresh terkoordinasi:

1. baca refresh token dari `LocalStorageRepository`;
2. kirim `POST /auth/refresh` dengan `{refresh_token}`;
3. setelah sukses, simpan pasangan token baru dengan mengganti access token di
   memory dan refresh token lama secara atomik;
4. ulangi request awal tepat satu kali.

Request ke `/auth/refresh` tidak boleh memicu interceptor refresh. Request
paralel harus menunggu promise refresh yang sama, bukan membuat refresh request
baru. Jika refresh token tidak tersedia atau refresh gagal, frontend menghapus
access token, refresh token, session profile, permission/menu cache, dan
TanStack Query cache sensitif, lalu mengarahkan pengguna ke `/login`.

### 10.1.1 Logout dan session invalidation

Jika refresh token tersedia, frontend mengirim:

```json
{ "refresh_token": "<current-refresh-token>" }
```

ke `POST /auth/logout` dengan Bearer access token yang masih aktif. Terlepas
dari hasil request logout, frontend wajib membersihkan memory session, key
refresh token, user profile, menu, dan cache query sensitif. Reuse detection
atau `401 AUTH_TOKEN_INVALID` pada refresh diperlakukan sebagai session
termination; frontend tidak boleh mencoba token lama lagi.

### 10.2 Route guard

- public route: `/`, `/login`;
- authenticated route: semua workspace;
- permission guard menampilkan forbidden state bila direct navigation tidak
  diizinkan;
- permission guard tidak dianggap security boundary;
- `is_active`, role, permission, dan assignment dapat berubah di backend pada
  request berikutnya.

### 10.3 Warehouse scoping

Warehouse Staff dibatasi pada gudang yang ditugaskan; operasi tertentu memerlukan
akses gudang asal atau tujuan. UI harus:

- memfilter pilihan warehouse berdasarkan `/auth/me`;
- tidak menyembunyikan error scope dari backend;
- menampilkan scope aktif pada page header/filter;
- membedakan akses asal dan tujuan pada transfer;
- tidak mengasumsikan user dengan satu warehouse selalu boleh melihat semua
  modul lintas gudang.

---

## 11. Frontend Architecture

Struktur mengikuti [FOLDER_STRUCTURE.MD](./FOLDER_STRUCTURE.MD):

```text
src/
├── app/                 # providers, router, guards
├── content/
│   └── landing/         # seluruh konten landing page dalam JSON + schema/loader
├── components/
│   ├── layout/          # AppShell, sidebar, topbar
│   ├── shared/          # DataTable, StatusBadge, ErrorState, QtyInput
│   └── ui/              # shadcn primitives
├── features/
│   ├── auth/
│   ├── master-data/
│   ├── warehouses/
│   ├── stock/
│   ├── purchase-orders/
│   ├── goods-receipts/
│   ├── stock-transfers/
│   ├── stock-opnames/
│   ├── users/
│   └── audit-logs/
├── hooks/
├── lib/                 # api-client, errors, query-client, decimal, storage
│   └── storage/         # interface repository + LocalStorageRepository
├── pages/
├── styles/
├── test/
└── types/
```

Pola feature:

```text
features/<domain>/
├── api.ts               # Axios calls, tanpa JSX
├── keys.ts              # query key
├── queries.ts           # useQuery/useMutation
├── schemas.ts           # Zod schema
├── types.ts             # tipe domain
├── components/
└── pages/
```

`api.ts` tidak boleh mengandung UI. `pages/` tipis. Komponen domain tidak
dipindahkan ke `components/ui`. Content loader landing page harus memisahkan
data JSON dari komponen section; komponen menerima typed props, bukan membaca
file JSON secara tersebar.

### 11.1 Struktur content landing page

Folder `src/content/landing/` minimal memiliki struktur berikut:

```text
src/content/landing/
├── hero.json
├── proof-points.json
├── workflow.json
├── pain-points.json
├── security.json
├── cta.json
├── footer.json
├── schema.ts
└── index.ts
```

`index.ts` adalah entry point tunggal untuk loader dan export content yang sudah
divalidasi. Nama file dapat disesuaikan selama seluruh data landing tetap
berada di folder tersebut. JSON tidak boleh memuat token, credential, data
operasional aktual, atau klaim yang belum didukung backend.

---

## 12. Testing Strategy

### 12.1 Unit test

Uji tanpa browser untuk:

- decimal/format helper;
- query key;
- normalisasi API error;
- permission predicate;
- route/menu tree mapping;
- format tanggal dan pagination params.

### 12.2 Component test

Uji dengan Testing Library:

- login form dan pesan validation;
- status badge dan action visibility;
- table empty/error/loading;
- form line add/remove dan duplicate item;
- dialog konfirmasi post/ship/receive/approve;
- mobile navigation dan keyboard interaction.

### 12.3 API integration dengan MSW

Mock response contract, bukan implementasi service internal. Minimal mock:

- login/me/refresh/logout;
- menu tree;
- paginated list;
- `401`, `403`, `409`, `422`, `429`, dan network error;
- mutation sukses dan invalidation.

### 12.4 Skenario acceptance utama

- login gagal lima kali menampilkan lockout;
- expired token refresh hanya sekali lalu request diulang;
- Warehouse Staff tidak dapat membuat GR di warehouse yang tidak ditugaskan;
- PO issue menolak line kosong;
- GR post menolak over-receipt dan location frozen;
- transfer menolak insufficient stock dan variance tanpa alasan;
- opname freeze memblokir movement normal;
- opname reject meminta alasan;
- user tanpa `audit:read` tidak melihat audit route;
- menu parent tidak muncul jika seluruh child tidak terlihat.

### 12.5 Quality gate

```powershell
npm run typecheck
npm run lint
npm test
npm run build
```

Tidak ada error TypeScript/ESLint, test yang relevan lulus, dan tidak ada
regresi pada acceptance criteria sebelum merge.

---

## 13. Non-Functional Requirements

### Performa

- first render tidak menunggu query yang tidak dibutuhkan route aktif;
- gunakan code splitting per feature ketika bundle mulai membesar;
- tabel besar memakai pagination server-side;
- refetch tidak menghilangkan data yang sedang dibaca;
- hindari request duplikat melalui query key yang konsisten.

Target backend `<200 ms` untuk endpoint tertentu bukan SLA frontend; frontend
harus tetap menampilkan loading dan error state bila response lebih lambat.

### Accessibility

- keyboard, focus, semantic labels, contrast, screen reader dasar, dan reduced
  motion mengikuti DESIGN.MD;
- error dan success penting dapat diumumkan melalui `aria-live`.

### Security

- jangan log token, password, atau payload sensitif;
- jangan menaruh secret pada `VITE_*`;
- clear session/cache sensitif saat logout atau refresh gagal;
- XSS-safe rendering untuk notes, audit JSON, dan API message;
- frontend permission adalah UX control; backend tetap security boundary.

### Maintainability

- feature boundary jelas;
- API types dipelihara di `src/types/` berdasarkan kontrak backend; tidak ada
  artifact OpenAPI atau generator tidak menjadi dependency frontend;
- shared component memiliki test dan API props yang stabil;
- endpoint path tidak disebar sebagai string ad hoc;
- perubahan kontrak backend menghasilkan update schema/test frontend.

### Compatibility

Target awal: browser modern yang mendukung React 19, Vite output, ES2022,
Fetch/AbortController, dan CSS modern. Matrix browser final menunggu keputusan
produk.

---

## 14. Environment dan Development Setup

### 14.1 Variable

```env
VITE_API_BASE_URL=http://localhost:8000
FRONTEND_DEV_PORT=5173
```

Hanya variable `VITE_*` yang masuk bundle. Jangan simpan secret di `.env` yang
akan dikirim ke browser.

Storage MVP memakai `localStorage` melalui adapter yang didefinisikan pada
Section 8.1. Key wajib memiliki namespace aplikasi, misalnya
`wms.frontend.<scope>.<key>`. Content landing page bukan data runtime
`localStorage`; content tersebut dibundel dari JSON statis agar dapat divalidasi
ketika build.

Keputusan token MVP:

```text
access token  -> memory/Zustand saja
refresh token -> LocalStorageRepository
```

Refresh token disimpan hanya pada key `wms.frontend.auth.refresh-token` dan
hanya digunakan untuk request `/auth/refresh` serta `/auth/logout`. Jangan
menyimpan password, token pada URL, atau token pada log browser. HttpOnly cookie
belum menjadi kontrak backend; migrasi ke cookie merupakan perubahan kontrak
terpisah yang tidak boleh memaksa perubahan komponen UI.

### 14.2 Local

```powershell
npm install
Copy-Item .env.example .env
npm run dev
```

### 14.3 Docker development

```powershell
docker compose up --build
```

Compose yang saat ini ada hanya menyediakan PostgreSQL dan API FastAPI,
termasuk hot reload API; belum ada service frontend Node. Frontend developer
harus menjalankan Vite di host (`npm run dev`) atau mengusulkan perubahan
compose terpisah. API tersedia di `http://localhost:8000`; CORS/origin harus
disiapkan backend sebelum browser frontend mengaksesnya.

### 14.4 API contract types

Frontend tidak memerlukan atau menyimpan artifact OpenAPI. Tipe request/response
ditulis dan dipelihara di `src/types/` berdasarkan dokumentasi API serta schema
backend yang sudah direview. Setiap perubahan kontrak backend harus diikuti
penyesuaian tipe, service, schema Zod, dan test frontend yang relevan.

Tipe API bukan alasan untuk membuat endpoint atau field baru. Jika dokumentasi
dan implementasi backend berbeda, pekerjaan terkait harus ditandai sebagai
blocked sampai kontrak diklarifikasi.

---

## 15. Implementation Plan

### Phase 0 — Contract dan foundation (P0)

1. Bekukan response/error contract yang dipakai frontend.
2. Tulis dan review API types berdasarkan dokumentasi endpoint serta schema
   backend yang tersedia.
3. Implement Axios error normalization, query client, auth store, refresh mutex.
4. Implement storage interface dan `LocalStorageRepository`; uji migrasi
   komponen terhadap interface, bukan API browser langsung.
5. Implement public route, auth routes, dynamic menu, guards, dan redirect
   pasca-login ke dashboard informatif tanpa dependency dashboard operasional.
6. Implement typed landing content loader dari `src/content/landing/`.
7. Implement shared form field, status, dialog, loading/error/empty.

**Dependency:** backend auth, `/auth/me`, dan `/menus/my-menu`. Konfigurasi CORS
development sudah disediakan backend melalui `FRONTEND_ORIGINS`.

### Phase 1 — Read foundation (P0)

1. Implement dashboard informatif berbasis teks statis.
2. Master data read + warehouse/location read.
3. Stock balance dan ledger read-only.
4. Pagination/filter URL state.

**Dependency:** stable list response dan permission errors.

### Phase 2 — Master and PO (P0)

1. Master create/update/deactivate.
2. PO draft create/update.
3. PO issue/cancel/close.
4. Query invalidation dan acceptance tests.

**Dependency:** active reference behavior, PO schemas/state machine.

### Phase 3 — GR (P0)

1. GR list/detail/draft.
2. Post/cancel.
3. Over-receipt, frozen location, and atomic mutation feedback.

**Dependency:** PO and location data.

### Phase 4 — Transfer (P0)

1. Draft and scoped source selection.
2. Approval, ship, receive, variance.
3. In-transit and ledger refresh.

**Dependency:** stock/location and transfer permission/scoping.

### Phase 5 — Opname (P0)

1. Session create/start/snapshot.
2. Counting grid with precision validation.
3. Submit/approve/reject/cancel and freeze states.

**Dependency:** inventory/ledger contract and location freeze errors.

### Phase 6 — Administration and audit (P1)

1. User/role/permission/assignment.
2. Dynamic menu administration only if product requires UI admin for it.
3. Audit log read-only.

**Dependency:** Super Admin permission contract and sensitive field masking.

### Phase 7 — Landing page dan polish (P0)

1. Validasi seluruh JSON content dan schema landing page.
2. Implement section landing page dari typed content tanpa copy hard-coded.
3. Accessibility audit, responsive pass, performance, dan visual QA.

Dashboard operasional tetap berada di backlog terpisah dan tidak menjadi
dependency untuk menyelesaikan fase MVP.

Setiap fase harus melewati quality gate dan review acceptance criteria sebelum
fase berikutnya dimulai.

---

## 16. Definition of Done

Sebuah feature frontend dinyatakan selesai jika:

### Contract dan behavior

- [ ] endpoint, method, payload, response, permission, dan error code cocok
      dengan dokumentasi backend;
- [ ] access token hanya disimpan di memory dan refresh token hanya dikelola
      melalui `LocalStorageRepository` dengan key namespace yang ditentukan;
- [ ] refresh token dirotasi atomik setelah refresh berhasil dan tidak pernah
      ditulis ke log, URL, atau error message;
- [ ] logout, refresh gagal, token reuse, dan session invalid menghapus token
      serta cache sensitif;
- [ ] state machine hanya menyediakan transisi yang sah;
- [ ] warehouse scoping diterapkan pada pilihan dan action UI;
- [ ] server response menjadi sumber kebenaran setelah mutation;
- [ ] tidak ada endpoint atau aturan bisnis hasil tebakan.

### UI/UX

- [ ] page header, breadcrumb, primary action, dan scope jelas;
- [ ] loading, empty, error, success, forbidden, dan not-found tersedia;
- [ ] filter/pagination/sort tersimpan pada URL bila relevan;
- [ ] desain mengikuti token, layout, status, dan responsive rule DESIGN.MD;
- [ ] tidak ada status yang hanya dibedakan oleh warna;
- [ ] form mempertahankan input saat server menolak request.

### Quality

- [ ] unit/component/API tests untuk acceptance criteria lulus;
- [ ] `npm run typecheck` lulus;
- [ ] `npm run lint` lulus;
- [ ] `npm test` lulus;
- [ ] `npm run build` lulus;
- [ ] tidak ada secret pada source, log, atau bundle;
- [ ] keyboard, zoom 200%, mobile, dan contrast dasar telah diuji.

### Documentation

- [ ] feature, route, query key, schema, dan permission terdokumentasi;
- [ ] asumsi atau blocker kontrak dicatat;
- [ ] API types di `src/types/` diperbarui jika schema backend berubah;
- [ ] perubahan besar pada struktur atau visual memperbarui dokumentasi terkait.

---

## 17. Backend contract review dan gap

Bagian ini adalah hasil pemeriksaan langsung terhadap `app/api/routes`,
`app/schemas`, `app/core/exceptions.py`, dan dokumentasi API. Jika bagian
sebelumnya menggunakan istilah yang lebih umum, tabel ini menjadi rujukan
implementasi yang lebih spesifik.

### 17.1 Konvensi response dan parameter

- Semua endpoint domain berada di `/api/v1`; health tersedia di
  `/health` dan `/api/v1/health`, tanpa autentikasi.
- Request dan response memakai `application/json`. Timestamp response adalah
  ISO 8601 dengan timezone; field tanggal dokumen adalah `YYYY-MM-DD`.
- Daftar paginated memakai query `limit` (default 50, 1–200), `offset` (>= 0),
  dan response `{items, total, limit, offset}`. Filter/sort tidak boleh
  mengirim nama kolom di luar whitelist backend.
- `GET /menus/my-menu`, `GET /users/roles`,
  `GET /users/permissions`, `GET /users/{id}/warehouses`, dan
  `PUT /users/{id}/warehouses` mengembalikan array langsung.
- Nilai kuantitas pada response selalu string dengan empat angka desimal,
  misalnya `"12.5000"`. Payload kuantitas harus dikirim sebagai string desimal
  atau integer; backend menolak JSON number bertipe float. Frontend memakai
  `Decimal.js` dan tidak boleh memakai `parseFloat`.
- Error selalu berbentuk
  `{ "error": { "code": string, "message": string, "details": object } }`.
  Error 422 dari Pydantic menempatkan rincian field pada `details.errors`.
  `X-Request-ID` dikembalikan server dan ditampilkan hanya sebagai metadata
  bantuan, bukan sebagai pesan error utama.

### 17.2 Auth dan session

| Method dan path | Request utama | Response | Auth |
|---|---|---|---|
| `POST /auth/login` | `{username, password}`; username 1–64, password 1–255 | `{access_token, refresh_token, token_type, expires_in, access_expires_at}` | publik |
| `POST /auth/refresh` | `{refresh_token}` | pasangan token baru dengan shape yang sama | publik + refresh token |
| `POST /auth/logout` | `{refresh_token}` | `{message}` | Bearer aktif |
| `GET /auth/me` | — | id, username, email, full_name, role, permissions, warehouse_ids, timestamps | Bearer aktif |
| `POST /auth/change-password` | `{current_password, new_password}`; password baru 8–255 | `{message}` | Bearer aktif |

Refresh melakukan rotation. Pemakaian ulang refresh token yang sudah dicabut
mematikan seluruh sesi user dan menghasilkan `401 AUTH_TOKEN_INVALID`.
Perubahan password juga mencabut seluruh sesi lama. Interceptor hanya boleh
menjalankan satu refresh terkoordinasi; request refresh tidak boleh
di-refresh ulang.

### 17.3 Endpoint domain dan payload mutation

| Domain | List/detail | Create/update | Action dan permission route |
|---|---|---|---|
| Category, UoM, Supplier, Item | `GET /categories`, `/uoms`, `/suppliers`, `/items` + `GET /{id}` | `POST`, `PATCH` pada resource; read `master:read`, mutation `master:manage` | soft deactivate; tidak ada DELETE |
| Warehouse | `GET/POST /warehouses`, `GET/PATCH /warehouses/{id}` | body warehouse code/name/address/allow_negative_stock/is_active; mutation `warehouse:manage` | tidak ada DELETE |
| Location | `GET/POST /locations`, `GET/PATCH /locations/{id}`; juga nested `GET/POST /warehouses/{warehouse_id}/locations` | body code/name/is_active; nested create tidak mengirim `warehouse_id` | read `master:read`, mutation `location:manage` |
| PO | `GET/POST /purchase-orders`, `GET/PATCH /purchase-orders/{id}` | `{supplier_id, warehouse_id, order_date, notes, lines:[{item_id, qty_ordered, notes}]}` | `/issue` `po:issue`; `/close` `{closed_reason}` + `po:close`; cancel memerlukan `po:create` untuk DRAFT atau `po:cancel` untuk ISSUED |
| GR | `GET/POST /goods-receipts`, `GET/PATCH /goods-receipts/{id}` | `{po_id, received_date, notes, lines:[{po_line_id, location_id, qty_received, notes}]}` | `/post` dan `/cancel` `gr:manage`; read `gr:read` |
| Transfer | `GET/POST /stock-transfers`, `GET/PATCH /stock-transfers/{id}` | `{source_warehouse_id, source_location_id, destination_warehouse_id, destination_location_id, notes, lines:[{item_id, qty}]}` | `/approve` `transfer:approve`, `/ship` `transfer:ship`, `/receive` `{lines:[{line_id, qty_received, variance_reason}]}` `transfer:receive`, cancel `transfer:create` atau `transfer:approve` |
| Opname | `GET/POST /stock-opnames`, `GET/PATCH /stock-opnames/{id}` | create `{warehouse_id, location_id?, notes}`; update `{location_id?, clear_location?, notes?}` | `/start`/`/cancel` `opname:manage`; `/count`, `/lines` (POST/PUT), `/submit` `opname:count`; `/approve`/`/reject` `{rejection_reason}` `opname:approve` |

Semua mutation mengembalikan detail entity terbaru, bukan envelope paginated.
Frontend harus memakai response itu untuk navigasi/refetch dan tidak
menghasilkan nomor dokumen, status, saldo, atau qty variance sendiri.

### 17.4 Read endpoint dan filter aktual

| Endpoint | Filter yang boleh dikirim |
|---|---|
| Master/warehouse/location | `limit`, `offset`, `is_active`, `search`, `sort_by`, `sort_dir`; location juga `warehouse_id` |
| PO | `warehouse_id`, `supplier_id`, `status`, `date_from`, `date_to`, `search`, pagination/sort |
| GR | `warehouse_id`, `po_id`, `status`, `date_from`, `date_to`, `search`, pagination/sort |
| Transfer | `warehouse_id`, `source_warehouse_id`, `destination_warehouse_id`, `status`, `date_from`, `date_to`, `search`, pagination/sort |
| Opname | `warehouse_id`, `location_id`, `status`, `date_from`, `date_to`, `search`, pagination/sort |
| Stock location/balance | `warehouse_id`, `location_id`, `item_id`, `category_id`, `search`, pagination/sort |
| Stock warehouse/summary | `warehouse_id`, `item_id`, `category_id`, `search`, pagination/sort |
| Movement/ledger | `warehouse_id`, `location_id`, `item_id`, `movement_type`, `reference_type`, `reference_id`, `date_from`, `date_to`, pagination/sort |
| Audit log | `user_id`, `action`, `entity_type`, `entity_id`, `date_from`, `date_to`, pagination/sort |

`/stock/balances` dan `/stock/by-location` adalah alias dengan response yang
sama; `/stock/movements` dan `/stock/ledger` juga alias. Frontend memilih satu
URL kanonik per halaman agar cache tidak terduplikasi.

### 17.5 Gap dan keputusan yang wajib dicatat

1. **Dashboard operasional ditunda:** route `/dashboard` MVP hanya berisi teks
   informatif statis. KPI, chart, recent activity, dan alert count tetap berada
   di backlog sampai scope dan kontrak disetujui.
2. **Frontend Docker — keputusan implementasi MVP:** tambahkan service
   `frontend` ke `docker-compose.yml` dengan `Dockerfile.frontend`. Service
   menjalankan Vite pada `0.0.0.0:5173`, memetakan port host
   `${FRONTEND_PORT:-5173}`, dan memakai named volume khusus untuk
   `/app/node_modules`. Source frontend di-mount ke container agar perubahan
   file memicu hot reload. Service ini dijalankan dengan:

   ```powershell
   docker compose up --build
   ```

   Frontend dibuka melalui `http://localhost:5173`. Karena request API
   dilakukan oleh browser host, `VITE_API_BASE_URL` harus bernilai
   `http://localhost:8000`, bukan `http://api:8000`. URL `api` hanya digunakan
   untuk komunikasi antarkontainer dan tidak boleh diekspos sebagai URL API
   browser.

   Struktur konfigurasi minimum yang harus dibuat pada tahap implementasi:

   ```text
   Dockerfile.frontend
   docker-compose.yml      # service frontend + named volume frontend_node_modules
   .env.frontend            # VITE_API_BASE_URL=http://localhost:8000
   ```

   Compose yang ada saat ini belum menerapkan keputusan ini; penambahan service
   frontend merupakan pekerjaan setup frontend, bukan perubahan kontrak bisnis
   backend.
3. **CORS — sudah diakomodasi backend untuk development:** backend menggunakan
   `CORSMiddleware` dengan allowlist dari `FRONTEND_ORIGINS`. Nilai default dan
   konfigurasi `.env.example`/`.env.docker` adalah
   `["http://localhost:5173"]`. Method `GET`, `POST`, `PATCH`, `PUT`, dan
   `OPTIONS`, header `Authorization`, `Content-Type`, dan `X-Request-ID`, serta
   response header `X-Request-ID` sudah dikonfigurasi. `allow_credentials` tetap
   `false` karena autentikasi menggunakan Bearer header dan refresh token JSON,
   bukan cookie. Production wajib mengganti allowlist dengan origin frontend
   resmi dan tidak boleh menggunakan wildcard tanpa review keamanan.
4. **Refresh-token storage — keputusan MVP:** karena kontrak backend menerima
   refresh token melalui JSON body, access token disimpan memory-only di
   Zustand dan refresh token disimpan melalui `LocalStorageRepository` pada
   key `wms.frontend.auth.refresh-token`. Rotasi token mengganti nilai lama
   hanya setelah refresh berhasil. Logout, refresh gagal, token reuse, dan
   session invalid harus menghapus token serta cache sensitif. Komponen UI
   tidak boleh mengakses `localStorage` langsung.

   Keputusan ini memiliki risiko XSS karena `localStorage` dapat dibaca
   JavaScript. Mitigasinya adalah secure rendering, tidak menggunakan
   `dangerouslySetInnerHTML`, tidak menyimpan password, tidak menulis token ke
   log/URL, dan membatasi script pihak ketiga. Migrasi ke HttpOnly cookie
   memerlukan perubahan kontrak backend pada login/refresh/logout dan harus
   diisolasi pada token manager, storage adapter, serta HTTP client.
5. **Dynamic menu path:** backend dapat mengirim path menu yang belum memiliki
   route frontend. Frontend harus menampilkan fallback/404 dan mencatat gap,
   bukan mendaftarkan route arbitrer dari server.
6. **Landing content:** kebutuhan konten statis sudah diputuskan; yang tersisa
   hanya pengisian dan review isi JSON sebelum implementasi section.

## 18. Traceability matrix

| Kebutuhan backend | Requirement frontend |
|---|---|
| JWT + refresh rotation | FR-01, Section 10, session expiry flow |
| RBAC + warehouse scoping | FR-02, FR-10, Section 10 |
| Dynamic menu | FR-02 |
| Master data soft deactivate | FR-04 |
| PO state machine | FR-06 |
| GR atomic posting/freeze/over-receipt | FR-07 |
| Transfer ship/receive/variance | FR-08 |
| Opname snapshot/freeze/approval | FR-09 |
| Read-only stock/ledger | FR-05 |
| Append-only audit | FR-11 |
| UI visual system | Section 7 dan DESIGN.MD |
| Feature architecture | Section 11 dan FOLDER_STRUCTURE.MD |
| Static landing content | FR-12, Section 8.1, Section 11.1 |
| Local storage abstraction | Section 8.1, Section 14.1 |
| Informational dashboard | FR-03, Section 5 |
