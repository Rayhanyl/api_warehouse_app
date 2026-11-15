# Warehouse Management System (WMS) — REST API

Layanan REST API manajemen gudang multi-lokasi (*multi-warehouse & bin location*) berbasis **Python**, **FastAPI**, dan **PostgreSQL** (akses SQL langsung via `psycopg` 3 tanpa ORM). Dirancang untuk memberikan kontrol operasional persediaan secara *real-time*, akurat, aman terhadap akses konkuren (*row-level locking*), dan memiliki ketertelusuran penuh (*append-only stock ledger & audit log*).

---

## Fitur Utama (Ruang Lingkup MVP & Ekstensi Fase 1)

1. **Autentikasi, RBAC, Keamanan Cookie & Warehouse Scoping:**
   * Autentikasi JWT (*Access Token* 15 menit & *Refresh Token* 7 hari dengan rotasi serta deteksi penggunaan ulang token yang dicabut, dikirim melalui cookie `HttpOnly; SameSite=Lax` maupun body opsional untuk klien API).
   * Penguncian akun sementara setelah 5 kali gagal login berturut-turut dan pembersihan cookie saat logout.
   * 5 Peran (*Super Admin*, *Warehouse Manager*, *Purchasing Staff*, *Warehouse Staff*, *Auditor*) dengan 24 kode *permission* granular dan penegakan pembatasan penugasan gudang (*global `warehouse_id` scoping*) di seluruh endpoint operasional.
   * Endpoint profil `/auth/me` diperkaya dengan `has_all_warehouse_access` dan daftar referensi `warehouses` aktif.
2. **Master Data:**
   * Kategori, Satuan Ukur (*UoM* dengan pengaturan `allow_decimal`), Barang (*Item* dengan SKU unik dan Barcode EAN/UPC/GS1 internal opsional unik via `012_add_barcode_to_items.sql`), Pemasok (*Supplier*), Gudang (*Warehouse* dengan pengaturan `allow_negative_stock`), dan Lokasi Penyimpanan (*Storage Location / Bin*).
   * Import Excel massal untuk Barang dan Pemasok (`openpyxl`) serta tanpa penghapusan permanen (*soft deactivate* via `is_active` dengan validasi saldo & dokumen aktif).
3. **Dashboard Operasional & Menu Navigasi Dinamis:**
   * Endpoint `GET /api/v1/dashboard/summary` menyajikan ringkasan metrik stok real-time, antrean dokumen operasional tertunda, dan mutasi terkini sesuai *warehouse scoping* pengguna (mendukung filter `?warehouse_id=`).
   * Menu navigasi dinamis (`/api/v1/menus/my-menu` & CRUD `/api/v1/menus`) tersaring otomatis oleh permission aktif pengguna, termasuk konsolidasi menu stok (`013_consolidate_stock_monitoring_menu.sql`) dan menu Template Dokumen (`015_create_document_templates_table.sql`).
4. **Purchase Order (PO) & Goods Receipt (GR):**
   * Siklus PO (`DRAFT` → `ISSUED` → `PARTIALLY_RECEIVED` / `RECEIVED` / `CLOSED` / `CANCELLED`).
   * Penerimaan barang bertahap (parsial) maupun penuh terhadap PO dengan pencegahan *over-receipt* di bawah penguncian baris (`SELECT ... FOR UPDATE`).
   * **Cetak Bukti Penerimaan Barang / GRN (AC-32)**, **Template Dokumen Modular (Tahap 17)**, dan **Pemindai Barcode / QR (AC-33)** saat penerimaan.
5. **Transfer Stok Antar-Gudang / Antar-Lokasi:**
   * Siklus dua tahap fisik eksplisit (`DRAFT` → `APPROVED` → `SHIPPED` → `RECEIVED` / `CANCELLED`) untuk melacak stok dalam perjalanan (*in-transit*).
   * Pencatatan selisih penerimaan (`qty_received < qty`) dengan kewajiban alasan selisih (`variance_reason`).
   * **Cetak Surat Jalan Transfer Stok Fisik (AC-32)** dan **Pemindai Barcode / QR (AC-33)**.
6. **Stock Opname & Saldo Awal:**
   * Pengambilan *snapshot* `qty_system` dan **pembekuan lokasi** otomatis selama sesi berlangsung (`IN_PROGRESS` / `WAITING_APPROVAL`).
   * Rekonsiliasi stok fisik dengan persetujuan *Warehouse Manager* (`COMPLETED` menghasilkan penyesuaian `ADJUSTMENT_PLUS` / `ADJUSTMENT_MINUS`), input temuan/saldo awal berbasis scan barcode.
