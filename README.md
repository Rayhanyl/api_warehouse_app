# Warehouse Management System (WMS) — REST API

Layanan REST API manajemen gudang multi-lokasi (*multi-warehouse & bin location*) berbasis **Python**, **FastAPI**, dan **PostgreSQL** (akses SQL langsung via `psycopg` 3 tanpa ORM). Dirancang untuk memberikan kontrol operasional persediaan secara *real-time*, akurat, aman terhadap akses konkuren (*row-level locking*), dan memiliki ketertelusuran penuh (*append-only stock ledger & audit log*).

---

## Fitur Utama (Ruang Lingkup MVP)

1. **Autentikasi, RBAC & Warehouse Scoping:**
   * Autentikasi JWT (*Access Token* 15 menit & *Refresh Token* 7 hari dengan rotasi serta deteksi penggunaan ulang token yang dicabut).
   * Penguncian akun sementara setelah 5 kali gagal login berturut-turut.
   * 5 Peran (*Super Admin*, *Warehouse Manager*, *Purchasing Staff*, *Warehouse Staff*, *Auditor*) dengan 24 kode *permission* granular dan pembatasan penugasan gudang (*warehouse scoping*).
2. **Master Data:**
   * Kategori, Satuan Ukur (*UoM* dengan pengaturan `allow_decimal`), Barang (*Item* dengan SKU unik), Pemasok (*Supplier*), Gudang (*Warehouse* dengan pengaturan `allow_negative_stock`), dan Lokasi Penyimpanan (*Storage Location / Bin*).
   * Tanpa penghapusan permanen (*soft deactivate* via `is_active` dengan validasi saldo & dokumen aktif).
3. **Purchase Order (PO) & Goods Receipt (GR):**
   * Siklus PO (`DRAFT` → `ISSUED` → `PARTIALLY_RECEIVED` / `RECEIVED` / `CLOSED` / `CANCELLED`).
   * Penerimaan barang bertahap (parsial) maupun penuh terhadap PO dengan pencegahan *over-receipt* di bawah penguncian baris (`SELECT ... FOR UPDATE`).
4. **Transfer Stok Antar-Gudang / Antar-Lokasi:**
   * Siklus dua tahap fisik eksplisit (`DRAFT` → `APPROVED` → `SHIPPED` → `RECEIVED` / `CANCELLED`) untuk melacak stok dalam perjalanan (*in-transit*).
   * Pencatatan selisih penerimaan (`qty_received < qty`) dengan kewajiban alasan selisih (`variance_reason`).
5. **Stock Opname & Saldo Awal:**
   * Pengambilan *snapshot* `qty_system` dan **pembekuan lokasi** otomatis selama sesi berlangsung (`IN_PROGRESS` / `WAITING_APPROVAL`).
   * Rekonsiliasi stok fisik dengan persetujuan *Warehouse Manager* (`COMPLETED` menghasilkan penyesuaian `ADJUSTMENT_PLUS` / `ADJUSTMENT_MINUS`), sekaligus menjadi mekanisme input saldo awal gudang.
6. **Imutabilitas Buku Besar & Audit Log:**
   * Tabel `stock_movements` dan `audit_logs` bersifat *append-only*, dilindungi oleh *trigger* PostgreSQL serta pencabutan hak `UPDATE`/`DELETE`/`TRUNCATE` pada role database aplikasi (`wms_app`).

---

## Teknologi Utama

| Komponen | Teknologi |
| --- | --- |
| Bahasa & Framework | Python 3.11+, FastAPI, Pydantic v2 (`pydantic-settings`) |
| Database & Driver | PostgreSQL 13+, `psycopg[binary,pool]` v3 (sinkron, tanpa ORM) |
| Keamanan | `PyJWT` (HS256), `argon2-cffi` (Argon2id password hashing) |
| Migrasi Database | Berkas `.sql` berurutan (*forward-only*) + runner `db/migrate.py` |
| Pengujian & Coverage | `pytest`, `httpx`, `pytest-cov` (diuji langsung terhadap PostgreSQL sungguhan `wms_test`) |

---

## Status Implementasi Saat Ini

Pengembangan dilakukan bertahap sesuai urutan milestone pada [`docs/CORE/FOLDER_STRUCTURE.MD`](docs/CORE/FOLDER_STRUCTURE.MD):

| Tahap | Modul / Cakupan | Status | Acceptance Criteria Tercakup |
| :---: | --- | :---: | --- |
| **M0** | Kerangka aplikasi, connection pool, middleware `X-Request-ID`, exception handler, `/health` & `/api/v1/health` | ✅ **Selesai** | – |
| **M1** | Runner migrasi (`db/migrate.py`), migrasi DDL `001`–`008`, role `wms_app`, trigger imutabilitas, seed RBAC, `create_superadmin.py` | ✅ **Selesai** | `AC-08` |
| **M2** | Autentikasi JWT, rotasi & *reuse detection* Refresh Token, *account lockout*, CRUD Pengguna, RBAC, *Warehouse Scoping*, & Audit Log | ✅ **Selesai** | `AC-05`, `AC-11`, `AC-12` |
| **M3** | Master Data (Kategori, UoM, Barang, Pemasok) & Gudang + Lokasi Penyimpanan | ✅ **Selesai** | `AC-05`, `AC-12` |
| **M4** | Inti Persediaan (`inventory_service.apply_movement`), Saldo Stok, & Buku Besar Pergerakan | ✅ **Selesai** | Pembacaan saldo/ledger dan penerapan mutasi stok |
| **M5** | Purchase Order (PO) & Goods Receipt (GR) | ✅ **Selesai** | `AC-01`, `AC-07`, `AC-13` |
| **M6** | Stock Transfer Dua Tahap (`DRAFT` → `APPROVED` → `SHIPPED` → `RECEIVED`) | ✅ **Selesai** | `AC-02`, `AC-03`, `AC-06`, `AC-09` |
| **M7** | Stock Opname, Pembekuan Lokasi, & Rekonsiliasi Stok | ✅ **Selesai** | `AC-04`, `AC-10` |
| **M8** | Tinjauan akhir AC, performa query stok/ledger, logging, dan request ID | ✅ **Selesai** | `AC-01` s.d. `AC-13`; hasil benchmark lokal diringkas di indeks API |

