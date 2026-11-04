# Review Menyeluruh Dokumen PRD, Skema Database, Backend, Frontend, dan Arsitektur Sistem (JejakStok WMS)

**Tanggal Review:** 3 November 2026
**Cakupan Analisis:**
- `AGENTS.MD` (Aturan tata kelola repositori)
- `PRD v2.0 legacy yang telah diintegrasikan ke docs/CORE/PRD_GENERAL.md` (PRD v2.0 — Single-Tenant)
- `docs/CORE/PRD JejakStok - Sistem Manajemen Gudang (Modular).md` (PRD Modular v3.1 Draf — Multi-Tenant SaaS)
- `docs/CORE/SCHEMA_DATABASE.MD` (Dokumentasi Skema Database v2.0)
- `docs/CORE/FOLDER_STRUCTURE.MD` (Arsitektur & Struktur Direktori Backend)
- `docs/CORE/CATATAN_PERMASALAHAN_ADMIN.md` (Catatan Integrasi Frontend Admin & Menu Navigasi)
- `docs/API/README.md` & `docs/QA/QA.MD` (Indeks Kontrak API, Hasil Benchmark M8, dan Panduan QA)
- `db/migrations/001_create_auth_tables.sql` s.d. `009_create_menu_tables.sql`
- Implementasi Kode Sumber Backend (`app/main.py`, `app/core/`, `app/api/`, `app/services/`, `app/repositories/`, `app/schemas/`)

---

## Daftar Isi

