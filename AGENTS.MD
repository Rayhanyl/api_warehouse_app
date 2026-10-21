# AGENTS.md — Aturan Kerja untuk AI Coding Agent (WMS API)

Dokumen ini mengikat setiap agen yang menulis, mengubah, atau meninjau kode di repositori ini. Tujuannya satu: **membangun persis apa yang ada di PRD, tidak kurang dan tidak lebih.**

---

## 1. Sumber Kebenaran

Urutan rujukan (yang di atas menang bila bertentangan):

1. `docs/core/PRODUCT_REQUIREMENTS_DOCUMENT.md` — apa yang dibangun: lingkup, peran, status dokumen, aturan bisnis, acceptance criteria (AC-01 s.d. AC-13), entitas data (Lampiran A), konvensi API dan kode error (Lampiran B).
2. `docs/core/FOLDER_STRUCTURE.md` — bagaimana kode disusun: folder, lapisan, pola transaksi, pola penguncian, urutan implementasi.
3. `AGENTS.md` (dokumen ini, di root repositori) — cara agen bekerja.

Dokumen rujukan nomor 1 dan 2 tersimpan di folder `docs/core`.

Aturan turunannya:

* **Baca bagian PRD yang relevan sebelum menulis kode.** Jangan mengandalkan ingatan atau asumsi umum tentang "WMS pada umumnya".
* **Jangan mengubah PRD atau FOLDER_STRUCTURE** tanpa persetujuan eksplisit dari pemilik proyek. Bila perubahan disetujui, catat di Lampiran C PRD.
* Bila PRD ambigu, bertentangan dengan dirinya sendiri, atau tidak menjawab suatu kasus: **berhenti dan tanya** (lihat bagian 10). Jangan mengarang aturan sendiri.

---

## 2. Teknologi Terkunci

| Hal | Ketentuan |
| --- | --- |
| Bahasa & framework | Python, FastAPI, Pydantic v2 |
| Database | PostgreSQL, diakses **langsung** lewat `psycopg` 3 + `psycopg_pool` (sinkron) |
| Autentikasi | JWT (PyJWT, HS256), hash kata sandi `argon2-cffi` (Argon2id) |
| Migrasi | Berkas `.sql` berurutan + `db/migrate.py` + tabel `schema_migrations` |
| Pengujian | `pytest` + `httpx`, terhadap PostgreSQL sungguhan |

**Dilarang tanpa persetujuan eksplisit:**

* ORM atau pembangun query apa pun: SQLAlchemy, SQLModel, Tortoise, Peewee, Django ORM, dan sejenisnya. **Alembic juga dilarang** (tidak ada `--autogenerate`).
* Mencampur `async def` dengan driver sinkron. Route memakai `def` biasa.
* Menambah infrastruktur baru: Redis, Celery, RabbitMQ, Kafka, cache, *message queue*, *background worker*.
* Menambah dependensi baru di luar daftar pada `docs/core/FOLDER_STRUCTURE.md`. Bila perlu, tanyakan dulu beserta alasannya.

---

## 3. Batas Lingkup (MVP)

Hanya bangun yang tercantum di PRD bagian 2.1. **Fitur berikut di luar lingkup dan tidak boleh diimplementasikan, bahkan "sedikit" atau "sebagai persiapan":**

* Lot/batch/expiry, serial number, inventory costing/valuasi, stock reservation.
* Goods Issue (pengeluaran barang), retur ke pemasok, pembalikan (*reversal*) GR.
* Konversi satuan (UoM conversion), penerimaan Transfer bertahap, persetujuan PO multi-level.
* UI/frontend, notifikasi, integrasi eksternal (ERP, barcode, email, WhatsApp).

Selain itu, **jangan menambah tanpa persetujuan:** endpoint, tabel, kolom, status dokumen, kode permission, kode error, atau peran yang tidak ada di PRD. Jangan menambah fitur "bonus", utilitas serbaguna, atau abstraksi spekulatif.

---

## 4. Arsitektur Berlapis

Arah ketergantungan hanya satu: **routes → services → repositories → core/database.**

| Lapisan | Tugas | Dilarang |
| --- | --- | --- |
| `api/routes` | Parse request, `Depends(require_permission(...))`, panggil **satu** fungsi service, kembalikan schema. | SQL, aturan bisnis, `commit`, membuat error bisnis manual. |
| `services` | Aturan bisnis, urutan langkah use case, **membuka transaksi** (`with conn.transaction():`), melempar `DomainError`. | Import FastAPI/HTTP, menulis string SQL. |
| `repositories` | **Satu-satunya tempat SQL.** SQL berparameter, menerima `conn`, mengembalikan `dict`. | Keputusan bisnis, membuka/commit transaksi. |
| `schemas` | Validasi bentuk request/response. | Logika bisnis, akses DB. |
| `core` | Config, pool, keamanan, exception. | Mengetahui detail modul gudang. |