---

## Arsitektur & Struktur Proyek

Proyek mengikuti arsitektur berlapis satu arah: **`routes` → `services` → `repositories` → `core/database`**.

```text
warehouse_app/
├── app/
│   ├── main.py                     # Inisialisasi FastAPI, lifespan connection pool, router & exception handler
│   ├── core/                       # Konfigurasi (.env), connection pool, JWT/Argon2, permission, DomainError, logging
│   ├── schemas/                    # Kontrak request/response Pydantic (kuantitas Decimal diserialisasi sebagai string)
│   ├── api/
│   │   ├── deps.py                 # Dependency get_current_user, validasi proxy IP & koneksi per-request
│   │   └── routes/                 # Endpoint HTTP tipis & pemeriksaan require_permission()
│   ├── services/                   # Logika bisnis, pemeriksaan warehouse scoping, pemilik transaksi (with conn.transaction():)
│   ├── repositories/               # Satu-satunya lapisan yang berisi query SQL berparameter
│   └── utils/                      # Enum status/tipe pergerakan & helper pagination (whitelist ORDER BY)
├── db/
│   ├── init/                       # Skrip inisialisasi role database aplikasi (wms_app)
│   ├── migrations/                 # Berkas migrasi SQL berurutan (001 s.d. 008)
│   ├── seeds/                      # Data contoh untuk pengembangan lokal (dev_seed.sql)
│   └── migrate.py                  # Runner migrasi SQL (mencatat versi di tabel schema_migrations)
├── docs/
│   ├── API/                        # Dokumentasi REST API per modul dan indeks
│   ├── CORE/                       # Dokumen acuan utama (PRD, FOLDER_STRUCTURE, SCHEMA_DATABASE, aturan dokumentasi)
│   └── QA/                         # Rencana dan spesifikasi pengujian
├── scripts/
│   ├── create_superadmin.py        # Bootstrap akun Super Admin pertama
│   └── seed_users.py               # Membuat akun pengembangan untuk setiap role
├── tests/                          # Pengujian otomatis berbasis pytest terhadap database wms_test
├── htmlcov/                        # Hasil generate laporan web Code Coverage (diabaikan oleh Git)
├── .env.example                    # Template variabel lingkungan umum
├── .env.local.example              # Template variabel lingkungan untuk koneksi langsung (DBeaver / PostgreSQL lokal)
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
* [**Indeks Dokumentasi API (`docs/API/README.md`)**](docs/API/README.md) — Konvensi global, modul aktif, daftar 82 path/method, dan ringkasan verifikasi.
* [**Autentikasi & Otorisasi**](docs/API/authentication.md) — Login, rotasi *Refresh Token*, deteksi penggunaan ulang token, logout, profil `/me`, dan ganti kata sandi.
* [**Pengguna, RBAC & Penugasan Gudang**](docs/API/users.md) — CRUD pengguna, permission, dan *Warehouse Scoping*.
* [**Master Data**](docs/API/master-data.md) — Kategori, UoM, pemasok, dan barang.
* [**Gudang & Lokasi Penyimpanan**](docs/API/warehouses.md) — Gudang, lokasi penyimpanan, dan penugasan akses.
* [**Purchase Order**](docs/API/purchase-orders.md) — Pembuatan, penerbitan, pemenuhan, pembatalan, dan penutupan PO.
* [**Goods Receipt**](docs/API/goods-receipts.md) — Penerimaan PO, posting saldo/ledger, dan pencegahan over-receipt.
* [**Transfer Stok**](docs/API/stock-transfers.md) — Persetujuan, pengiriman, penerimaan, dan pencatatan selisih transfer.
* [**Stock Opname**](docs/API/stock-opnames.md) — Snapshot, pembekuan lokasi, hitung fisik, persetujuan, dan penyesuaian.
* [**Stok & Buku Besar**](docs/API/stock-ledger.md) — Saldo, stok dalam perjalanan, dan pergerakan stok.
* [**Audit Log**](docs/API/audit-logs.md) — Pembacaan jejak audit *append-only*.
* [**Health Check**](docs/API/health.md) — Status layanan dan konektivitas pool PostgreSQL.

### Dokumen Spesifikasi, Arsitektur & QA
* [**PRD**](docs/CORE/PRODUCT_REQUIREMENTS_DOCUMENT.MD) — Kebutuhan fungsional, RBAC, status, validasi, error, dan AC-01–AC-13.
* [**Struktur Proyek**](docs/CORE/FOLDER_STRUCTURE.MD) — Arsitektur, transaksi, locking, serta urutan milestone.
* [**Skema Database**](docs/CORE/SCHEMA_DATABASE.MD) — Entitas, relasi, migrasi, dan trigger.
* [**Aturan Dokumentasi API**](docs/CORE/RULE_CREATE_API_DOKUMENTATION.MD) — Standar dokumentasi endpoint.
* [**Panduan QA**](docs/QA/QA.MD) — Cakupan backend saat ini dan rencana QA frontend bila klien terpisah dibangun.
* [**AGENTS.md**](AGENTS.MD) — Aturan kerja dan batasan invarian bisnis.