7. **Template Dokumen Cetak Modular (`/api/v1/document-templates`):**
   * Pengaturan tata letak dokumen cetak berbasis PostgreSQL (`document_templates` — `GOODS_RECEIPT`, `STOCK_TRANSFER`, `PURCHASE_ORDER`), termasuk upload logo aman (validasi magic bytes PNG/JPEG/WEBP maks. 2 MB), ukuran kertas (`A4`/`LETTER`/`F4`), margin, urutan bagian, visibilitas kolom, dan blok tanda tangan.
8. **Imutabilitas Buku Besar, Audit Log Kaya Konteks & Monitoring Alert:**
   * Tabel `stock_movements` dan `audit_logs` bersifat *append-only*, dilindungi *trigger* PostgreSQL serta pencabutan hak `UPDATE`/`DELETE`/`TRUNCATE` pada role `wms_app`.
   * Enrichment audit log (`014_enhance_audit_logs.sql`: `status`, `user_agent`, `request_id`, `details` JSONB), sanitasi otomatis rahasia/kredensial (`app/core/sanitizer.py`), filter `category` (`business`/`security`/`failed`) & `include_technical`, serta penghapusan spam rotasi token rutin.
   * Integrasi peringatan galat 5xx/fatal dan monitoring infrastruktur ke Telegram Bot asinkron (`app/core/telegram_alert.py`).

---

## Teknologi Utama

| Komponen | Teknologi |
| --- | --- |
| Bahasa & Framework | Python 3.11+, FastAPI, Pydantic v2 (`pydantic-settings`) |
| Database & Driver | PostgreSQL 13+, `psycopg[binary,pool]` v3 (sinkron, tanpa ORM) |
| Keamanan | `PyJWT` (HS256), `argon2-cffi` (Argon2id password hashing), `HttpOnly` Refresh Cookie, `sanitizer.py` |
| Migrasi Database | Berkas `.sql` berurutan (*forward-only*, `001`–`015`) + runner `db/migrate.py` |
| Excel & Upload | `openpyxl`, `python-multipart` |
| Monitoring & Alert | Integrasi HTTP `httpx` non-blocking ke Telegram Bot API (`telegram_alert.py`) |
| Pengujian & Coverage | `pytest`, `httpx`, `pytest-cov` (84 test lulus terhadap PostgreSQL `wms_test`) |

---

## Status Implementasi Saat Ini

Pengembangan dilakukan bertahap sesuai urutan milestone pada [`docs/core/FOLDER_STRUCTURE.MD`](docs/core/FOLDER_STRUCTURE.MD):

| Tahap | Modul / Cakupan | Status | Acceptance Criteria & Verifikasi |
| :---: | --- | :---: | --- |
| **M0** | Kerangka aplikasi, connection pool, middleware `X-Request-ID`, exception handler, `/health` & `/api/v1/health` | ✅ **Selesai** | `AC-17` |
| **M1** | Runner migrasi (`db/migrate.py`), migrasi DDL `001`–`008`, role `wms_app`, trigger imutabilitas, seed RBAC, `create_superadmin.py` | ✅ **Selesai** | `AC-08`, `AC-18` |
| **M2** | Autentikasi JWT, rotasi & *reuse detection* Refresh Token, *account lockout*, CRUD Pengguna, RBAC, *Warehouse Scoping*, & Audit Log | ✅ **Selesai** | `AC-05`, `AC-11`, `AC-12` |
| **M3** | Master Data (Kategori, UoM, Barang, Pemasok) & Gudang + Lokasi Penyimpanan | ✅ **Selesai** | `AC-05`, `AC-12`, `AC-19`, `AC-20` |
| **M4** | Inti Persediaan (`inventory_service.apply_movement`), Saldo Stok, & Buku Besar Pergerakan | ✅ **Selesai** | `AC-03`, `AC-12` |
| **M5** | Purchase Order (PO) & Goods Receipt (GR) | ✅ **Selesai** | `AC-01`, `AC-07`, `AC-13`, `AC-15`, `AC-21` |
| **M6** | Stock Transfer Dua Tahap (`DRAFT` → `APPROVED` → `SHIPPED` → `RECEIVED`) | ✅ **Selesai** | `AC-02`, `AC-03`, `AC-06`, `AC-09`, `AC-21` |
| **M7** | Stock Opname, Pembekuan Lokasi, & Rekonsiliasi Stok | ✅ **Selesai** | `AC-04`, `AC-10`, `AC-21` |
| **M8** | Tinjauan akhir AC, optimasi indeks (`010`, `011`), performa query stok/ledger, logging, & request ID | ✅ **Selesai** | `AC-01` s.d. `AC-22` |
| **Fase 1 Ekstensi** | Import Excel (Item/Supplier), Barcode Barang (`012`), Menu Dinamis (`009`, `013`), Dashboard Summary, Cetak Fisik GRN/Surat Jalan | ✅ **Selesai** | `AC-14`, `AC-30` s.d. `AC-38` |
| **Tahap 12–30 (Hardening & Operasional)** | Audit log enrichment (`014`), validasi terpusat (`validation.py`), template dokumen cetak (`015`), HttpOnly cookie auth, global `warehouse_id` scoping, pembersihan noise audit (`category`/`include_technical`), multi-env guard (`env_files.py`), & Telegram alert | ✅ **Selesai** | **84/84 pytest lulus** (`wms_test`) |