* Ikuti struktur folder di `docs/core/FOLDER_STRUCTURE.md`. **Jangan membuat folder atau lapisan baru** (misalnya `controllers/`, `domain/`, `managers/`, `helpers/`) dan jangan memindahkan file keluar dari tempatnya.
* Pemeriksaan **permission** dilakukan di route; pemeriksaan **penugasan gudang** (`ensure_warehouse_access`) dilakukan di service.
* **Middleware hanya** `core/middleware.py` untuk *request id* (dan CORS di `main.py` bila perlu). Autentikasi/permission adalah *dependency*, penanganan error adalah *exception handler*, audit log dan transaksi berada di service. Jangan memindahkan hal-hal itu ke middleware.
* Satu use case = satu transaksi database di satu fungsi service.

---

## 5. Invarian Bisnis (Tidak Boleh Dilanggar)

1. **Semua perubahan saldo stok hanya lewat `inventory_service.apply_movement()`.** Tidak boleh ada `UPDATE inventory_balances` di tempat lain, dan tidak ada perubahan saldo tanpa baris `stock_movements`.
2. **`stock_movements` dan `audit_logs` append-only.** Tidak ada `UPDATE`, `DELETE`, atau `TRUNCATE` terhadap keduanya dari kode aplikasi. Koreksi = baris baru.
3. **Satu aksi bisnis = satu transaksi** yang mencakup status dokumen, saldo, ledger, dan audit log. Gagal di tengah → rollback total.
4. **Urutan penguncian seragam** (PRD 6.5): header dokumen → PO terkait → lokasi (diurutkan `id`) → saldo stok (diurutkan `(warehouse_id, location_id, item_id)`). Baris saldo dibuat lewat `INSERT ... ON CONFLICT DO NOTHING` sebelum dikunci `FOR UPDATE`.
5. **Stok negatif** ditolak di aplikasi, di dalam transaksi, setelah saldo dikunci, bila `allow_negative_stock = FALSE`. **Jangan memasang `CHECK (qty_on_hand >= 0)`** di tabel, karena aturan ini per gudang.
6. **Over-receipt:** `qty_received_gr + po_line.qty_received ≤ qty_ordered`, dihitung ulang saat posting setelah baris PO dikunci; hanya GR `POSTED` yang dihitung.
7. **Pembekuan lokasi** saat Opname (`IN_PROGRESS`/`WAITING_APPROVAL`): GR, pengiriman Transfer, dan penerimaan Transfer ke lokasi tersebut ditolak (`LOCATION_FROZEN`). Penyesuaian `ADJUSTMENT_*` melewati pemeriksaan ini.
8. **Perubahan status hanya lewat endpoint aksi** (`POST /{id}/issue`, `/post`, `/ship`, dst.) dan **hanya transisi yang ada di tabel PRD 5.1.** Dilarang menyediakan endpoint yang mengubah kolom `status` secara bebas.
9. **Tidak ada hard delete** pada master data maupun dokumen; gunakan `is_active` atau status `CANCELLED`/`CLOSED`.
10. **Kuantitas selalu `Decimal`**, tipe DB `NUMERIC(18,4)`; **jangan pernah `float`.** Pada JSON, kuantitas berupa string desimal.
11. **Pergerakan stok hanya lima tipe** (PRD 5.3): `IN_PURCHASE`, `OUT_TRANSFER`, `IN_TRANSFER`, `ADJUSTMENT_PLUS`, `ADJUSTMENT_MINUS`. `qty_change` bertanda; `qty_after = qty_before + qty_change`.
12. **Selisih penerimaan Transfer:** `qty_received ≤ qty`; alasan wajib bila kurang; selisih tidak dikembalikan ke gudang asal dan tidak menghasilkan ledger.
13. **Warehouse scoping:** aksi bertanda (g) di Matriks 3.1 hanya pada gudang yang ditugaskan (`WAREHOUSE_NOT_ASSIGNED`).
14. Peran dan status aktif pengguna **diverifikasi dari database pada setiap request**, bukan dipercaya dari isi token.

---

## 6. Keamanan

* **Semua SQL berparameter** (`%s`/`%(nama)s`). Dilarang f-string, `.format()`, atau penggabungan string untuk memasukkan nilai ke SQL. Nama kolom pada `ORDER BY` hanya dari *whitelist* (`utils/pagination.py`).
* Rahasia (kunci JWT, kredensial DB) hanya dari variabel lingkungan. **Jangan menulis rahasia ke kode, log, `.env.example` (selain placeholder), atau commit.**
* Kata sandi, *hash* kata sandi, dan token **tidak boleh** muncul di log maupun `old_values`/`new_values` audit log.
* Access token 15 menit, refresh token 7 hari (disimpan sebagai hash, dirotasi, penggunaan ulang token yang sudah dicabut mencabut seluruh sesi pengguna), penguncian akun setelah 5 kali gagal login.
* Pesan error tidak boleh membocorkan detail internal (stack trace, SQL, struktur tabel).

