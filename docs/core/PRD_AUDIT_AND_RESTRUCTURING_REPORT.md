# Audit dan Restrukturisasi PRD JejakStok

| Informasi | Nilai |
| --- | --- |
| Tanggal | 2026-11-03 |
| Status | Selesai untuk baseline dokumentasi |
| Sumber yang diaudit | PRD v2.0 legacy, `PRD JejakStok — Sistem Manajemen Gudang (Modular).md`, `PRD_GENERAL.md` |
| Sumber requirement hasil restrukturisasi | [PRD_GENERAL.md](PRD_GENERAL.md) |

Dokumen ini berisi hasil audit, gap analysis, modularization analysis, rekomendasi
arsitektur PRD, mapping, dan validasi akhir. Audit dilakukan sebelum file PRD v2.0
legacy dihapus. Requirement yang relevan telah diintegrasikan ke PRD General.

## 1. Audit PRD Lama

### 1.1 Inventarisasi sumber

| Sumber | Status saat diaudit | Isi utama | Peran setelah restrukturisasi |
| --- | --- | --- | --- |
| PRD v2.0 legacy | Acuan implementasi MVP v2.0 | Tujuan, scope, role, permission, FR-01 sampai FR-11, workflow, business rules, NFR, AC-01 sampai AC-14, data, API convention | Telah diintegrasikan ke PRD General |
| `PRD JejakStok — Sistem Manajemen Gudang (Modular).md` | Draft v3.x | Modul, kontrak, ID fitur/aturan, tenant, konfigurasi, roadmap, RTM parsial | Sumber analisis desain; bagian yang belum disetujui tidak menjadi MVP |
| `PRD_GENERAL.md` lama | Ringkasan approved MVP | Visi, role, scope, FR, NFR, AC, traceability | Digantikan oleh PRD General baru |

### 1.2 Modul dan fitur yang ditemukan

| Modul | Fitur yang ditemukan | Status sumber |
| --- | --- | --- |
| PLT, Platform | Penomoran dokumen, pagination/filter/sorting, format error, request ID, health, migrasi | MVP |
| IAM, Identity dan Akses | Login, refresh, logout, lockout, RBAC, pengguna, warehouse scoping, menu, profil, ganti password | MVP |
| AUD, Audit | Audit log append-only dan pembacaan/filter audit | MVP |
| MST, Master Data | Kategori, UoM, item/SKU, supplier, soft deactivate | MVP |
| WHS, Gudang dan Lokasi | Gudang, konfigurasi negative stock, storage location, validasi lokasi | MVP |
| INV, Inventory | Saldo, agregasi, in-transit view, ledger, `apply_movement`, negative stock, frozen location | MVP |
| PUR, Purchase Order | Create/edit draft, issue, cancel, close, fulfillment tracking | MVP |
| RCV, Goods Receipt | GR dari PO, partial receiving, posting atomik, cancel draft, over-receipt prevention | MVP |
| TRF, Transfer Stok | Create, approve, ship, receive final, variance, in-transit | MVP |
| OPN, Stock Opname | Session, snapshot, freeze, count, submit, approve/reject, adjustment, opening balance | MVP |
| TNT, Tenant | Tenant lifecycle, plan/quota, platform admin, tenant provisioning | Draft v3.x, perlu konfirmasi |
| CFG, Konfigurasi | Setting registry dan inheritance tenant/gudang | Draft v3.x, perlu konfirmasi |
| ISS, Goods Issue | Pengeluaran barang | Usulan, out of scope MVP |
| RPT, Pelaporan | Laporan read-only | Usulan, belum memiliki requirement final |

### 1.3 Aktor dan permission

Role aktif yang konsisten pada baseline MVP adalah Super Admin, Warehouse Manager,
Purchasing Staff, Warehouse Staff, dan Auditor. Permission yang ditemukan mencakup
manajemen user, warehouse, location, master, PO, GR, transfer, opname, stock,
ledger, dan audit. Permission tenant/platform hanya muncul pada draft modular dan
tidak dipromosikan ke MVP.

### 1.4 Workflow dan aturan yang ditemukan