---

## Arsitektur & Struktur Proyek

Proyek mengikuti arsitektur berlapis satu arah: **`routes` → `services` → `repositories` → `core/database`**.

```text
api_warehouse_app/
├── app/
│   ├── main.py                     # Inisialisasi FastAPI, lifespan connection pool, router & exception handler
│   ├── core/                       # config.py, database.py, env_files.py, exceptions.py, logging.py, middleware.py, permissions.py, sanitizer.py, security.py, telegram_alert.py, validation.py
│   ├── schemas/                    # Kontrak request/response Pydantic (kuantitas Decimal diserialisasi sebagai string)
│   ├── api/
│   │   ├── deps.py                 # Dependency get_current_user, validasi proxy IP & koneksi per-request
│   │   └── routes/                 # Endpoint HTTP tipis: health, auth, users, menus, master, warehouses, stock, purchase_orders, goods_receipts, stock_transfers, stock_opnames, audit_logs, dashboard, document_templates
│   ├── services/                   # Logika bisnis, access_service (warehouse scoping), audit_service, inventory_service, document_template_service, dll.
│   ├── repositories/               # Satu-satunya lapisan yang berisi query SQL berparameter
│   └── utils/                      # Enum status/tipe pergerakan & helper pagination (whitelist ORDER BY)
├── db/
│   ├── init/                       # Skrip inisialisasi role database aplikasi (wms_app)
│   ├── migrations/                 # 15 berkas migrasi SQL berurutan (001_... s.d. 015_...)
│   ├── seeds/                      # Data contoh untuk pengembangan lokal (dev_seed.sql)
│   └── migrate.py                  # Runner migrasi SQL (mencatat versi di tabel schema_migrations)
├── docs/
│   ├── API/                        # Dokumentasi REST API per modul dan indeks (95 path/method)
│   ├── core/                       # PRD, skema DB, arsitektur, multi-env guide, security guide, & Telegram monitoring guide
│   ├── QA/                         # Rencana dan spesifikasi pengujian Backend & Frontend
│   ├── RULE_SYSTEM/                # Ringkasan aturan sistem & tinjauan PRD
│   └── STANDARDS/                  # Standar dokumentasi & technical quality gate
├── scripts/
│   ├── create_superadmin.py        # Bootstrap akun Super Admin pertama
│   └── seed_users.py               # Membuat akun pengembangan untuk setiap role
├── tests/                          # 18 suite pengujian otomatis (84 pytest lulus) terhadap PostgreSQL wms_test
├── htmlcov/                        # Hasil generate laporan web Code Coverage (diabaikan oleh Git)
├── .env.example                    # Template variabel lingkungan umum
├── .env.local.example              # Template variabel lingkungan untuk koneksi langsung (PostgreSQL lokal)
├── .env.docker.example             # Template variabel lingkungan untuk Docker Compose
├── docker-compose.yml              # Orkestrasi container PostgreSQL & API
├── pyproject.toml                  # Konfigurasi proyek, dependensi, pytest, dan coverage
└── AGENTS.MD                       # Aturan kerja dan batasan invarian bisnis
```

### Membuat User Pengembangan untuk Setiap Role

Setelah migrasi selesai, jalankan seeder berikut:

```powershell
python scripts/seed_users.py
```

Seeder membuat satu akun untuk setiap role RBAC. Password diminta melalui
prompt tersembunyi. Untuk penggunaan non-interaktif, isi environment berikut
sebelum menjalankan script:

```powershell
$env:SEED_SUPER_ADMIN_PASSWORD = "ubah-password-ini"
$env:SEED_WAREHOUSE_MANAGER_PASSWORD = "ubah-password-ini"
$env:SEED_PURCHASING_STAFF_PASSWORD = "ubah-password-ini"
$env:SEED_WAREHOUSE_STAFF_PASSWORD = "ubah-password-ini"
$env:SEED_AUDITOR_PASSWORD = "ubah-password-ini"
python scripts/seed_users.py
```

