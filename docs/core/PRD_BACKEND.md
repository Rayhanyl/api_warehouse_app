# PRD Backend — Spesifikasi Implementasi

Dokumen ini menerjemahkan [PRD General](PRD_GENERAL.md) ke kebutuhan backend.
Ia tidak mendefinisikan ulang tujuan bisnis, role, scope, atau acceptance
criteria; setiap ID `FR` dan `AC` mengacu pada PRD General.

## 1. Tanggung jawab dan batas

Backend bertanggung jawab atas HTTP API, autentikasi, otorisasi, validasi,
aturan bisnis, transaksi, persistence, audit, dan error terstruktur. Backend
tidak bertanggung jawab atas UI atau keputusan bisnis yang belum disetujui.

Implementasi mengikuti [FOLDER_STRUCTURE](FOLDER_STRUCTURE.MD):
`routes -> services -> repositories -> core/database`. SQL hanya berada di
repository, transaksi dibuka oleh service, dan route memanggil satu use case service.

## 2. API requirements

- Base path: `/api/v1`; health check tersedia pada root dan prefix v1.
- Payload: JSON; waktu ISO 8601 dengan timezone.
- Auth: `Authorization: Bearer <access-token>` untuk endpoint terlindungi.
- Request ID: `X-Request-ID` dipertahankan atau dibuat server.
- Pagination: `limit` 1–200, default 50, dan `offset >= 0` bila endpoint mendukung.
- Kuantitas: string desimal yang dipetakan ke `Decimal`, bukan `float`.
- Error: `{ "error": { "code", "message", "details" } }`.

Daftar endpoint aktual dan contoh payload berada di [API documentation](../API/README.md)
dan [API Contract](API_CONTRACT.md). Dokumen ini hanya menetapkan kebutuhan
implementasi, bukan menyalin seluruh katalog endpoint.

## 3. Arsitektur service dan persistence

### 3.1 Layer

| Layer | Tanggung jawab |
| --- | --- |
| Routes/dependencies | Parse request, permission dependency, panggil service |
| Services | Use case, aturan bisnis, transaction boundary, audit |
| Repositories | SQL berparameter, locking, query, dan persistence |
| Schemas | Bentuk request/response dan validasi format |
| Core | Config, pool, security, exception, request ID |

### 3.2 Transaksi dan locking

Satu aksi bisnis adalah satu transaksi yang mencakup status dokumen, saldo,
ledger, dan audit. Lock ordering: header dokumen, PO terkait, lokasi terurut,
lalu saldo terurut `(warehouse_id, location_id, item_id)`. Saldo dibuat dengan
`INSERT ... ON CONFLICT DO NOTHING` sebelum `FOR UPDATE`.

Seluruh perubahan saldo melewati `inventory_service.apply_movement()`.

## 4. Business logic dan validasi

- Verifikasi user aktif, role, dan permission dari database pada setiap request.
- Terapkan warehouse scoping melalui service, bukan middleware.
- Validasi state transition hanya pada endpoint aksi yang sah.
- Tolak referensi tidak aktif, lokasi yang tidak cocok, duplicate, dan entity in use
  sesuai katalog error.
- Hitung ulang over-receipt setelah PO line dikunci; hanya GR `POSTED` dihitung.
- Tolak stok negatif setelah saldo dikunci jika `allow_negative_stock = FALSE`.
- Tolak operasi pada lokasi frozen, kecuali adjustment opname yang diizinkan.
- Gunakan movement type hanya `IN_PURCHASE`, `OUT_TRANSFER`, `IN_TRANSFER`,
  `ADJUSTMENT_PLUS`, dan `ADJUSTMENT_MINUS`.

## 5. Authentication dan authorization

- Access token berlaku 15 menit; refresh token 7 hari.
- Refresh token disimpan sebagai hash, dirotasi, dan reuse token revoked
  mencabut seluruh sesi pengguna.
- Password menggunakan Argon2id.
- Akun dikunci setelah lima kegagalan login sesuai aturan produk.
- Permission berasal dari role/database, bukan dipercaya dari claim token saja.

## 6. Error handling dan observability

Gunakan `DomainError` dan kode katalog yang sudah ada: auth, permission,
warehouse assignment, not found, validation, duplicate, invalid state,
insufficient stock, over-receipt, frozen location, entity in use, dan internal
error. Jangan membocorkan SQL, stack trace, struktur tabel, password, hash,
atau token. Audit mencatat aksi dan nilai bisnis yang aman tanpa secret.

## 7. Integrasi dan operasional

Backend menggunakan PostgreSQL melalui `psycopg` 3/`psycopg_pool` sinkron,
tanpa ORM, migration SQL forward-only, dan role aplikasi `wms_app`. Tidak ada
Redis, queue, worker, atau integrasi eksternal dalam MVP.

## 8. Traceability backend

| PRD General | Komponen backend |
| --- | --- |
| FR-01 | `auth_service`, auth routes, security, user dependencies |
| FR-02 | master/warehouse services dan repositories |
| FR-03/08 | stock, inventory service, ledger repository |
| FR-04 | PO service/routes/repository |
| FR-05 | GR service/routes/repository |
| FR-06 | transfer service/routes/repository |
| FR-07 | opname service/routes/repository |
| FR-09/10/11 | audit/numbering services dan pagination utility |

Detail struktur file dan pola kode tetap berada di [FOLDER_STRUCTURE](FOLDER_STRUCTURE.MD).