Workflow utama:

1. Master data dan gudang disiapkan.
2. PO dibuat sebagai `DRAFT`, diterbitkan, lalu menerima GR.
3. GR `POSTED` menambah saldo melalui `IN_PURCHASE` dan memperbarui fulfillment PO.
4. Transfer bergerak `DRAFT -> APPROVED -> SHIPPED -> RECEIVED`.
5. `SHIPPED` mengurangi saldo asal dan menjadi in-transit; `RECEIVED` menambah saldo tujuan.
6. Opname mengambil snapshot, membekukan lokasi, menghitung fisik, menyetujui, lalu
   menulis adjustment.
7. Semua perubahan saldo melewati satu pintu `apply_movement`.
8. Perubahan penting dan autentikasi penting dicatat pada audit log.

Aturan lintas modul yang paling penting adalah transaksi atomik, append-only ledger
dan audit, lock ordering, negative stock per gudang, over-receipt, frozen location,
warehouse scoping, Decimal-only quantity, dan status transition melalui action endpoint.

### 1.5 Duplikasi

| Area | Lokasi duplikasi | Keputusan |
| --- | --- | --- |
| Scope dan out of scope | PRD v2.0, PRD General lama, draft modular | Satu daftar scope aktif di PRD General baru; draft multi-tenant tetap dicatat sebagai Need Confirmation |
| Role dan permission | Bagian aktor, matriks, modul IAM | Matriks permission menjadi sumber role access; modul hanya merujuk permission |
| Stock movement | FR-03/FR-08, business rules, modul INV | Registri movement dan aturan INV menjadi sumber tunggal |
| Frozen location | workflow opname, rule inventory, rule opname | OPN memiliki status freeze; INV menjadi enforcement point |
| Acceptance criteria | tabel AC global dan AC per modul | AC global dipertahankan, owner dan mapping modul ditambahkan |
| API dan database | PRD, dokumen backend/database | PRD General hanya menyimpan kebutuhan perilaku dan data konseptual; detail teknis dirujuk ke dokumen layer |

### 1.6 Konflik

| ID | Konflik | Keputusan dokumentasi |
| --- | --- | --- |
| CON-001 | v2.0 single-tenant versus draft modular multi-tenant | MVP tetap single-tenant. Multi-tenant menjadi Future Development/Need Confirmation |
| CON-002 | Platform Admin dan permission platform tidak ada di v2.0 | Tidak masuk acceptance criteria MVP |
| CON-003 | Nama role `Auditor` versus `Auditor / Viewer` | Gunakan nama resmi `Auditor`; alias lama dicatat hanya untuk traceability |
| CON-004 | ISS disebut dalam tujuan proyek, tetapi eksplisit out of scope v2.0 | Tetap Out of Scope MVP, kandidat Phase 2 setelah keputusan bisnis |
| CON-005 | RPT disebut sebagai kebutuhan umum, tetapi tidak ada requirement rinci | Tidak membuat scope aktif; kandidat Future Development |
| CON-006 | Draft modular menambahkan AC-15 sampai AC-21 untuk tenant/config | Ditahan sebagai requirement draft, bukan status tested/implemented |
| CON-007 | Detail API, frontend, dan migrasi tidak selalu sama antar dokumen | PRD General menyimpan perilaku produk; kontrak layer harus diverifikasi melalui RTM |

### 1.7 Kekurangan dan informasi tidak relevan

- Master data dan warehouse/location belum memiliki AC eksplisit pada PRD v2.0.
- PLT, AUD, PUR, dan beberapa fitur INV hanya diverifikasi melalui AC modul lain.
- Target performa belum memiliki dataset dan lingkungan benchmark yang disepakati.
- Status implementasi atau hasil test tidak dapat disimpulkan hanya dari isi PRD.
- Detail endpoint dan path kode pada draft modular belum seluruhnya diverifikasi terhadap implementasi aktual.
- Multi-tenant, plan/quota, data retention tenant, SSO, 2FA, billing, dan export tenant
  merupakan tambahan draft yang belum menjadi keputusan produk.

## 2. Gap Analysis

