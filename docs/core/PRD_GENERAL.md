# PRD General — JejakStok

| Informasi | Nilai |
| --- | --- |
| Status | Baseline Fase 1 (MVP Single-Tenant) dengan tambahan MST-F06 dan MST-F07; spesifikasi Fase 2 (M9 Multi-Tenant SaaS) |
| Versi | 2.2-general |
| Pemilik | Product / Business |
| Sumber historis | PRD v2.0 (Single-Tenant) & PRD Modular v3.1 (Multi-Tenant SaaS) yang telah diaudit dan diintegrasikan |
| Catatan | Baseline Fase 1 (M0–M8) telah selesai diimplementasikan dan diuji. Tambahan MST-F06 dan MST-F07 kini diimplementasikan; seluruh 47 tes backend lulus, termasuk AC-30 dan AC-31. Fase 2 tetap mencakup `TNT`, `CFG`, `tenant_id` + RLS sebelum Fase 3 (`ISS`, `RPT`). |

Dokumen ini adalah sumber utama requirement produk. Dokumen Backend, Frontend,
Database, API, dan QA hanya menjabarkan konsekuensi requirement ini dan tidak boleh
menambah business rule baru tanpa perubahan PRD.

## Daftar Isi

- [1. Cara membaca dan standar ID](#1-cara-membaca-dan-standar-id)
- [2. Tujuan dan scope](#2-tujuan-dan-scope)
- [3. Pengguna dan akses](#3-pengguna-dan-akses)
- [4. Arsitektur modular](#4-arsitektur-modular)
- [5. Aturan bisnis global](#5-aturan-bisnis-global)
- [6. Spesifikasi modul](#6-spesifikasi-modul)
- [7. Workflow end-to-end](#7-workflow-end-to-end)
- [8. Data requirements](#8-data-requirements)
- [9. Non-functional requirements](#9-non-functional-requirements)
- [10. Acceptance criteria](#10-acceptance-criteria)
- [11. Requirement Traceability Matrix](#11-requirement-traceability-matrix)
- [12. Prioritas dan roadmap](#12-prioritas-dan-roadmap)
- [13. Asumsi, konflik, dan konfirmasi](#13-asumsi-konflik-dan-konfirmasi)
- [14. Change impact dan validation](#14-change-impact-dan-validation)

## 1. Cara membaca dan standar ID

### 1.1 Status requirement

`MVP` berarti wajib untuk baseline aktif. `Phase 2` berarti kandidat lanjutan yang
memiliki dasar cukup tetapi tidak menjadi acceptance criteria MVP. `Future Development`
berarti rencana yang belum cukup jelas. `Out of Scope` berarti tidak boleh
diimplementasikan pada scope ini.

Status traceability: `Not Mapped`, `Mapped`, `In Development`, `Implemented`,
`Tested`, `Verified`, dan `Need Confirmation`. Dokumen ini tidak menyatakan
`Implemented`, `Tested`, atau `Verified` tanpa bukti yang dirujuk.

### 1.2 Registry ID

ID tidak boleh dipakai ulang. Perubahan nama atau posisi tidak mengubah ID.

| Jenis | Format | Contoh |
| --- | --- | --- |
| Module | Tiga huruf | `INV` |
| Feature | `<MODULE>-Fnn` | `INV-F01` |
| Functional requirement | `FR-<MODULE>-nnn` | `FR-INV-001` |
| Business rule | `BR-<MODULE>-nnn` | `BR-INV-001` |
| Non-functional requirement | `NFR-nnn` | `NFR-001` |
| Acceptance criteria | `AC-nn` | `AC-01` |
| Open decision | `CONF-nnn` | `CONF-001` |
| Risk | `RSK-nnn` | `RSK-001` |

## 2. Tujuan dan scope

### 2.1 Tujuan produk

JejakStok menyediakan visibilitas stok per gudang dan lokasi, penerimaan yang
tertelusur ke PO, transfer dengan status in-transit, rekonsiliasi melalui opname,
dan jejak audit yang dapat diperiksa.

| ID | Tujuan | Modul |
| --- | --- | --- |
| G-01 | Visibilitas stok per lokasi, gudang, agregat, dan in-transit | INV, TRF |
| G-02 | Penerimaan tervalidasi terhadap PO, termasuk parsial | PUR, RCV |
| G-03 | Traceability melalui movement ledger dan audit log append-only | INV, AUD |
| G-04 | Integritas persediaan dan rekonsiliasi fisik | INV, OPN |
| G-05 | Isolasi data multi-tenant, manajemen siklus hidup/kuota tenant, dan konfigurasi per tenant/gudang (Fase 2 — M9) | TNT, CFG, PLT, IAM |

### 2.2 Fase 1 — Baseline MVP (M0–M8, Single-Tenant)

| Module | Feature ID | Fitur | MoSCoW |
| --- | --- | --- | --- |
| PLT | PLT-F01..F05 | Numbering, query convention, error, request ID/health, migration | Must Have |
| IAM | IAM-F01..F09 | Auth, RBAC, user, warehouse scope, menu, profile | Must Have |
| AUD | AUD-F01..F02 | Write/read audit log | Must Have |
| MST | MST-F01..F06 | Category, UoM, item, supplier, deactivation, import massal item | Must Have |
| WHS | WHS-F01..F03 | Warehouse, location, validation | Must Have |
| INV | INV-F01..F06 | Balance, ledger, movement gateway, negative stock, freeze enforcement | Must Have |
| PUR | PUR-F01..F04 | PO lifecycle and fulfillment | Must Have |
| RCV | RCV-F01..F04 | Goods receipt and posting | Must Have |
| TRF | TRF-F01..F05 | Transfer lifecycle and in-transit | Must Have |
| OPN | OPN-F01..F06 | Count, freeze, approval, adjustment, opening balance | Must Have |

### 2.3 Fase 2 (M9 — Multi-Tenant SaaS), Fase 3, Future Development, dan Out of Scope

| Kategori | Fitur | Dasar/status |
| --- | --- | --- |
| **Phase 2 (M9 — Target Langsung Berikutnya)** | **Multi-Tenant SaaS Foundation (`TNT`, `CFG`, `PLT-F06`, `IAM-F10`)**: isolasi `tenant_id` + PostgreSQL RLS, provisioning tenant oleh Platform Admin (`POST /api/v1/platform/tenants`), siklus hidup tenant (`TRIAL`, `ACTIVE`, `SUSPENDED`, `DEACTIVATED`), paket kuota (`max_warehouses`, `max_active_users`, `max_active_items`), login tenant ber-`slug`, login Platform Admin terpisah (`/api/v1/platform/auth/login`), dan pewarisan konfigurasi (`CFG`) | **Disetujui (`CONF-001` Resolved)** — dikerjakan sebelum modul operasional baru agar tabel baru langsung ber-`tenant_id` |
| **Phase 3 (M10)** | **Goods Issue (`ISS`)** — pengeluaran barang operasional | Menunggu detail workflow (`CONF-002`), dibangun di atas skema Multi-Tenant M9 |
| **Phase 3 (M10)** | **Laporan dasar (`RPT`)** — laporan agregat read-only | Menunggu daftar laporan wajib (`CONF-003`), dibangun di atas skema Multi-Tenant M9 |
| Future Development | Self-service tenant signup publik, billing/invoicing otomatis, SSO, 2FA, export data tenant | Pasca-M9 |
| Future Development | Export laporan, reorder point, notification, barcode/QR, picking/putaway | Roadmap lanjutan, belum requirement final |
| Out of Scope | Lot/batch/expiry dan serial number | OOS-01, OOS-02 |
| Out of Scope | Costing/valuation | OOS-03 |
| Out of Scope | Reservation | OOS-04 |
| Out of Scope | Return supplier dan reversal GR | OOS-06 |
| Out of Scope | UoM conversion | OOS-07 |
| Out of Scope | Partial transfer receiving | OOS-08 |
| Out of Scope | Multi-level PO approval | OOS-09 |
| Out of Scope | UI/frontend di repository API, notification, ERP/barcode/email/WhatsApp integration | OOS-10 |

## 3. Pengguna dan akses

| Role | Fokus |
| --- | --- |
| Super Admin | User, role/permission, assignment, warehouse configuration, audit (lintas gudang) |
| Warehouse Manager | Location, transfer approval, opname approval, PO close, monitoring pada warehouse assigned |
| Purchasing Staff | Master procurement serta pengelolaan dan pemantauan PO/GR/stok pada warehouse assigned |
| Warehouse Staff | GR, transfer physical execution, opname count, dan pembacaan operasional pada warehouse assigned |
| Auditor | Read-only master, stock, documents, ledger, opname, audit (lintas gudang) |

### 3.1 Matriks permission per role (MVP)

Tanda `✓` berarti diizinkan secara global; tanda `✓ (g)` berarti diizinkan hanya pada
gudang yang ditugaskan kepada pengguna (`user_warehouses`). Super Admin memiliki
seluruh 24 permission tanpa batasan penugasan gudang.

| Kode Permission | Deskripsi | Super Admin | Warehouse Manager | Purchasing Staff | Warehouse Staff | Auditor |
| --- | --- | :---: | :---: | :---: | :---: | :---: |
| `user:manage` | Kelola pengguna, role/permission, penugasan gudang, dan katalog menu | ✓ | – | – | – | – |
| `warehouse:manage` | Kelola gudang & konfigurasi `allow_negative_stock` | ✓ | – | – | – | – |
| `location:manage` | Kelola lokasi penyimpanan | ✓ | ✓ `(g)` | – | – | – |
| `master:manage` | Kelola kategori, UoM, barang, pemasok | ✓ | – | ✓ | – | – |
| `master:read` | Baca master data, gudang, dan lokasi | ✓ | ✓ `(g)` | ✓ `(g)` | ✓ `(g)` | ✓ |
| `po:create` | Buat/ubah PO `DRAFT`, batalkan PO `DRAFT` | ✓ | – | ✓ `(g)` | – | – |
| `po:issue` | Terbitkan PO (`DRAFT -> ISSUED`) | ✓ | – | ✓ `(g)` | – | – |
| `po:cancel` | Batalkan PO `ISSUED` | ✓ | – | ✓ `(g)` | – | – |
| `po:close` | Tutup PO (`ISSUED`/`PARTIALLY_RECEIVED -> CLOSED`) | ✓ | ✓ `(g)` | ✓ `(g)` | – | – |
| `po:read` | Baca PO | ✓ | ✓ `(g)` | ✓ `(g)` | ✓ `(g)` | ✓ |
| `gr:manage` | Buat, ubah, posting, batalkan GR | ✓ | – | – | ✓ `(g)` | – |
| `gr:read` | Baca GR | ✓ | ✓ `(g)` | ✓ `(g)` | ✓ `(g)` | ✓ |
| `transfer:create` | Buat/ubah/batalkan Transfer `DRAFT` | ✓ | – | – | ✓ `(g)` | – |
| `transfer:approve` | Setujui Transfer `DRAFT` atau batalkan Transfer `APPROVED` | ✓ | ✓ `(g)` | – | – | – |
| `transfer:ship` | Kirim Transfer (`APPROVED -> SHIPPED`) | ✓ | – | – | ✓ `(g)` | – |
| `transfer:receive` | Terima Transfer (`SHIPPED -> RECEIVED`) | ✓ | – | – | ✓ `(g)` | – |
| `transfer:read` | Baca Transfer | ✓ | ✓ `(g)` | – | ✓ `(g)` | ✓ |
| `opname:manage` | Buat, ubah draft, mulai (`start`), batalkan sesi Opname | ✓ | ✓ `(g)` | – | – | – |
| `opname:count` | Input hitung fisik & ajukan persetujuan (`submit`) | ✓ | – | – | ✓ `(g)` | – |
| `opname:approve` | Setujui (`approve`) atau tolak (`reject`) hasil Opname | ✓ | ✓ `(g)` | – | – | – |
| `opname:read` | Baca sesi Opname | ✓ | ✓ `(g)` | – | ✓ `(g)` | ✓ |
| `stock:read` | Baca saldo stok | ✓ | ✓ `(g)` | ✓ `(g)` | ✓ `(g)` | ✓ |
| `ledger:read` | Baca Stock Movement Ledger | ✓ | ✓ `(g)` | – | ✓ `(g)` | ✓ |
| `audit:read` | Baca Audit Log | ✓ | – | – | – | ✓ |

### 3.2 Aturan warehouse scoping `(g)`

1. **Operasi mutasi bertanda `(g)`:** Setiap aksi mutasi yang ditandai `(g)` pada
   Matriks 3.1 wajib memeriksa `ensure_warehouse_access` terhadap gudang bisnis yang
   relevan; bila pengguna (selain `Super Admin`) tidak ditugaskan ke gudang tersebut,
   request ditolak dengan `403 WAREHOUSE_NOT_ASSIGNED`:
   - `location:manage`: `warehouse_id` tempat lokasi berada.
   - `po:create`, `po:issue`, `po:cancel`, `po:close`: `warehouse_id` pada dokumen Purchase Order (`PO`).
   - `gr:manage`: `warehouse_id` pada dokumen PO/GR.
   - `transfer:create`, `transfer:approve`, `transfer:ship`: `source_warehouse_id`
     (gudang asal transfer).
   - `transfer:receive`: `destination_warehouse_id` (gudang tujuan transfer).
   - `opname:manage`, `opname:count`, `opname:approve`: `warehouse_id` pada sesi
     Stock Opname.
2. **Operasi baca bagi `Warehouse Staff`, `Warehouse Manager`, dan `Purchasing Staff` (`(g)`):** Seluruh data operasional yang muncul untuk ketiga peran ini wajib disesuaikan dengan gudang yang ditugaskan (`user_warehouses`) dan lokasi penyimpanan di dalam gudang tersebut:
   - **Gudang & Lokasi (`master:read` pada `warehouses` dan `storage_locations`):** Secara default, pembacaan daftar maupun detail gudang dan lokasi penyimpanan hanya mengembalikan gudang yang ditugaskan pada `user_warehouses` beserta lokasi di dalamnya; akses detail atau filter ke `warehouse_id` di luar penugasan ditolak dengan `403 WAREHOUSE_NOT_ASSIGNED`. Khusus saat memilih gudang dan lokasi tujuan untuk pembuatan Stock Transfer antar-gudang, endpoint daftar gudang dan lokasi menyediakan parameter query referensi tujuan transfer yang mengembalikan gudang dan lokasi aktif lintas gudang.
   - **Katalog Master Global (`master:read` pada `categories`, `uoms`, `items`, `suppliers`):** Tidak terikat pada gudang tertentu sehingga dapat dibaca lintas gudang oleh seluruh pemegang `master:read`.
   - **Dokumen, Saldo Stok, dan Buku Besar (`po:read`, `gr:read`, `opname:read`, `stock:read`, `ledger:read`):** Ketiga peran hanya dapat membaca PO, GR, Opname, saldo stok (per lokasi, per gudang, maupun ringkasan agregat `summary`), serta buku besar (`stock_movements`) pada gudang yang ditugaskan (`user_warehouses`). Permintaan dengan filter atau ID dokumen/gudang di luar penugasan ditolak dengan `403 WAREHOUSE_NOT_ASSIGNED`.
   - **Transfer Stok (`transfer:read`):** Pengguna ber-scope `(g)` dapat membaca dokumen Transfer apabila ditugaskan pada `source_warehouse_id` **atau** `destination_warehouse_id`.
   - **Peran Lintas Gudang:** Hanya `Super Admin` dan `Auditor` yang membaca seluruh gudang, lokasi, stok, buku besar, dan dokumen tanpa batasan `user_warehouses`.

### 3.3 Aktor dan permission tambahan Fase 2 (M9 — Multi-Tenant SaaS)

Pada Fase 2 (M9), sistem memisahkan secara tegas antara **konteks Platform (`scope: "platform"`)** dan **konteks Tenant (`scope: "tenant"`)**:

1. **`Platform Admin` (Tabel `platform_admins`, `tenant_id = null`, `scope = "platform"`):**
   - Mengelola penyediaan (*provisioning*) tenant baru (`POST /api/v1/platform/tenants`), daftar & detail tenant, perubahan status langganan (`activate`, `suspend`, `deactivate`), serta perubahan paket kuota (`plans`).
   - Memiliki permission khusus platform: `platform:tenants:manage` dan `platform:tenants:read`.
   - Token `Platform Admin` **ditolak** pada seluruh endpoint operasional tenant (`PERMISSION_DENIED`), dan sebaliknya token pengguna tenant **ditolak** pada seluruh endpoint `/api/v1/platform/*`.
2. **Perluasan Permission `Super Admin` Tenant (`scope = "tenant"`):**
   - Selain 24 permission pada Matriks 3.1 di dalam cakupan `tenant_id`-nya sendiri, `Super Admin` tenant pada Fase 2 mendapatkan `tenant:manage` (melihat/memperbarui profil organisasi tenant & melihat pemakaian kuota) serta `settings:manage` dan `settings:read` (mengelola konfigurasi level tenant dan override level gudang di modul `CFG`).

## 4. Arsitektur modular

### 4.1 Module registry

| ID | Modul | Tanggung jawab | Status |
| --- | --- | --- | --- |
| PLT | Platform | Numbering, pagination, error format, request ID, health, migration convention, dan konteks `current_tenant` (M9) | MVP (Fase 1) + Ekstensi M9 |
| IAM | Identity dan Akses | Authentication, RBAC, user, scope, menu, serta login ber-`slug` tenant (M9) | MVP (Fase 1) + Ekstensi M9 |
| AUD | Audit | Append-only audit events dan read/filter (terisolasi per tenant pada M9) | MVP (Fase 1) + Ekstensi M9 |
| MST | Master Data | Category, UoM, item, supplier | MVP (Fase 1) + Ekstensi M9 |
| WHS | Gudang dan Lokasi | Warehouse, setting negative stock, location | MVP (Fase 1) + Ekstensi M9 |
| INV | Inventory | Balance, ledger, movement gateway, stock views | MVP (Fase 1) + Ekstensi M9 |
| PUR | Purchase Order | PO lifecycle dan fulfillment | MVP (Fase 1) + Ekstensi M9 |
| RCV | Goods Receipt | GR lifecycle dan atomic posting | MVP (Fase 1) + Ekstensi M9 |
| TRF | Transfer Stok | Transfer lifecycle, variance, in-transit | MVP (Fase 1) + Ekstensi M9 |
| OPN | Stock Opname | Snapshot, freeze, count, approval, adjustment | MVP (Fase 1) + Ekstensi M9 |
| TNT | Tenant | Provisioning tenant, siklus hidup (`TRIAL`/`ACTIVE`/`SUSPENDED`/`DEACTIVATED`), paket kuota (`plans`), dan `Platform Admin` | Phase 2 (M9 — Approved) |
| CFG | Konfigurasi | Registri pengaturan dan pewarisan nilai (`warehouse -> tenant -> platform default`) | Phase 2 (M9 — Approved) |

### 4.2 Dependency graph

```text
Fase 1 (MVP M0–M8):
PLT -> IAM -> MST/WHS -> INV -> PUR/RCV
                         INV -> TRF
                         INV -> OPN

Fase 2 (M9 Multi-Tenant SaaS):
PLT -> TNT -> IAM -> CFG -> MST/WHS -> INV -> (PUR/RCV, TRF, OPN)
AUD dipanggil oleh setiap modul yang mengubah data.
```

Write ownership tidak boleh membentuk siklus. Read dependency hanya melalui
contract owner. Saldo dan ledger hanya boleh ditulis oleh INV melalui
`apply_movement`; PO fulfillment hanya boleh diperbarui melalui contract PUR.

### 4.3 Contract register

Contract berikut adalah batas publik antar modul. Consumer tidak boleh menulis
data milik owner secara langsung atau membuat implementasi duplikat dari contract.
Perubahan signature, perilaku, atau kode error contract harus memperbarui
requirement owner, consumer, RTM, dan test terkait.

| Contract | Owner | Consumer | Operasi yang dijamin | Batas ownership |
|---|---|---|---|---|
| `authorize` | IAM | Semua route terlindungi | Memverifikasi user aktif, role, dan permission dari database pada setiap request | IAM tidak menentukan validasi bisnis dokumen |
| `ensure_warehouse_access` | IAM | PUR, RCV, TRF, OPN, WHS, INV | Memverifikasi assignment user terhadap warehouse yang menjadi scope aksi | Modul consumer tetap menentukan warehouse bisnis yang harus diperiksa |
| `record` | AUD | Semua modul yang mengubah data | Menulis audit event dalam transaksi perubahan | AUD tidak menentukan validitas aksi atau mengubah data owner |
| `next_number` | PLT | PUR, RCV, TRF, OPN | Menghasilkan nomor unik per tipe dan periode secara atomik (per tenant pada M9) | Consumer tidak membuat nomor dokumen sendiri |
| `apply_movement` | INV | RCV, TRF, OPN | Mengunci balance, memvalidasi negative stock/freeze, mengubah balance, dan menulis ledger | Consumer tidak boleh update `inventory_balances` atau `stock_movements` |
| `apply_receipt` | PUR | RCV | Menghitung ulang dan memperbarui `qty_received` serta fulfillment PO setelah lock PO | RCV tidak mengubah PO atau fulfillment secara langsung |
| `is_location_frozen` | OPN | INV, RCV, TRF | Mengembalikan status freeze lokasi berdasarkan sesi opname aktif | INV menjadi enforcement point untuk movement; adjustment opname dikecualikan sesuai BR-GLB-014 |
| `validate_location` | WHS | INV, RCV, TRF, OPN | Memastikan lokasi aktif dan dimiliki warehouse yang direferensikan | Consumer tidak mengganti ownership location dengan pemeriksaan lokal |
| `gr_status_summary` | RCV | PUR | Mengembalikan ringkasan GR draft/posted yang diperlukan untuk aturan cancel/close PO | PUR tidak membaca tabel GR secara langsung |
| `in_transit` | TRF | INV | Mengembalikan kuantitas transfer yang sudah shipped dan belum received | INV tidak menghitung ulang status transfer dari tabel TRF |
| `current_tenant` *(M9)* | PLT / IAM | Semua modul tenant | Mengembalikan `tenant_id` aktif yang terverifikasi serta mengatur/me-reset sesi RLS `app.current_tenant_id` | Consumer tidak boleh menerima `tenant_id` dari payload body/query klien |
| `ensure_tenant_active` *(M9)* | TNT | IAM & semua route tenant | Memverifikasi tenant berstatus `TRIAL` atau `ACTIVE` (`TENANT_SUSPENDED` bila ditangguhkan/nonaktif) | Modul bisnis tidak mengimplementasikan pengecekan status tenant sendiri |
| `check_quota` *(M9)* | TNT | WHS, IAM, MST | Mengunci baris `tenants` (`FOR UPDATE`) dan memverifikasi batas `max_warehouses`, `max_active_users`, `max_active_items` (`QUOTA_EXCEEDED` bila penuh) | Consumer tidak membaca tabel `plans` secara langsung |
| `get_setting` *(M9)* | CFG | WHS, INV, PUR, RCV, TRF, OPN | Meresolusi nilai konfigurasi efektif dengan urutan `warehouse override -> tenant setting -> platform default` | Consumer tidak membaca tabel `settings` secara langsung |

Semua contract dipanggil di dalam transaksi use case pemanggil. Contract yang
menghasilkan perubahan data mengikuti lock ordering dan invariant owner. Kegagalan
contract menggagalkan transaksi pemanggil secara keseluruhan; tidak boleh ada
success-shaped fallback atau perubahan sebagian.

## 5. Aturan bisnis global

| ID | Aturan |
| --- | --- |
| BR-GLB-001 | Setiap perubahan saldo harus melewati `apply_movement` dan menghasilkan ledger row. |
| BR-GLB-002 | `stock_movements` dan `audit_logs` append-only; tidak ada update/delete/truncate oleh role aplikasi. |
| BR-GLB-003 | Satu aksi bisnis mencakup status, saldo, ledger, dan audit dalam satu transaksi atomik. |
| BR-GLB-004 | Status hanya berubah melalui action endpoint dan transisi yang terdaftar. |
| BR-GLB-005 | Quantity memakai Decimal dan precision `NUMERIC(18,4)`; JSON memakai string desimal, tanpa float. |
| BR-GLB-006 | Tidak ada hard delete pada master atau dokumen; gunakan deactivate atau status final. |
| BR-GLB-007 | Warehouse scoping diperiksa pada warehouse bisnis yang relevan; pelanggaran memakai `WAREHOUSE_NOT_ASSIGNED`. |
| BR-GLB-008 | Lokasi aktif harus dimiliki warehouse yang direferensikan; mismatch memakai `INVALID_LOCATION`. |
| BR-GLB-009 | Semua SQL berparameter; nama sorting hanya dari whitelist. |
| BR-GLB-010 | Role dan status aktif user diverifikasi dari database pada setiap request. |
| BR-GLB-011 | Lock ordering: dokumen, PO terkait, lokasi terurut id, lalu balance terurut `(warehouse_id, location_id, item_id)`. |
| BR-GLB-012 | Baris balance dibuat dengan `INSERT ... ON CONFLICT DO NOTHING` sebelum `FOR UPDATE`. |
| BR-GLB-013 | Movement type MVP hanya `IN_PURCHASE`, `OUT_TRANSFER`, `IN_TRANSFER`, `ADJUSTMENT_PLUS`, `ADJUSTMENT_MINUS`. |
| BR-GLB-014 | Lokasi opname `IN_PROGRESS` atau `WAITING_APPROVAL` menolak GR, transfer ship, dan transfer receive; adjustment opname dikecualikan. |
| BR-GLB-015 | Perubahan status hanya boleh dilakukan melalui action endpoint yang terdaftar pada matriks transisi. Endpoint update status generik tidak disediakan. |
| BR-GLB-016 | Status terminal tidak dapat berpindah ke status lain dan tidak dapat dibatalkan atau dibuka kembali. Koreksi dilakukan melalui transaksi atau dokumen baru yang diizinkan. |
| BR-GLB-017 | Action yang diulang setelah berhasil harus idempotent secara bisnis: tidak boleh menggandakan saldo, ledger, fulfillment, atau audit event. Request bersamaan yang kalah mendapat error transisi atau konflik yang sesuai. |
| BR-GLB-018 | Setiap transisi invalid ditolak tanpa perubahan data dan menggunakan kode error katalog `INVALID_STATE_TRANSITION`, kecuali kondisi memiliki kode error yang lebih spesifik. |
| BR-GLB-019 | *(Fase 2 — M9)* Setiap tabel bisnis operasional wajib memiliki `tenant_id NOT NULL`, *Composite FK* `(tenant_id, <fk>_id)` untuk seluruh relasi intra-tenant, serta kebijakan PostgreSQL `ENABLE` dan `FORCE ROW LEVEL SECURITY`. |
| BR-GLB-020 | *(Fase 2 — M9)* Satu akun `users` terikat ketat ke tepat satu `tenant_id`; `Platform Admin` dikelola pada tabel terpisah `platform_admins` (`scope: "platform"`, `tenant_id: null`) dan tidak boleh menggunakan token platform untuk memanggil endpoint operasional tenant. |
| BR-GLB-021 | *(Fase 2 — M9)* Keunikan kode master (`categories`, `uoms`, `suppliers`, `items.sku`), `warehouses.code`, `users.username`, `users.email`, `roles.name`, `menus.code`, nomor dokumen (`PO`, `GR`, `TRF`, `OPN`), dan `document_sequences` berlaku per tenant `(tenant_id, ...)`. |
| BR-GLB-022 | *(Fase 2 — M9)* Perubahan status tenant menjadi `SUSPENDED` atau `DEACTIVATED` mencabut seluruh sesi aktif tenant tersebut dan segera menolak setiap request operasional tenant dengan `403 TENANT_SUSPENDED`. |
| BR-MST-001 | Import massal hanya membuat item baru; import tidak memperbarui item yang sudah ada dan tidak membuat saldo stok. |
| BR-MST-002 | Validasi item impor mengikuti validasi pembuatan item tunggal. `sku` menjadi satu-satunya kode barang, unik case-insensitive; kategori dan UoM harus ditemukan serta aktif. |
| BR-MST-003 | SKU duplikat dalam file, di database, atau akibat request bersamaan membuat baris terkait gagal dengan `DUPLICATE`; baris valid lainnya tetap dapat diimpor. |
| BR-MST-004 | Semua baris yang berhasil dibuat dan audit event-nya commit dalam satu transaksi impor. Kesalahan infrastruktur membatalkan seluruh perubahan transaksi; kesalahan validasi per baris tidak membatalkan baris valid lain. |
| BR-MST-005 | Hasil impor memberi nomor baris sumber, kolom, kode error katalog, dan alasan aman untuk setiap kesalahan validasi. |

## 6. Spesifikasi modul

Setiap tabel di bawah memakai format: fitur, requirement, business rules, workflow,
data, permission, dependency, dan acceptance criteria.

### 6.1 PLT, Platform

**Fitur dan requirement**

| Feature ID | Requirement ID | Kebutuhan | Priority |
| --- | --- | --- | --- |
| PLT-F01 | FR-PLT-001 | Nomor dokumen atomik per tipe dan bulan | MVP |
| PLT-F02 | FR-PLT-002 | List resource mendukung pagination, filtering, sorting aman | MVP |
| PLT-F03 | FR-PLT-003 | Error domain diterjemahkan ke format konsisten | MVP |
| PLT-F04 | FR-PLT-004 | Request ID, structured log, dan health endpoint tersedia | MVP |
| PLT-F05 | FR-PLT-005 | Migrasi SQL berurutan dan forward-only | MVP |

**Business rules dan workflow:** prefix dokumen harus terdaftar (`PO`, `GR`, `TRF`,
dan `OPN`); sequence diambil secara atomik per tipe dan periode `YYYYMM` melalui
contract `next_number`; endpoint list menegakkan batas `limit`/`offset`, filter,
pencarian, whitelist kolom sort (`BR-GLB-009`), serta serialisasi kuantitas sebagai
string desimal `NUMERIC(18,4)` (`BR-GLB-005`); error domain dan validasi diterjemahkan
ke envelope standar tanpa membocorkan detail internal; `X-Request-ID` yang valid
dipertahankan atau dibuat server bila tidak dikirim/tidak aman; health endpoint
tersedia tanpa autentikasi; migrasi yang telah diterapkan bersifat forward-only dan
tidak diedit.

**Data, permission, dependency:** `document_sequences` dan `schema_migrations`
dimiliki PLT. Tidak memiliki permission bisnis. Dipakai semua modul.

**Acceptance:** `AC-15` numbering atomik tidak menghasilkan nomor ganda pada request
bersamaan; `AC-16` perilaku query list konsisten untuk pagination, filter, pencarian,
sort whitelist, dan format kuantitas desimal; `AC-17` format error, korelasi
`X-Request-ID`, dan health endpoint mengikuti kontrak global; `AC-18` migration runner
berjalan berurutan, idempotent, dan forward-only.

### 6.2 IAM, Identity dan Akses

**Fitur dan requirement**

| Feature ID | Requirement ID | Kebutuhan | Priority |
| --- | --- | --- | --- |
| IAM-F01 | FR-IAM-001 | Login menerbitkan access token 15 menit dan refresh token 7 hari | MVP |
| IAM-F02 | FR-IAM-002 | Refresh token di-hash, dirotasi, dan reuse dideteksi | MVP |
| IAM-F03 | FR-IAM-003 | Logout mencabut token; password change/deactivate mencabut semua sesi | MVP |
| IAM-F04 | FR-IAM-004 | Lima login gagal berturut-turut mengunci akun 15 menit | MVP |
| IAM-F05 | FR-IAM-005 | RBAC dan permission diverifikasi setiap request | MVP |
| IAM-F06 | FR-IAM-006 | User, role, permission dapat dikelola sesuai permission | MVP |
| IAM-F07 | FR-IAM-007 | User dapat ditugaskan ke warehouse | MVP |
| IAM-F08 | FR-IAM-008 | Menu aktif dikembalikan sesuai permission | MVP |
| IAM-F09 | FR-IAM-009 | User dapat melihat profil dan mengganti password sendiri | MVP |

**Business rules dan workflow:** access token JWT HS256 memuat `sub`, `jti`, `iat`,
`exp`; password di-hash Argon2id (`argon2-cffi`) minimal 8 karakter; user aktif dan
permission dibaca dari database; endpoint login/refresh/health dikecualikan dari
auth; menu parent tanpa permission hanya muncul bila child terlihat; tidak ada hard
delete menu.

**Data, permission, dependency:** `users`, `roles`, `permissions`,
`role_permissions`, `user_warehouses`, `refresh_tokens`, `menus`. Memakai
`user:manage` untuk administrasi. Membaca WHS dan dipakai semua modul.

**Acceptance:** `AC-05` unauthorized action ditolak; `AC-11` refresh rotation dan
reuse ditangani; `AC-12` warehouse scoping ditegakkan; `AC-14` menu tersaring.

### 6.3 AUD, Audit

**Fitur dan requirement**

| Feature ID | Requirement ID | Kebutuhan | Priority |
| --- | --- | --- | --- |
| AUD-F01 | FR-AUD-001 | Perubahan data penting dan event auth dicatat otomatis | MVP |
| AUD-F02 | FR-AUD-002 | Audit log dapat dibaca dan difilter oleh role berwenang | MVP |

**Business rules dan workflow:** event ditulis melalui contract `record` dalam
transaksi perubahan yang sama; memuat actor (`user_id`), `action`, `entity_type`,
`entity_id`, `old_values`/`new_values`, `ip_address`, dan `created_at`; password,
hash, dan token disanitasi serta tidak boleh masuk log atau payload audit; audit log
bersifat append-only tanpa update/delete endpoint dan hanya dapat dibaca/difilter oleh
pemegang `audit:read`.

**Data, permission, dependency:** `audit_logs`; `audit:read`; dipanggil semua
modul melalui `record`.

**Acceptance:** `AC-08` role aplikasi tidak dapat mengubah/menghapus ledger maupun
audit; `AC-05` perubahan sah menghasilkan audit event; `AC-07` rollback menghapus
event yang berasal dari transaksi gagal; `AC-22` kelengkapan atribut audit, sanitasi
field sensitif, serta pembatasan akses dan pemfilteran pembacaan audit log; `AC-16`
pagination dan sorting daftar audit log.

### 6.4 MST, Master Data

| Feature ID | Requirement ID | Kebutuhan | Priority |
| --- | --- | --- | --- |
| MST-F01 | FR-MST-001 | CRUD/soft deactivate kategori | MVP |
| MST-F02 | FR-MST-002 | UoM dengan `allow_decimal` | MVP |
| MST-F03 | FR-MST-003 | Item dengan SKU unik dan satu base UoM | MVP |
| MST-F04 | FR-MST-004 | Supplier | MVP |
| MST-F05 | FR-MST-005 | Deactivation terkontrol tanpa hard delete | MVP |
| MST-F06 | FR-MST-006 | Import massal item dari template Excel dengan validasi per baris dan hasil parsial | MVP |
| MST-F07 | FR-MST-007 | Import massal supplier dari template Excel dengan validasi per baris dan hasil parsial | MVP |

**Business rules:** nama kategori, kode UoM, SKU item, dan kode supplier harus unik;
item wajib merujuk kategori dan base UoM yang aktif; kuantitas transaksi mengikuti
`allow_decimal` pada UoM; atribut `allow_decimal` tidak dapat diubah ke `false`
setelah UoM digunakan; `sku` dan base `uom_id` tidak dapat diubah setelah item dipakai
transaksi atau memiliki saldo; tidak ada hard delete (`BR-GLB-006`); kategori/UoM yang
dipakai item aktif, item yang memiliki saldo non-nol atau dokumen aktif, serta supplier
yang masih direferensikan PO non-final atau GR draft tidak dapat dinonaktifkan.

**Data, permission, dependency:** `categories`, `uoms`, `items`, `suppliers`;
`master:manage` dan `master:read`; dipakai INV, PUR, RCV, TRF, OPN.

**MST-F06 — Import massal item:** Pengguna dengan `master:manage` mengunduh
template `.xlsx` dan mengunggah satu workbook untuk membuat item baru. Template
memiliki sheet `Items` dan `Referensi`. Sheet `Items` memiliki kolom berurutan
`sku`, `name`, `description`, `category_name`, `uom_name`, `is_active`.
Sheet `Referensi` memiliki kolom `category_name`, `uom_name`, `uom_code` dan
berisi pilihan kategori serta UoM yang aktif saat template dibuat. Header ada
pada baris 1; data item dimulai pada baris 2. Kolom template dan validasinya:

| Header | Tipe sel Excel | Wajib | Validasi |
| --- | --- | --- | --- |
| `sku` | Teks | Ya | 1–64 karakter; unik tanpa membedakan kapitalisasi |
| `name` | Teks | Ya | 1–200 karakter |
| `description` | Teks | Tidak | Kosong menjadi `null` |
| `category_name` | Teks | Ya | Maksimal 120 karakter; harus cocok case-insensitive dengan kategori aktif |
| `uom_name` | Teks | Ya | Maksimal 60 karakter; harus cocok case-insensitive dengan tepat satu nama UoM aktif |
| `is_active` | Teks/Boolean | Tidak | Dropdown `active`/`inactive`, menerima boolean Excel; kosong menjadi `true` |

SKU disimpan sebagai teks agar karakter awal seperti nol tidak hilang. Header
harus tepat dan urut seperti tabel pada masing-masing sheet; kolom di luar
template ditolak. Sheet referensi merupakan snapshot untuk panduan dan dropdown,
bukan sumber kebenaran relasi. Baris kosong dilewati; nomor error mengacu pada
nomor baris workbook. Header atau struktur workbook yang tidak valid menolak
seluruh file sebelum penyimpanan.

Backend memvalidasi semua baris sebelum insert, mendeteksi SKU duplikat di file
dan database, mencocokkan `category_name` dan `uom_name` ke ID master saat ini,
serta mengembalikan ringkasan `total_rows`, `imported_count`,
`failed_count`, dan rincian kesalahan berisi nomor baris, field, kode, dan
pesan. `total_rows` menghitung baris data non-kosong; `imported_count` menghitung
item yang commit; `failed_count` menghitung baris yang memiliki satu atau lebih
error. Baris valid dibuat meskipun baris lain gagal. Insert item dan audit
`ITEM_CREATED` berada dalam satu transaksi; kegagalan infrastruktur me-rollback
semua insert request tersebut. Tidak ada upsert, perubahan item lama, saldo,
atau kategori/UoM baru. Referensi yang tidak ditemukan menghasilkan `NOT_FOUND`;
referensi tunggal yang nonaktif menghasilkan `INACTIVE_REFERENCE`; nama yang
cocok ke beberapa referensi menghasilkan error baris `VALIDATION_ERROR` dan
tidak dipilih otomatis. Karena database hanya menjamin keunikan kode UoM,
error ambiguitas UoM menyertakan kode kandidat. Validasi database menangani
duplikasi SKU konkuren.

Untuk membatasi pemakaian memori dan query database, backend memproses workbook
secara read-only, mengambil referensi dan SKU existing secara kelompok, dan
menyimpan item secara batch berparameter tanpa query lookup per baris. Batas
yang disetujui adalah 1.000 baris data dan ukuran file 5 MiB. Parser memakai
`openpyxl` untuk workbook `.xlsx` dan `python-multipart` untuk
`multipart/form-data`; kedua dependensi telah disetujui dan tercantum pada
konfigurasi proyek.

**API:** `GET /api/v1/items/import-template` (permission
`master:read`) membuat template dengan referensi aktif dan dropdown; `POST
/api/v1/items/import` (permission `master:manage`) menerima satu file
`multipart/form-data`. Backend selalu mencocokkan nilai referensi ke database
saat import, bukan mempercayai isi sheet `Referensi`. Berkas rusak,
header/sheet tidak cocok, atau batas file/baris terlampaui ditolak dengan
`422 VALIDATION_ERROR` tanpa penyimpanan. File valid diproses dengan respons
`200 OK`, termasuk bila hasilnya parsial. Rincian setiap baris menggunakan
kode yang sudah ada (`DUPLICATE`, `NOT_FOUND`, `INACTIVE_REFERENCE`,
`VALIDATION_ERROR`); tidak menambah kode error global.

**Frontend:** halaman Master Data Barang menampilkan unduh template dan unggah
file bagi pengguna berizin, status proses, ringkasan, serta tabel kesalahan
baris. UI menyediakan loading, empty, dan error state serta tidak menampilkan
baris berhasil sebelum respons backend diterima.

**MST-F07 — Import massal supplier:** Pengguna dengan `master:manage` mengunduh
template `.xlsx` dengan sheet `Suppliers` dan kolom berurutan `code`, `name`,
`contact_person`, `phone`, `email`, `address`, `is_active`. Batas dan validasi
mengikuti `SupplierCreate`: kode wajib 1–50 karakter dan format kode master;
nama wajib 1–150; kontak opsional maksimal 120; telepon opsional maksimal 30
dan harus mengikuti format telepon; email opsional maksimal 255 dan harus
sesuai format email; alamat opsional maksimal 1.000. Status menerima teks
`active`/`inactive` atau boolean Excel; nilai kosong menjadi aktif.

Backend mendeteksi kode supplier case-insensitive yang berulang di file,
database, atau request bersamaan. Semua baris dengan kode yang berulang di file
gagal sebagai `DUPLICATE`; baris valid lainnya tetap dapat diimpor. Kesalahan
validasi memuat nomor baris, field, kode error, dan pesan. Batasnya 1.000 baris
data dan 5 MiB. Insert batch serta satu event `SUPPLIER_CREATED` per supplier
berhasil berada dalam satu transaksi; kegagalan infrastruktur me-rollback semua
insert pada request tersebut.

**API:** `GET /api/v1/suppliers/import-template` dengan `master:read` mengunduh
template; `POST /api/v1/suppliers/import` dengan `master:manage` menerima satu
file `.xlsx` pada field `file` (`multipart/form-data`). Workbook rusak,
header/sheet salah, atau batas file/baris terlampaui ditolak dengan
`422 VALIDATION_ERROR`. File yang terbaca mengembalikan `200 OK` dengan
`total_rows`, `imported_count`, `failed_count`, dan `errors[]`, termasuk untuk
hasil parsial.

**Acceptance:** `AC-19` duplikasi dan referensi nonaktif ditolak, aturan
`allow_decimal` ditegakkan, perubahan SKU/UoM setelah item dipakai transaksi ditolak,
dan penonaktifan entitas yang masih direferensikan ditolak (`ENTITY_IN_USE`); `AC-16`
pencarian, filter, pagination, dan sort whitelist katalog master; `AC-30`
template dan impor massal memvalidasi baris, melaporkan hasil parsial dengan nomor
baris, dan mencatat audit untuk setiap item yang berhasil dibuat; `AC-31`
memastikan import supplier memvalidasi data master, mendeteksi kode duplikat,
melaporkan hasil parsial, dan mencatat audit secara atomik.

### 6.5 WHS, Gudang dan Lokasi

| Feature ID | Requirement ID | Kebutuhan | Priority |
| --- | --- | --- | --- |
| WHS-F01 | FR-WHS-001 | Warehouse dengan `allow_negative_stock` | MVP |
| WHS-F02 | FR-WHS-002 | Storage location dalam warehouse | MVP |
| WHS-F03 | FR-WHS-003 | Validasi location aktif dan ownership | MVP |

**Business rules:** kode warehouse unik; kode location unik di dalam warehouse;
pembuatan location mewajibkan warehouse aktif; contract `validate_location` memastikan
location aktif dan dimiliki oleh warehouse yang direferensikan (`BR-GLB-008`);
`allow_negative_stock` default `false`, hanya Super Admin (`warehouse:manage`) yang
mengubahnya, dan setiap perubahan wajib tercatat pada audit log; tidak boleh
menonaktifkan warehouse atau location yang masih memiliki saldo non-nol atau referensi
dokumen aktif; pembacaan daftar dan detail warehouse serta storage location bagi `Warehouse Staff`, `Warehouse Manager`, dan `Purchasing Staff` terfilter sesuai `user_warehouses` (dengan pengecualian parameter referensi tujuan Transfer saat memilih gudang/lokasi tujuan Stock Transfer).

**Data, permission, dependency:** `warehouses`, `storage_locations`;
`warehouse:manage`, `location:manage`, `master:read`; dipakai IAM, INV, PUR, RCV,
TRF, OPN.

**Acceptance:** `AC-20` duplikasi kode warehouse/location dan mismatch kepemilikan
location (`INVALID_LOCATION`) ditolak, penonaktifan dengan open reference atau saldo
non-nol ditolak (`ENTITY_IN_USE`), dan perubahan konfigurasi `allow_negative_stock`
diaudit; `AC-12` warehouse scoping pada pembacaan dan pengelolaan gudang/lokasi; `AC-16` pencarian, filter,
pagination, dan sort whitelist daftar warehouse/location.

### 6.6 INV, Inventory

| Feature ID | Requirement ID | Kebutuhan | Priority |
| --- | --- | --- | --- |
| INV-F01 | FR-INV-001 | Balance per warehouse/location/item | MVP |
| INV-F02 | FR-INV-002 | View per location, warehouse, aggregate, dan in-transit | MVP |
| INV-F03 | FR-INV-003 | Append-only movement ledger | MVP |
| INV-F04 | FR-INV-004 | `apply_movement` sebagai satu-satunya movement gateway | MVP |
| INV-F05 | FR-INV-005 | Negative stock sesuai konfigurasi warehouse | MVP |
| INV-F06 | FR-INV-006 | Frozen location enforcement | MVP |

**Business rules:** balance dibuat saat movement pertama; ledger menyimpan
`qty_before`, `qty_change`, `qty_after`, type, reference, actor, time; `qty_after`
harus sama dengan before plus change; negative stock ditolak dengan
`INSUFFICIENT_STOCK`; movement non-adjustment di lokasi beku ditolak
`LOCATION_FROZEN`; pembacaan view saldo (`balances`, `by-warehouse`, `summary`) dan `stock_movements` (`ledger`) bagi `Warehouse Staff`, `Warehouse Manager`, dan `Purchasing Staff` dibatasi pada gudang yang ditugaskan (`user_warehouses`).

**Data, permission, dependency:** `inventory_balances`, `stock_movements`;
`stock:read`, `ledger:read`; membaca MST/WHS/OPN/TRF dan dipicu RCV/TRF/OPN.

**Acceptance:** `AC-02` negative stock transfer ditolak; `AC-03` view saldo per
lokasi, gudang, agregat, dan `in_transit` konsisten; `AC-06` concurrency hanya
menghasilkan satu ship; `AC-08` append-only; `AC-12` warehouse scoping pada pembacaan stok dan ledger; `AC-13` lock ordering konsisten; `AC-16`
filter, pagination, sort whitelist, dan format kuantitas string desimal pada query
saldo serta movement ledger.

### 6.7 PUR, Purchase Order

| Feature ID | Requirement ID | Kebutuhan | Priority |
| --- | --- | --- | --- |
| PUR-F01 | FR-PUR-001 | PO header dan satu atau lebih PO lines | MVP |
| PUR-F02 | FR-PUR-002 | Draft, issue, cancel, close | MVP |
| PUR-F03 | FR-PUR-003 | `qty_received` dan fulfillment status otomatis | MVP |
| PUR-F04 | FR-PUR-004 | Contract `apply_receipt` untuk RCV | MVP |

**Business rules dan workflow:** PO draft hanya dapat diedit; issue butuh supplier,
warehouse aktif, item aktif, dan quantity positif; satu item satu kali per PO;
`PARTIALLY_RECEIVED` dan `RECEIVED` otomatis. PO `DRAFT` dapat dibatalkan oleh
pemegang `po:create` selama belum memiliki GR draft atau posted. PO `ISSUED` dapat
dibatalkan oleh pemegang `po:cancel` hanya bila belum memiliki GR draft atau posted.
PO `ISSUED` dan `PARTIALLY_RECEIVED` dapat ditutup melalui aksi close (`po:close`)
dengan alasan penutupan wajib (`closed_reason`) setelah tidak ada GR draft yang perlu
diselesaikan. PO `RECEIVED`, `CANCELLED`, dan `CLOSED` adalah terminal.

Setiap aksi pembuatan/pembaruan draft, issue, cancel, close, serta pembacaan PO wajib menegakkan warehouse scoping (`user_warehouses`) terhadap `warehouse_id` PO bagi `Purchasing Staff`, `Warehouse Manager`, dan `Warehouse Staff`. Setiap aksi issue, cancel, dan close mengubah status serta menulis audit dalam satu
transaksi. Perubahan fulfillment akibat posting GR dilakukan oleh contract PUR,
bukan oleh route atau modul RCV secara langsung.

**Data, permission, dependency:** `purchase_orders`, `po_lines`; PO permissions;
MST/WHS/PLT dependency, RCV consumer melalui contract `apply_receipt` dan
`gr_status_summary`.

**Acceptance:** `AC-01` partial lalu full receiving mengubah fulfillment; `AC-12` warehouse scoping pada pengelolaan dan pembacaan PO; `AC-21`
status transition invalid ditolak; `AC-16` pagination, filter, dan sort daftar PO.

### 6.8 RCV, Goods Receipt

| Feature ID | Requirement ID | Kebutuhan | Priority |
| --- | --- | --- | --- |
| RCV-F01 | FR-RCV-001 | GR dari PO yang eligible, beberapa GR per PO | MVP |
| RCV-F02 | FR-RCV-002 | Posting atomik ke stock, PO, ledger, audit | MVP |
| RCV-F03 | FR-RCV-003 | Cancel GR draft | MVP |
| RCV-F04 | FR-RCV-004 | Over-receipt prevention saat posting | MVP |

**Business rules dan workflow:** GR hanya dari PO `ISSUED`/`PARTIALLY_RECEIVED`;
warehouse sama dengan PO; setiap line menunjuk PO line dan location; draft tidak
mencadangkan quantity; posting mengunci header, PO, dan lines, menghitung ulang
over-receipt, lalu menjalankan movement dan `apply_receipt`; posted tidak dapat
dibalik. GR `DRAFT` dapat dibatalkan. GR `POSTED` dan `CANCELLED` adalah terminal.
Posting yang diulang atau dikirim bersamaan untuk GR yang sama hanya boleh
menghasilkan satu posting dan satu set side effect.

**Data, permission, dependency:** `goods_receipts`, `gr_lines`; `gr:manage`,
`gr:read`; memakai PLT, PUR, INV, WHS, AUD. RCV menggunakan
`next_number`, `validate_location`, `is_location_frozen`, `apply_movement`,
`apply_receipt`, dan `record`; RCV tidak menulis tabel owner tersebut secara
langsung.

**Acceptance:** `AC-01` over-receipt dan fulfillment; `AC-07` rollback total;
`AC-12` warehouse scope; `AC-13` concurrent posting; `AC-21` status transition
invalid ditolak; `AC-16` pagination, filter, dan sort daftar GR.

### 6.9 TRF, Transfer Stok

| Feature ID | Requirement ID | Kebutuhan | Priority |
| --- | --- | --- | --- |
| TRF-F01 | FR-TRF-001 | Transfer source/destination warehouse/location | MVP |
| TRF-F02 | FR-TRF-002 | Approval oleh Warehouse Manager source warehouse | MVP |
| TRF-F03 | FR-TRF-003 | Ship mengurangi saldo source | MVP |
| TRF-F04 | FR-TRF-004 | Receive final menambah saldo destination | MVP |
| TRF-F05 | FR-TRF-005 | In-transit view | MVP |

**Business rules dan workflow:** `DRAFT -> APPROVED -> SHIPPED -> RECEIVED`;
source/destination tidak boleh sama; satu item hanya boleh muncul satu kali per
dokumen Transfer; referensi gudang, lokasi, dan item harus aktif saat dokumen dibuat,
disetujui (`approve`), dikirim (`ship`), dan diterima (`receive`); ship memakai
`OUT_TRANSFER`; receive final memakai `IN_TRANSFER`; `qty_received <= qty`; variance
reason wajib bila kurang; selisih tidak kembali ke source dan tidak membuat ledger
tambahan. Transfer `DRAFT` dapat dibatalkan. Transfer `APPROVED` dapat dibatalkan
selama belum shipped. Transfer `SHIPPED`, `RECEIVED`, dan `CANCELLED` tidak dapat
dibatalkan atau dibuka kembali. Ship dan receive yang diulang tidak boleh menggandakan
movement atau saldo.

**Data, permission, dependency:** `stock_transfers`, `stock_transfer_lines`;
transfer permissions; memakai PLT, INV, WHS, AUD dan dibaca INV. TRF menggunakan
`next_number`, `validate_location`, `is_location_frozen`, `apply_movement`, dan
`record`; TRF tidak menulis saldo atau ledger secara langsung.

**Acceptance:** `AC-02`, `AC-03`, `AC-06`, `AC-09`, `AC-21` mencakup stock,
in-transit, variance, concurrency, scoping, dan penolakan transisi invalid; `AC-16`
pagination, filter, dan sort daftar Transfer.

### 6.10 OPN, Stock Opname

| Feature ID | Requirement ID | Kebutuhan | Priority |
| --- | --- | --- | --- |
| OPN-F01 | FR-OPN-001 | Sesi per warehouse atau location | MVP |
| OPN-F02 | FR-OPN-002 | Snapshot dan freeze saat mulai | MVP |
| OPN-F03 | FR-OPN-003 | Input physical count dan submit | MVP |
| OPN-F04 | FR-OPN-004 | Approve/reject dan adjustment | MVP |
| OPN-F05 | FR-OPN-005 | Opening balance melalui opname | MVP |
| OPN-F06 | FR-OPN-006 | `is_location_frozen` contract | MVP |

**Business rules dan workflow:** hanya satu sesi aktif pada lokasi; snapshot server
tidak editable; physical quantity >= 0; seluruh line harus diisi; reject wajib
alasan dan kembali ke `IN_PROGRESS`; approve menjalankan adjustment plus/minus
hanya untuk variance nonzero lalu langsung menyelesaikan sesi; freeze dilepas saat
complete/cancel. `REJECTED` bukan status tersimpan, melainkan hasil action yang
langsung mengembalikan sesi ke `IN_PROGRESS` dalam transaksi yang sama.
`COMPLETED` dan `CANCELLED` adalah status terminal. Adjustment hanya dapat terjadi
satu kali setelah seluruh line valid.

**Data, permission, dependency:** `stock_opnames`, `stock_opname_lines`;
opname permissions; memakai WHS, INV, PLT, AUD. OPN menggunakan
`next_number`, `validate_location`, `apply_movement`, dan `record`; adjustment
opname adalah satu-satunya pengecualian terhadap freeze movement sesuai
BR-GLB-014.

**Acceptance:** `AC-04` frozen location; `AC-10` adjustment dan opening balance;
`AC-21` invalid active-session transition.

### 6.11 TNT, Manajemen Tenant & Langganan (Phase 2 — M9)

| Feature ID | Requirement ID | Kebutuhan | Priority |
| --- | --- | --- | --- |
| TNT-F01 | FR-TNT-001 | Autentikasi `Platform Admin` terpisah (`POST /api/v1/platform/auth/login`) dengan JWT `scope: "platform"` | Phase 2 (M9) |
| TNT-F02 | FR-TNT-002 | Provisioning tenant baru secara atomik oleh `Platform Admin` (`POST /api/v1/platform/tenants`) | Phase 2 (M9) |
| TNT-F03 | FR-TNT-003 | Siklus hidup status tenant (`TRIAL`, `ACTIVE`, `SUSPENDED`, `DEACTIVATED`) dan blokir sesi otomatis | Phase 2 (M9) |
| TNT-F04 | FR-TNT-004 | Paket langganan (`plans`) dan penegakan batas kuota (`max_warehouses`, `max_active_users`, `max_active_items`) | Phase 2 (M9) |
| TNT-F05 | FR-TNT-005 | Profil organisasi tenant dan ringkasan pemakaian kuota bagi `Super Admin` tenant (`/api/v1/tenant/profile`) | Phase 2 (M9) |
| TNT-F06 | FR-TNT-006 | Isolasi konteks `current_tenant` (`PLT-F06`) dan login pengguna tenant ber-`slug` (`IAM-F10`) | Phase 2 (M9) |

**Business rules dan workflow:**
- `slug` tenant unik secara global (huruf kecil, angka, tanda hubung `^[a-z0-9][a-z0-9-]{1,62}$`) dan bersifat imutabel setelah dibuat;
- provisioning tenant baru oleh `Platform Admin` berjalan dalam satu transaksi yang: (1) membuat baris `tenants`, (2) menginisialisasi 5 role standar, pemetaan permission, menu bawaan, dan pengaturan default tenant, (3) membuat akun `Super Admin` pertama tenant, serta (4) mencatat audit log;
- siklus status tenant hanya melalui action endpoint platform: `TRIAL -> activate -> ACTIVE`, `TRIAL/ACTIVE -> suspend -> SUSPENDED` (alasan wajib), `SUSPENDED -> activate -> ACTIVE`, dan `TRIAL/ACTIVE/SUSPENDED -> deactivate -> DEACTIVATED` (terminal, alasan wajib);
- saat tenant di-`suspend` atau `deactivate`, seluruh `refresh_tokens` milik pengguna tenant tersebut dicabut dalam transaksi yang sama, dan setiap request ke endpoint operasional tenant ditolak dengan `403 TENANT_SUSPENDED`;
- pemeriksaan kuota (`check_quota`) mengunci baris `tenants` (`FOR UPDATE`) sebelum menambah/mengaktifkan gudang (`max_warehouses`), pengguna aktif (`max_active_users`), atau barang aktif (`max_active_items`); pelanggaran kuota ditolak dengan `409 QUOTA_EXCEEDED`; menurunkan paket ke batas di bawah jumlah entitas aktif yang sudah ada tidak menghapus data lama tetapi memblokir penambahan baru sampai penggunaan turun di bawah batas.

**Data, permission, dependency:** `plans`, `tenants`, `platform_admins`, `platform_refresh_tokens`; permission `platform:tenants:manage`, `platform:tenants:read`, `tenant:manage`; memakai `PLT` dan `AUD`, serta menyediakan contract `ensure_tenant_active` dan `check_quota` bagi `IAM`, `WHS`, dan `MST`.

**Acceptance:** `AC-23` isolasi RLS lintas tenant; `AC-24` siklus status tenant dan blokir `TENANT_SUSPENDED`; `AC-25` penegakan kuota konkuren (`QUOTA_EXCEEDED`); `AC-27` keunikan kode dan sequence nomor dokumen independen per tenant; `AC-28` pemisahan token `scope: "platform"` vs `scope: "tenant"`; `AC-29` provisioning tenant atomik.

### 6.12 CFG, Konfigurasi Tenant & Gudang (Phase 2 — M9)

| Feature ID | Requirement ID | Kebutuhan | Priority |
| --- | --- | --- | --- |
| CFG-F01 | FR-CFG-001 | Katalog kunci pengaturan resmi dengan validasi tipe data (`bool`, `int`, `string`, `decimal`) | Phase 2 (M9) |
| CFG-F02 | FR-CFG-002 | Pembacaan dan pembaruan pengaturan level tenant oleh `Super Admin` tenant | Phase 2 (M9) |
| CFG-F03 | FR-CFG-003 | Override pengaturan level gudang (`warehouse_id`) untuk kunci yang mengizinkan cakupan gudang | Phase 2 (M9) |
| CFG-F04 | FR-CFG-004 | Resolusi berjenjang `get_setting` (`warehouse override -> tenant setting -> platform default`) | Phase 2 (M9) |

**Business rules dan workflow:**
- hanya kunci pengaturan yang terdaftar pada katalog resmi yang dapat disimpan (antara lain: `inventory.allow_negative_stock_default`, `opname.require_variance_note`, `transfer.require_variance_reason`, `document.po_prefix`, `document.gr_prefix`, `document.trf_prefix`, `document.opn_prefix`, `ui.default_page_size`);
- pembaruan pengaturan memvalidasi tipe dan rentang nilai (`422 VALIDATION_ERROR` bila kunci tidak dikenal atau tipe tidak sesuai) serta mencatat perubahan ke `audit_logs` (`old_values`/`new_values`);
- untuk `warehouses.allow_negative_stock`, kolom pada tabel `warehouses` bertindak sebagai sumber eksekusi cepat saat mutasi stok (`apply_movement`), sementara `inventory.allow_negative_stock_default` di `CFG` menentukan nilai default saat gudang baru dibuat pada tenant tersebut.

**Data, permission, dependency:** `settings`; permission `settings:manage` dan `settings:read`; memakai `PLT`, `TNT`, `WHS`, dan `AUD`, serta menyediakan contract `get_setting`.

**Acceptance:** `AC-26` resolusi pewarisan konfigurasi (`default -> tenant -> warehouse`), validasi tipe kunci, dan pencatatan audit log.

## 7. Workflow end-to-end

### 7.1 Procurement sampai receiving

```text
MST/WHS setup -> PUR DRAFT -> PUR ISSUED
-> RCV DRAFT -> RCV POSTED
-> INV IN_PURCHASE + PUR fulfillment status
```

### 7.2 Transfer

```text
TRF DRAFT -> APPROVED -> SHIPPED
-> INV OUT_TRANSFER, source decreases, in-transit appears
-> RECEIVED -> INV IN_TRANSFER, destination increases
```

### 7.3 Stock opname

```text
OPN DRAFT -> IN_PROGRESS (snapshot + freeze)
-> count -> WAITING_APPROVAL
-> COMPLETED (approve + adjustment) or IN_PROGRESS (reject + reason)
```

### 7.4 Status registry

| Dokumen | Status |
| --- | --- |
| PO | `DRAFT`, `ISSUED`, `PARTIALLY_RECEIVED`, `RECEIVED`, `CANCELLED`, `CLOSED` |
| GR | `DRAFT`, `POSTED`, `CANCELLED` |
| Transfer | `DRAFT`, `APPROVED`, `SHIPPED`, `RECEIVED`, `CANCELLED` |
| Opname | `DRAFT`, `IN_PROGRESS`, `WAITING_APPROVAL`, `COMPLETED`, `CANCELLED` |

### 7.5 Matriks transisi status

Matriks ini adalah sumber normatif untuk status, action endpoint, kondisi,
permission, dan side effect. Perubahan status di luar matriks harus ditolak.

| Dokumen | Status awal | Action endpoint | Permission utama | Kondisi wajib | Status akhir | Side effect |
|---|---|---|---|---|---|---|
| PO | `DRAFT` | `issue` | `po:issue` | Supplier, warehouse, item, dan quantity valid | `ISSUED` | Audit |
| PO | `DRAFT` | `cancel` | `po:create` | Tidak ada GR draft atau posted | `CANCELLED` | Audit |
| PO | `ISSUED` | `cancel` | `po:cancel` | Tidak ada GR draft atau posted | `CANCELLED` | Audit |
| PO | `ISSUED` atau `PARTIALLY_RECEIVED` | `close` | `po:close` | Alasan close wajib (`closed_reason`); tidak ada GR draft yang perlu diselesaikan | `CLOSED` | Audit |
| GR | `DRAFT` | `post` | `gr:manage` | PO eligible, tidak over-receipt, lokasi tidak frozen | `POSTED` | Stock, ledger, PO fulfillment, audit |
| GR | `DRAFT` | `cancel` | `gr:manage` | GR belum posted | `CANCELLED` | Audit |
| Transfer | `DRAFT` | `approve` | `transfer:approve` | Source, destination, dan item aktif serta lokasi asal/tujuan berbeda | `APPROVED` | Audit |
| Transfer | `DRAFT` | `cancel` | `transfer:create` | Belum approved atau shipped | `CANCELLED` | Audit |
| Transfer | `APPROVED` | `ship` | `transfer:ship` | Stock cukup, lokasi source tidak frozen | `SHIPPED` | OUT_TRANSFER, source balance, ledger, audit |
| Transfer | `APPROVED` | `cancel` | `transfer:approve` | Belum shipped | `CANCELLED` | Audit |
| Transfer | `SHIPPED` | `receive` | `transfer:receive` | Quantity received valid, variance reason bila kurang, destination aktif dan tidak frozen | `RECEIVED` | IN_TRANSFER bila quantity diterima, destination balance, ledger, audit |
| Opname | `DRAFT` | `start` | `opname:manage` | Satu sesi aktif per lokasi, snapshot dapat dibuat | `IN_PROGRESS` | Snapshot, freeze, audit |
| Opname | `IN_PROGRESS` | `submit` | `opname:count` | Semua line diisi dan quantity valid | `WAITING_APPROVAL` | Audit |
| Opname | `WAITING_APPROVAL` | `approve` | `opname:approve` | Semua line valid | `COMPLETED` | Adjustment, ledger, audit, release freeze |
| Opname | `WAITING_APPROVAL` | `reject` | `opname:approve` | Alasan reject wajib | `IN_PROGRESS` | Audit |
| Opname | `DRAFT` atau `IN_PROGRESS` | `cancel` | `opname:manage` | Sesi belum completed | `CANCELLED` | Audit, release freeze bila aktif |

Status `RECEIVED`, `CLOSED`, `CANCELLED`, `POSTED`, dan `COMPLETED` adalah
terminal. Status `ISSUED`, `PARTIALLY_RECEIVED`, `APPROVED`, `SHIPPED`, dan
`WAITING_APPROVAL` hanya dapat berubah melalui baris matriks yang sesuai.

Setiap action harus mengunci dokumen dan entitas terkait sesuai BR-GLB-011,
memvalidasi status setelah lock, lalu menjalankan seluruh side effect dalam satu
transaksi. Retry setelah commit harus mengembalikan representasi hasil yang sama
atau error status yang terdokumentasi, tanpa menulis side effect kedua.

Transisi yang tidak memenuhi status awal atau kondisi wajib menggunakan
`INVALID_STATE_TRANSITION`. Kondisi yang lebih spesifik tetap menggunakan kode
yang sudah terdaftar, seperti `INSUFFICIENT_STOCK`, `LOCATION_FROZEN`,
`OVER_RECEIPT`, `WAREHOUSE_NOT_ASSIGNED`, atau `INVALID_LOCATION`.

## 8. Data requirements

### 8.1 Kepemilikan entitas konseptual per modul dan fitur

Setiap entitas data memiliki tepat satu modul pemilik (*write owner*). Modul lain
hanya boleh memodifikasi entitas tersebut melalui contract yang terdaftar pada
bagian 4.3.

| Entitas | Owner | Feature ID | Kunci bisnis / keunikan konseptual | Relationship utama | Aturan siklus hidup dan proteksi referensi |
| --- | --- | --- | --- | --- | --- |
| `document_sequences` | PLT | `PLT-F01` | `(doc_type, period)` | Mandiri; dipakai contract `next_number` | Bertambah secara atomik per tipe (`PO`, `GR`, `TRF`, `OPN`) dan periode `YYYYMM` |
| `schema_migrations` | PLT | `PLT-F05` | `version` | Mandiri | Append-only bagi runner migrasi; role aplikasi tidak memiliki hak tulis/ubah/hapus |
| `roles` | IAM | `IAM-F05`, `IAM-F06` | `name` | Memiliki banyak `users` dan `role_permissions` | Seeded untuk lima role MVP; role `Super Admin` tidak boleh kehilangan `user:manage` |
| `permissions` | IAM | `IAM-F05`, `IAM-F06` | `code` | Dipetakan ke `roles` melalui `role_permissions` | Katalog permission MVP bersifat tetap sesuai bagian 3.1 |
| `role_permissions` | IAM | `IAM-F05`, `IAM-F06` | `(role_id, permission_id)` | Menghubungkan `roles` dan `permissions` | Diperbarui dalam satu transaksi beserta pencatatan audit |
| `users` | IAM | `IAM-F01..F06`, `IAM-F09` | `username`, `email` | Mengacu ke satu `roles`; memiliki banyak `user_warehouses` dan `refresh_tokens` | Tidak ada hard delete (`is_active`); deaktivasi atau ganti password mencabut seluruh `refresh_tokens` aktif |
| `user_warehouses` | IAM | `IAM-F07` | `(user_id, warehouse_id)` | Menghubungkan `users` dengan `warehouses` (`WHS`) | Mengatur warehouse scoping `(g)`; diverifikasi dari database pada setiap request |
| `refresh_tokens` | IAM | `IAM-F01..F03` | `token_hash` | Mengacu ke `users` | Disimpan sebagai hash, dirotasi saat refresh, dan dicabut (`revoked_at`) saat logout atau deteksi reuse |
| `menus` | IAM | `IAM-F08` | `code` | Self-reference `parent_id -> menus`; opsional mengacu `permission_code` | Tidak ada hard delete (`is_active`); siklus hierarki parent ditolak |
| `audit_logs` | AUD | `AUD-F01`, `AUD-F02` | `id` (kronologis `created_at`) | Mengacu ke `users` (actor opsional untuk event gagal login) | Append-only (`BR-GLB-002`); bebas dari secret/password/hash/token |
| `categories` | MST | `MST-F01`, `MST-F05` | `name` (case-insensitive) | Direferensikan oleh `items` | Soft deactivate (`is_active`); tidak dapat dinonaktifkan bila masih dipakai `items` aktif (`ENTITY_IN_USE`) |
| `uoms` | MST | `MST-F02`, `MST-F05` | `code` (case-insensitive) | Direferensikan oleh `items` | Soft deactivate (`is_active`); `allow_decimal` tidak dapat diubah ke `false` setelah dipakai; tidak dapat dinonaktifkan bila dipakai `items` aktif (`ENTITY_IN_USE`) |
| `suppliers` | MST | `MST-F04`, `MST-F05` | `code` (case-insensitive) | Direferensikan oleh `purchase_orders` | Soft deactivate (`is_active`); tidak dapat dinonaktifkan bila masih direferensikan PO non-final atau GR draft (`ENTITY_IN_USE`) |
| `items` | MST | `MST-F03`, `MST-F05` | `sku` (case-insensitive) | Mengacu ke `categories` dan base `uoms` | `sku` dan `uom_id` imutabel setelah item dipakai transaksi/saldo; tidak dapat dinonaktifkan bila memiliki saldo non-nol atau dokumen non-final (`ENTITY_IN_USE`) |
| `warehouses` | WHS | `WHS-F01` | `code` (case-insensitive) | Memiliki banyak `storage_locations`; direferensikan oleh `user_warehouses`, saldo, dan dokumen | Menyimpan `allow_negative_stock`; tidak dapat dinonaktifkan bila masih memiliki saldo non-nol atau dokumen non-final (`ENTITY_IN_USE`) |
| `storage_locations` | WHS | `WHS-F02`, `WHS-F03` | `(warehouse_id, code)` dan pasangan komposit `(id, warehouse_id)` | Mengacu ke `warehouses` | Hanya dapat dibuat pada warehouse aktif; tidak dapat dinonaktifkan bila masih memiliki saldo non-nol atau referensi dokumen aktif (`ENTITY_IN_USE`) |
| `inventory_balances` | INV | `INV-F01`, `INV-F04`, `INV-F05` | `(warehouse_id, location_id, item_id)` | Mengacu komposit ke `storage_locations (id, warehouse_id)` dan ke `items` | Dibuat otomatis saat movement pertama (`BR-GLB-012`); hanya boleh diubah melalui `apply_movement` (`BR-GLB-001`) |
| `stock_movements` | INV | `INV-F03`, `INV-F04` | `id` (kronologis `created_at`) | Mengacu komposit ke `storage_locations (id, warehouse_id)`, `items`, dan `users` | Append-only (`BR-GLB-002`); wajib memenuhi `qty_after = qty_before + qty_change` dan lima `movement_type` resmi (`BR-GLB-013`) |
| `purchase_orders` | PUR | `PUR-F01..F04` | `po_number` | Mengacu ke `suppliers`, `warehouses`, dan `users`; memiliki banyak `po_lines` | Siklus status mengikuti matriks bagian 7.5; tidak ada hard delete |
| `po_lines` | PUR | `PUR-F01`, `PUR-F03`, `PUR-F04` | `(po_id, item_id)` | Mengacu ke `purchase_orders` dan `items` | `qty_ordered > 0`; `qty_received <= qty_ordered` hanya diperbarui melalui contract `apply_receipt` |
| `goods_receipts` | RCV | `RCV-F01..F04` | `gr_number` | Mengacu ke `purchase_orders`, `warehouses`, dan `users`; memiliki banyak `gr_lines` | `warehouse_id` wajib sama dengan `warehouse_id` pada PO; status terminal `POSTED`/`CANCELLED` |
| `gr_lines` | RCV | `RCV-F01`, `RCV-F02`, `RCV-F04` | `id` per baris penerimaan | Mengacu ke `goods_receipts`, `po_lines`, `items`, dan komposit ke `storage_locations (id, warehouse_id)` | `qty_received > 0`; tidak mencadangkan kuota PO saat masih `DRAFT` |
| `stock_transfers` | TRF | `TRF-F01..F05` | `transfer_number` | Mengacu komposit ke source `(source_warehouse_id, source_location_id)` dan destination `(destination_warehouse_id, destination_location_id)` | Pasangan lokasi asal dan tujuan tidak boleh identik; status mengikuti matriks bagian 7.5 |
| `stock_transfer_lines` | TRF | `TRF-F01`, `TRF-F04`, `TRF-F05` | `(transfer_id, item_id)` | Mengacu ke `stock_transfers` dan `items` | `qty > 0`; saat `RECEIVED`, `0 <= qty_received <= qty` dan `variance_reason` wajib bila `qty_received < qty` |
| `stock_opnames` | OPN | `OPN-F01..F06` | `opname_number`; maksimum satu sesi aktif (`IN_PROGRESS`/`WAITING_APPROVAL`) per cakupan lokasi | Mengacu ke `warehouses` dan opsional komposit ke `storage_locations (id, warehouse_id)` | Membekukan lokasi cakupan selama `IN_PROGRESS` dan `WAITING_APPROVAL` (`BR-GLB-014`) |
| `stock_opname_lines` | OPN | `OPN-F02..F05` | `(opname_id, location_id, item_id)` | Mengacu ke `stock_opnames`, komposit ke `storage_locations (id, warehouse_id)`, dan ke `items` | `qty_system` diambil dari snapshot server dan tidak dapat diedit; `qty_physical >= 0`; `qty_variance = qty_physical - qty_system` |

### 8.2 Peta relasi konseptual dan aturan integritas lintas modul

```text
[IAM: roles, permissions, users] ──(user_warehouses)──> [WHS: warehouses]
                                                               │
                                                  (id, warehouse_id) komposit
                                                               ▼
[MST: categories, uoms] ──> [MST: items] <────── [WHS: storage_locations]
                                 │                             │
      ┌──────────────────────────┼─────────────────────────────┼───────────────────────┐
      ▼                          ▼                             ▼                       ▼
[PUR: purchase_orders]    [INV: inventory_balances]     [TRF: stock_transfers]   [OPN: stock_opnames]
[PUR: po_lines]           [INV: stock_movements]        [TRF: transfer_lines]    [OPN: opname_lines]
      ▲
      │ (po_id, po_line_id, warehouse_id)
[RCV: goods_receipts, gr_lines]
```

Database dan service layer wajib menegakkan lima invariant relasi konseptual berikut:

1. **Konsistensi komposit lokasi–gudang (`BR-GLB-008`):** Setiap entitas yang
   menyimpan `warehouse_id` sekaligus `location_id` (`inventory_balances`,
   `stock_movements`, `gr_lines` melalui header GR, `stock_transfers`,
   `stock_opnames`, dan `stock_opname_lines`) wajib menjamin bahwa `location_id`
   benar-benar milik `warehouse_id` yang sama, baik melalui validasi contract
   `validate_location` maupun relasi komposit `(location_id, warehouse_id) -> storage_locations (id, warehouse_id)`.
2. **Kesesuaian referensi PO dan GR (`RCV-F01`, `RCV-F04`):** `goods_receipts.warehouse_id`
   harus sama dengan `purchase_orders.warehouse_id`, dan setiap `gr_lines.po_line_id`
   harus berasal dari `po_lines` milik `po_id` yang sama serta mengacu pada `item_id`
   yang identik.
3. **Proteksi penonaktifan terhadap referensi terbuka (`MST-F05`, `WHS-F01`, `WHS-F02`):**
   Entitas master atau lokasi tidak boleh dinonaktifkan (`ENTITY_IN_USE`) selama:
   - `categories` atau `uoms` masih direferensikan oleh `items` yang berstatus `is_active = true`;
   - `items`, `warehouses`, atau `storage_locations` masih memiliki `inventory_balances.qty_on_hand != 0` atau tercantum pada dokumen belum final (`PO` berstatus `DRAFT`/`ISSUED`/`PARTIALLY_RECEIVED`, `GR` berstatus `DRAFT`, `Transfer` berstatus `DRAFT`/`APPROVED`/`SHIPPED`, `Opname` berstatus `DRAFT`/`IN_PROGRESS`/`WAITING_APPROVAL`);
   - `suppliers` masih direferensikan oleh `PO` berstatus `DRAFT`/`ISSUED`/`PARTIALLY_RECEIVED` atau `GR` berstatus `DRAFT`.
4. **Ketergantungan aturan stok negatif pada konfigurasi gudang (`INV-F05`):**
   Database tidak memasang constraint statis `qty_on_hand >= 0` pada
   `inventory_balances` karena izin saldo negatif ditentukan per gudang oleh
   `warehouses.allow_negative_stock` dan ditegakkan setelah penguncian baris di dalam
   `apply_movement`.
5. **Pemisahan hak akses tabel append-only (`BR-GLB-002`, `PLT-F05`):**
   `stock_movements`, `audit_logs`, dan `schema_migrations` dilindungi pada level
   database agar role aplikasi tidak dapat melakukan `UPDATE`, `DELETE`, atau
   `TRUNCATE`. Detail DDL berada pada spesifikasi layer database.

### 8.3 Entitas tambahan dan aturan transisi skema Fase 2 (M9 — Multi-Tenant SaaS)

| Entitas (M9) | Owner | Feature ID | Kunci bisnis / keunikan konseptual | Relationship utama | Aturan siklus hidup dan proteksi |
| --- | --- | --- | --- | --- | --- |
| `plans` | TNT | `TNT-F04` | `code` (case-insensitive) | Direferensikan oleh `tenants` | Menyimpan batas kuota `max_warehouses`, `max_active_users`, `max_active_items`; paket default di-seed pada migrasi `012` |
| `tenants` | TNT | `TNT-F02..F05` | `slug` (global, imutabel) | Mengacu ke `plans`; menjadi induk `tenant_id` bagi seluruh tabel bisnis tenant | Siklus status `TRIAL`, `ACTIVE`, `SUSPENDED`, `DEACTIVATED`; tidak ada hard delete |
| `platform_admins` | TNT | `TNT-F01` | `username`, `email` | Memiliki banyak `platform_refresh_tokens` | Tabel level platform (tanpa `tenant_id`); terpisah dari `users` tenant |
| `platform_refresh_tokens` | TNT | `TNT-F01` | `token_hash` | Mengacu ke `platform_admins` | Rotasi dan pencabutan sesi khusus `Platform Admin` |
| `settings` | CFG | `CFG-F01..F04` | `(tenant_id, COALESCE(warehouse_id, 0), key)` | Mengacu ke `tenants` dan opsional komposit ke `warehouses (tenant_id, id)` | Hanya menyimpan kunci pengaturan terdaftar; perubahan diaudit |

Pada migrasi Fase 2 (`012_create_tenants_settings.sql` dan `013_add_tenant_scope.sql`), seluruh 21 tabel bisnis dari Fase 1 (`roles`, `role_permissions`, `users`, `user_warehouses`, `refresh_tokens`, `menus`, `audit_logs`, `document_sequences`, `categories`, `uoms`, `suppliers`, `items`, `warehouses`, `storage_locations`, `inventory_balances`, `stock_movements`, `purchase_orders`, `po_lines`, `goods_receipts`, `gr_lines`, `stock_transfers`, `stock_transfer_lines`, `stock_opnames`, `stock_opname_lines`) ditambahkan `tenant_id BIGINT NOT NULL REFERENCES tenants(id)` dengan tiga jaminan teknis wajib pada [DATABASE_DESIGN.md](DATABASE_DESIGN.md):
1. Penonaktifan sementara trigger imutabilitas `007` pada `stock_movements` dan `audit_logs` hanya selama transaksi migrasi `013` melakukan *backfill* `tenant_id` untuk tenant default, lalu diaktifkan kembali sebelum commit.
2. Pembuatan constraint `UNIQUE (tenant_id, id)` pada seluruh tabel induk sebelum memasang *Composite FK* `(tenant_id, <fk>_id)` agar lintas-referensi antar-tenant mustahil terjadi di level database.
3. Penggantian 14 constraint `UNIQUE`/`PK` global menjadi komposit berawalan `tenant_id`, disertai kebijakan PostgreSQL `ENABLE` & `FORCE ROW LEVEL SECURITY`.

## 9. Non-functional requirements

| ID | Requirement | Acceptance evidence |
| --- | --- | --- |
| NFR-001 | Transaksi atomik untuk status, stock, ledger, audit | AC-07 |
| NFR-002 | JWT HS256, password hash, secret environment-only, no secret in log | AC-05, AC-11, AC-22 |
| NFR-003 | Query list terindeks dan pagination; target p95 200 ms hanya setelah dataset/environment disepakati | AC-16, benchmark evidence (`CONF-007`) |
| NFR-004 | Decimal `NUMERIC(18,4)`, JSON decimal string | AC-16 |
| NFR-005 | PostgreSQL direct driver, no ORM, SQL repository-only, forward-only migration | AC-18, architecture checks |
| NFR-006 | Structured error, request ID, health, OpenAPI | AC-17, operational checks |
| NFR-007 | Test memakai PostgreSQL sungguhan; concurrency memakai koneksi terpisah | AC-06, AC-13, AC-15 |
| NFR-008 | Layer separation: route -> service -> repository -> core/database | Architecture review |

## 10. Acceptance criteria

| ID | Skenario | Owner | Status |
| --- | --- | --- | --- |
| AC-01 | GR parsial, over-receipt ditolak, full receipt mengubah PO | RCV | Mapped |
| AC-02 | Ship yang membuat stock negatif ditolak | TRF/INV | Mapped |
| AC-03 | Transfer ship/receive mengubah saldo dan in-transit sesuai tahap | TRF | Mapped |
| AC-04 | Lokasi opname menolak GR/transfer yang dilarang | OPN/INV | Mapped |
| AC-05 | Permission role dan audit event ditegakkan | IAM/AUD | Mapped |
| AC-06 | Dua ship bersamaan hanya satu yang berhasil | TRF/INV | Mapped |
| AC-07 | Kegagalan di tengah transaksi rollback total | RCV/AUD | Mapped |
| AC-08 | Ledger dan audit immutable pada role aplikasi | INV/AUD | Mapped |
| AC-09 | Transfer variance dan warehouse scope benar | TRF/IAM | Mapped |
| AC-10 | Opname approve menyelesaikan sesi dan menghasilkan adjustment serta opening balance | OPN/INV | Mapped |
| AC-11 | Refresh rotation, reuse revoke, logout revoke | IAM | Mapped |
| AC-12 | Penugasan gudang ditegakkan pada operasi dan pembacaan ber-scope gudang; akses di luar cakupan ditolak | IAM/WHS | Mapped |
| AC-13 | Dua posting GR yang sama tidak menggandakan stock/PO | RCV/PUR | Mapped |
| AC-14 | Menu hanya berisi node yang diizinkan | IAM | Mapped |
| AC-15 | Penomoran dokumen atomik per tipe dan periode menghasilkan nomor unik tanpa duplikasi pada request bersamaan | PLT | Mapped |
| AC-16 | Perilaku query list menegakkan pagination, filter, pencarian, sort whitelist, dan serialisasi kuantitas string desimal | PLT/INV | Mapped |
| AC-17 | Format error domain/validasi, korelasi `X-Request-ID`, dan kesiapan health endpoint konsisten dengan kontrak global | PLT | Mapped |
| AC-18 | Migration runner menerapkan migrasi SQL secara berurutan, idempotent, dan forward-only tanpa mengubah riwayat yang telah diterapkan | PLT | Mapped |
| AC-19 | Master data menolak duplikasi dan referensi nonaktif, menegakkan `allow_decimal`, memproteksi SKU/UoM setelah dipakai transaksi, dan menolak deactivate yang masih direferensikan | MST | Mapped |
| AC-20 | Warehouse dan storage location menegakkan keunikan kode, kepemilikan lokasi, audit perubahan `allow_negative_stock`, dan menolak deactivate saat masih memiliki saldo atau referensi aktif | WHS | Mapped |
| AC-21 | Semua invalid state transition ditolak tanpa perubahan data dan memakai error katalog | PUR/TRF/OPN/RCV | Mapped |
| AC-22 | Pencatatan dan pembacaan audit log memuat atribut wajib tanpa rahasia serta membatasi akses dan filter sesuai `audit:read` | AUD | Mapped |
| AC-23 | *(Fase 2 — M9)* Isolasi data lintas tenant & PostgreSQL RLS mencegah pembacaan, pengubahan, atau referensi silang antar-tenant, termasuk pembersihan konteks koneksi pool `autocommit=True` | PLT/TNT | Mapped (Phase 2 - M9) |
| AC-24 | *(Fase 2 — M9)* Siklus hidup status tenant (`TRIAL`, `ACTIVE`, `SUSPENDED`, `DEACTIVATED`) mencabut sesi dan menolak akses operasional tenant nonaktif (`TENANT_SUSPENDED`) | TNT/IAM | Mapped (Phase 2 - M9) |
| AC-25 | *(Fase 2 — M9)* Penegakan batas kuota paket (`max_warehouses`, `max_active_users`, `max_active_items`) secara atomik menolak pelanggaran kuota (`QUOTA_EXCEEDED`), termasuk pada request konkuren | TNT/WHS/IAM/MST | Mapped (Phase 2 - M9) |
| AC-26 | *(Fase 2 — M9)* Pewarisan konfigurasi (`CFG`) meresolusi nilai efektif `warehouse override -> tenant setting -> platform default`, memvalidasi tipe kunci, dan mencatat audit | CFG | Mapped (Phase 2 - M9) |
| AC-27 | *(Fase 2 — M9)* Keunikan kode master/SKU/username dan urutan nomor dokumen (`document_sequences`) bersifat independen antar-tenant | PLT/MST/WHS/IAM | Mapped (Phase 2 - M9) |
| AC-28 | *(Fase 2 — M9)* Pemisahan otorisasi `scope: "platform"` (`Platform Admin`) dan `scope: "tenant"` (`Tenant User`) menolak penggunaan token lintas cakupan | TNT/IAM | Mapped (Phase 2 - M9) |
| AC-29 | *(Fase 2 — M9)* Provisioning tenant baru oleh `Platform Admin` membuat tenant, role/menu/setting awal, dan `Super Admin` pertama secara atomik (rollback total bila gagal) | TNT/IAM/CFG | Mapped (Phase 2 - M9) |
| AC-30 | *(Tambahan Fase 1 — MST-F06)* Import item dari template Excel memvalidasi seluruh baris, mengimpor item valid saja, menangani SKU duplikat termasuk request konkuren, memberi ringkasan dan rincian error per baris, serta mencatat audit untuk item sukses secara atomik | MST/AUD | Mapped |
| AC-31 | *(Tambahan Fase 1 — MST-F07)* Import supplier dari template Excel memvalidasi seluruh baris, mengimpor supplier valid saja, menangani kode duplikat termasuk request konkuren, memberi ringkasan dan rincian error per baris, serta mencatat audit untuk supplier sukses secara atomik | MST/AUD | Mapped |

### 10.1 Spesifikasi acceptance criteria terpisah (numbering, query, platform, master, warehouse, dan audit)

Kriteria berikut bersifat normatif untuk menutup verifikasi fitur yang sebelumnya
hanya diuji secara tidak langsung melalui workflow dokumen lain.

| AC | Area dan fitur | Kondisi uji wajib | Hasil dan invariant yang harus terbukti | Error katalog saat dilanggar |
| --- | --- | --- | --- | --- |
| `AC-15` | Numbering (`PLT-F01`, contract `next_number`) | Pembuatan dokumen (`PO`, `GR`, `TRF`, `OPN`) secara berurutan maupun konkuren pada periode `YYYYMM` yang sama, lintas pergantian bulan, serta saat transaksi pemanggil gagal | Nomor mengikuti `{PREFIX}-{YYYYMM}-{NNNN}`, bertambah secara berurutan per tipe dan periode tanpa nomor ganda pada request bersamaan; rollback transaksi pemanggil tidak meninggalkan dokumen yatim | `VALIDATION_ERROR` bila prefix tidak terdaftar |
| `AC-16` | Query behavior (`PLT-F02`, `INV-F02`, `BR-GLB-005`, `BR-GLB-009`) | Request list pada master, warehouse/location, stok, ledger, dokumen, dan audit dengan kombinasi `limit`, `offset`, `search`, filter atribut, `sort_by`, dan `sort_dir` | Respons memuat `items`, `total`, `limit`, `offset` secara konsisten; filter mengikuti warehouse scope pengguna; seluruh kuantitas berupa string desimal `NUMERIC(18,4)` tanpa `float`; kolom `sort_by` di luar whitelist atau batas pagination tidak valid ditolak tanpa mengeksekusi SQL tidak aman | `VALIDATION_ERROR`, `WAREHOUSE_NOT_ASSIGNED` |
| `AC-17` | Platform error, Request ID, dan Health (`PLT-F03`, `PLT-F04`) | Pengiriman request dengan `X-Request-ID` valid, tanpa `X-Request-ID`, dengan `X-Request-ID` tidak aman/terlalu panjang, pemanggilan health endpoint, serta pemicuan error domain/validasi | Health endpoint merespons tanpa autentikasi; `X-Request-ID` valid dipertahankan dan nilai tidak valid diganti UUID baru pada header respons; setiap kegagalan menghasilkan `{ "error": { "code", "message", "details" } }` tanpa membocorkan SQL, stack trace, atau rahasia | Kode error katalog sesuai domain (`VALIDATION_ERROR`, `NOT_FOUND`, `PERMISSION_DENIED`, dll.) |
| `AC-18` | Migration runner (`PLT-F05`) | Eksekusi runner migrasi pada database kosong, eksekusi ulang ketika migrasi sudah tercatat di `schema_migrations`, serta percobaan modifikasi `schema_migrations` oleh role aplikasi | Migrasi diterapkan berurutan satu kali dan dicatat pada `schema_migrations`; eksekusi ulang bersifat idempotent (melewati migrasi yang sudah applied); kegagalan satu berkas membatalkan migrasi tersebut; role aplikasi (`wms_app`) tidak dapat mengubah riwayat migrasi | Kegagalan migrasi atau penolakan privilege database |
| `AC-19` | Master data (`MST-F01..F05`) | CRUD dan soft deactivate pada kategori, UoM, item, dan supplier; pembuatan item dengan kategori/UoM nonaktif; transaksi dengan UoM `allow_decimal = false` vs `true`; perubahan `sku`/`uom_id` atau `allow_decimal` setelah dipakai; penonaktifan entitas yang masih direferensikan | Duplikasi nama kategori, kode UoM, SKU item, atau kode supplier ditolak; referensi nonaktif ditolak; kuantitas pecahan pada UoM integer ditolak; `sku` dan `uom_id` dapat diubah sebelum bertransaksi tetapi ditolak setelah item memiliki transaksi/saldo; penonaktifan kategori/UoM yang dipakai item aktif, item bersaldo/berdokumen aktif, atau supplier dengan PO non-final ditolak tanpa hard delete | `DUPLICATE`, `INACTIVE_REFERENCE`, `VALIDATION_ERROR`, `ENTITY_IN_USE` |
| `AC-20` | Warehouse dan location (`WHS-F01..F03`, contract `validate_location`) | CRUD warehouse dan storage location; perubahan `allow_negative_stock` oleh Super Admin vs role lain; penggunaan location dari warehouse berbeda atau location nonaktif pada transaksi; penonaktifan warehouse/location yang masih memiliki saldo atau dokumen aktif | Kode warehouse unik global dan kode location unik per warehouse; perubahan `allow_negative_stock` hanya diizinkan bagi pemegang `warehouse:manage` dan menghasilkan audit log (`old_values`/`new_values`); location milik warehouse lain ditolak oleh `validate_location`; location/warehouse dengan saldo non-nol atau referensi dokumen terbuka tidak dapat dinonaktifkan | `DUPLICATE`, `INACTIVE_REFERENCE`, `INVALID_LOCATION`, `PERMISSION_DENIED`, `ENTITY_IN_USE` |
| `AC-22` | Audit log (`AUD-F01..F02`, contract `record`) | Eksekusi aksi perubahan data (master, warehouse, user/role/assignment/menu, status dokumen) dan autentikasi; pemeriksaan isi `old_values`/`new_values`; pembacaan dan pemfilteran daftar audit oleh `Auditor`/`Super Admin` vs role tanpa `audit:read` | Setiap perubahan yang commit mencatat baris `audit_logs` dengan `user_id`, `action`, `entity_type`, `entity_id`, `old_values`/`new_values`, `ip_address`, dan `created_at`; field sensitif (`password`, `hash`, `token`, secret) tidak pernah tersimpan di `old_values`/`new_values`; endpoint baca audit mendukung filter (`user_id`, `action`, `entity_type`, `entity_id`, rentang tanggal) dan menolak pengguna tanpa `audit:read` | `PERMISSION_DENIED`, `VALIDATION_ERROR` |
| `AC-30` | Import massal item (`MST-F06`, `FR-MST-006`) | Unduh template dengan referensi aktif; impor file valid; nama kategori/UoM tidak ditemukan, nonaktif, atau ambigu; SKU duplikat di file/database dan request bersamaan; baris wajib kosong/nilai terlalu panjang; file rusak, header/sheet salah, ukuran/row limit terlampaui; pengguna tanpa permission | Template `.xlsx` memiliki sheet `Items` dan `Referensi`, dropdown kategori/UoM, dan header sesuai kontrak. Baris kosong dilewati; setiap baris data valid dibuat; baris invalid tidak dibuat dan hasil memuat nomor baris, field, kode error, dan alasan. SKU duplikat dilaporkan `DUPLICATE`; nama referensi ambigu dilaporkan `VALIDATION_ERROR` tanpa pemilihan otomatis; baris valid lain tetap berhasil. Respons merangkum total, sukses, dan gagal sesuai hasil commit. Sheet referensi tidak dipercaya untuk relasi; backend mencocokkan ke database. File struktural tidak valid ditolak tanpa insert. Semua item sukses dan audit `ITEM_CREATED` berada di satu transaksi; kegagalan infrastruktur me-rollback semua item pada request. Pengguna tanpa `master:manage` ditolak. Batas file dan jumlah baris mengikuti nilai yang disetujui pada `CONF-010`. | `DUPLICATE`, `NOT_FOUND`, `INACTIVE_REFERENCE`, `VALIDATION_ERROR`, `PERMISSION_DENIED` |
| `AC-31` | Import massal supplier (`MST-F07`, `FR-MST-007`) | Unduh template; file supplier valid; kode berulang dalam file/database dan request konkuren; field wajib kosong, nilai melebihi batas, format kode/telepon/email salah; nilai `active`/`inactive` dan boolean; file rusak, sheet/header salah, batas file/baris terlampaui; pengguna tanpa permission | Template `.xlsx` memiliki satu sheet `Suppliers` dan header sesuai kontrak. Baris kosong dilewati; setiap supplier valid dibuat; baris invalid tidak dibuat dan hasil memuat nomor baris, field, kode, dan alasan. Semua baris dengan kode duplikat dalam file gagal sebagai `DUPLICATE`; konflik database/kongkuren ditandai per baris, supplier valid lain tetap berhasil. Email dinormalisasi ke huruf kecil; field opsional kosong menjadi `null`; status kosong menjadi aktif. Ringkasan menghitung total, sukses, gagal sesuai hasil commit. File struktural tidak valid ditolak tanpa insert. Semua supplier sukses dan audit `SUPPLIER_CREATED` berada dalam satu transaksi; kegagalan infrastruktur me-rollback seluruh insert request. Pengguna tanpa `master:manage` ditolak. Batas file/baris adalah 5 MiB/1.000. | `DUPLICATE`, `VALIDATION_ERROR`, `PERMISSION_DENIED` |

## 11. Requirement Traceability Matrix

### 11.1 Aturan status evidence

Setiap baris RTM memakai satu status berikut agar klaim kesiapan tidak tercampur
antara desain dan bukti verifikasi:

| Status | Arti dan syarat penggunaan |
| --- | --- |
| `Not Mapped` | Requirement belum dipetakan ke target database, backend, frontend, API, dan QA |
| `Mapped` | Requirement MVP telah memiliki target entitas database, modul backend, integrasi frontend, perilaku API, dan AC terkait |
| `In Development` | Implementasi sedang berlangsung pada layer target |
| `Implemented` | Kode dan migrasi pada layer target tersedia, tetapi belum seluruh bukti test AC dirujuk |
| `Tested` | Test otomatis untuk AC terkait tersedia dan lulus pada environment uji |
| `Verified` | Bukti implementasi dan hasil run QA lintas layer telah ditinjau dan disahkan untuk rilis |
| `Need Confirmation` | Requirement bergantung pada keputusan bisnis terbuka (`CONF-nnn`) dan tidak boleh diimplementasikan sebagai scope aktif |

Dokumen PRD General menggunakan `Mapped` untuk baseline MVP dan `Need Confirmation`
untuk kandidat masa depan; klaim `Implemented`, `Tested`, atau `Verified` dicatat
pada dokumen bukti layer dan laporan QA.

### 11.2 Matriks traceability requirement MVP

| Requirement ID | Feature ID | Database | Backend | Frontend | API | QA | Status |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `FR-PLT-001` | `PLT-F01` | `document_sequences` | numbering service (`next_number`) | tampilkan nomor dokumen read-only | pembuatan PO, GR, Transfer, Opname | `AC-15` | `Mapped` |
| `FR-PLT-002` | `PLT-F02` | indeks dan kolom filter/sort | pagination utility dan list services | kontrol pagination, search, filter, sort | query params list (`limit`, `offset`, `search`, `sort_by`, `sort_dir`) | `AC-16` | `Mapped` |
| `FR-PLT-003` | `PLT-F03` | n/a | `DomainError` dan exception handlers | penanganan pesan dan state error | envelope `{ "error": { "code", "message", "details" } }` | `AC-17`, `AC-21` | `Mapped` |
| `FR-PLT-004` | `PLT-F04` | n/a | request ID middleware, structured log, health route | pelacakan `X-Request-ID` pada klien | header `X-Request-ID` dan endpoint health | `AC-17` | `Mapped` |
| `FR-PLT-005` | `PLT-F05` | `schema_migrations` | migration runner | n/a | n/a | `AC-18` | `Mapped` |
| `FR-IAM-001` | `IAM-F01` | `users`, `refresh_tokens` | auth service (login) | halaman login dan inisialisasi sesi | endpoint login | `AC-11` | `Mapped` |
| `FR-IAM-002` | `IAM-F02` | `refresh_tokens` | auth service (refresh rotation & reuse detection) | interceptor refresh token | endpoint refresh token | `AC-11` | `Mapped` |
| `FR-IAM-003` | `IAM-F03` | `users`, `refresh_tokens` | auth service (logout & session revoke) | aksi logout dan pembersihan sesi | endpoint logout, change password, deactivate user | `AC-05`, `AC-11` | `Mapped` |
| `FR-IAM-004` | `IAM-F04` | `users` (`failed_login_attempts`, `locked_until`) | auth service (lockout guard) | pesan akun terkunci pada login | endpoint login | `AC-05`, `AC-11` | `Mapped` |
| `FR-IAM-005` | `IAM-F05` | `users`, `roles`, `permissions`, `role_permissions` | dependency `authorize` (`require_permission`) | route guard dan visibilitas aksi berdasar permission | seluruh endpoint terlindungi | `AC-05` | `Mapped` |
| `FR-IAM-006` | `IAM-F06` | `users`, `roles`, `permissions`, `role_permissions` | user service | layar manajemen user dan role/permission | CRUD user, daftar role, update permission role | `AC-05`, `AC-22` | `Mapped` |
| `FR-IAM-007` | `IAM-F07` | `user_warehouses`, `warehouses` | user service & access service (`ensure_warehouse_access`) | pengaturan assignment gudang dan filter gudang aktif | endpoint assignment warehouse user & aksi ber-scope `(g)` | `AC-09`, `AC-12` | `Mapped` |
| `FR-IAM-008` | `IAM-F08` | `menus`, `permissions`, `role_permissions` | menu service | navigasi sidebar dinamis dan admin menu | endpoint `my-menu` dan CRUD menu | `AC-14`, `AC-22` | `Mapped` |
| `FR-IAM-009` | `IAM-F09` | `users`, `refresh_tokens` | auth/user service (profil & ganti password) | halaman profil pengguna dan form ganti password | endpoint profil `me` dan ganti password sendiri | `AC-05`, `AC-11`, `AC-22` | `Mapped` |
| `FR-AUD-001` | `AUD-F01` | `audit_logs` | audit service (`record`) | n/a | seluruh endpoint mutasi data dan autentikasi penting | `AC-05`, `AC-07`, `AC-08`, `AC-22` | `Mapped` |
| `FR-AUD-002` | `AUD-F02` | `audit_logs` | audit service (read & filter) | layar penelusuran dan filter audit log | endpoint list dan filter audit log (`GET /api/v1/audit-logs`) | `AC-16`, `AC-22` | `Mapped` |
| `FR-MST-001` | `MST-F01` | `categories` | master service (category) | layar CRUD kategori | endpoint CRUD/list kategori | `AC-16`, `AC-19`, `AC-22` | `Mapped` |
| `FR-MST-002` | `MST-F02` | `uoms` | master service (UoM & validasi `allow_decimal`) | layar CRUD UoM dan format input kuantitas | endpoint CRUD/list UoM | `AC-16`, `AC-19`, `AC-22` | `Mapped` |
| `FR-MST-003` | `MST-F03` | `items`, `categories`, `uoms` | master service (item & proteksi SKU/UoM) | layar CRUD/katalog item | endpoint CRUD/list item dan item per kategori | `AC-16`, `AC-19`, `AC-22` | `Mapped` |
| `FR-MST-004` | `MST-F04` | `suppliers` | master service (supplier) | layar CRUD supplier | endpoint CRUD/list supplier | `AC-16`, `AC-19`, `AC-22` | `Mapped` |
| `FR-MST-005` | `MST-F05` | `categories`, `uoms`, `items`, `suppliers` | master service (open-reference guard & soft deactivate) | aksi aktivasi/deaktivasi master | endpoint update master (`is_active`) | `AC-19`, `AC-22` | `Mapped` |
| `FR-MST-006` | `MST-F06` | `items`, `categories`, `uoms`, `audit_logs` (tanpa tabel/kolom baru) | master import service dengan validasi baris, pemeriksaan SKU batch, insert batch, dan transaksi/audit | unduh template, unggah workbook, ringkasan dan daftar error per baris | `GET /api/v1/items/import-template`, `POST /api/v1/items/import` | `AC-30` | `Mapped` |
| `FR-MST-007` | `MST-F07` | `suppliers`, `audit_logs` (tanpa tabel/kolom baru) | master import service dengan validasi supplier, pemeriksaan kode batch, insert batch, dan transaksi/audit | unduh template, unggah workbook, ringkasan dan daftar error per baris | `GET /api/v1/suppliers/import-template`, `POST /api/v1/suppliers/import` | `AC-31` | `Mapped` |
| `FR-WHS-001` | `WHS-F01` | `warehouses` | warehouse service | layar CRUD gudang dan pengaturan `allow_negative_stock` | endpoint CRUD/list warehouse | `AC-02`, `AC-12`, `AC-16`, `AC-20`, `AC-22` | `Mapped` |
| `FR-WHS-002` | `WHS-F02` | `storage_locations`, `warehouses` | warehouse service | layar CRUD lokasi penyimpanan per gudang | endpoint CRUD/list storage location | `AC-12`, `AC-16`, `AC-20`, `AC-22` | `Mapped` |
| `FR-WHS-003` | `WHS-F03` | `storage_locations`, `warehouses` | warehouse service (`validate_location`) | pemilihan lokasi terfilter berdasarkan gudang | seluruh endpoint dokumen dan stok yang menerima `location_id` | `AC-20` | `Mapped` |
| `FR-INV-001` | `INV-F01` | `inventory_balances` | inventory/stock service | tabel saldo per lokasi/item | endpoint saldo per lokasi | `AC-01`, `AC-03`, `AC-12`, `AC-16` | `Mapped` |
| `FR-INV-002` | `INV-F02` | `inventory_balances`, `stock_transfers`, `stock_transfer_lines` | stock service & contract `in_transit` | tampilan stok per lokasi, per gudang, ringkasan, dan in-transit | endpoint stock balances, by-warehouse, dan summary | `AC-03`, `AC-12`, `AC-16` | `Mapped` |
| `FR-INV-003` | `INV-F03` | `stock_movements` | inventory/stock service | layar buku besar pergerakan stok (ledger) | endpoint list dan detail stock movements | `AC-08`, `AC-12`, `AC-16` | `Mapped` |
| `FR-INV-004` | `INV-F04` | `inventory_balances`, `stock_movements` | inventory service (`apply_movement`) | n/a | dipicu oleh action post GR, ship/receive Transfer, approve Opname | `AC-01`, `AC-03`, `AC-06`, `AC-07`, `AC-10`, `AC-13` | `Mapped` |
| `FR-INV-005` | `INV-F05` | `inventory_balances`, `warehouses` | inventory service (`apply_movement`) | tampilan peringatan stok tidak cukup | action ship Transfer dan approve Opname (`ADJUSTMENT_MINUS`) | `AC-02`, `AC-06` | `Mapped` |
| `FR-INV-006` | `INV-F06` | `stock_opnames` | inventory service (`apply_movement`) & contract `is_location_frozen` | indikator lokasi sedang dibekukan opname | action post GR, ship Transfer, receive Transfer | `AC-04`, `AC-10` | `Mapped` |
| `FR-PUR-001` | `PUR-F01` | `purchase_orders`, `po_lines` | PO service | form pembuatan/edit draft PO dan detail baris | endpoint create, update draft, get, dan list PO | `AC-01`, `AC-12`, `AC-15`, `AC-16` | `Mapped` |
| `FR-PUR-002` | `PUR-F02` | `purchase_orders` | PO service & contract `gr_status_summary` | tombol aksi issue, cancel, dan close PO | action endpoint `issue`, `cancel`, `close` PO | `AC-01`, `AC-12`, `AC-21`, `AC-22` | `Mapped` |
| `FR-PUR-003` | `PUR-F03` | `purchase_orders`, `po_lines` | PO service | indikator progres `qty_received` dan status PO | detail PO dan respons posting GR | `AC-01`, `AC-13` | `Mapped` |
| `FR-PUR-004` | `PUR-F04` | `purchase_orders`, `po_lines` | PO service (`apply_receipt`) | n/a | dipanggil secara internal saat action `post` GR | `AC-01`, `AC-07`, `AC-13` | `Mapped` |
| `FR-RCV-001` | `RCV-F01` | `goods_receipts`, `gr_lines` | GR service | form pembuatan/edit draft GR dari PO eligible | endpoint create, update draft, get, dan list GR | `AC-01`, `AC-12`, `AC-15`, `AC-16` | `Mapped` |
| `FR-RCV-002` | `RCV-F02` | `goods_receipts`, `gr_lines`, `po_lines`, `inventory_balances`, `stock_movements`, `audit_logs` | GR service (`post` atomik) | aksi post GR dan konfirmasi penerimaan | action endpoint `post` GR | `AC-01`, `AC-07`, `AC-12`, `AC-13`, `AC-21`, `AC-22` | `Mapped` |
| `FR-RCV-003` | `RCV-F03` | `goods_receipts` | GR service (`cancel`) | aksi batalkan GR draft | action endpoint `cancel` GR | `AC-12`, `AC-21`, `AC-22` | `Mapped` |
| `FR-RCV-004` | `RCV-F04` | `po_lines`, `goods_receipts`, `gr_lines` | GR service & contract `apply_receipt` | validasi sisa kuantitas PO pada form GR | action endpoint `post` GR (`OVER_RECEIPT`) | `AC-01`, `AC-13` | `Mapped` |
| `FR-TRF-001` | `TRF-F01` | `stock_transfers`, `stock_transfer_lines` | transfer service | form pembuatan/edit draft transfer antar lokasi/gudang | endpoint create, update draft, get, dan list transfer | `AC-03`, `AC-09`, `AC-12`, `AC-15`, `AC-16` | `Mapped` |
| `FR-TRF-002` | `TRF-F02` | `stock_transfers` | transfer service (`approve`, `cancel`) | aksi approve dan cancel transfer | action endpoint `approve` dan `cancel` transfer | `AC-03`, `AC-12`, `AC-21`, `AC-22` | `Mapped` |
| `FR-TRF-003` | `TRF-F03` | `stock_transfers`, `inventory_balances`, `stock_movements` | transfer service (`ship`) | aksi kirim (`ship`) transfer | action endpoint `ship` transfer | `AC-02`, `AC-03`, `AC-04`, `AC-06`, `AC-12`, `AC-21`, `AC-22` | `Mapped` |
| `FR-TRF-004` | `TRF-F04` | `stock_transfers`, `stock_transfer_lines`, `inventory_balances`, `stock_movements` | transfer service (`receive`) | form penerimaan transfer dan input `variance_reason` | action endpoint `receive` transfer | `AC-03`, `AC-04`, `AC-09`, `AC-12`, `AC-21`, `AC-22` | `Mapped` |
| `FR-TRF-005` | `TRF-F05` | `stock_transfers`, `stock_transfer_lines` | transfer service (`in_transit`) | tampilan stok in-transit menuju lokasi/gudang tujuan | endpoint stock views dan detail transfer `SHIPPED` | `AC-03`, `AC-16` | `Mapped` |
| `FR-OPN-001` | `OPN-F01` | `stock_opnames` | opname service | form pembuatan sesi opname per gudang/lokasi | endpoint create, update draft, get, dan list opname | `AC-10`, `AC-12`, `AC-15`, `AC-16` | `Mapped` |
| `FR-OPN-002` | `OPN-F02` | `stock_opnames`, `stock_opname_lines`, `inventory_balances` | opname service (`start`) | aksi mulai opname dan tampilan snapshot sistem | action endpoint `start` dan `cancel` opname | `AC-04`, `AC-10`, `AC-21`, `AC-22` | `Mapped` |
| `FR-OPN-003` | `OPN-F03` | `stock_opnames`, `stock_opname_lines` | opname service (`count`, `submit`) | layar input hasil hitung fisik dan submit | endpoint input count line dan action `submit` opname | `AC-10`, `AC-12`, `AC-21`, `AC-22` | `Mapped` |
| `FR-OPN-004` | `OPN-F04` | `stock_opnames`, `stock_opname_lines`, `inventory_balances`, `stock_movements` | opname service (`approve`, `reject`) | layar review selisih, approve, atau reject dengan alasan | action endpoint `approve` dan `reject` opname | `AC-10`, `AC-21`, `AC-22` | `Mapped` |
| `FR-OPN-005` | `OPN-F05` | `stock_opname_lines`, `inventory_balances`, `stock_movements` | opname service (penambahan item saldo awal) | aksi tambah baris item temuan fisik (`qty_system = 0`) | endpoint tambah line opname dan `approve` | `AC-10` | `Mapped` |
| `FR-OPN-006` | `OPN-F06` | `stock_opnames` | opname service (`is_location_frozen`) | badge/status lokasi beku pada layar operasional | diperiksa saat post GR, ship Transfer, receive Transfer, start Opname | `AC-04`, `AC-10`, `AC-21` | `Mapped` |

### 11.3 Matriks traceability Fase 2 (M9 — Multi-Tenant SaaS Foundation)

Seluruh kebutuhan Fase 2 (M9) berikut telah disetujui pemilik proyek (`CONF-001` Resolved) sebagai tahap langsung berikutnya sebelum penambahan modul operasional Fase 3:

| Requirement ID | Feature ID | Database (`012` & `013`) | Backend | Frontend | API | QA | Status |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `FR-TNT-001` | `TNT-F01` | `platform_admins`, `platform_refresh_tokens` | platform auth service & dependency `require_platform_admin` | halaman login Platform Admin | `POST /api/v1/platform/auth/login`, `/refresh`, `/logout` | `AC-28` | `Mapped (Phase 2 - M9)` |
| `FR-TNT-002` | `TNT-F02` | `tenants`, `plans`, `roles`, `menus`, `users`, `settings` | tenant provisioning service (atomik) | form pembuatan tenant baru di panel Platform Admin | `POST /api/v1/platform/tenants`, `GET /api/v1/platform/tenants`, `GET /api/v1/platform/tenants/{id}` | `AC-29` | `Mapped (Phase 2 - M9)` |
| `FR-TNT-003` | `TNT-F03` | `tenants`, `refresh_tokens` | tenant lifecycle service & contract `ensure_tenant_active` | aksi activate/suspend/deactivate tenant & state `TENANT_SUSPENDED` | `POST /api/v1/platform/tenants/{id}/activate`, `/suspend`, `/deactivate` | `AC-24` | `Mapped (Phase 2 - M9)` |
| `FR-TNT-004` | `TNT-F04` | `plans`, `tenants`, `warehouses`, `users`, `items` | quota service (`check_quota` dengan lock `tenants FOR UPDATE`) | indikator pemakaian kuota & pengelolaan paket tenant | `GET /api/v1/platform/plans`, `PATCH /api/v1/platform/tenants/{id}` | `AC-25` | `Mapped (Phase 2 - M9)` |
| `FR-TNT-005` | `TNT-F05` | `tenants`, `plans` | tenant profile service | halaman profil organisasi & bar pemakaian kuota (`Super Admin` tenant) | `GET /api/v1/tenant/profile`, `PATCH /api/v1/tenant/profile` | `AC-25`, `AC-28` | `Mapped (Phase 2 - M9)` |
| `FR-TNT-006` | `TNT-F06` | kolom `tenant_id`, *Composite FK*, `UNIQUE (tenant_id, ...)`, kebijakan RLS (`013`) | context `current_tenant()`, pool `RESET app.current_tenant_id`, login ber-`tenant_slug` | input `tenant_slug` pada halaman login tenant | `POST /api/v1/auth/login` (dengan `tenant_slug`) dan seluruh endpoint `/api/v1/*` | `AC-23`, `AC-27`, `AC-28` | `Mapped (Phase 2 - M9)` |
| `FR-CFG-001` | `CFG-F01` | `settings` | setting registry & type validator | form dinamis sesuai tipe nilai pengaturan | validasi pada `PUT /api/v1/settings` | `AC-26` | `Mapped (Phase 2 - M9)` |
| `FR-CFG-002` | `CFG-F02` | `settings`, `audit_logs` | setting service (tenant level) | layar pengaturan tenant (`Super Admin` tenant) | `GET /api/v1/settings`, `PUT /api/v1/settings` | `AC-22`, `AC-26` | `Mapped (Phase 2 - M9)` |
| `FR-CFG-003` | `CFG-F03` | `settings`, `warehouses`, `audit_logs` | setting service (warehouse override) | pengaturan override per gudang | `GET /api/v1/warehouses/{id}/settings`, `PUT /api/v1/warehouses/{id}/settings` | `AC-22`, `AC-26` | `Mapped (Phase 2 - M9)` |
| `FR-CFG-004` | `CFG-F04` | `settings` | contract `get_setting(conn, key, warehouse_id=None)` | tampilan nilai efektif beserta sumber pewarisan | dipakai internal oleh `WHS`, `INV`, `PUR`, `RCV`, `TRF`, `OPN` | `AC-26` | `Mapped (Phase 2 - M9)` |

### 11.4 Kandidat Fase 3 dan Future Development (belum masuk Fase 1/2)

| Kandidat / Modul | Cakupan usulan | Keputusan yang dibutuhkan | Status |
| --- | --- | --- | --- |
| `ISS` (Goods Issue — Fase 3 / M10) | Pengeluaran barang operasional ke luar gudang (dibangun langsung dengan `tenant_id`) | `CONF-002` (tujuan pengeluaran, workflow persetujuan, tipe movement `OUT_ISSUE`) | `Need Confirmation` |
| `RPT` (Pelaporan — Fase 3 / M10) | Laporan agregat operasional read-only per tenant | `CONF-003` (daftar laporan wajib, filter, dan kebutuhan ekspor) | `Need Confirmation` |

## 12. Prioritas dan roadmap

### 12.1 Urutan tahapan pengembangan (Fase 1 -> Fase 2 -> Fase 3)

```text
Fase 1 baseline (M0–M8, Selesai):
PLT -> IAM/AUD -> MST/WHS -> INV -> (PUR + RCV), (TRF), (OPN) [Single-Tenant Baseline]
Tambahan sebelum M9: MST-F06 (import massal item) dan MST-F07 (import massal supplier; memakai master service dan pola M3)

Fase 2 (M9, Target Langsung Berikutnya — Multi-Tenant SaaS):
M9a (Database & RLS: migrasi 012 & 013 + current_tenant context & pool reset)
 -> M9b (Modul TNT & CFG + Platform Admin Auth & Tenant Provisioning)
 -> M9c (Adaptasi login tenant ber-slug, kuota check_quota, & injeksi tenant_id di repository M0–M8)
 -> M9d (Verifikasi AC-23 s.d. AC-29 + regresi penuh AC-01 s.d. AC-22 dan AC-30..AC-31)

Fase 3 (M10, Pasca-M9):
ISS (Goods Issue) & RPT (Pelaporan Operasional) di atas skema Multi-Tenant M9
```

Menempatkan Fase 2 (M9 Multi-Tenant SaaS) **sebelum** Fase 3 (`ISS` dan `RPT`) menjamin bahwa tabel baru pada Fase 3 langsung dibuat dengan `tenant_id` dan RLS sejak awal tanpa perlu dimigrasikan dua kali.

### 12.2 Future roadmap (Pasca-M10)

Self-service registrasi tenant publik, penagihan otomatis (*billing*), SSO, 2FA,
ekspor laporan, serta perluasan dimensi stok (Lot/Batch/Expiry, Serial Number,
Reservasi, Valuasi FIFO/Average) dievaluasi setelah Fase 2 (M9) dan Fase 3 (M10)
berjalan stabil.

## 13. Asumsi, konflik, dan konfirmasi

### 13.1 Temuan aktual

Audit lengkap, termasuk konflik dan gap, ada pada
[PRD_AUDIT_AND_RESTRUCTURING_REPORT.md](PRD_AUDIT_AND_RESTRUCTURING_REPORT.md).

### 13.2 Asumsi

- Frontend adalah consumer terpisah dan belum menjadi deliverable repository API.
- Target benchmark belum final.
- Status `Mapped` tidak sama dengan `Implemented`, `Tested`, atau `Verified`.

### 13.3 Status Keputusan Produk (`CONF-001` s.d. `CONF-010`)

| ID | Keputusan / Pertanyaan |
| --- | --- |
| CONF-001 | **Selesai / Ditetapkan:** Produk menuju **Multi-Tenant SaaS pada Fase 2 (M9)** tepat setelah Fase 1 (M0–M8 Single-Tenant). Model yang dikunci: (a) 1 database + `tenant_id` + PostgreSQL RLS, (b) 1 akun `users` terikat ke 1 `tenant_id` dengan login menyertakan `tenant_slug`, (c) `Platform Admin` terpisah di tabel `platform_admins` (`/api/v1/platform/auth/login`), dan (d) provisioning tenant oleh `Platform Admin` (`POST /api/v1/platform/tenants`) dengan paket kuota (`max_warehouses`, `max_active_users`, `max_active_items`) tanpa self-signup publik pada tahap awal |
| CONF-002 | Apakah Goods Issue (`ISS` — Fase 3 / M10) menggunakan alur 1 tahap (`DRAFT -> POSTED`) atau 2 tahap (`DRAFT -> APPROVED -> ISSUED`)? |
| CONF-003 | Laporan apa saja yang wajib pada modul `RPT` (Fase 3 / M10) dan apakah membutuhkan ekspor file? |
| CONF-004 | **Selesai pada baseline PRD:** satu item hanya boleh muncul satu kali pada satu dokumen Transfer (`uq_stock_transfer_lines_transfer_item` dan validasi `TRF`) |
| CONF-005 | **Selesai pada baseline PRD:** `INTERNAL_ERROR` (HTTP 500) terdaftar resmi dalam katalog error pada `PRD_BACKEND.md` dan `API_CONTRACT.md` |
| CONF-006 | **Selesai pada baseline PRD:** AC terpisah untuk numbering (`AC-15`), query (`AC-16`), platform (`AC-17`, `AC-18`), master (`AC-19`), warehouse (`AC-20`), audit (`AC-22`), serta multi-tenant & konfigurasi Fase 2 (`AC-23` s.d. `AC-29`) telah ditetapkan |
| CONF-007 | Dataset dan environment benchmark produksi final apa? |
| CONF-008 | Kontrak penyimpanan refresh token pada frontend consumer apa (JSON body vs HttpOnly cookie)? |
| CONF-009 | **Selesai / Disetujui:** Fitur MST-F06 dan dependensi `openpyxl` serta `python-multipart` disetujui pemilik proyek dan ditambahkan ke konfigurasi proyek. |
| CONF-010 | **Selesai / Disetujui:** Batas import ditetapkan pada 1.000 baris data dan ukuran file 5 MiB. |

## 14. Change impact dan validation

Perubahan requirement harus memperbarui ID, module owner, workflow, data
relationship, permission, dependency, AC, RTM, dan dokumen layer yang terdampak.
Perubahan pada `INV`, movement registry, atau lock ordering selalu dinilai sebagai
perubahan lintas modul.

### Final validation

- Seluruh modul dan fitur lama memiliki mapping.
- Fase 1 (MVP M0–M8), Fase 2 (M9 Multi-Tenant SaaS), Fase 3 (`ISS`, `RPT`), Future Development, dan Out of Scope terpisah secara tegas.
- Feature ID dan requirement ID unik serta memiliki owner.
- Seluruh feature Fase 1 (`AC-01` s.d. `AC-22`, serta tambahan `AC-30` dan `AC-31`) dan Fase 2 (`AC-23` s.d. `AC-29`) memiliki acceptance criteria eksplisit.
- Konflik dan asumsi tidak diperlakukan sebagai fakta.
- RTM menghubungkan database, backend, frontend, API, dan QA baik untuk Fase 1 maupun Fase 2 (M9).
- Tidak ada klaim implementasi/test tanpa evidence.
- Detail teknis tetap berada di dokumen layer.

## Lampiran C — Riwayat Perubahan

| Tanggal | Versi | Perubahan |
| --- | --- | --- |
| 2026-11-06 | 2.2-general | Menambahkan `FR-MST-006` / `MST-F06` import massal item Fase 1; menetapkan nama kategori/UoM, sheet referensi aktif, dan validasi ambiguitas; menyelesaikan `CONF-009`–`CONF-010`; dan mencatat implementasi yang lulus 41 tes backend. Tidak ada perubahan skema database. |
| 2026-11-06 | 2.2-general | Menambahkan `FR-MST-007` / `MST-F07` import supplier massal dengan validasi per baris, deteksi kode duplikat, audit atomik, serta `AC-31`; implementasi lulus regresi 47 tes backend. Tidak ada perubahan skema database. |
