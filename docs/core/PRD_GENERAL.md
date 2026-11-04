# PRD General — JejakStok

| Informasi | Nilai |
| --- | --- |
| Status | Baseline MVP, hasil restrukturisasi |
| Versi | 2.0-general |
| Pemilik | Product / Business |
| Sumber historis | PRD v2.0 yang telah diaudit dan diintegrasikan |
| Catatan | Draft multi-tenant dan modul usulan tetap dipertahankan sebagai Future Development atau Need Confirmation |

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

### 2.2 MVP

| Module | Feature ID | Fitur | MoSCoW |
| --- | --- | --- | --- |
| PLT | PLT-F01..F05 | Numbering, query convention, error, request ID/health, migration | Must Have |
| IAM | IAM-F01..F09 | Auth, RBAC, user, warehouse scope, menu, profile | Must Have |
| AUD | AUD-F01..F02 | Write/read audit log | Must Have |
| MST | MST-F01..F05 | Category, UoM, item, supplier, deactivation | Must Have |
| WHS | WHS-F01..F03 | Warehouse, location, validation | Must Have |
| INV | INV-F01..F06 | Balance, ledger, movement gateway, negative stock, freeze enforcement | Must Have |
| PUR | PUR-F01..F04 | PO lifecycle and fulfillment | Must Have |
| RCV | RCV-F01..F04 | Goods receipt and posting | Must Have |
| TRF | TRF-F01..F05 | Transfer lifecycle and in-transit | Must Have |
| OPN | OPN-F01..F06 | Count, freeze, approval, adjustment, opening balance | Must Have |

### 2.3 Phase 2, Future Development, Out of Scope

| Kategori | Fitur | Dasar/status |
| --- | --- | --- |
| Phase 2 | Goods Issue | Disebut sebagai rekomendasi fase berikutnya, detail workflow belum diputuskan |
| Phase 2 | Laporan dasar | Kebutuhan umum disebut, daftar laporan belum disetujui |
| Future Development | Multi-tenant, tenant lifecycle, plan/quota, platform admin | Draft modular v3.x, `CONF-001` |
| Future Development | Configuration registry/inheritance | Draft modular v3.x, `CONF-001` |
| Future Development | Export, reorder point, notification, barcode/QR, picking/putaway | Roadmap draft modular, belum requirement final |
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
| Super Admin | User, role/permission, assignment, warehouse configuration, audit |
| Warehouse Manager | Location, transfer approval, opname approval, PO close, monitoring |
| Purchasing Staff | Master procurement dan PO |
| Warehouse Staff | GR, transfer physical execution, opname count pada warehouse assigned |
| Auditor | Read-only master, stock, documents, ledger, opname, audit |

### 3.1 Permission registry MVP

| Domain | Permission |
| --- | --- |
| IAM/WHS/MST | `user:manage`, `warehouse:manage`, `location:manage`, `master:manage`, `master:read` |
| PUR | `po:create`, `po:issue`, `po:cancel`, `po:close`, `po:read` |
| RCV | `gr:manage`, `gr:read` |
| TRF | `transfer:create`, `transfer:approve`, `transfer:ship`, `transfer:receive`, `transfer:read` |
| OPN | `opname:manage`, `opname:count`, `opname:approve`, `opname:read` |
| INV/AUD | `stock:read`, `ledger:read`, `audit:read` |

Super Admin memiliki seluruh permission. Warehouse scoping berlaku pada aksi yang
ditandai `(g)`. Warehouse Staff hanya membaca dokumen dan saldo gudang yang
ditugaskan, kecuali Transfer yang terlihat bila ditugaskan di asal atau tujuan.

## 4. Arsitektur modular

### 4.1 Module registry