### 2.1 Temuan aktual

| ID | Temuan | Dampak | Tindakan pada PRD General |
| --- | --- | --- | --- |
| GAP-001 | Tidak semua fitur memiliki AC sendiri | QA tidak dapat menutup fitur secara langsung | Tambahkan AC untuk master, warehouse, platform, audit, numbering, dan query behavior berdasarkan requirement yang sudah ada |
| GAP-002 | Status MVP dan draft v3.x bercampur | Scope creep dan perubahan skema prematur | Pisahkan MVP, Phase 2, Future Development, dan Out of Scope |
| GAP-003 | Requirement ID lama belum konsisten dengan module ownership | Traceability sulit | Gunakan Feature ID stabil dan Requirement ID ber-prefix modul |
| GAP-004 | RTM lama hanya berupa domain mapping | Tidak cukup untuk database/backend/frontend/API/QA | Tambahkan RTM per requirement dengan status evidence |
| GAP-005 | Dependensi lintas modul tersirat di workflow | Perubahan modul dapat menimbulkan regresi | Selesai: PRD General memiliki contract register normatif, owner/consumer, batas ownership, dan aturan perubahan contract |
| GAP-006 | Beberapa acceptance criteria mengklaim behavior tanpa status bukti | Implemented/tested dapat disalahartikan | Gunakan status Not Mapped sampai Verified sesuai evidence |
| GAP-007 | Data requirements belum seluruhnya dikaitkan dengan feature | Database design dapat menyimpang | Tambahkan conceptual data ownership dan relationship map |

### 2.2 Asumsi yang tidak boleh diperlakukan sebagai requirement

| ID | Asumsi | Alasan |
| --- | --- | --- |
| AS-001 | Frontend berada di repository terpisah | Tidak ada source frontend yang diaudit di repository ini |
| AS-002 | Baseline MVP tetap single-tenant | Didukung PRD v2.0 dan scope implementasi, tetapi perlu keputusan bila SaaS diinginkan |
| AS-003 | Endpoint pada draft modular merepresentasikan desain, bukan bukti implementasi | Sebagian ditandai usulan dan belum diverifikasi terhadap kode |
| AS-004 | Target p95 200 ms berlaku pada workload contoh | Dataset dan environment final belum ditetapkan |
| AS-005 | Dokumen QA berisi histori atau rencana sampai dibuktikan dengan run terbaru | PRD tidak boleh menyatakan test lulus tanpa evidence |

### 2.3 Need Confirmation

| ID | Keputusan yang dibutuhkan | Dampak |
| --- | --- | --- |
| CONF-001 | Apakah multi-tenant menjadi target produk, dan kapan? | Mengubah IAM, PLT, database isolation, onboarding, dan deployment |
| CONF-002 | Apakah Goods Issue masuk Phase 2? Apa tujuan, approval, dan statusnya? | Menambah movement type, permission, workflow, dan audit |
| CONF-003 | Laporan mana yang wajib dan kapan? | Menentukan RPT, query, export, dan acceptance criteria |
| CONF-004 | Apakah satu item boleh muncul satu kali pada Transfer? | Constraint data dan TRF-BR01 |
| CONF-005 | Apakah `INTERNAL_ERROR` merupakan kode error resmi? | API error catalog |
| CONF-006 | Apakah master data, warehouse, location, numbering, dan search memerlukan AC terpisah? | QA scope dan release gate |
| CONF-007 | Dataset dan environment benchmark final | NFR performance dan release evidence |
| CONF-008 | Strategi penyimpanan refresh token pada consumer frontend | Security integration, bukan perubahan business requirement |

## 3. Modularization Analysis

### 3.1 Ownership

Setiap modul memiliki satu tanggung jawab utama, data owner, permission owner, dan
kontrak publik. Modul tidak menulis tabel milik modul lain secara langsung.