---

## 7. Database & Migrasi

* Skema ditulis **tangan** sebagai `db/migrations/NNN_deskripsi.sql`. **Forward-only.** Migrasi yang sudah diterapkan **tidak boleh diedit**; perubahan = berkas migrasi baru.
* Ikuti konvensi PRD 7.5: nama *constraint* eksplisit (`pk_`, `fk_`, `uq_`, `ck_`, `ix_`), kunci utama `BIGINT GENERATED ALWAYS AS IDENTITY`, waktu `TIMESTAMPTZ` (UTC), *composite FK* lokasi–gudang.
* Aplikasi berjalan dengan role `wms_app` (bukan pemilik tabel, tanpa `UPDATE`/`DELETE`/`TRUNCATE` pada tabel append-only). Migrasi dan seed memakai role pemilik.
* **Jangan menjalankan perintah destruktif** (`DROP`, `TRUNCATE`, `DELETE` massal, `docker compose down -v`, reset database) kecuali pada database uji `wms_test`. Jangan menyentuh database selain milik pengembangan lokal.

---

## 8. Pengujian dan Definisi Selesai

* Uji memakai **PostgreSQL sungguhan**, bukan *mock* untuk DB. Skenario konkurensi (AC-06, AC-13) memakai koneksi terpisah dan pereset data antar test, bukan rollback-per-test.
* Setiap AC memiliki test dengan nama yang memuat kodenya, misalnya `test_ac06_concurrent_ship_only_one_succeeds`.
* Sebuah tugas **baru dianggap selesai** bila:
  1. Perilakunya sesuai bagian PRD yang dirujuk, termasuk kode error dan status HTTP dari Lampiran B.
  2. Test untuk AC yang relevan ada dan **lulus** (jalankan sungguhan; jangan menyatakan lulus tanpa menjalankannya).
  3. Tidak ada SQL di luar `repositories/`, tidak ada `commit` di luar `with conn.transaction()` milik service, tidak ada `float` untuk kuantitas.
  4. Tidak ada file, endpoint, tabel, atau dependensi di luar yang disetujui.
  5. Tidak ada rahasia di dalam perubahan.
* Jangan menghapus atau melemahkan test agar hasil menjadi hijau. Bila test salah, jelaskan dan minta persetujuan.

---

## 9. Cara Bekerja

* Kerjakan **satu tahap pada satu waktu** sesuai urutan M0 → M8 di `docs/core/FOLDER_STRUCTURE.md` bagian 9. Jangan melompati tahap atau mengerjakan modul yang dependensinya belum ada.
* Buat perubahan **kecil dan terfokus.** Jangan merapikan, me-refactor, atau mengganti nama hal yang tidak berkaitan dengan tugas.
* Sebelum mengerjakan tugas, sebutkan FR/AC/bagian PRD yang dituju. Setelah selesai, laporkan apa yang berubah, AC mana yang tercakup, dan apa yang **belum** dikerjakan.
* Penamaan mengikuti `docs/core/FOLDER_STRUCTURE.md` bagian 6 (`snake_case`; service = kata kerja use case; repository `get_/list_/insert_/update_/lock_`; schema `XxxCreate/XxxUpdate/XxxOut`).
* Aturan bisnis dilempar sebagai turunan `DomainError` dengan `code` dan `http_status` dari katalog Lampiran B; jangan membuat kode error baru tanpa persetujuan.
* Git: commit kecil dengan pesan jelas; jangan `push --force`, jangan menulis ulang riwayat, jangan commit `.env` atau berkas rahasia.

---

## 10. Berhenti dan Tanya Bila

* PRD tidak mencakup kasusnya, ambigu, atau dua bagian PRD saling bertentangan.
* Tugas membutuhkan fitur di luar lingkup (bagian 3), dependensi baru, atau perubahan struktur folder.
* Tugas menuntut melanggar salah satu invarian di bagian 5 (misalnya "ubah saldo langsung biar cepat").
* Perlu mengubah migrasi yang sudah diterapkan, atau menjalankan perintah destruktif di luar `wms_test`.
* Test gagal dan penyebabnya tampak berasal dari PRD, bukan dari kode.

Saat bertanya: nyatakan masalahnya, bagian PRD yang terkait, dan dua atau tiga opsi beserta rekomendasi. Jangan lanjut dengan tebakan.

---

## 11. Perintah Umum

Perintah ini disepakati saat tahap M0 dan dapat disesuaikan di sana; jaga agar tetap sederhana.

```
uvicorn app.main:app --reload          # menjalankan API lokal
python -m db.migrate                   # menerapkan migrasi .sql yang belum terpasang
python scripts/create_superadmin.py    # membuat Super Admin pertama
pytest                                 # seluruh pengujian
pytest -k ac06                         # satu AC tertentu
```