1. [Ringkasan Eksekutif Berdasarkan 6 Aspek Review](#1-ringkasan-eksekutif-berdasarkan-6-aspek-review)
2. [Bagian I — Temuan Aktual (Verified Findings)](#2-bagian-i--temuan-aktual-verified-findings)
   - [VF-01: Dualisme Sumber Kebenaran antara PRD v2.0 (Single-Tenant) dan PRD Modular v3.1 (Multi-Tenant SaaS)](#vf-01-dualisme-sumber-kebenaran-antara-prd-v20-single-tenant-dan-prd-modular-v31-multi-tenant-saas)
   - [VF-02: Kendala Teknis Migrasi Multi-Tenant (`011_add_tenant_scope.sql`) pada Composite FK, Unique Constraint, dan Trigger Imutabilitas](#vf-02-kendala-teknis-migrasi-multi-tenant-011_add_tenant_scopesql-pada-composite-fk-unique-constraint-dan-trigger-imutabilitas)
   - [VF-03: Risiko Kebocoran Konteks Tenant (`current_tenant()`) dan Kegagalan RLS pada Connection Pool `autocommit=True`](#vf-03-risiko-kebocoran-konteks-tenant-current_tenant-dan-kegagalan-rls-pada-connection-pool-autocommittrue)
   - [VF-04: Dokumen Rujukan Frontend (`PRD_FRONTEND.md` & `FOLDER_STRUCTURE.md` Frontend) Tidak Ditemukan di Repositori](#vf-04-dokumen-rujukan-frontend-prd_frontendmd--folder_structuremd-frontend-tidak-ditemukan-di-repositori)
   - [VF-05: Ketidaksesuaian Kontrak JSON Menu (`short_name`) dan Allowlist Icon antara `CATATAN_PERMASALAHAN_ADMIN.md`, `009_create_menu_tables.sql`, dan `app/schemas/menu.py`](#vf-05-ketidaksesuaian-kontrak-json-menu-short_name-dan-allowlist-icon-antara-catatan_permasalahan_adminmd-009_create_menu_tablessql-dan-appschemasmenupy)
   - [VF-06: Celah Aturan Bisnis pada Perubahan `uoms.allow_decimal` (`TRUE` ke `FALSE`) Setelah Barang Memiliki Saldo atau Transaksi Pecahan](#vf-06-celah-aturan-bisnis-pada-perubahan-uomsallow_decimal-true-ke-false-setelah-barang-memiliki-saldo-atau-transaksi-pecahan)
   - [VF-07: Ketidakselarasan Batas Kontrak Antarmodul (`BND-02` & `BND-03`) dan Penamaan File Route di PRD Modular v3.1 dengan Implementasi Aktual](#vf-07-ketidakselarasan-batas-kontrak-antarmodul-bnd-02--bnd-03-dan-penamaan-file-route-di-prd-modular-v31-dengan-implementasi-aktual)
   - [VF-08: Celah Validasi Status Aktif Referensi (`GBR-11`) pada Transisi `approve_transfer`, `receive_transfer`, dan `post_goods_receipt`](#vf-08-celah-validasi-status-aktif-referensi-gbr-11-pada-transisi-approve_transfer-receive_transfer-dan-post_goods_receipt)
   - [VF-09: Ketidaksesuaian Urutan Tahapan Pengembangan (Roadmap Fase 0–7 di PRD Modular v3.1) terhadap Status Implementasi Eksisting (M0–M8 Selesai)](#vf-09-ketidaksesuaian-urutan-tahapan-pengembangan-roadmap-fase-07-di-prd-modular-v31-terhadap-status-implementasi-eksisting-m0m8-selesai)
   - [VF-10: Risiko Rework Skema Inti pada Urutan Pengembangan Pasca-MVP (`P1` Goods Issue & Pelaporan Sebelum `P2` Lot/Serial/Lokasi Hierarkis)](#vf-10-risiko-rework-skema-inti-pada-urutan-pengembangan-pasca-mvp-p1-goods-issue--pelaporan-sebelum-p2-lotseriallokasi-hierarkis)
   - [VF-11: Inkonsistensi Dokumentasi Penempatan Tabel `user_warehouses`, Kode Error `INTERNAL_ERROR`, dan Keunikan Baris Transfer](#vf-11-inkonsistensi-dokumentasi-penempatan-tabel-user_warehouses-kode-error-internal_error-dan-keunikan-baris-transfer)
   - [VF-12: Beban Eksekusi Ganda CTE `FULL OUTER JOIN` dan Ketiadaan Partial Index *In-Transit* pada Query Stok & Ledger](#vf-12-beban-eksekusi-ganda-cte-full-outer-join-dan-ketiadaan-partial-index-in-transit-pada-query-stok--ledger)
3. [Bagian II — Asumsi (Assumptions — Need Confirmation)](#3-bagian-ii--asumsi-assumptions--need-confirmation)
   - [AS-01: Penetapan Dokumen Sumber Kebenaran Utama (`PRD Modular v3.1` vs `PRD v2.0`) pada `AGENTS.MD`](#as-01-penetapan-dokumen-sumber-kebenaran-utama-prd-modular-v31-vs-prd-v20-pada-agentsmd)
   - [AS-02: Mekanisme Login Platform Admin, Skema Kuota Paket (`plans`), dan Kebijakan *Impersonation* (`OQ-11` s.d. `OQ-17`)](#as-02-mekanisme-login-platform-admin-skema-kuota-paket-plans-dan-kebijakan-impersonation-oq-11-sd-oq-17)
   - [AS-03: Spesifikasi Siklus Hidup, Aturan Bisnis, dan Skema Modul Usulan `ISS` (Goods Issue) dan `RPT` (Pelaporan) (`OQ-02`)](#as-03-spesifikasi-siklus-hidup-aturan-bisnis-dan-skema-modul-usulan-iss-goods-issue-dan-rpt-pelaporan-oq-02)
   - [AS-04: Pemisahan Repositori Frontend dan Strategi Penyimpanan Refresh Token (`JSON Body / localStorage` vs `HttpOnly Cookie`)](#as-04-pemisahan-repositori-frontend-dan-strategi-penyimpanan-refresh-token-json-body--localstorage-vs-httponly-cookie)
   - [AS-05: Perlakuan Sesi Aktif Saat Pengguna Ditugaskan/Dicabut dari Gudang (`OQ-01`) dan Detail Perubahan Nilai Audit Log (`OQ-03`)](#as-05-perlakuan-sesi-aktif-saat-pengguna-ditugaskanDicabut-dari-gudang-oq-01-dan-detail-perubahan-nilai-audit-log-oq-03)
4. [Bagian III — Pemisahan Rekomendasi & Usulan Tahapan Pengembangan](#4-bagian-iii--pemisahan-rekomendasi--usulan-tahapan-pengembangan)
   - [4.1. Rekomendasi yang Dapat Langsung Dilakukan (Immediate Actions)](#41-rekomendasi-yang-dapat-langsung-dilakukan-immediate-actions)
   - [4.2. Rekomendasi yang Membutuhkan Konfirmasi Terlebih Dahulu (Pending Confirmation)](#42-rekomendasi-yang-membutuhkan-konfirmasi-terlebih-dahulu-pending-confirmation)
   - [4.3. Usulan Perbaikan Tahapan Pengembangan Fitur (Revised Roadmap)](#43-usulan-perbaikan-tahapan-pengembangan-fitur-revised-roadmap)

---

## 1. Ringkasan Eksekutif Berdasarkan 6 Aspek Review

| No | Aspek Review | Ringkasan Evaluasi | Temuan Terkait |
|---|---|---|---|
| 1 | **Kelengkapan Informasi PRD** | PRD v2.0 (`PRD v2.0 legacy`) sudah sangat lengkap untuk cakupan MVP Single-Tenant dan telah diimplementasikan 100% (M0–M8). Namun, PRD Modular v3.1 (`PRD JejakStok - Sistem Manajemen Gudang (Modular).md`) menambahkan cakupan Multi-Tenant (`TNT`, `CFG`) sebagai MVP dan dua modul usulan (`ISS`, `RPT`) yang masih menyisakan **17 pertanyaan terbuka (`OQ-01` s.d. `OQ-17`)**, kontradiksi metrik `SM-04` ("AC-01 sampai AC-21: Target 14 dari 14"), serta merujuk dokumen `PRD_FRONTEND.md` yang tidak ada di repositori. | `VF-01`, `VF-04`, `VF-11`, `AS-01`, `AS-02`, `AS-03`, `AS-05` |
| 2 | **Konsistensi Database** | Skema database saat ini (`001`–`009` dan `SCHEMA_DATABASE.MD` v2.0) konsisten dengan PRD v2.0. Namun, rancangan migrasi multi-tenant di PRD Modular v3.1 (`010_create_tenants_settings.sql` dan `011_add_tenant_scope.sql`) memiliki hambatan teknis nyata: (a) *Composite FK* `(tenant_id, id)` membutuhkan `UNIQUE (tenant_id, id)` di semua tabel induk, (b) seluruh constraint unik eksisting masih global (bukan per-tenant), dan (c) *backfill* `UPDATE` kolom `tenant_id` pada `stock_movements` dan `audit_logs` akan diblokir oleh trigger imutabilitas `007_append_only_guards.sql` kecuali trigger dinonaktifkan sementara. | `VF-02`, `VF-03`, `VF-12` |
| 3 | **Kesesuaian Backend dan Frontend** | Terdapat perbedaan kontrak JSON menu dan daftar nama icon Lucide antara `docs/CORE/CATATAN_PERMASALAHAN_ADMIN.md` dengan migrasi `db/migrations/009_create_menu_tables.sql` dan `app/schemas/menu.py`. Selain itu, perubahan kontrak `POST /api/v1/auth/login` di PRD Modular v3.1 yang mewajibkan `slug` tenant berpotensi memutus kompatibilitas dengan aplikasi frontend jika tidak dikoordinasikan. | `VF-04`, `VF-05`, `AS-04` |
| 4 | **Konsistensi Arsitektur Sistem** | Arsitektur berlapis (`routes -> services -> repositories -> core`) pada kode `app/` sudah rapi dan patuh pada `AGENTS.MD`. Namun, terdapat ketidakselarasan dengan PRD Modular v3.1 terkait: (a) cara injeksi `app.current_tenant_id` untuk PostgreSQL RLS pada `ConnectionPool` yang memakai `autocommit=True`, (b) aturan batas kontrak antarmodul (`BND-02`/`BND-03`) yang jika dipaksakan di level service akan merusak efisiensi query JOIN/CTE di repository, dan (c) penamaan file route di peta kode PRD Modular. | `VF-03`, `VF-07` |
| 5 | **Tahapan Pengembangan Fitur** | Roadmap di PRD Modular v3.1 (Fase 0 s.d. Fase 7) disusun seolah-olah sistem belum dibangun (menempatkan `tenant_id` di Fase 0 sebelum modul bisnis di Fase 3–6), padahal implementasi aktual sudah menyelesaikan **M0 s.d. M8** (87 endpoint, migrasi `001`–`009` terpasang dan bersifat *forward-only*). Selain itu, penempatan `P1` (`ISS` Goods Issue & `RPT` Pelaporan) sebelum keputusan struktur kunci saldo di `P2` (Lot/Batch/Expiry/Serial/Hierarki Lokasi) berisiko menimbulkan *rework* besar pada tabel saldo dan ledger. | `VF-09`, `VF-10` |
| 6 | **Identifikasi Gap dan Risiko** | Ditemukan celah aturan bisnis pada `master_service.update_uom` (mengizinkan perubahan `allow_decimal` dari `TRUE` ke `FALSE` saat barang sudah memiliki saldo/transaksi desimal sehingga stok pecahan terkunci) dan ketidakkonsistenan pemeriksaan status aktif referensi (`GBR-11`) pada transisi dokumen bertahap (`approve_transfer`, `receive_transfer`, `post_goods_receipt`). | `VF-06`, `VF-08`, `VF-12` |

---

## 2. Bagian I — Temuan Aktual (Verified Findings)

Seluruh temuan pada bagian ini didasarkan pada bukti nyata yang dapat diverifikasi langsung pada dokumen di `docs/`, skema SQL di `db/migrations/`, maupun kode sumber di `app/`.

---

### VF-01: Dualisme Sumber Kebenaran antara PRD v2.0 (Single-Tenant) dan PRD Modular v3.1 (Multi-Tenant SaaS)

| Aspek | Keterangan |
|---|---|
| Kategori | Temuan Aktual |
| Area | PRD / Database / Backend / Arsitektur |
| Referensi | 1. `AGENTS.MD` (Bagian 1: *Sumber Kebenaran*, Bagian 3: *Batas Lingkup*)<br>2. `PRD v2.0 legacy yang telah diintegrasikan ke docs/CORE/PRD_GENERAL.md` (v2.0, Single-Tenant)<br>3. `docs/CORE/PRD JejakStok - Sistem Manajemen Gudang (Modular).md` (v3.1 Draf, Multi-Tenant SaaS: `G-05`, `GBR-16` s.d. `GBR-18`, `BND-07`, Modul `TNT` & `CFG`, `SM-04`, `AC-15` s.d. `AC-21`)<br>4. `docs/CORE/SCHEMA_DATABASE.MD` (v2.0) |
| Deskripsi | **Kondisi Saat Ini:**<br>Di dalam direktori `docs/CORE/` terdapat dua dokumen PRD berbeda:<br>1. `PRD v2.0 legacy` (v2.0) yang mendefinisikan sistem *single-tenant* dengan 14 Acceptance Criteria (`AC-01` s.d. `AC-14`) dan 9 berkas migrasi (`001` s.d. `009`). Seluruh kode di `app/`, `db/migrations/`, `docs/CORE/SCHEMA_DATABASE.MD`, dan `docs/API/README.md` saat ini selaras 100% dengan PRD v2.0 ini.<br>2. `PRD JejakStok - Sistem Manajemen Gudang (Modular).md` (v3.1 Draf) yang mengubah arsitektur dasar menjadi **Multi-Tenant SaaS** dengan menambahkan modul `TNT` (Manajemen Tenant & Langganan) dan `CFG` (Konfigurasi Tenant) ke dalam lingkup **MVP**, mewajibkan kolom `tenant_id` di semua tabel bisnis (`GBR-16`), mengubah kontrak login menjadi wajib menyertakan `slug` tenant (`IAM-BR17`), serta menambah `AC-15` s.d. `AC-21` dan migrasi `010`–`011`.<br><br>**Masalah yang Ditemukan:**<br>- `AGENTS.MD` Bagian 1 masih mengunci `docs/core/PRODUCT_REQUIREMENTS_DOCUMENT.md` sebagai rujukan nomor 1 dan melarang penambahan endpoint/tabel/kolom di luar dokumen tersebut.<br>- Pada `PRD JejakStok - Sistem Manajemen Gudang (Modular).md` tabel **Ukuran Keberhasilan** baris `SM-04` tertulis: *"Kriteria penerimaan AC-01 sampai AC-21 lulus pada PostgreSQL sungguhan — Target: **14 dari 14**"* (angka target `14 dari 14` belum diperbarui menjadi `21 dari 21`).<br>- `SCHEMA_DATABASE.MD` masih berada pada versi 2.0 (hanya memuat 22 tabel dari migrasi `001`–`009`) dan belum mencerminkan tabel `tenants`, `plans`, `platform_admins`, `settings`, maupun kolom `tenant_id` dari PRD Modular v3.1. |
| Dampak | - Pengembang maupun AI Coding Agent mengalami konflik aturan kerja: mengikuti `PRD v2.0 legacy` (sesuai `AGENTS.MD`) berarti mengabaikan seluruh spesifikasi Multi-Tenant di PRD Modular v3.1; sebaliknya, mengimplementasikan PRD Modular v3.1 tanpa memperbarui `AGENTS.MD` dan `SCHEMA_DATABASE.MD` akan melanggar aturan tata kelola repositori.<br>- Kesalahan angka target pada `SM-04` (`14 dari 14` untuk `AC-01` s.d. `AC-21`) menimbulkan ambiguitas kriteria kelulusan QA. |
| Rekomendasi | 1. Perbaiki redaksi `SM-04` pada `PRD JejakStok - Sistem Manajemen Gudang (Modular).md` dari `14 dari 14` menjadi `21 dari 21`.<br>2. Tetapkan secara eksplisit di `AGENTS.MD` Bagian 1 dokumen mana yang menjadi sumber kebenaran aktif (misalnya menetapkan PRDv2.0 sebagai baseline *Phase 1 / Single-Tenant Completed* dan PRD Modular v3.1 sebagai baseline *Phase 2 / Multi-Tenant Upgrade*).<br>3. Sinkronkan `docs/CORE/SCHEMA_DATABASE.MD` ke versi 3.1 setelah keputusan desain Multi-Tenant (`OQ-11` s.d. `OQ-17`) disetujui. |
| Prioritas | **Critical** |
| Status Validasi | **Verified** |

---

### VF-02: Kendala Teknis Migrasi Multi-Tenant (`011_add_tenant_scope.sql`) pada Composite FK, Unique Constraint, dan Trigger Imutabilitas

| Aspek | Keterangan |
|---|---|
| Kategori | Temuan Aktual |
| Area | Database / PRD |
| Referensi | 1. `docs/CORE/PRD JejakStok - Sistem Manajemen Gudang (Modular).md` (`GBR-16`, `GBR-18`, `PLT-BR03`, `Model Data Konseptual`, rencana migrasi `010_create_tenants_settings.sql` & `011_add_tenant_scope.sql`)<br>2. `docs/CORE/SCHEMA_DATABASE.MD` (Bagian 5.1 s.d. 5.9)<br>3. `db/migrations/001_create_auth_tables.sql` s.d. `007_append_only_guards.sql` |
| Deskripsi | **Kondisi Saat Ini:**<br>PRD Modular v3.1 (`GBR-16`, `GBR-18`, dan bagian *Model Data Konseptual*) mengamanatkan bahwa seluruh tabel bisnis существующий (dari migrasi `001`–`008`) ditambahkan kolom `tenant_id` melalui migrasi *forward-only* `011_add_tenant_scope.sql`, dengan ketentuan:<br>- Setiap Foreign Key (FK) antar-entitas milik tenant **wajib komposit** `(tenant_id, xxx_id)` (`GBR-16`).<br>- Keunikan kode master, nomor dokumen, urutan penomoran, serta username/email pengguna berlaku **per tenant** `(tenant_id, ...)` (`GBR-18`).<br>- Migrasi yang sudah diterapkan (`001`–`009`) **tidak boleh diedit** (`PLT-BR03` & `AGENTS.MD` Bagian 7).<br><br>**Masalah yang Ditemukan:**<br>1. **Prasyarat `UNIQUE (tenant_id, id)` untuk Composite FK:** Di PostgreSQL, sebuah tabel anak tidak dapat mendefinisikan `FOREIGN KEY (tenant_id, item_id) REFERENCES items (tenant_id, id)` kecuali tabel induk (`items`, `warehouses`, `locations`, `suppliers`, `categories`, `uoms`, `users`, `roles`, `purchase_orders`, `po_lines`, `goods_receipts`, `stock_transfers`, `stock_opnames`) memiliki constraint `UNIQUE (tenant_id, id)` atau `PRIMARY KEY (tenant_id, id)`. Saat ini PK seluruh tabel tersebut hanya `(id)` (kecuali `locations` yang sudah memiliki `uq_locations_id_warehouse (id, warehouse_id)`). Rencana migrasi `011_add_tenant_scope.sql` di PRD Modular belum mencantumkan kewajiban membuat `UNIQUE (tenant_id, id)` pada semua tabel induk sebelum mengganti FK.<br>2. **Blokir Trigger Imutabilitas saat Backfill `011_add_tenant_scope.sql`:** Migrasi `007_append_only_guards.sql` telah memasang trigger `trg_stock_movements_immutable` pada `stock_movements` dan `trg_audit_logs_immutable` pada `audit_logs` yang menolak setiap perintah `UPDATE` (`RAISE EXCEPTION ... USING ERRCODE = '42501'`). Apabila migrasi `011_add_tenant_scope.sql` menambahkan kolom `tenant_id` lalu menjalankan `UPDATE stock_movements SET tenant_id = ...` dan `UPDATE audit_logs SET tenant_id = ...` untuk mengisi data tenant default sebelum memasang `SET NOT NULL`, **migrasi `011` akan gagal total karena ditolak oleh trigger `007`**.<br>3. **Penggantian Seluruh Constraint Unique & PK Eksisting:** Terdapat 14 constraint unik/PK global dari migrasi `001`–`005` yang harus di-`DROP` dan dibuat ulang menjadi komposit per-tenant di migrasi `011`: `uq_roles_name`, `uq_users_username`, `uq_users_email`, `uq_categories_name`, `uq_uoms_code`, `uq_suppliers_code`, `uq_items_sku`, `uq_warehouses_code`, `uq_purchase_orders_po_number`, `uq_goods_receipts_gr_number`, `uq_stock_transfers_transfer_number`, `uq_stock_opnames_opname_number`, dan `pk_document_sequences (doc_type, period)` -> `(tenant_id, doc_type, period)`. |
| Dampak | Jika spesifikasi teknis migrasi `011_add_tenant_scope.sql` tidak merinci ketiga langkah di atas di dalam dokumen PRD dan `SCHEMA_DATABASE.MD`, eksekusi migrasi `011` pada database eksisting akan gagal dengan error PostgreSQL (`42830: there is no unique constraint matching given keys for referenced table` dan `42501: Append-only table`). |
| Rekomendasi | Lengkapi spesifikasi migrasi `011_add_tenant_scope.sql` pada PRD Modular v3.1 dan `SCHEMA_DATABASE.MD` dengan urutan operasi eksplisit:<br>1. `ALTER TABLE stock_movements DISABLE TRIGGER trg_stock_movements_immutable;` dan `ALTER TABLE audit_logs DISABLE TRIGGER trg_audit_logs_immutable;` sebelum *backfill* `tenant_id`, lalu `ENABLE TRIGGER` kembali di akhir transaksi migrasi.<br>2. Tambahkan `CONSTRAINT uq_<table>_tenant_id UNIQUE (tenant_id, id)` pada seluruh tabel induk sebelum mengganti FK tunggal menjadi *Composite FK* `(tenant_id, <fk>_id)`.<br>3. Cantumkan daftar eksplisit 14 constraint `UNIQUE`/`PK` global yang wajib di-`DROP` dan dibuat ulang dengan awalan `tenant_id`. |
| Prioritas | **High** |
| Status Validasi | **Verified** |

---

### VF-03: Risiko Kebocoran Konteks Tenant (`current_tenant()`) dan Kegagalan RLS pada Connection Pool `autocommit=True`

| Aspek | Keterangan |
|---|---|
| Kategori | Temuan Aktual |
| Area | Arsitektur / Database / Backend |
| Referensi | 1. `docs/CORE/PRD JejakStok - Sistem Manajemen Gudang (Modular).md` (`GBR-16`, `NFR-08`, Kontrak Antarmodul: `current_tenant()`, `IAM-BR17`, `IAM-BR18`)<br>2. `docs/CORE/FOLDER_STRUCTURE.MD` (Bagian 3: *Pola Koneksi & Transaksi*)<br>3. `app/core/database.py` & `app/api/deps.py` (`get_db`, `get_current_user`)<br>4. `app/services/auth_service.py` (`login`, `refresh_session`) |
| Deskripsi | **Kondisi Saat Ini:**<br>- Berdasarkan `FOLDER_STRUCTURE.MD` Bagian 3 dan implementasi `app/core/database.py`, `ConnectionPool` (`psycopg_pool`) dikonfigurasi dengan `autocommit=True`.<br>- Seluruh endpoint pembacaan (`GET`) serta dependency autentikasi `get_current_user` (`app/api/deps.py` baris 42–81) mengeksekusi query `SELECT` **langsung pada koneksi `autocommit=True` tanpa membuka blok `with conn.transaction():`**.<br>- Sementara itu, PRD Modular v3.1 (`GBR-16` dan `NFR-08`) mewajibkan PostgreSQL **Row Level Security (`ENABLE` & `FORCE ROW LEVEL SECURITY`)** pada seluruh tabel bisnis menggunakan variabel sesi database (umumnya `current_setting('app.current_tenant_id')`).<br><br>**Masalah yang Ditemukan:**<br>1. **Masalah `SET LOCAL` vs `SET` pada Connection Pool `autocommit=True`:**<br>   - Jika menggunakan `SET LOCAL app.current_tenant_id = '<id>'`, perintah ini di PostgreSQL **hanya berlaku di dalam blok transaksi (`BEGIN ... COMMIT`)**. Pada koneksi `autocommit=True` di luar `with conn.transaction():`, `SET LOCAL` langsung hilang setelah statement `SET LOCAL` itu sendiri selesai, sehingga seluruh query `SELECT` pada endpoint `GET` (dan `get_current_user`) akan melihat `app.current_tenant_id` kosong dan ditolak oleh RLS!<br>   - Sebaliknya, jika menggunakan `SET app.current_tenant_id = '<id>'` (level sesi), nilai tersebut akan menempel pada koneksi di dalam pool. Jika request berikutnya meminjam koneksi yang sama dari `ConnectionPool` (misalnya endpoint publik atau admin platform) dan gagal me-reset variabel tersebut, terjadi **kebocoran data lintas tenant (*session variable bleed*)**.<br>2. **Deadlock Konteks RLS saat Login (`POST /auth/login`) dan Refresh Token (`POST /auth/refresh`):**<br>   - Pada saat `POST /api/v1/auth/login`, pengguna belum memiliki JWT (`current_tenant()` belum bisa membaca klaim `tenant_id` dari token), melainkan baru mengirimkan `slug` tenant di body request (`IAM-BR17`).<br>   - Pada saat `POST /api/v1/auth/refresh`, klien hanya mengirimkan `refresh_token` mentah tanpa `slug` maupun access token. Jika tabel `refresh_tokens` dan `users` dipasangi `FORCE ROW LEVEL SECURITY` (`NFR-08`), maka query `get_refresh_token_by_hash` di `auth_service.refresh_session` tidak dapat menemukan baris token karena `tenant_id` belum diketahui sebelum baris `refresh_tokens` itu sendiri dibaca! |
| Dampak | - Kegagalan seluruh operasi baca (`GET`) akibat `SET LOCAL` tidak bertahan pada mode `autocommit=True`.<br>- Kegagalan proses `POST /api/v1/auth/refresh` karena *chicken-and-egg problem* antara pencarian `token_hash` dan kebijakan RLS pada tabel `refresh_tokens`.<br>- Risiko kritikal kebocoran data antar-tenant jika variabel sesi PostgreSQL tidak dibersihkan (`RESET app.current_tenant_id` / `DISCARD ALL`) saat koneksi dikembalikan ke `psycopg_pool`. |
| Rekomendasi | Definisikan secara eksplisit arsitektur propagasi konteks tenant di PRD Modular v3.1 (`Bagian PLT / Kontrak current_tenant()`) dan `FOLDER_STRUCTURE.MD`:<br>1. **Manajemen Koneksi Pool:** Gunakan `SET app.current_tenant_id = %s` pada saat konteks tenant diaktifkan di `deps.py`, **DAN wajib** pasang callback `reset` pada `ConnectionPool(..., reset=...)` (atau di blok `finally` pada `get_db()`) yang mengeksekusi `RESET app.current_tenant_id; RESET app.current_scope;` sebelum koneksi kembali ke pool.<br>2. **Resolusi Konteks Pra-Autentikasi:**<br>   - Untuk `POST /auth/login`: fungsi service terlebih dahulu melakukan query ke tabel `tenants` (yang tidak dibatasi RLS tenant, atau dibaca berdasarkan `slug`) untuk mendapatkan `tenant.id` dan memverifikasi `status == 'ACTIVE'`, lalu meng-set `app.current_tenant_id` pada koneksi sebelum mencari `users`.<br>   - Untuk `POST /auth/refresh`: izinkan pencocokan `token_hash` pada `refresh_tokens` (atau sertakan `tenant_id` / gunakan fungsi `SECURITY DEFINER` terbatas untuk resolusi `token_hash -> tenant_id`) sebelum mengaktifkan konteks RLS tenant untuk memuat data `users`. |
| Prioritas | **High** |
| Status Validasi | **Verified** |

---

### VF-04: Dokumen Rujukan Frontend (`PRD_FRONTEND.md` & `FOLDER_STRUCTURE.md` Frontend) Tidak Ditemukan di Repositori

| Aspek | Keterangan |
|---|---|
| Kategori | Temuan Aktual |
| Area | PRD / Frontend |
| Referensi | 1. `docs/CORE/PRD JejakStok - Sistem Manajemen Gudang (Modular).md` (Bagian *Dokumen terkait*, `OOS-10`, `IAM`, `Katalog kode error`, `Peta kebutuhan frontend ke modul (FR-01 s.d. FR-12)`, `RSK-04`, `OQ-07`, `OQ-09`)<br>2. `docs/QA/QA.MD` (Bagian 3.1: merujuk `docs/PRD_FRONTEND.md` dan `docs/FOLDER_STRUCTURE.md`)<br>3. Isi direktori `d:\Training\Python\warehouse_app\docs\` |
| Deskripsi | **Kondisi Saat Ini:**<br>PRD Modular v3.1 dan `docs/QA/QA.MD` secara ekstensif merujuk dokumen bernama `PRD_FRONTEND.md` (termasuk rujukan spesifik ke Bagian 8, Bagian 8.1, Bagian 17, Bagian 17.5, serta kebutuhan `FR-01` s.d. `FR-12`) dan menyebutkan pada `OQ-07` & `OQ-09` adanya dua berkas bernama mirip yaitu `FOLDER_STRUCTURE.md` (frontend) dan `FOLDER_STRUCTURE.MD` (backend).<br><br>**Masalah yang Ditemukan:**<br>Berdasarkan pemeriksaan seluruh pohon direktori di workspace `d:\Training\Python\warehouse_app`, berkas `PRD_FRONTEND.md` maupun `FOLDER_STRUCTURE.md` versi frontend **tidak ada di dalam repositori ini** (yang ada di `docs/CORE/` hanyalah `FOLDER_STRUCTURE.MD` milik backend dan `CATATAN_PERMASALAHAN_ADMIN.md`). |
| Dampak | - Seluruh tautan dan rujukan silang ke `PRD_FRONTEND.md` di dalam PRD Modular v3.1 dan `QA.MD` menjadi referensi terputus (*broken references*).<br>- Spesifikasi detail `FR-01` s.d. `FR-12` milik frontend serta daftar lengkap kode error khusus tampilan (yang disebut di `OQ-05` seperti ` FORBIDDEN `, `NOT_FOUND`, `UNPROCESSABLE_ENTITY`, `RATE_LIMITED`) tidak dapat diverifikasi langsung dari repositori ini. |
| Rekomendasi | 1. Jika dokumen `PRD_FRONTEND.md` dan `FOLDER_STRUCTURE_FRONTEND.md` disimpan di repositori frontend terpisah atau masih berada di penyimpanan lokal penulis, salin/masukkan dokumen tersebut ke dalam `docs/CORE/` (dengan nama yang tidak bentrok, yaitu `docs/CORE/PRD_FRONTEND.MD` dan `docs/CORE/FOLDER_STRUCTURE_FRONTEND.MD`, sekaligus menyelesaikan `OQ-07` dan `OQ-09`).<br>2. Perbarui path rujukan pada `docs/QA/QA.MD` Bagian 3.1 agar menunjuk ke path di dalam `docs/CORE/`. |
| Prioritas | **High** |
| Status Validasi | **Verified** |

---

### VF-05: Ketidaksesuaian Kontrak JSON Menu (`short_name`) dan Allowlist Icon antara `CATATAN_PERMASALAHAN_ADMIN.md`, `009_create_menu_tables.sql`, dan `app/schemas/menu.py`

| Aspek | Keterangan |
|---|---|
| Kategori | Temuan Aktual |
| Area | Backend / Frontend / Database |
| Referensi | 1. `docs/CORE/CATATAN_PERMASALAHAN_ADMIN.md` (Bagian 2 baris 256–315: *Struktur JSON yang disarankan*, baris 416–439: *Contoh enum icon yang disarankan*, Bagian 3.4 baris 573–595)<br>2. `db/migrations/009_create_menu_tables.sql` (baris 1–20 & baris 58–133)<br>3. `app/schemas/menu.py` (`MenuTreeOut`, `MenuOut`)<br>4. `app/services/menu_service.py` (`get_my_menu_tree`) |
| Deskripsi | **Kondisi Saat Ini:**<br>Dokumen `docs/CORE/CATATAN_PERMASALAHAN_ADMIN.md` menjadi acuan integrasi antara endpoint `GET /api/v1/menus/my-menu` di backend dan komponen sidebar dinamis di frontend.<br><br>**Masalah yang Ditemukan:**<br>1. **Perbedaan daftar nama Icon (`icon`):**<br>   - Pada `CATATAN_PERMASALAHAN_ADMIN.md` Bagian 2 (baris 420–436), daftar enum icon canonical yang disarankan untuk dipetakan melalui *allowlist* di frontend hanya terdiri dari 11 nama: `layout-dashboard`, `database`, `package`, `warehouse`, `truck`, `clipboard-check`, `arrow-left-right`, `users`, `shield-check`, `file-text`, `settings`.<br>   - Namun, data *seed* aktual di `db/migrations/009_create_menu_tables.sql` (baris 61–132) dan `docs/CORE/SCHEMA_DATABASE.MD` (Bagian 5.9) menggunakan **14 nama icon berbeda** yang tidak ada di daftar Bagian 2 tersebut, yaitu: `boxes`, `shopping-cart`, `shield` (bukan `shield-check`), `folder-tree`, `scale`, `building-2`, `map-pin`, `layers`, `bar-chart-3`, `book-open`, `package-check`, `key-round`, `menu`, dan `scroll-text`.<br>2. **Inkosistensi Field `short_name` di Dokumentasi:**<br>   - Pada `CATATAN_PERMASALAHAN_ADMIN.md` Bagian 2 (baris 261 & 310), contoh payload dan tabel arti field mencantumkan properti `"short_name": "Master"`, sedangkan tabel `menus` di `009_create_menu_tables.sql`, schema `MenuTreeOut` di `app/schemas/menu.py`, dan interface TypeScript `MenuNode` di `CATATAN_PERMASALAHAN_ADMIN.md` Bagian 3.4 tidak memiliki field `short_name`. |
| Dampak | Apabila pengembang frontend membuat *icon mapper allowlist* (`Record<string, LucideIcon>`) hanya berdasarkan daftar 11 icon di Bagian 2 `CATATAN_PERMASALAHAN_ADMIN.md`, maka **14 dari 19 menu** yang dikembalikan oleh backend (`GET /api/v1/menus/my-menu`) tidak akan dikenali icon-nya oleh frontend dan akan jatuh ke *fallback icon* default. |
| Rekomendasi | 1. Perbarui daftar enum icon canonical pada `docs/CORE/CATATAN_PERMASALAHAN_ADMIN.md` Bagian 2 (dan tambahkan ke spesifikasi modul `IAM` di PRD Modular v3.1) agar mencantumkan seluruh 19 nama icon aktual yang di-seed pada `db/migrations/009_create_menu_tables.sql` (`layout-dashboard`, `database`, `warehouse`, `boxes`, `shopping-cart`, `arrow-left-right`, `clipboard-check`, `shield`, `folder-tree`, `scale`, `truck`, `package`, `building-2`, `map-pin`, `layers`, `bar-chart-3`, `book-open`, `file-text`, `package-check`, `users`, `key-round`, `menu`, `scroll-text`), serta `settings` dan `building` untuk menu modul baru (`TNT`/`CFG`).<br>2. Hapus referensi `"short_name"` pada contoh JSON Bagian 2 di `CATATAN_PERMASALAHAN_ADMIN.md` agar konsisten dengan Bagian 3.4 dan `app/schemas/menu.py`. |
| Prioritas | **Medium** |
| Status Validasi | **Verified** |

---

### VF-06: Celah Aturan Bisnis pada Perubahan `uoms.allow_decimal` (`TRUE` ke `FALSE`) Setelah Barang Memiliki Saldo atau Transaksi Pecahan

| Aspek | Keterangan |
|---|---|
| Kategori | Temuan Aktual |
| Area | PRD / Backend / Database |
| Referensi | 1. `docs/CORE/PRD JejakStok - Sistem Manajemen Gudang (Modular).md` (`GBR-05`, `MST-BR01`, `MST-BR02`)<br>2. `app/services/master_service.py` (`update_uom` baris 329–422; `update_item` baris 872–890)<br>3. `app/services/transfer_service.py` (`_ensure_integer_if_required`), `app/services/opname_service.py` (`_ensure_integer_if_required`) |
| Deskripsi | **Kondisi Saat Ini:**<br>- Aturan `MST-BR02` telah diimplementasikan dengan benar pada `master_service.update_item` (baris 872–890): satuan (`uom_id`) pada barang tidak boleh diubah setelah barang tersebut pernah dipakai dalam transaksi atau memiliki saldo (`master_repo.is_item_used_in_transactions`).<br>- Aturan `GBR-05` menyatakan bahwa untuk barang dengan satuan `allow_decimal = FALSE`, semua kuantitas pada PO, GR, Transfer, dan Opname harus berupa bilangan bulat.<br><br>**Masalah yang Ditemukan:**<br>Pada `master_service.update_uom` (`PATCH /api/v1/uoms/{uom_id}`, baris 329–422), sistem mengizinkan perubahan kolom `allow_decimal` dari `TRUE` menjadi `FALSE` kapan saja tanpa memeriksa apakah UoM tersebut sudah digunakan oleh barang (`items`) yang telah bertransaksi atau sedang memiliki saldo pecahan (mis. `qty_on_hand = 10.5000`). |
| Dampak | Jika sebuah UoM (mis. `KG` dengan `allow_decimal = TRUE`) digunakan oleh barang yang menerima stok `10.5000`, lalu admin mengubah `allow_decimal` pada UoM tersebut menjadi `FALSE`:<br>- Saldo `10.5000` di `inventory_balances` menjadi tidak valid terhadap aturan `allow_decimal = FALSE`.<br>- Saat petugas gudang mencoba melakukan **Stock Opname** atau **Stock Transfer** untuk mengosongkan/menyesuaikan stok `10.5000` tersebut, fungsi `_ensure_integer_if_required` akan melempar `DECIMAL_QTY_NOT_ALLOWED`, atau jika petugas memasukkan angka bulat pada Opname (mis. `10`), selisihnya (`-0.5000`) tetap pecahan. Akibatnya, stok maupun dokumen `DRAFT`/`APPROVED`/`SHIPPED` yang memuat angka desimal akan terjebak (*dead-end state*). |
| Rekomendasi | 1. Tambahkan aturan bisnis eksplisit pada modul `MST` di PRD (`MST-BR07`): *"Atribut `allow_decimal` pada satuan (UoM) tidak dapat diubah (atau minimal tidak dapat diubah dari `TRUE` menjadi `FALSE`) apabila satuan tersebut sudah digunakan oleh barang yang pernah bertransaksi atau memiliki saldo stok."*<br>2. Pada `app/services/master_service.py` (`update_uom`), tambahkan pengecekan sebelum mengizinkan perubahan `allow_decimal` (gunakan kode error `UOM_IN_USE` yang sudah terdaftar di `app/core/exceptions.py` dan Lampiran B PRD). |
| Prioritas | **Medium** |
| Status Validasi | **Verified** |

---

### VF-07: Ketidakselarasan Batas Kontrak Antarmodul (`BND-02` & `BND-03`) dan Penamaan File Route di PRD Modular v3.1 dengan Implementasi Aktual

| Aspek | Keterangan |
|---|---|
| Kategori | Temuan Aktual |
| Area | Arsitektur / PRD / Backend |
| Referensi | 1. `docs/CORE/PRD JejakStok - Sistem Manajemen Gudang (Modular).md` (`BND-02`, `BND-03`, Tabel *Kontrak Antarmodul*, `OQ-10`, serta Peta Kode pada spesifikasi modul `TNT` dan `CFG`)<br>2. `docs/CORE/FOLDER_STRUCTURE.MD` (Bagian 1 & Bagian 4)<br>3. `AGENTS.MD` (Bagian 4: *Satu use case = satu transaksi database di satu fungsi service*)<br>4. `app/services/gr_service.py`, `app/services/po_service.py`, `app/repositories/inventory_repo.py`, `app/repositories/master_repo.py`, `app/repositories/warehouse_repo.py` |
| Deskripsi | **Kondisi Saat Ini & Masalah yang Ditemukan:**<br>1. **Kontrak Antarmodul vs Query Lintas Tabel di Repository:**<br>   PRD Modular v3.1 (`BND-02`, `BND-03`, dan tabel *Kontrak Antarmodul*) menyatakan bahwa modul tidak boleh menulis/membaca tabel milik modul lain secara langsung di luar kontrak yang didefinisikan (`apply_receipt`, `gr_status_summary`, `in_transit`, `validate_location`, `open_references`). Namun, pada implementasi aktual yang mengikuti `FOLDER_STRUCTURE.MD`:<br>   - `app/services/gr_service.py` (`post_goods_receipt`) memanggil langsung fungsi-fungsi di `po_repo` (`lock_po_by_id`, `lock_po_lines`, `add_po_line_received_qty`, `update_po_status`) di dalam transaksi `gr_service`, bukan memanggil fungsi `po_service.apply_receipt()`. Hal ini selaras dengan `FOLDER_STRUCTURE.MD` Bagian 3 (*"Jangan membuka `with conn.transaction():` di dalam fungsi yang dipanggil oleh fungsi service lain... `inventory_service.apply_movement(conn, ...)` dan `audit_service.record_log(conn, ...)` tidak membuka transaksi sendiri"*), tetapi di `po_service.py` belum ada fungsi helper internal `apply_receipt(conn, ...)`.<br>   - `app/repositories/inventory_repo.py` (`list_stock_by_location`, `list_stock_by_warehouse`, `list_stock_summary`) menggabungkan tabel `inventory_balances` (modul `INV`) dan `stock_transfer_lines` + `stock_transfers` (modul `TRF`) secara langsung di dalam satu SQL CTE `FULL OUTER JOIN` agar paginasi dan filter `include_zero` dapat dieksekusi di level database.<br>   - `app/repositories/master_repo.py` (`is_item_in_use`, `is_item_used_in_transactions`) dan `app/repositories/warehouse_repo.py` (`is_warehouse_in_use`, `is_location_in_use`) melakukan query `EXISTS` langsung ke tabel `purchase_orders`, `goods_receipts`, `stock_transfers`, `stock_opnames`, dan `inventory_balances`.<br>2. **Ketidakkonsistenan Penamaan File Route di PRD Modular v3.1:**<br>   - Pada seluruh modul eksisting (`IAM`, `MST`, `WHS`, `INV`, `PUR`, `RCV`, `TRF`, `OPN`, `AUD`), peta kode di PRD Modular dan `FOLDER_STRUCTURE.MD` menggunakan pola `app/api/routes/<resource>.py` tanpa akhiran `_routes` (contoh: `routes/users.py`, `routes/warehouses.py`).<br>   - Namun pada modul baru `TNT` dan `CFG` di PRD Modular v3.1, peta kode menulis `routes/tenant_routes.py`, `routes/platform_routes.py`, dan `routes/settings_routes.py` (memakai akhiran `_routes`). |
| Dampak | - Jika aturan `BND-02` dan `BND-03` ditafsirkan secara kaku bahwa `inventory_repo` dilarang melakukan SQL JOIN ke `stock_transfers` untuk menghitung `qty_in_transit`, maka paginasi `GET /api/v1/stock/by-location` dan `by-warehouse` harus menarik seluruh data ke memori Python, yang akan merusak target performa `NFR-03` (< 200 ms).<br>- Ketidakkonsistenan nama file `*_routes.py` melanggar konvensi penamaan di `FOLDER_STRUCTURE.MD` Bagian 1 & 6. |
| Rekomendasi | 1. Jawab dan tutup `OQ-10` di PRD Modular v3.1 dengan menegaskan bahwa:<br>   - Untuk **operasi tulis lintas modul** dalam satu transaksi (seperti `RCV` memperbarui progres `PUR`), pemanggilan wajib melalui fungsi helper service internal yang menerima `conn` tanpa membuka transaksi baru (mis. `po_service.apply_receipt(conn, ...)`), sebagaimana pola `inventory_service.apply_movement(conn, ...)`.<br>   - Untuk **operasi baca agregat/paginasi dan pemeriksaan referensi terbuka (`in_transit`, `open_references`)**, diizinkan diwujudkan sebagai query/CTE terenkapsulasi di lapisan `repositories/` demi menjaga performa SQL (`NFR-03`).<br>2. Seragamkan penamaan peta kode route modul `TNT` dan `CFG` di PRD Modular v3.1 menjadi `routes/tenants.py`, `routes/platform.py`, dan `routes/settings.py` agar sesuai dengan konvensi `FOLDER_STRUCTURE.MD`. |
| Prioritas | **Medium** |
| Status Validasi | **Verified** |

---

### VF-08: Celah Validasi Status Aktif Referensi (`GBR-11`) pada Transisi `approve_transfer`, `receive_transfer`, dan `post_goods_receipt`

| Aspek | Keterangan |
|---|---|
| Kategori | Temuan Aktual |
| Area | PRD / Backend |
| Referensi | 1. `docs/CORE/PRD JejakStok - Sistem Manajemen Gudang (Modular).md` (`GBR-11`, `GBR-13`, `PUR-BR06`, `RCV-BR06`, `TRF-BR07`)<br>2. `app/services/transfer_service.py` (`approve_transfer` baris 581–636, `ship_transfer` baris 639–725, `receive_transfer` baris 728–903)<br>3. `app/services/gr_service.py` (`post_goods_receipt` baris 563–729)<br>4. `app/services/inventory_service.py` (`apply_movement` baris 51–116) |
| Deskripsi | **Kondisi Saat Ini:**<br>`GBR-11` menyebutkan *"Gudang, barang, pemasok, dan lokasi pada dokumen baru harus aktif."* Sementara itu, `GBR-13` melarang penonaktifan gudang, lokasi, atau barang apabila masih ada dokumen aktif/terbuka.<br><br>**Masalah yang Ditemukan pada Implementasi Transisi Status:**<br>1. Pada `transfer_service.approve_transfer` (`POST /api/v1/stock-transfers/{id}/approve`): sistem hanya memeriksa status dokumen `DRAFT` dan akses gudang asal, tanpa memeriksa apakah gudang asal/tujuan, lokasi asal/tujuan, dan barang masih aktif.<br>2. Pada `transfer_service.receive_transfer` (`POST /api/v1/stock-transfers/{id}/receive`): untuk baris dengan `qty_received > 0`, sistem memanggil `inventory_service.apply_movement` yang di dalamnya memvalidasi `warehouse.is_active`, `location.is_active`, dan `item.is_active`. Namun, untuk baris dengan `qty_received == 0` (seluruh barang hilang/rusak di perjalanan), `apply_movement` **tidak dipanggil** (karena `if qty_received > Decimal("0"):` pada baris 841), sehingga validasi status aktif lokasi tujuan dan barang pada baris tersebut terlewat.<br>3. Pada `gr_service.post_goods_receipt` (`POST /api/v1/goods-receipts/{id}/post`): sistem tidak memeriksa ulang apakah `supplier` pada PO/GR masih berstatus `is_active = TRUE` saat GR di-posting (pemasok bisa saja dinonaktifkan setelah PO `ISSUED` karena `master_repo.is_supplier_in_use` hanya memeriksa keberadaan PO/GR secara historis jika belum pernah dipakai, namun wait: `master_service.update_supplier` saat ini bahkan **tidak memanggil `is_supplier_in_use`** saat menonaktifkan pemasok!).<br>4. Verifikasi tambahan pada `app/services/master_service.py` (`update_supplier`, baris 516–592): berbeda dengan `update_warehouse`, `update_location`, dan `update_item` yang memblokir penonaktifan (`is_active = FALSE`) bila ada dokumen terbuka (`GBR-13`), fungsi `update_supplier` mengizinkan `is_active = FALSE` pada pemasok meskipun pemasok tersebut masih memiliki PO berstatus `DRAFT` atau `ISSUED` atau GR berstatus `DRAFT`! |
| Dampak | - Pemasok yang masih memiliki PO `DRAFT` / `ISSUED` atau GR `DRAFT` dapat dinonaktifkan (`is_active = FALSE`), menyebabkan inkonsistensi ketika PO `DRAFT` tersebut hendak diterbitkan (`issue_purchase_order` akan gagal dengan `INACTIVE_REFERENCE`) atau GR `DRAFT` diposting.<br>- Perilaku validasi `INACTIVE_REFERENCE` pada `receive_transfer` menjadi tidak konsisten antara baris dengan `qty_received > 0` dan `qty_received == 0`. |
| Rekomendasi | 1. Perjelas di PRD Modular v3.1 (`GBR-11` & `GBR-13`) apakah pemasok (`suppliers`) juga dilarang dinonaktifkan selama masih memiliki PO terbuka (`DRAFT`, `ISSUED`, `PARTIALLY_RECEIVED`) atau GR `DRAFT`.<br>2. Tambahkan pengecekan referensi aktif secara konsisten pada `approve_transfer` dan `receive_transfer` (termasuk sebelum loop `if qty_received > 0`), serta tambahkan pengecekan PO/GR terbuka pada `master_service.update_supplier` saat `is_active` diubah menjadi `FALSE`. |
| Prioritas | **Medium** |
| Status Validasi | **Verified** |

---

### VF-09: Ketidaksesuaian Urutan Tahapan Pengembangan (Roadmap Fase 0–7 di PRD Modular v3.1) terhadap Status Implementasi Eksisting (M0–M8 Selesai)

| Aspek | Keterangan |
|---|---|
| Kategori | Temuan Aktual |
| Area | PRD / Arsitektur |
| Referensi | 1. `docs/CORE/PRD JejakStok - Sistem Manajemen Gudang (Modular).md` (Bagian *Roadmap dan Prioritas*: Tabel Urutan Fase Pengembangan MVP `Fase 0` s.d. `Fase 7`)<br>2. `docs/CORE/FOLDER_STRUCTURE.MD` (Bagian 9: *Urutan Implementasi yang Disarankan* `M0` s.d. `M8`)<br>3. `docs/API/README.md` (Bagian 4: *Hasil Pengujian & Benchmark Tahap M8*, 87 endpoint aktif, migrasi `001`–`009` terpasang) |
| Deskripsi | **Kondisi Saat Ini:**<br>Berdasarkan `docs/API/README.md` dan kode di `app/`, proyek saat ini **telah menyelesaikan seluruh tahapan M0 sampai M8** (pondasi `PLT`, `IAM` + Menu RBAC, `AUD`, `MST`, `WHS`, `INV`, `PUR`, `RCV`, `TRF`, `OPN`, serta pengujian `AC-01` s.d. `AC-14` pada PostgreSQL).<br><br>**Masalah yang Ditemukan:**<br>Tabel **Urutan Fase Pengembangan (MVP)** pada `PRD JejakStok - Sistem Manajemen Gudang (Modular).md` menulis tahapan dari `Fase 0` sampai `Fase 7` seolah-olah aplikasi dibangun dari awal dengan multi-tenancy sejak Fase 0:<br>- `Fase 0 — Fondasi`: *"PLT dengan konteks tenant, kerangka aplikasi, seluruh skema ber-tenant_id (migrasi 001 sampai 011)"*<br>- `Fase 1 — Identitas, Tenant, Konfigurasi, dan Audit`: `TNT`, `IAM`, `CFG`, `AUD`<br>- `Fase 2` s.d. `Fase 6`: `MST`, `WHS`, `INV`, `PUR`, `RCV`, `TRF`, `OPN`.<br><br>Urutan ini bertentangan dengan kenyataan bahwa migrasi `001` sampai `009` dan modul `IAM` s.d. `OPN` sudah selesai dibangun dalam mode *single-tenant* dan aturan `PLT-BR03` / `AGENTS.MD` Bagian 7 melarang pengeditan migrasi `001`–`009` yang sudah diterapkan. |
| Dampak | Pengembang yang membaca bagian *Roadmap dan Prioritas* di PRD Modular v3.1 akan bingung apakah harus menulis ulang migrasi `001`–`009` dari Fase 0 (yang dilarang oleh aturan *forward-only migration*) atau melakukan migrasi inkremental di atas M8. |
| Rekomendasi | Perbarui bagian **Roadmap dan Prioritas** pada `PRD JejakStok - Sistem Manajemen Gudang (Modular).md` agar memisahkan dengan jelas antara:<br>1. **Tahap Baseline (M0–M8 — Selesai / Implemented):** Pondasi Single-Tenant (`PLT`, `IAM`, `AUD`, `MST`, `WHS`, `INV`, `PUR`, `RCV`, `TRF`, `OPN`, Migrasi `001`–`009`, `AC-01` s.d. `AC-14`).<br>2. **Tahap Transisi Multi-Tenant SaaS (M9 — Target Berikutnya):**<br>   - **M9a:** Migrasi `010_create_tenants_settings.sql` & `011_add_tenant_scope.sql` + RLS + Konteks `current_tenant()` di `PLT`.<br>   - **M9b:** Implementasi modul baru `TNT` dan `CFG`.<br>   - **M9c:** Adaptasi `IAM` (login ber-`slug`, manajemen sesi per-tenant), `AUD` (filter tenant), dan injeksi `tenant_id` pada repository modul `MST`, `WHS`, `INV`, `PUR`, `RCV`, `TRF`, `OPN`.<br>   - **M9d:** Pengujian `AC-15` s.d. `AC-21` dan regresi `AC-01` s.d. `AC-14`. |
| Prioritas | **Medium** |
| Status Validasi | **Verified** |

---

### VF-10: Risiko Rework Skema Inti pada Urutan Pengembangan Pasca-MVP (`P1` Goods Issue & Pelaporan Sebelum `P2` Lot/Serial/Lokasi Hierarkis)

| Aspek | Keterangan |
|---|---|
| Kategori | Temuan Aktual |
| Area | PRD / Database / Arsitektur |
| Referensi | `docs/CORE/PRD JejakStok - Sistem Manajemen Gudang (Modular).md` (Bagian *Kandidat Pasca-MVP*: Tabel `P1` s.d. `P7`, Bagian `RSK-01`, `RSK-02`, `RSK-03`) |
| Deskripsi | **Kondisi Saat Ini:**<br>Pada tabel **Kandidat Pasca-MVP** di PRD Modular v3.1, urutan prioritas pasca-MVP ditetapkan sebagai berikut:<br>- `P1`: Pengeluaran barang (`ISS`) dan pelaporan operasional (`RPT`)<br>- `P2`: Perluasan katalog dan lokasi (pelacakan opsional batch/lot, kedaluwarsa, nomor seri; konversi satuan; hierarki lokasi Zona -> Lorong -> Rak -> Bin)<br>- `P3`: Perluasan alur transaksi (persetujuan PO bertingkat, pembalikan GR, retur ke pemasok, penerimaan transfer bertahap)<br>- `P4`: Siklus opname terjadwal dan penugasan petugas per zona<br>- `P5`: Reservasi stok dan penilaian nilai persediaan (FIFO / rata-rata tertimbang).<br><br>**Masalah yang Ditemukan pada Urutan Dependensi:**<br>- Saat ini kunci unik saldo di `inventory_balances` adalah `(warehouse_id, location_id, item_id)` (atau `(tenant_id, warehouse_id, location_id, item_id)`).<br>- Fitur `P2` (Lot/Batch/Expiry & Serial Number) serta `P5` (Reservasi Stok & Valuasi FIFO/Average) mengubah struktur dasar tabel `inventory_balances`, `stock_movements`, dan tanda tangan fungsi `inventory_service.apply_movement()` (sebagaimana diakui sendiri pada `RSK-01` dan `RSK-02`).<br>- Apabila `P1` (`ISS` Goods Issue & `RPT` Laporan Operasional) dan `P3` (Retur ke pemasok, Pembalikan GR) dibangun terlebih dahulu tanpa merancang struktur ekstensi dimensi stok (`lot_id` opsional, `qty_reserved` opsional), maka ketika `P2` dan `P5` dikerjakan, seluruh query transaksi di `ISS`, `RCV`, `TRF`, `OPN`, dan seluruh query agregasi di `RPT` harus dibongkar dan ditulis ulang. |
| Dampak | Tingginya biaya *rework* (perombakan ulang migrasi database, service, repository, dan kontrak API) pada modul `ISS` dan `RPT` ketika memasuki tahap `P2` dan `P5`. |
| Rekomendasi | Sesuaikan tata urutan dan prasyarat arsitektur pada tabel **Kandidat Pasca-MVP**:<br>1. Sebelum mengimplementasikan `P1` (`ISS` & `RPT`), kunci terlebih dahulu desain ekstensi skema `INV` (apakah `lot_id` akan menjadi bagian dari kunci komposit `inventory_balances` atau tabel sub-saldo terpisah).<br>2. Untuk `Hierarki Lokasi (Zona -> Lorong -> Rak -> Bin)` pada `P2`: fitur ini hanya membutuhkan penambahan kolom opsional `parent_location_id` / `level_type` pada tabel `locations` tanpa mengubah kunci saldo `inventory_balances` (karena stok tetap disimpan pada `location_id` level terbawah/leaf). Oleh karena itu, hierarki lokasi dapat dikerjakan lebih awal tanpa mengganggu modul transaksi. |
| Prioritas | **Medium** |
| Status Validasi | **Verified** |

---

### VF-11: Inkonsistensi Dokumentasi Penempatan Tabel `user_warehouses`, Kode Error `INTERNAL_ERROR`, dan Keunikan Baris Transfer

| Aspek | Keterangan |
|---|---|
| Kategori | Temuan Aktual |
| Area | PRD / Database / Backend |
| Referensi | 1. `docs/CORE/FOLDER_STRUCTURE.MD` (Bagian 1 baris 97–98) vs `docs/CORE/SCHEMA_DATABASE.MD` (Bagian 2 baris 39–40) & `db/migrations/001`–`002`<br>2. `docs/CORE/PRD JejakStok - Sistem Manajemen Gudang (Modular).md` (`OQ-04`, `OQ-05`, `OQ-06`, `OQ-08`)<br>3. `app/main.py` (baris 115–127: `INTERNAL_ERROR`), `db/migrations/005_create_transfer_opname.sql` (`uq_stock_transfer_lines_transfer_item`), `app/services/transfer_service.py` (baris 295–299) |
| Deskripsi | **Kondisi Saat Ini & Masalah yang Ditemukan:**<br>1. **Lokasi Migrasi `user_warehouses` (`OQ-08`):** `docs/CORE/FOLDER_STRUCTURE.MD` baris 97 mencatat tabel `user_warehouses` dibuat di `001_create_auth_tables.sql`. Faktanya, di `db/migrations/002_create_master_tables.sql` (baris 95–107) dan `docs/CORE/SCHEMA_DATABASE.MD`, tabel `user_warehouses` berada di `002_create_master_tables.sql` karena memiliki Foreign Key ke tabel `warehouses` yang baru dibuat di `002`.<br>2. **Status Kode Error `INTERNAL_ERROR` (`OQ-05`):** Di `app/main.py` (baris 122) dan `docs/API/README.md`, handler exception tidak terduga (HTTP 500) sudah mengembalikan `"code": "INTERNAL_ERROR"`. Namun di `PRD v2.0 legacy` v2.0 Lampiran B kode ini belum tercantum, dan di PRD Modular v3.1 masih diberi label *Perlu Ditinjau (`OQ-05`)*.<br>3. **Keunikan Barang per Dokumen Transfer (`OQ-04`) dan Penolakan Duplikasi Baris PO (`PUR-BR08`):**<br>   - Pada `db/migrations/004_create_po_gr.sql` sudah terpasang `uq_po_lines_po_item UNIQUE (po_id, item_id)` dan pada `db/migrations/005_create_transfer_opname.sql` sudah terpasang `uq_stock_transfer_lines_transfer_item UNIQUE (transfer_id, item_id)`.<br>   - Baik `po_service.py` (baris 226–232) maupun `transfer_service.py` (baris 295–299) sudah memvalidasi dan menolak duplikasi `item_id` dalam satu dokumen dengan error `VALIDATION_ERROR` (HTTP 422). Namun di PRD Modular v3.1 hal ini masih berstatus pertanyaan terbuka (`OQ-04`).<br>4. **Jalur Endpoint Barang di Bawah Kategori (`OQ-06`):** `app/api/routes/categories.py` dan `docs/API/03_master_data.md` sudah mengimplementasikan `GET /api/v1/categories/{category_id}/items` secara resmi, tetapi di PRD Modular v3.1 masih ditandai `OQ-06`. |
| Dampak | Menyisakan pertanyaan terbuka semu (`OQ-04`, `OQ-05`, `OQ-06`, `OQ-08`) pada PRD Modular v3.1 atas hal-hal yang sebenarnya sudah diputuskan dan terimplementasi dengan baik di codebase maupun migrasi database. |
| Rekomendasi | 1. Perbaiki `docs/CORE/FOLDER_STRUCTURE.MD` baris 97–98 agar mencantumkan `user_warehouses` di bawah `002_create_master_tables.sql`.<br>2. Tutup `OQ-04`, `OQ-06`, dan `OQ-08` di PRD Modular v3.1 dengan mengadopsi perilaku aktual yang sudah teruji di `db/migrations/` dan `app/`.<br>3. Untuk `OQ-05`: resmikan `INTERNAL_ERROR` (HTTP 500) ke dalam katalog error inti karena sudah diimplementasikan di `app/main.py`. |
| Prioritas | **Low** |
| Status Validasi | **Verified** |

---

### VF-12: Beban Eksekusi Ganda CTE `FULL OUTER JOIN` dan Ketiadaan Partial Index *In-Transit* pada Query Stok & Ledger

| Aspek | Keterangan |
|---|---|
| Kategori | Temuan Aktual |
| Area | Database / Backend |
| Referensi | 1. `app/repositories/inventory_repo.py` (`list_stock_by_location` baris 129–245, `list_stock_by_warehouse` baris 248–359, `list_stock_summary` baris 362–414, `list_stock_movements` baris 417–527)<br>2. `db/migrations/005_create_transfer_opname.sql` (Indeks pada `stock_transfers` dan `stock_transfer_lines`)<br>3. `docs/API/README.md` (Bagian 4 poin 7: Hasil Benchmark `NFR-03` pada 1.000.000 baris `stock_movements`)<br>4. `docs/CORE/PRD JejakStok - Sistem Manajemen Gudang (Modular).md` (`NFR-03`, `NFR-09`) |
| Deskripsi | **Kondisi Saat Ini & Masalah yang Ditemukan:**<br>1. Pada `inventory_repo.list_stock_by_location` dan `list_stock_by_warehouse`, sistem membangun CTE yang melakukan agregasi `inventory_balances` dan `FULL OUTER JOIN` dengan agregasi `stock_transfer_lines JOIN stock_transfers WHERE st.status = 'SHIPPED'`. Di dalam fungsi repository tersebut, CTE yang sama dieksekusi **dua kali berturut-turut** dalam satu request: pertama untuk `SELECT COUNT(*) AS total FROM combined`, dan kedua untuk `SELECT ... FROM combined ORDER BY ... LIMIT %s OFFSET %s`.<br>2. Pada `db/migrations/005_create_transfer_opname.sql`, indeks pada `stock_transfers` dibuat secara terpisah pada `(status)` dan `(destination_warehouse_id)`. Belum ada *partial composite index* khusus untuk status `SHIPPED` (misalnya `ON stock_transfers (destination_warehouse_id, destination_location_id) WHERE status = 'SHIPPED'`).<br>3. Pada `docs/API/README.md` Bagian 4 poin 7, hasil benchmark M8 menunjukkan bahwa eksekusi `COUNT(*)` terpisah pada 1.000.000 baris `stock_movements` memakan waktu `122,527 ms` (dan sempat mencapai `271,429 ms` sebelum `VACUUM ANALYZE`, melewati batas `200 ms` `NFR-03`). |
| Dampak | Ketika volume data meningkat pada skema Multi-Tenant (`NFR-09`: 100 tenant aktif, jutaan baris `stock_movements`, dan ribuan dokumen transfer), eksekusi ganda CTE `FULL OUTER JOIN` serta `COUNT(*)` penuh akan menjadi *bottleneck* utama yang melampaui target latensi `p95 < 200 ms` (`NFR-03`). |
| Rekomendasi | 1. Tambahkan *partial index* pada migrasi berikutnya: `CREATE INDEX ix_stock_transfers_shipped_dest ON stock_transfers (destination_warehouse_id, destination_location_id) WHERE status = 'SHIPPED';` (serta menyertakan `tenant_id` di urutan pertama saat migrasi multi-tenant).<br>2. Pada `list_stock_by_location` dan `list_stock_by_warehouse`, gunakan `COUNT(*) OVER() AS total_count` di dalam satu query tunggal (dengan fallback query `COUNT` hanya bila halaman yang diminta di luar jangkauan / hasil kosong pada `page > 1`) untuk memangkas waktu eksekusi query hingga ~45%. |
| Prioritas | **Low** |
| Status Validasi | **Verified** |

---

## 3. Bagian II — Asumsi (Assumptions — Need Confirmation)

Seluruh butir pada bagian ini merupakan hal-hal yang **belum memiliki informasi atau keputusan final yang cukup di dalam dokumentasi** untuk dinyatakan sebagai fakta. Asumsi ini **tidak boleh** langsung dijadikan dasar pengubahan kode sebelum dikonfirmasi oleh pemilik proyek.

---

### AS-01: Penetapan Dokumen Sumber Kebenaran Utama (`PRD Modular v3.1` vs `PRD v2.0`) pada `AGENTS.MD`

| Aspek | Keterangan |
|---|---|
| Kategori | Asumsi |
| Area | PRD / Arsitektur |
| Referensi | `AGENTS.MD` (Bagian 1 & 3), `PRD v2.0 legacy yang telah diintegrasikan ke docs/CORE/PRD_GENERAL.md` (v2.0), `docs/CORE/PRD JejakStok - Sistem Manajemen Gudang (Modular).md` (v3.1 Draf) |
| Deskripsi | **Dasar Asumsi:**<br>Diasumsikan bahwa `docs/CORE/PRD JejakStok - Sistem Manajemen Gudang (Modular).md` (v3.1) disusun untuk menggantikan `PRD v2.0 legacy` (v2.0) sebagai cetak biru pengembangan tahap berikutnya (evolusi dari Single-Tenant MVP yang sudah selesai di M8 menuju Multi-Tenant SaaS), bukan untuk menghapus atau membatalkan fitur M0–M8 yang sudah berjalan.<br><br>**Mengapa Perlu Dikonfirmasi:**<br>`AGENTS.MD` melarang keras agen mengubah `PRD v2.0 legacy` atau menambah tabel/endpoint di luar dokumen tersebut tanpa persetujuan eksplisit pemilik proyek. Selain itu, status dokumen PRD Modular v3.1 masih tertulis `3.1 · Draf`. |
| Dampak | Jika asumsi ini salah (misalnya pemilik proyek hanya ingin merapikan struktur PRD menjadi modular **tanpa** mengimplementasikan fitur Multi-Tenant `TNT`/`CFG` dalam waktu dekat), maka merombak skema database untuk menambahkan `tenant_id` sekarang akan membuang waktu dan menambah kompleksitas yang tidak diperlukan. Sebaliknya, jika Multi-Tenant memang wajib untuk rilis saat ini, maka seluruh modul perlu segera dimigrasikan ke `tenant_id`. |
| Rekomendasi | **Pertanyaan Konfirmasi untuk Pemilik Proyek:**<br>1. Apakah modul Multi-Tenant (`TNT` dan `CFG` beserta penambahan `tenant_id` di seluruh tabel) memang ditetapkan sebagai target implementasi langsung berikutnya (Tahap M9), ataukah `TNT` & `CFG` sebaiknya dipindahkan dari kategori **MVP** ke kategori **Pasca-MVP (`P1`)** agar selaras dengan implementasi M0–M8 saat ini?<br>2. Apakah `AGENTS.MD` Bagian 1 diizinkan untuk diperbarui agar merujuk ke `PRD JejakStok - Sistem Manajemen Gudang (Modular).md` setelah seluruh pertanyaan terbuka (`OQ`) diselesaikan? |
| Prioritas | **Critical** |
| Status Validasi | **Need Confirmation** |

---

### AS-02: Mekanisme Login Platform Admin, Skema Kuota Paket (`plans`), dan Kebijakan *Impersonation* (`OQ-11` s.d. `OQ-17`)

| Aspek | Keterangan |
|---|---|
| Kategori | Asumsi |
| Area | PRD / Database / Backend / Arsitektur |
| Referensi | `docs/CORE/PRD JejakStok - Sistem Manajemen Gudang (Modular).md` (Modul `TNT`, `IAM-BR20`, `TNT-BR03`, `TNT-BR05`, `TNT-BR06`, serta Pertanyaan Terbuka `OQ-11` s.d. `OQ-17`) |
| Deskripsi | **Dasar Asumsi:**<br>Dalam PRD Modular v3.1, terdapat 7 pertanyaan terbuka untuk arsitektur Multi-Tenant (`OQ-11` s.d. `OQ-17`). Diasumsikan pendekatan paling bersih dan aman untuk MVP Multi-Tenant adalah:<br>1. **Isolasi Data (`OQ-11`):** Satu database PostgreSQL dan satu skema `public` bersama dengan `tenant_id` + PostgreSQL RLS.<br>2. **Autentikasi Platform Admin (`OQ-12`):** Tabel `platform_admins` terpisah dengan endpoint login khusus `POST /api/v1/platform/auth/login` (tanpa input `slug` tenant) yang menerbitkan JWT dengan klaim `scope: "platform"` dan `tenant_id: null`.<br>3. **Onboarding Tenant (`OQ-13`):** Hanya dilakukan oleh Platform Admin (`POST /api/v1/platform/tenants`), belum ada *self-service sign-up* publik.<br>4. **Relasi Pengguna–Tenant (`OQ-14`):** Satu baris `users` terikat ketat ke satu `tenant_id` (pengguna di dua perusahaan memiliki akun per-tenant masing-masing).<br>5. **Akses Dukungan / *Impersonation* (`OQ-17`):** Platform Admin tidak mengakses endpoint bisnis tenant secara langsung menggunakan token platform, melainkan harus melalui mekanisme eksplisit yang tercatat di `audit_logs` (atau tidak diizinkan mengakses data operasional tenant pada fase awal).<br><br>**Mengapa Perlu Dikonfirmasi:**<br>Tanpa kepastian atas `OQ-12`, `OQ-15`, `OQ-16`, dan `OQ-17`, struktur kolom tabel `plans`, `tenants`, dan `platform_admins` pada migrasi `010_create_tenants_settings.sql` serta struktur klaim JWT tidak dapat dikunci. |
| Dampak | Jika asumsi mekanisme login Platform Admin (`OQ-12`) atau relasi *multi-tenant user* (`OQ-14`) berbeda dengan keinginan bisnis (misalnya satu email pengguna harus bisa berpindah-pindah tenant tanpa login ulang seperti Slack/Notion), maka desain tabel `users` (apakah `tenant_id` berada di tabel `users` atau di tabel penghubung `tenant_memberships`) akan berubah secara fundamental. |
| Rekomendasi | **Pertanyaan Konfirmasi untuk Pemilik Proyek:**<br>1. Apakah disetujui bahwa satu akun `users` terikat ke tepat satu `tenant_id` (`OQ-14`), dan Platform Admin login melalui endpoint terpisah `/api/v1/platform/auth/login` (`OQ-12`)?<br>2. Apa daftar paket awal (`plans`) beserta batas angka kuota `max_warehouses`, `max_active_users`, dan `max_active_items` yang harus di-seed pada migrasi `010` (`OQ-16`)?<br>3. Apakah Platform Admin memerlukan fitur *impersonation* (masuk sebagai Super Admin tenant untuk bantuan teknis) pada tahap ini (`OQ-17`), atau cukup mengelola status/kuota tenant saja? |
| Prioritas | **High** |
| Status Validasi | **Need Confirmation** |

---

### AS-03: Spesifikasi Siklus Hidup, Aturan Bisnis, dan Skema Modul Usulan `ISS` (Goods Issue) dan `RPT` (Pelaporan) (`OQ-02`)

| Aspek | Keterangan |
|---|---|
| Kategori | Asumsi |
| Area | PRD / Database / Backend |
| Referensi | `docs/CORE/PRD JejakStok - Sistem Manajemen Gudang (Modular).md` (Bagian Modul `ISS`, Modul `RPT`, `OOS-05`, `OQ-02`, `RSK-03`) |
| Deskripsi | **Dasar Asumsi:**<br>Modul `ISS` (Pengeluaran Barang) dan `RPT` (Pelaporan Operasional) dicantumkan di PRD Modular v3.1 dengan status `0.1 · Usulan` tanpa spesifikasi detail (`OQ-02`). Diasumsikan bahwa:<br>- Modul `ISS` akan memiliki tabel `goods_issues` dan `goods_issue_lines`, mendukung tipe pengeluaran (`SALES`, `PRODUCTION`, `INTERNAL_USE`, `SCRAP`), serta menghasilkan tipe pergerakan baru `OUT_ISSUE` pada `stock_movements` melalui `inventory_service.apply_movement()`.<br>- Modul `RPT` bersifat *read-only* di atas tabel `stock_movements`, `inventory_balances`, dan dokumen transaksi tanpa memiliki tabel sendiri.<br><br>**Mengapa Perlu Dikonfirmasi:**<br>Belum ada definisi mengenai:<br>1. Siklus status dokumen `ISS`: apakah 1 langkah (`DRAFT -> POSTED / CANCELLED` seperti Goods Receipt) atau 2 langkah (`DRAFT -> APPROVED -> ISSUED / CANCELLED` seperti Stock Transfer)?<br>2. Apakah `ISS` wajib merujuk ke dokumen eksternal (mis. nomor Sales Order / Work Order sebagai teks referensi bebas) atau berdiri sendiri?<br>3. Untuk `RPT`: apakah hanya menyediakan endpoint JSON untuk grafik/tabel di UI atau wajib menyediakan ekspor file (`CSV` / `XLSX` / `PDF`)? |
| Dampak | Jika `ISS` ternyata membutuhkan reservasi stok saat berstatus `APPROVED` (sebelum barang benar-benar dikeluarkan saat `ISSUED`), maka fitur `ISS` akan memiliki ketergantungan langsung pada fitur *Stock Reservation* (`P5`). Selain itu, jika `RPT` mewajibkan ekspor `.xlsx` atau `.pdf`, maka diperlukan penambahan dependensi baru (seperti `openpyxl` atau `reportlab`) yang saat ini dilarang oleh `AGENTS.MD` Bagian 2 tanpa persetujuan eksplisit. |
| Rekomendasi | **Pertanyaan Konfirmasi untuk Pemilik Proyek:**<br>1. Untuk `ISS` (Goods Issue): apakah alur statusnya cukup `DRAFT -> POSTED / CANCELLED` (1 tahap tanpa reservasi stok) atau memerlukan tahap `APPROVED` oleh Warehouse Manager?<br>2. Untuk `ISS`: apakah tipe pergerakan stok di `stock_movements` cukup satu nilai baru `OUT_ISSUE` (dengan kolom `issue_type` disimpan di header `goods_issues`)?<br>3. Untuk `RPT` (Pelaporan): laporan spesifik apa saja yang dibutuhkan pada tahap pertama, dan apakah format keluarannya cukup JSON API (atau memerlukan ekspor CSV/XLSX)? |
| Prioritas | **Medium** |
| Status Validasi | **Need Confirmation** |

---

### AS-04: Pemisahan Repositori Frontend dan Strategi Penyimpanan Refresh Token (`JSON Body / localStorage` vs `HttpOnly Cookie`)

| Aspek | Keterangan |
|---|---|
| Kategori | Asumsi |
| Area | Frontend / Backend / Arsitektur |
| Referensi | 1. `docs/CORE/CATATAN_PERMASALAHAN_ADMIN.md` (Bagian 1.3 & 1.4: *Analisis Penyebab Refresh Token*, Opsi A `HttpOnly Cookie` vs Opsi B `localStorage`)<br>2. `docs/CORE/PRD JejakStok - Sistem Manajemen Gudang (Modular).md` (`RSK-04`, `OQ-07`)<br>3. `app/main.py` (baris 55–66: konfigurasi `CORSMiddleware` dengan `allow_credentials=False`)<br>4. `app/api/routes/auth.py` & `app/schemas/auth.py` (`RefreshRequest`, `LogoutRequest`) |
| Deskripsi | **Dasar Asumsi:**<br>Berdasarkan `CATATAN_PERMASALAHAN_ADMIN.md` dan `app/main.py`, diasumsikan bahwa:<br>1. Kode sumber frontend (React + Vite + TypeScript + Zustand) dikelola di repositori terpisah dari repositori backend `warehouse_app` ini.<br>2. Untuk cakupan MVP saat ini, kontrak pengiriman `refresh_token` tetap menggunakan **JSON request/response body** (disimpan di `localStorage` pada sisi frontend sesuai Opsi B di `CATATAN_PERMASALAHAN_ADMIN.md` Bagian 1.4.2), bukan menggunakan `HttpOnly Cookie` (karena `app/main.py` baris 62 menetapkan `allow_credentials=False` dan endpoint `/api/v1/auth/refresh` menerima JSON body `{"refresh_token": "..."}`).<br><br>**Mengapa Perlu Dikonfirmasi:**<br>`CATATAN_PERMASALAHAN_ADMIN.md` Bagian 1.4.1 mencantumkan Opsi A (`HttpOnly Cookie`) sebagai *"Rekomendasi Utama / Production Grade"*, sedangkan Bagian 1.4.2 mencantumkan Opsi B (`localStorage`) sebagai solusi pragmatis tanpa mengubah backend. Perlu dipastikan apakah tim ingin tetap mempertahankan kontrak JSON body saat ini atau beralih ke `HttpOnly Cookie`. |
| Dampak | Apabila frontend mengharapkan `HttpOnly Cookie` sementara backend (`app/main.py` dan `app/api/routes/auth.py`) menggunakan `allow_credentials=False` dan membaca `refresh_token` dari JSON body, maka pembaruan sesi saat *hard refresh* (F5) di browser akan selalu gagal. |
| Rekomendasi | **Pertanyaan Konfirmasi untuk Pemilik Proyek:**<br>1. Apakah kontrak autentikasi `/api/v1/auth/login`, `/refresh`, dan `/logout` tetap dipertahankan menggunakan **JSON body** (Opsi B) untuk menjaga kompatibilitas dengan seluruh pengujian `AC-01`/`AC-02` yang sudah lulus?<br>2. Apakah dokumen `PRD_FRONTEND.md` berada di repositori frontend terpisah, dan apakah akan disatukan ke dalam folder `docs/CORE/` di repositori ini? |
| Prioritas | **Medium** |
| Status Validasi | **Need Confirmation** |

---

### AS-05: Perlakuan Sesi Aktif Saat Pengguna Ditugaskan/Dicabut dari Gudang (`OQ-01`) dan Detail Perubahan Nilai Audit Log (`OQ-03`)

| Aspek | Keterangan |
|---|---|
| Kategori | Asumsi |
| Area | PRD / Backend |
| Referensi | 1. `docs/CORE/PRD JejakStok - Sistem Manajemen Gudang (Modular).md` (`OQ-01`, `OQ-03`, `IAM-BR08`, `AUD-BR01`, `AUD-BR02`)<br>2. `app/services/user_service.py` (`assign_warehouse`, `revoke_warehouse`, `update_user`)<br>3. `app/services/access_service.py` (`ensure_warehouse_access`) |
| Deskripsi | **Dasar Asumsi:**<br>1. **Terkait `OQ-01` (pencabutan sesi saat perubahan penugasan gudang):** Pada implementasi aktual di `app/services/access_service.py` (`ensure_warehouse_access`), daftar gudang yang ditugaskan kepada pengguna **tidak disimpan di dalam klaim JWT**, melainkan **diperiksa langsung ke tabel `user_warehouses` di database pada setiap request**. Oleh karena itu, ketika seorang pengguna dicabut penugasan gudangnya (`DELETE /api/v1/users/{id}/warehouses/{wh_id}`), akses pengguna ke gudang tersebut **otomatis langsung terputus pada detik itu juga** tanpa perlu mencabut seluruh `refresh_tokens` pengguna tersebut.<br>2. **Terkait `OQ-03` (granularitas `old_values` dan `new_values` pada `audit_logs`):** Implementasi aktual di seluruh service (`app/services/`) sudah mencatat `old_values` dan `new_values` secara terstruktur (mis. perubahan status dokumen `{"status": "DRAFT"}` -> `{"status": "ISSUED"}`, perubahan field pada operasi `UPDATE` master data, serta penyaringan field sensitif oleh `audit_service.record_log`).<br><br>**Mengapa Perlu Dikonfirmasi:**<br>`OQ-01` dan `OQ-03` masih tercantum sebagai pertanyaan terbuka di PRD Modular v3.1. Perlu dikonfirmasi apakah perilaku yang sudah berjalan di kode saat ini sudah diterima sebagai aturan final. |
| Dampak | Jika `OQ-01` diputuskan bahwa pencabutan satu gudang harus me-logout paksa pengguna dari seluruh gudang lainnya (mencabut semua `refresh_tokens`), maka perilaku ini akan mengganggu pengguna yang masih bekerja secara sah di gudang lain yang tidak dicabut. |
| Rekomendasi | **Pertanyaan Konfirmasi untuk Pemilik Proyek:**<br>1. Apakah disetujui untuk menutup `OQ-01` dengan menetapkan bahwa perubahan penugasan gudang **tidak** perlu mencabut `refresh_tokens` (karena pemeriksaan akses gudang sudah dilakukan secara *real-time* ke database pada setiap request melalui `ensure_warehouse_access`)?<br>2. Apakah struktur `old_values` dan `new_values` pada `audit_service.py` saat ini sudah mencukupi untuk menutup `OQ-03`? |
| Prioritas | **Low** |
| Status Validasi | **Need Confirmation** |

---

## 4. Bagian III — Pemisahan Rekomendasi & Usulan Tahapan Pengembangan

Sesuai aturan review, rekomendasi di bawah ini dipisahkan secara tegas antara tindakan perbaikan yang **dapat langsung dieksekusi** (karena berdasar pada temuan aktual terverifikasi dan tidak mengubah keputusan bisnis yang belum pasti) dan tindakan yang **wajib menunggu konfirmasi** dari pemilik proyek.

---

### 4.1. Rekomendasi yang Dapat Langsung Dilakukan (Immediate Actions)

Rekomendasi berikut dapat langsung diterapkan pada dokumentasi maupun perbaikan *bug* aturan bisnis tanpa menunggu keputusan fitur baru:

1. **Perbaikan Konsistensi Dokumen PRD & Struktur Folder (`VF-01`, `VF-07`, `VF-11`):**
   - Perbaiki target metrik `SM-04` di `docs/CORE/PRD JejakStok - Sistem Manajemen Gudang (Modular).md` dari `14 dari 14` menjadi `21 dari 21`.
   - Seragamkan penamaan peta kode route pada modul `TNT` dan `CFG` di PRD Modular v3.1 dari `routes/tenant_routes.py`, `routes/platform_routes.py`, `routes/settings_routes.py` menjadi `routes/tenants.py`, `routes/platform.py`, `routes/settings.py`.
   - Perbaiki `docs/CORE/FOLDER_STRUCTURE.MD` Bagian 1 (baris 97–98) agar tabel `user_warehouses` tercatat pada `002_create_master_tables.sql` (sesuai implementasi aktual dan `SCHEMA_DATABASE.MD`).
   - Tutup pertanyaan terbuka `OQ-04` (keunikan barang per dokumen Transfer), `OQ-05` (`INTERNAL_ERROR` HTTP 500), `OQ-06` (`GET /api/v1/categories/{id}/items`), dan `OQ-08` (`user_warehouses` di migrasi `002`) pada PRD Modular v3.1 karena semuanya sudah diimplementasikan dan teruji.

2. **Sinkronisasi Kontrak Menu & Daftar Icon dengan Frontend (`VF-05`):**
   - Perbarui daftar allowlist icon pada `docs/CORE/CATATAN_PERMASALAHAN_ADMIN.md` Bagian 2 agar memuat seluruh 19 nama icon Lucide yang digunakan oleh `db/migrations/009_create_menu_tables.sql`.
   - Hapus field `"short_name"` dari contoh JSON di Bagian 2 `CATATAN_PERMASALAHAN_ADMIN.md` agar konsisten dengan `app/schemas/menu.py` dan Bagian 3.4.

3. **Penutupan Celah Aturan Bisnis pada Master Data & Transisi Dokumen (`VF-06`, `VF-08`):**
   - Pada `app/services/master_service.py` (`update_uom`), cegah perubahan `allow_decimal` dari `TRUE` menjadi `FALSE` apabila UoM tersebut sudah digunakan oleh barang (`master_repo.is_uom_in_use`), dengan melempar `UomInUseError` (`UOM_IN_USE`, HTTP 409).
   - Pada `app/services/master_service.py` (`update_supplier`), tambahkan pemeriksaan ketika `is_active` diubah menjadi `FALSE` untuk memastikan tidak ada Purchase Order terbuka (`DRAFT`, `ISSUED`, `PARTIALLY_RECEIVED`) atau Goods Receipt `DRAFT` pada pemasok tersebut (`GBR-13`).
   - Pada `app/services/transfer_service.py`, pastikan pemeriksaan status aktif referensi (`warehouse`, `location`, `item`) juga dijalankan secara konsisten saat `approve_transfer` dan untuk seluruh baris pada `receive_transfer`.

4. **Optimasi Query Stok & Ledger (`VF-12`):**
   - Gunakan `COUNT(*) OVER() AS total_count` pada query CTE `list_stock_by_location` dan `list_stock_by_warehouse` di `app/repositories/inventory_repo.py` untuk menghindari eksekusi ganda CTE `FULL OUTER JOIN`.

---

### 4.2. Rekomendasi yang Membutuhkan Konfirmasi Terlebih Dahulu (Pending Confirmation)

Rekomendasi berikut **jangan dieksekusi ke kode/database** sebelum pemilik proyek menjawab pertanyaan pada Bagian II (`AS-01` s.d. `AS-05`):

1. **Keputusan Eksekusi Multi-Tenant (`AS-01` & `AS-02`):**
   - Menentukan apakah migrasi Multi-Tenant (`010_create_tenants_settings.sql` & `011_add_tenant_scope.sql`) langsung dikerjakan sekarang sebagai Tahap M9, serta mengonfirmasi desain login Platform Admin (`OQ-12`), kuota paket awal (`OQ-16`), dan kebijakan *impersonation* (`OQ-17`).
2. **Penyusunan Spesifikasi Detail Migrasi `010` & `011` serta Mekanisme RLS (`VF-02` & `VF-03`):**
   - Setelah `AS-01` dan `AS-02` dikonfirmasi, barulah dokumen `SCHEMA_DATABASE.MD` diperbarui ke v3.1 dengan menyertakan penonaktifan sementara trigger imutabilitas (`007`) saat backfill, pembuatan constraint `UNIQUE (tenant_id, id)` untuk Composite FK, serta mekanisme `SET` / `RESET app.current_tenant_id` pada `ConnectionPool`.
3. **Penyusunan Spesifikasi Modul `ISS` (Goods Issue) dan `RPT` (Pelaporan) (`AS-03` & `VF-10`):**
   - Menentukan siklus status `ISS`, tipe pergerakan stok `OUT_ISSUE`, dan daftar laporan `RPT` beserta keputusan struktur kunci saldo masa depan (`P2`) sebelum menulis migrasi tabel `goods_issues`.
4. **Penyatuan Dokumen Frontend (`VF-04` & `AS-04`):**
   - Menempatkan berkas `PRD_FRONTEND.MD` dan `FOLDER_STRUCTURE_FRONTEND.MD` ke dalam `docs/CORE/` serta mengonfirmasi penggunaan JSON body vs `HttpOnly Cookie` untuk refresh token.

---

### 4.3. Usulan Perbaikan Tahapan Pengembangan Fitur (Revised Roadmap)

Agar tahapan pengembangan selaras dengan kondisi aktual repositori (di mana tahap **M0 s.d. M8 Single-Tenant telah selesai 100%**) dan meminimalkan risiko *rework* antarfitur, berikut adalah urutan tahapan pengembangan yang direkomendasikan untuk dicantumkan pada PRD Modular v3.1:

| Tahap | Nama Tahap | Modul Terlibat | Fokus & Dependensi Utama | Status Saat Ini |
|---|---|---|---|---|
| **M0 – M8** | **Baseline MVP Single-Tenant** | `PLT`, `IAM`, `AUD`, `MST`, `WHS`, `INV`, `PUR`, `RCV`, `TRF`, `OPN` | Migrasi `001`–`009`, 87 endpoint API, pengujian `AC-01` s.d. `AC-14` dan benchmark 1 juta baris ledger. | **Selesai (100%)** |
| **M8.1** | **Hardening & Sinkronisasi Baseline** | `MST`, `TRF`, `IAM`, `INV`, `docs/` | Perbaikan celah `update_uom` (`VF-06`), `update_supplier` & `approve_transfer` (`VF-08`), sinkronisasi icon menu (`VF-05`), dan optimasi CTE stok (`VF-12`). | **Siap Dikerjakan (Immediate)** |
| **M9.1** | **Fondasi Database & Konteks Multi-Tenant** | `PLT`, `TNT`, `CFG`, Database | Migrasi `010_create_tenants_settings.sql` & `011_add_tenant_scope.sql` (dengan penanganan trigger `007` & `UNIQUE (tenant_id, id)` sesuai `VF-02`), serta implementasi `current_tenant()` + reset RLS pada `psycopg_pool` (`VF-03`). | **Menunggu Konfirmasi `AS-01` & `AS-02`** |
| **M9.2** | **Layanan Tenant, Konfigurasi, & Adaptasi Modul Inti** | `TNT`, `CFG`, `IAM`, `AUD`, `MST`, `WHS`, `INV`, `PUR`, `RCV`, `TRF`, `OPN` | Endpoint manajemen tenant (`/api/v1/platform/tenants`), pengaturan tenant (`/api/v1/settings`), login ber-`slug`, penegakan kuota (`TNT-BR03`), serta pengujian `AC-15` s.d. `AC-21` + regresi `AC-01` s.d. `AC-14`. | **Setelah M9.1** |
| **M10 (P1a)** | **Desain Ekstensi Dimensi Saldo & Hierarki Lokasi** | `WHS`, `INV`, `MST` | Penambahan hierarki lokasi opsional pada `locations` dan penguncian desain skema `lot_id` / `qty_reserved` agar tidak merombak modul transaksi berikutnya (`VF-10`). | **Pasca-M9** |
| **M11 (P1b)** | **Pengeluaran Barang (Goods Issue) & Pelaporan Operasional** | `ISS`, `RPT`, `INV` | Implementasi dokumen pengeluaran barang (`ISS`) melalui `inventory_service.apply_movement()` (`OUT_ISSUE`) dan endpoint laporan agregat operasional (`RPT`). | **Setelah M10 & Konfirmasi `AS-03`** |
| **M12 (P2–P5)** | **Perluasan Alur Transaksi, Opname Terjadwal, & Valuasi** | `PUR`, `RCV`, `TRF`, `OPN`, `INV` | Persetujuan PO bertingkat, retur pemasok, penerimaan transfer bertahap, opname per zona, serta reservasi & valuasi persediaan (FIFO/Average). | **Pasca-M11** |