| Modul | Tanggung jawab | Tidak bertanggung jawab atas |
| --- | --- | --- |
| PLT | Kapabilitas teknis lintas modul | Aturan bisnis gudang |
| IAM | Identitas, permission, role, dan scoping | Menentukan gudang dokumen yang harus dicek |
| AUD | Append-only audit trail | Menentukan apakah aksi bisnis valid |
| MST | Katalog item, UoM, kategori, supplier | Saldo dan status transaksi |
| WHS | Struktur gudang dan lokasi | Movement dan opname state |
| INV | Saldo, ledger, dan movement gateway | Lifecycle dokumen pemicu |
| PUR | PO dan fulfillment | Menambah saldo langsung |
| RCV | GR dan posting penerimaan | Mengubah PO di luar contract |
| TRF | Transfer lifecycle dan in-transit | Mengubah saldo di luar INV |
| OPN | Snapshot, freeze, count, adjustment | Operasi GR/transfer |
| TNT/CFG | Draft future untuk tenant dan configuration | Scope MVP sebelum dikonfirmasi |

### 3.2 Dependency dan contract

Status: register normatif dan batas ownership telah dipindahkan ke bagian 4.3
PRD General. Daftar berikut menjadi ringkasan audit dan harus tetap sinkron dengan
register tersebut.

Urutan dependency MVP:

```text
PLT
  -> IAM + AUD
  -> MST + WHS
  -> INV
  -> PUR + RCV
  -> TRF
  -> OPN
```

Kontrak penting:

| Contract | Owner | Consumer | Jenis |
| --- | --- | --- | --- |
| `authorize` dan `ensure_warehouse_access` | IAM | Semua modul | Cross-layer |
| `record` | AUD | Semua modul yang mengubah data | Write |
| `next_number` | PLT | PUR, RCV, TRF, OPN | Write |
| `apply_movement` | INV | RCV, TRF, OPN | Write |
| `apply_receipt` | PUR | RCV | Write |
| `is_location_frozen` | OPN | INV dan pemicu movement | Read |
| `validate_location` | WHS | INV, RCV, TRF, OPN | Read |
| `gr_status_summary` | RCV | PUR | Read |
| `in_transit` | TRF | INV | Read |

### 3.3 Tumpang tindih yang harus dihindari

- IAM memeriksa permission dan assignment, sedangkan RCV/TRF/OPN menentukan gudang
  bisnis yang harus diperiksa.
- OPN menentukan status pembekuan, sedangkan INV menolak movement non-adjustment.
- INV satu-satunya owner saldo dan ledger; RCV, TRF, OPN hanya pemicu melalui contract.
- PUR owner PO dan `qty_received`; RCV hanya memanggil `apply_receipt`.
- AUD menerima event; modul pemilik perubahan menentukan kapan event dibuat.

## 4. Rekomendasi PRD Architecture

PRD General baru menggunakan urutan tetap:

1. Metadata, status, dan source of truth.
2. Tujuan, pengguna, dan scope per fase.
3. Modul dan dependency.
4. Global business rules.
5. Spesifikasi per modul.
6. End-to-end workflow.
7. Conceptual data requirements.
8. Non-functional requirements.
9. Acceptance criteria.
10. RTM lintas layer.
11. Prioritas, change impact, assumptions, dan open questions.

Template setiap modul wajib memuat: tujuan, Feature ID, requirements, business rules,
workflow/state, data requirements, permission, dependencies/contracts, API behavior
level produk, acceptance criteria, priority, dan evidence status.

## 5. Mapping Requirement Lama

| Requirement lama | Feature/module baru | Status |
| --- | --- | --- |
| FR-01 | IAM-F01 sampai IAM-F09, PLT-F04, AUD-F01 | Mapped |
| FR-02 | MST-F01 sampai MST-F05, WHS-F01 sampai WHS-F03 | Mapped |
| FR-03 | INV-F01 sampai INV-F03, OPN-F05, TRF-F05 | Mapped |
| FR-04 | PUR-F01 sampai PUR-F04 | Mapped |
| FR-05 | RCV-F01 sampai RCV-F04 | Mapped |
| FR-06 | TRF-F01 sampai TRF-F05 | Mapped |
| FR-07 | OPN-F01 sampai OPN-F06 | Mapped |
| FR-08 | INV-F03 sampai INV-F05 | Mapped |
| FR-09 | AUD-F01 sampai AUD-F02 | Mapped |
| FR-10 | PLT-F01 | Mapped |
| FR-11 | PLT-F02 | Mapped |
| v2.0 AC-01, AC-07, AC-13 | RCV | Mapped |
| v2.0 AC-02, AC-03, AC-06, AC-09 | TRF | Mapped |
| v2.0 AC-04, AC-10 | OPN | Mapped |
| v2.0 AC-05, AC-11, AC-12, AC-14 | IAM | Mapped |
| v2.0 AC-08 | INV/AUD | Mapped |
| Draft v3.x TNT/CFG/AC-15 sampai AC-21 | TNT/CFG Future Development | Need Confirmation |