Seeder tidak mengubah akun yang sudah ada dan tidak pernah mencetak password.

---

## Persiapan & Cara Menjalankan Secara Lokal

### 1. Prasyarat

* **Python 3.10 / 3.11+**
* **PostgreSQL 13+** (lokal via DBeaver/pgAdmin atau melalui Docker)

### 2. Instalasi Dependensi

Aktifkan *virtual environment* lalu pasang paket beserta dependensi pengujian (`dev`):

```powershell
# Windows PowerShell
.\venv\Scripts\Activate.ps1
pip install fastapi "uvicorn[standard]" "psycopg[binary,pool]" pydantic-settings argon2-cffi pyjwt pytest httpx pytest-cov
```

### 3. Konfigurasi Variabel Lingkungan (`.env`)

Tersedia template konfigurasi sesuai cara Anda menjalankan database:
* **Koneksi langsung ke PostgreSQL lokal / DBeaver:** salin dari `.env.local.example`
* **Menggunakan Docker Compose:** salin dari `.env.docker.example`

```powershell
Copy-Item .env.local.example .env
```

Contoh isi `.env` (semua kredensial database dan `JWT_SECRET` minimal 32 karakter wajib diisi di `.env`):

```env
DATABASE_URL=postgresql://wms_app:<APP_PASSWORD>@127.0.0.1:5432/warehouse_db
MIGRATION_DATABASE_URL=postgresql://wms_owner:<OWNER_PASSWORD>@127.0.0.1:5432/warehouse_db
TEST_DATABASE_URL=postgresql://wms_owner:<OWNER_PASSWORD>@127.0.0.1:5432/wms_test

JWT_SECRET=ganti-dengan-string-acak-minimal-32-karakter
JWT_ALGORITHM=HS256
ACCESS_TOKEN_MINUTES=15
REFRESH_TOKEN_DAYS=7
LOGIN_MAX_ATTEMPTS=5
LOGIN_LOCK_MINUTES=15
TRUSTED_PROXY_IPS=[]
```

### 4. Menjalankan Migrasi Database & Bootstrap Super Admin

Jalankan migrasi skema menggunakan koneksi pemilik skema (`MIGRATION_DATABASE_URL`), lalu buat akun *Super Admin* pertama:

```powershell
.\venv\Scripts\python.exe -m db.migrate
.\venv\Scripts\python.exe scripts/create_superadmin.py
```

### 5. Menjalankan Server API

```powershell
.\venv\Scripts\python.exe -m uvicorn app.main:app --reload
```

Setelah server berjalan:
* **Swagger UI (OpenAPI):** `http://127.0.0.1:8000/docs`
* **ReDoc:** `http://127.0.0.1:8000/redoc`
* **Health Check:** `http://127.0.0.1:8000/health` atau `http://127.0.0.1:8000/api/v1/health`

---

## Pengujian (*Testing*) & Code Coverage

Pengujian dijalankan terhadap database PostgreSQL sungguhan (`TEST_DATABASE_URL` / `wms_test`) untuk memverifikasi perilaku transaksi, *row-level locking*, konkurensi, *trigger* imutabilitas, dan *constraint* database:

```powershell
# 1. Menjalankan seluruh pengujian
.\venv\Scripts\python.exe -m pytest

# 2. Menjalankan pengujian untuk Acceptance Criteria tertentu (mis. AC-08 imutabilitas)
.\venv\Scripts\python.exe -m pytest -k ac08

# 3. Menjalankan pengujian sekaligus menghasilkan laporan Code Coverage (Terminal + Web HTML)
.\venv\Scripts\python.exe -m pytest --cov=app --cov-report=term-missing --cov-report=html
```

### Membuka Laporan Web Code Coverage (`htmlcov`)

Setelah menjalankan perintah coverage di atas, Anda dapat melihat detail baris kode yang sudah dan belum teruji melalui browser:

```powershell
# Buka langsung file HTML di browser default Windows
Invoke-Item .\htmlcov\index.html

# Atau jalankan melalui HTTP server lokal di http://127.0.0.1:8080
.\venv\Scripts\python.exe -m http.server 8080 --directory htmlcov
```

---

## Dokumentasi API & Dokumen Rujukan