| ID | Modul | Tanggung jawab | Status |
| --- | --- | --- | --- |
| PLT | Platform | Numbering, pagination, error format, request ID, health, migration convention | MVP |
| IAM | Identity dan Akses | Authentication, RBAC, user, scope, menu | MVP |
| AUD | Audit | Append-only audit events dan read/filter | MVP |
| MST | Master Data | Category, UoM, item, supplier | MVP |
| WHS | Gudang dan Lokasi | Warehouse, setting negative stock, location | MVP |
| INV | Inventory | Balance, ledger, movement gateway, stock views | MVP |
| PUR | Purchase Order | PO lifecycle dan fulfillment | MVP |
| RCV | Goods Receipt | GR lifecycle dan atomic posting | MVP |
| TRF | Transfer Stok | Transfer lifecycle, variance, in-transit | MVP |
| OPN | Stock Opname | Snapshot, freeze, count, approval, adjustment | MVP |
| TNT | Tenant | Tenant SaaS | Future Development |
| CFG | Konfigurasi | Configuration inheritance | Future Development |

### 4.2 Dependency graph

```text
PLT -> IAM -> MST/WHS -> INV -> PUR/RCV
                         INV -> TRF
                         INV -> OPN
AUD is called by every module that changes data.
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
| `ensure_warehouse_access` | IAM | PUR, RCV, TRF, OPN, WHS | Memverifikasi assignment user terhadap warehouse yang menjadi scope aksi | Modul consumer tetap menentukan warehouse bisnis yang harus diperiksa |
| `record` | AUD | Semua modul yang mengubah data | Menulis audit event dalam transaksi perubahan | AUD tidak menentukan validitas aksi atau mengubah data owner |
| `next_number` | PLT | PUR, RCV, TRF, OPN | Menghasilkan nomor unik per tipe dan periode secara atomik | Consumer tidak membuat nomor dokumen sendiri |
| `apply_movement` | INV | RCV, TRF, OPN | Mengunci balance, memvalidasi negative stock/freeze, mengubah balance, dan menulis ledger | Consumer tidak boleh update `inventory_balances` atau `stock_movements` |
| `apply_receipt` | PUR | RCV | Menghitung ulang dan memperbarui `qty_received` serta fulfillment PO setelah lock PO | RCV tidak mengubah PO atau fulfillment secara langsung |
| `is_location_frozen` | OPN | INV, RCV, TRF | Mengembalikan status freeze lokasi berdasarkan sesi opname aktif | INV menjadi enforcement point untuk movement; adjustment opname dikecualikan sesuai BR-GLB-014 |
| `validate_location` | WHS | INV, RCV, TRF, OPN | Memastikan lokasi aktif dan dimiliki warehouse yang direferensikan | Consumer tidak mengganti ownership location dengan pemeriksaan lokal |
| `gr_status_summary` | RCV | PUR | Mengembalikan ringkasan GR draft/posted yang diperlukan untuk aturan cancel/close PO | PUR tidak membaca tabel GR secara langsung |
| `in_transit` | TRF | INV | Mengembalikan kuantitas transfer yang sudah shipped dan belum received | INV tidak menghitung ulang status transfer dari tabel TRF |

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
| BR-GLB-018 | Setiap transisi invalid ditolak tanpa perubahan data dan menggunakan kode error katalog `INVALID_STATUS_TRANSITION`, kecuali kondisi memiliki kode error yang lebih spesifik. |

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

**Business rules dan workflow:** prefix dokumen harus terdaftar; sequence diambil
atomik; request ID dibuat server bila tidak dikirim; migrasi yang telah diterapkan
tidak diedit. Prefix MVP adalah `PO`, `GR`, `TRF`, dan `OPN`.

**Data, permission, dependency:** `document_sequences` dan `schema_migrations`
dimiliki PLT. Tidak memiliki permission bisnis. Dipakai semua modul.

**Acceptance:** `AC-15` numbering tidak menghasilkan nomor ganda pada request
bersamaan; `AC-16` list query konsisten dengan limit/offset/filter/sort whitelist;
`AC-17` error dan request ID konsisten; `AC-18` migration runner forward-only.

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
`exp`; password di-hash Argon2id atau bcrypt minimal 8 karakter; user aktif dan
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

**Business rules dan workflow:** event ditulis dalam transaksi perubahan; memuat
actor, action, entity, old/new values, IP, timestamp; password, hash, dan token
tidak boleh masuk log; audit log tidak memiliki update/delete endpoint.

**Data, permission, dependency:** `audit_logs`; `audit:read`; dipanggil semua
modul melalui `record`.

**Acceptance:** `AC-08` role aplikasi tidak dapat mengubah/menghapus ledger maupun
audit; `AC-05` perubahan sah menghasilkan audit event; `AC-07` rollback menghapus
event yang berasal dari transaksi gagal.

### 6.4 MST, Master Data

| Feature ID | Requirement ID | Kebutuhan | Priority |
| --- | --- | --- | --- |
| MST-F01 | FR-MST-001 | CRUD/soft deactivate kategori | MVP |
| MST-F02 | FR-MST-002 | UoM dengan `allow_decimal` | MVP |
| MST-F03 | FR-MST-003 | Item dengan SKU unik dan satu base UoM | MVP |
| MST-F04 | FR-MST-004 | Supplier | MVP |
| MST-F05 | FR-MST-005 | Deactivation terkontrol tanpa hard delete | MVP |

**Business rules:** SKU tidak berubah setelah dipakai transaksi; quantity mengikuti
`allow_decimal`; nama kategori, kode UoM, kode supplier unik; supplier yang masih
direferensikan PO non-final tidak dapat dinonaktifkan.

**Data, permission, dependency:** `categories`, `uoms`, `items`, `suppliers`;
`master:manage` dan `master:read`; dipakai INV, PUR, RCV, TRF, OPN.

**Acceptance:** `AC-19` duplicate/invalid master ditolak, SKU protected setelah
dipakai, deactivate yang masih direferensikan ditolak.

### 6.5 WHS, Gudang dan Lokasi

| Feature ID | Requirement ID | Kebutuhan | Priority |
| --- | --- | --- | --- |
| WHS-F01 | FR-WHS-001 | Warehouse dengan `allow_negative_stock` | MVP |
| WHS-F02 | FR-WHS-002 | Storage location dalam warehouse | MVP |
| WHS-F03 | FR-WHS-003 | Validasi location aktif dan ownership | MVP |

**Business rules:** kode warehouse unik; kode location unik di dalam warehouse;
`allow_negative_stock` default false dan hanya Super Admin yang mengubahnya; tidak
boleh menonaktifkan entity yang masih memiliki referensi aktif.

**Data, permission, dependency:** `warehouses`, `storage_locations`;
`warehouse:manage`, `location:manage`, `master:read`; dipakai IAM, INV, PUR, RCV,
TRF, OPN.

**Acceptance:** `AC-20` duplicate/mismatch location ditolak; deactivation dengan
open reference ditolak; perubahan konfigurasi diaudit.

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
`LOCATION_FROZEN`.

**Data, permission, dependency:** `inventory_balances`, `stock_movements`;
`stock:read`, `ledger:read`; membaca MST/WHS/OPN/TRF dan dipicu RCV/TRF/OPN.

**Acceptance:** `AC-02` negative stock transfer ditolak; `AC-06` concurrency hanya
menghasilkan satu ship; `AC-08` append-only; `AC-13` lock ordering konsisten.

### 6.7 PUR, Purchase Order

| Feature ID | Requirement ID | Kebutuhan | Priority |
| --- | --- | --- | --- |
| PUR-F01 | FR-PUR-001 | PO header dan satu atau lebih PO lines | MVP |
| PUR-F02 | FR-PUR-002 | Draft, issue, cancel, close | MVP |
| PUR-F03 | FR-PUR-003 | `qty_received` dan fulfillment status otomatis | MVP |
| PUR-F04 | FR-PUR-004 | Contract `apply_receipt` untuk RCV | MVP |

**Business rules dan workflow:** PO draft hanya dapat diedit; issue butuh supplier,
warehouse aktif, item aktif, dan quantity positif; satu item satu kali per PO;
`PARTIALLY_RECEIVED` dan `RECEIVED` otomatis. PO `DRAFT` dapat dibatalkan.
PO `ISSUED` dapat dibatalkan hanya bila belum memiliki GR posted. PO
`PARTIALLY_RECEIVED` tidak dapat dibatalkan dan dapat ditutup melalui aksi close
setelah tidak ada GR draft yang perlu diselesaikan. PO `RECEIVED` dapat ditutup
melalui aksi close. PO `CANCELLED` dan `CLOSED` adalah terminal.

Setiap aksi issue, cancel, dan close mengubah status serta menulis audit dalam satu
transaksi. Perubahan fulfillment akibat posting GR dilakukan oleh contract PUR,
bukan oleh route atau modul RCV secara langsung.

**Data, permission, dependency:** `purchase_orders`, `po_lines`; PO permissions;
MST/WHS/PLT dependency, RCV consumer melalui contract `apply_receipt` dan
`gr_status_summary`.

**Acceptance:** `AC-01` partial lalu full receiving mengubah fulfillment; `AC-21`
status transition invalid ditolak.

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
`AC-12` warehouse scope; `AC-13` concurrent posting.

### 6.9 TRF, Transfer Stok

| Feature ID | Requirement ID | Kebutuhan | Priority |
| --- | --- | --- | --- |
| TRF-F01 | FR-TRF-001 | Transfer source/destination warehouse/location | MVP |
| TRF-F02 | FR-TRF-002 | Approval oleh Warehouse Manager source warehouse | MVP |
| TRF-F03 | FR-TRF-003 | Ship mengurangi saldo source | MVP |
| TRF-F04 | FR-TRF-004 | Receive final menambah saldo destination | MVP |
| TRF-F05 | FR-TRF-005 | In-transit view | MVP |

**Business rules dan workflow:** `DRAFT -> APPROVED -> SHIPPED -> RECEIVED`;
source/destination tidak boleh sama; ship memakai `OUT_TRANSFER`; receive final
memakai `IN_TRANSFER`; `qty_received <= qty`; variance reason wajib bila kurang;
selisih tidak kembali ke source dan tidak membuat ledger tambahan. Transfer `DRAFT`
dapat dibatalkan. Transfer `APPROVED` dapat dibatalkan selama belum shipped.
Transfer `SHIPPED`, `RECEIVED`, dan `CANCELLED` tidak dapat dibatalkan atau dibuka
kembali. Ship dan receive yang diulang tidak boleh menggandakan movement atau
saldo.

**Data, permission, dependency:** `stock_transfers`, `stock_transfer_lines`;
transfer permissions; memakai PLT, INV, WHS, AUD dan dibaca INV. TRF menggunakan
`next_number`, `validate_location`, `is_location_frozen`, `apply_movement`, dan
`record`; TRF tidak menulis saldo atau ledger secara langsung.

**Acceptance:** `AC-02`, `AC-03`, `AC-06`, `AC-09` mencakup stock, in-transit,
variance, concurrency, dan scoping.

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
| PO | `DRAFT` | `cancel` | `po:cancel` | Tidak ada GR posted | `CANCELLED` | Audit |
| PO | `ISSUED` | `cancel` | `po:cancel` | Tidak ada GR posted | `CANCELLED` | Audit |
| PO | `PARTIALLY_RECEIVED` | `close` | `po:close` | Tidak ada GR draft yang perlu diselesaikan | `CLOSED` | Audit |
| PO | `RECEIVED` | `close` | `po:close` | Tidak ada GR draft yang perlu diselesaikan | `CLOSED` | Audit |
| GR | `DRAFT` | `post` | `gr:manage` | PO eligible, tidak over-receipt, lokasi tidak frozen | `POSTED` | Stock, ledger, PO fulfillment, audit |
| GR | `DRAFT` | `cancel` | `gr:manage` | GR belum posted | `CANCELLED` | Audit |
| Transfer | `DRAFT` | `approve` | `transfer:approve` | Source dan destination valid serta berbeda | `APPROVED` | Audit |
| Transfer | `DRAFT` | `cancel` | `transfer:create` | Belum approved atau shipped | `CANCELLED` | Audit |
| Transfer | `APPROVED` | `ship` | `transfer:ship` | Stock cukup, lokasi source tidak frozen | `SHIPPED` | OUT_TRANSFER, source balance, ledger, audit |
| Transfer | `APPROVED` | `cancel` | `transfer:create` | Belum shipped | `CANCELLED` | Audit |
| Transfer | `SHIPPED` | `receive` | `transfer:receive` | Quantity received valid, variance reason bila kurang, destination tidak frozen | `RECEIVED` | IN_TRANSFER bila quantity diterima, destination balance, ledger, audit |
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
`INVALID_STATUS_TRANSITION`. Kondisi yang lebih spesifik tetap menggunakan kode
yang sudah terdaftar, seperti `INSUFFICIENT_STOCK`, `LOCATION_FROZEN`,
`OVER_RECEIPT`, `WAREHOUSE_NOT_ASSIGNED`, atau `INVALID_LOCATION`.

## 8. Data requirements

| Entitas | Owner | Relationship utama |
| --- | --- | --- |
| users, roles, permissions, user_warehouses, refresh_tokens, menus | IAM | user ke role/warehouse |
| categories, uoms, items, suppliers | MST | item ke category dan base UoM |
| warehouses, storage_locations | WHS | location berada dalam warehouse |
| inventory_balances, stock_movements | INV | balance keyed warehouse/location/item |
| purchase_orders, po_lines | PUR | PO ke supplier, warehouse, item lines |
| goods_receipts, gr_lines | RCV | GR ke PO/PO line/location |
| stock_transfers, stock_transfer_lines | TRF | transfer source/destination dan item lines |
| stock_opnames, stock_opname_lines | OPN | opname warehouse/location dan item lines |
| audit_logs | AUD | actor dan entity event |
| document_sequences, schema_migrations | PLT | numbering dan migration history |

Database layer harus menjaga foreign key ownership, composite warehouse-location
relationship, quantity checks yang bersumber dari requirement, dan append-only
privilege untuk ledger/audit. Detail DDL bukan bagian dari PRD General.

## 9. Non-functional requirements

| ID | Requirement | Acceptance evidence |
| --- | --- | --- |
| NFR-001 | Transaksi atomik untuk status, stock, ledger, audit | AC-07 |
| NFR-002 | JWT HS256, password hash, secret environment-only, no secret in log | Auth/security tests |
| NFR-003 | Query list terindeks dan pagination; target p95 200 ms hanya setelah dataset/environment disepakati | Benchmark evidence, `CONF-007` |
| NFR-004 | Decimal `NUMERIC(18,4)`, JSON decimal string | AC-12 |
| NFR-005 | PostgreSQL direct driver, no ORM, SQL repository-only, forward-only migration | Architecture and migration checks |
| NFR-006 | Structured error, request ID, health, OpenAPI | AC-12, operational checks |
| NFR-007 | Test memakai PostgreSQL sungguhan; concurrency memakai koneksi terpisah | AC-06, AC-13 |
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
| AC-12 | Error, request ID, pagination, dan quantity format konsisten | PLT | Mapped |
| AC-13 | Dua posting GR yang sama tidak menggandakan stock/PO | RCV/PUR | Mapped |
| AC-14 | Menu hanya berisi node yang diizinkan | IAM | Mapped |
| AC-15 | Sequence dokumen unik pada request bersamaan | PLT | Need Confirmation |
| AC-16 | List filter/sort/pagination menolak sort field di luar whitelist | PLT | Need Confirmation |
| AC-17 | Health dan request ID mengikuti kontrak global | PLT | Need Confirmation |
| AC-18 | Migration runner tidak mengubah migration yang sudah applied | PLT | Need Confirmation |
| AC-19 | Master duplicate, SKU protection, dan open-reference deactivation | MST | Need Confirmation |
| AC-20 | Warehouse/location ownership dan configuration audit | WHS | Need Confirmation |
| AC-21 | Semua invalid state transition ditolak tanpa perubahan data dan memakai error katalog | PUR/TRF/OPN/RCV | Mapped |

## 11. Requirement Traceability Matrix

Status `Mapped` berarti kebutuhan sudah memiliki target layer, bukan berarti
implementasi atau test sudah terbukti.

| Requirement ID | Feature ID | Database | Backend | Frontend | API | QA | Status |
| --- | --- | --- | --- | --- | --- | --- | --- |
| FR-IAM-001 | IAM-F01 | users, refresh_tokens | auth service | login/session | auth login | auth test | Mapped |
| FR-IAM-005 | IAM-F05 | roles, permissions | dependency/RBAC | permission-aware navigation | protected routes | RBAC test | Mapped |
| FR-MST-003 | MST-F03 | items | master service | item form/list | item CRUD | master test | Mapped |
| FR-WHS-002 | WHS-F02 | storage_locations | warehouse service | location screens | location CRUD | ownership test | Mapped |
| FR-INV-004 | INV-F04 | balances, movements | inventory service | stock views | movement-triggering actions | invariant test | Mapped |
| FR-PUR-002 | PUR-F02 | purchase_orders | PO service | PO workflow | issue/cancel/close | PO transition test | Mapped |
| FR-RCV-002 | RCV-F02 | GR, PO, balances, movements | GR service | receiving form | post GR | AC-01/07/13 | Mapped |
| FR-TRF-003 | TRF-F03 | transfers, balances, movements | transfer service | ship action | ship transfer | AC-02/06 | Mapped |
| FR-OPN-004 | OPN-F04 | opnames, balances, movements | opname service | approval/count | approve opname | AC-04/10 | Mapped |
| FR-AUD-001 | AUD-F01 | audit_logs | audit service | audit viewer | audit list | AC-05/07/08 | Mapped |
| FR-PLT-001 | PLT-F01 | document_sequences | numbering service | n/a | document actions | AC-15 | Need Confirmation |
| FR-PLT-002 | PLT-F02 | indexes/query fields | list services | list controls | query params | AC-16 | Need Confirmation |

## 12. Prioritas dan roadmap

### 12.1 Dependency delivery MVP

```text
PLT -> IAM/AUD -> MST/WHS -> INV -> (PUR + RCV), (TRF), (OPN)
```

PUR/RCV, TRF, dan OPN dapat dikembangkan paralel setelah INV tersedia, tetapi
masing-masing harus mengikuti contract dan AC.

### 12.2 Future roadmap

Goods Issue dan laporan dasar dapat dinilai sebagai Phase 2 setelah `CONF-002` dan
`CONF-003`. Multi-tenant, tenant lifecycle, platform admin, configuration
inheritance, subscription, SSO, 2FA, dan export tetap Future Development sampai
`CONF-001` diputuskan.

## 13. Asumsi, konflik, dan konfirmasi

### 13.1 Temuan aktual

Audit lengkap, termasuk konflik dan gap, ada pada
[PRD_AUDIT_AND_RESTRUCTURING_REPORT.md](PRD_AUDIT_AND_RESTRUCTURING_REPORT.md).

### 13.2 Asumsi

- Frontend adalah consumer terpisah dan belum menjadi deliverable repository API.
- Target benchmark belum final.
- Status `Mapped` tidak sama dengan `Implemented`, `Tested`, atau `Verified`.

### 13.3 Need Confirmation

| ID | Pertanyaan |
| --- | --- |
| CONF-001 | Apakah multi-tenant menjadi target produk? |
| CONF-002 | Apakah Goods Issue masuk Phase 2, dengan workflow apa? |
| CONF-003 | Laporan apa yang wajib dan kapan? |
| CONF-004 | Apakah satu item hanya boleh satu baris Transfer? |
| CONF-005 | Apakah `INTERNAL_ERROR` masuk katalog resmi? |
| CONF-006 | Apakah AC tambahan untuk master, warehouse, numbering, query perlu disahkan? |
| CONF-007 | Dataset dan environment benchmark final apa? |
| CONF-008 | Kontrak penyimpanan refresh token pada frontend consumer apa? |

## 14. Change impact dan validation

Perubahan requirement harus memperbarui ID, module owner, workflow, data
relationship, permission, dependency, AC, RTM, dan dokumen layer yang terdampak.
Perubahan pada `INV`, movement registry, atau lock ordering selalu dinilai sebagai
perubahan lintas modul.

### Final validation

- Seluruh modul dan fitur lama memiliki mapping.
- MVP, Phase 2, Future Development, dan Out of Scope terpisah.
- Feature ID dan requirement ID unik serta memiliki owner.
- Semua feature memiliki AC atau status `Need Confirmation`.
- Konflik dan asumsi tidak diperlakukan sebagai fakta.
- RTM menghubungkan database, backend, frontend, API, dan QA.
- Tidak ada klaim implementasi/test tanpa evidence.
- Detail teknis tetap berada di dokumen layer.