## 6. Cross-Layer Validation

| Kebutuhan | Database | Backend | Frontend | API | QA |
| --- | --- | --- | --- | --- | --- |
| Auth/RBAC/scoping | users, roles, permissions, refresh_tokens, user_warehouses | auth, dependency, access service | login, session, permission-aware navigation | auth, users, menus | auth, RBAC, scoping |
| Master/Warehouse | master, warehouses, locations | master and warehouse services | master and warehouse screens | CRUD/list endpoints | validation, deactivate, permission |
| Inventory | balances, movements | movement gateway, stock queries | stock and ledger views | stock list and movement endpoints | concurrency, negative stock, immutability |
| PO/GR | PO, PO lines, GR, GR lines | PO and GR transactions | PO and receiving workflow | PO/GR action endpoints | over-receipt, atomicity |
| Transfer | transfer headers and lines | approve/ship/receive transactions | transfer workflow | action endpoints | in-transit, variance, concurrency |
| Opname | opname headers and lines | snapshot/freeze/count/approval | counting and approval flow | action endpoints | freeze and adjustment |
| Audit/platform | audit logs, sequences, migrations | audit and numbering service | audit viewer where applicable | audit and health endpoints | append-only and request ID |

Frontend pages and API paths are integration targets, not claims that frontend is
implemented in this repository. Database column types, indexes, migration order,
and Python layer constraints remain in their specialized specifications.

## 7. Final Validation Report

| Check | Result | Evidence or limitation |
| --- | --- | --- |
| Semua modul lama terinventarisasi | PASS | Katalog modul pada bagian 1 dan PRD General |
| Requirement lama memiliki mapping | PASS | Mapping FR dan AC pada bagian 5 |
| MVP dan future dipisahkan | PASS | Scope dan roadmap PRD General |
| Feature ID unik dan stabil | PASS | Registry feature ID pada PRD General |
| Requirement penting memiliki ID | PASS | FR, BR, NFR, AC pada PRD General |
| Setiap modul memiliki format standar | PASS | Template dan spesifikasi modul |
| Setiap feature memiliki AC atau status gap | PASS | AC module tables; gap diberi Need Confirmation |
| Konflik tidak disembunyikan | PASS | CON-001 sampai CON-007 |
| RTM tersedia tanpa klaim implementasi palsu | PASS | RTM memakai status evidence |
| Database/backend/frontend/API/QA terhubung | PASS | Cross-Layer Validation |
| Tidak ada business rule baru yang tidak bersumber | PASS | Future items diberi Need Confirmation |
| Implemented/tested/verified didukung bukti run | NOT CLAIMED | PRD hanya menggunakan status Mapped/Need Confirmation; test run terpisah |
| Semua keputusan bisnis final | NOT COMPLETE | CONF-001 sampai CONF-008 masih membutuhkan pemilik produk |

## 8. Change Impact Procedure

Setiap perubahan requirement wajib:

1. mempertahankan ID lama atau membuat ID baru, tanpa reuse;
2. memperbarui Feature Registry, requirement, business rule, workflow, dan AC;
3. memperbarui RTM untuk database, backend, frontend, API, dan QA;
4. menilai dependency dan regression pada modul consumer;
5. menandai status menjadi `Need Confirmation` bila keputusan bisnis berubah;
6. memperbarui dokumen layer hanya setelah requirement PRD General disetujui.