### Dokumentasi Endpoint REST API (`docs/API/`)
* [**Indeks Dokumentasi API (`docs/API/README.md`)**](docs/API/README.md) — Konvensi global, modul aktif, daftar 95 path/method, dan ringkasan verifikasi.
* [**Autentikasi & Otorisasi**](docs/API/authentication.md) — Login, cookie `HttpOnly` Refresh Token, rotasi & deteksi reuse, logout, profil `/me`, dan ganti kata sandi.
* [**Pengguna, RBAC & Penugasan Gudang**](docs/API/users.md) — CRUD pengguna, permission, dan *Warehouse Scoping*.
* [**Menu Navigasi Dinamis**](docs/API/menus.md) — Pohon menu terfilter permission & administrasi katalog menu.
* [**Dashboard Operasional**](docs/API/dashboard.md) — Ringkasan KPI stok, tugas tertunda, mutasi terkini, dan filter gudang aktif (`GET /api/v1/dashboard/summary`).
* [**Template Dokumen Cetak**](docs/API/document-templates.md) — Konfigurasi tata letak dokumen cetak GRN/Surat Jalan/PO & upload logo perusahaan.
* [**Master Data**](docs/API/master-data.md) — Kategori, UoM, pemasok (termasuk import Excel), dan barang (termasuk barcode & import Excel).
* [**Gudang & Lokasi Penyimpanan**](docs/API/warehouses.md) — Gudang, lokasi penyimpanan, dan penugasan akses (`purpose=transfer_destination`, `warehouse_id`).
* [**Purchase Order**](docs/API/purchase-orders.md) — Pembuatan, penerbitan, pemenuhan, pembatalan, dan penutupan PO.
* [**Goods Receipt**](docs/API/goods-receipts.md) — Penerimaan PO, posting saldo/ledger, dan pencegahan over-receipt.
* [**Transfer Stok**](docs/API/stock-transfers.md) — Persetujuan, pengiriman, penerimaan, dan pencatatan selisih transfer.
* [**Stock Opname**](docs/API/stock-opnames.md) — Snapshot, pembekuan lokasi, hitung fisik, persetujuan, dan penyesuaian.
* [**Stok & Buku Besar**](docs/API/stock-ledger.md) — Saldo, stok dalam perjalanan, dan pergerakan stok.
* [**Audit Log**](docs/API/audit-logs.md) — Pembacaan jejak audit *append-only* (`category`, `include_technical`, korelasi `request_id`).
* [**Health Check**](docs/API/health.md) — Status layanan dan konektivitas pool PostgreSQL.

### Dokumen Spesifikasi, Operasional & QA (`docs/core/`, `docs/QA/`, `docs/STANDARDS/`)
* [**PRD General**](docs/core/PRD_GENERAL.md) — Master product requirements, scope, role, workflow, NFR, dan acceptance criteria.
* [**PRD Backend**](docs/core/PRD_BACKEND.md) — Kebutuhan API, service, validasi, keamanan, transaksi, dan error handling.
* [**PRD Frontend**](docs/core/PRD_FRONTEND.md) — Struktur halaman, UX, state, permission UI, dan integrasi API.
* [**API Contract**](docs/core/API_CONTRACT.md) — Kontrak global REST API, error envelope, pagination, & aturan impor/barcode.
* [**Struktur Proyek**](docs/core/FOLDER_STRUCTURE.MD) — Arsitektur backend & frontend, transaksi, locking, serta urutan milestone.
* [**Database Design**](docs/core/DATABASE_DESIGN.md) — Pemetaan entitas, relasi, integritas data, dan migration ownership.
* [**Skema Database**](docs/core/SCHEMA_DATABASE.MD) — Entitas, relasi, migrasi (`001`–`015`), dan trigger.
* [**Environment Setup Guide**](docs/core/environment-setup-guide.md) — Panduan multi-environment lokal/dev-server & guard proteksi DB production.
* [**Security Guide**](docs/core/security-server-and-app.md) — Keamanan server, firewall, cookie `HttpOnly`, dan hardening aplikasi.
* [**Telegram Monitoring Guide**](docs/core/telegram-monitoring-guide.md) — Konfigurasi alert galat API 5xx & pemantauan container ke Telegram Bot.
* [**CI/CD & Deployment Guide**](docs/core/DEPLOYMENT_GUIDE_CICD.md) — Alur PR Git, deployment server, dan pipeline CI/CD.
* [**Panduan QA**](docs/QA/QA.MD) — Matriks Acceptance Criteria Backend (84 tes `pytest`) & verifikasi Frontend (101 tes `vitest`).
* [**AGENTS.MD**](AGENTS.MD) — Aturan kerja dan batasan invarian bisnis.
