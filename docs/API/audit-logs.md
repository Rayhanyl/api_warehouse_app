# Audit Log

## 1. Informasi Umum

| Atribut | Keterangan |
| --- | --- |
| **Modul** | Audit Log (Jejak Audit Aktivitas & Perubahan Data) |
| **Base path** | `/api/v1/audit-logs` |
| **Rute frontend** | `/audit-logs`, `/audit`, `/admin/audit-logs` (dipetakan ke `<AuditLogsPage />` dengan permission `audit:read`) |
| **Rujukan PRD** | FR-09, FR-11, Bagian 3.1, 6.4 (Imutabilitas), AC-05, AC-08 |
| **Status implementasi** | ✅ Sudah diimplementasikan dan diuji (`tests/test_auth.py`, `tests/test_rbac_scoping.py`, `tests/test_immutability.py`) |
| **Kode sumber** | [routes/audit_logs.py](../../app/api/routes/audit_logs.py), [audit_service.py](../../app/services/audit_service.py), [audit_repo.py](../../app/repositories/audit_repo.py), [schemas/audit_log.py](../../app/schemas/audit_log.py) |
| **Tabel terkait** | `audit_logs`, `users` |
| **Modul terkait** | [Autentikasi & Otorisasi](authentication.md), [Pengguna & RBAC](users.md), [Master Data](master-data.md), [Gudang & Lokasi](warehouses.md) |

---

## 2. Penjelasan Fitur

### 2.1 Tujuan & Karakteristik Append-Only

Modul Audit Log menyediakan akses **baca-saja (*read-only*)** terhadap tabel `audit_logs` untuk menelusuri siapa melakukan aksi apa, kapan, status keberhasilannya (`SUCCESS` / `FAILED`), dari alamat IP & perangkat (*User-Agent*) mana, korelasi `request_id`, detail kegagalan (`details`), serta nilai sebelum (`old_values`) dan sesudah (`new_values`) perubahan.

Sesuai PRD 6.4, AGENTS.MD Invarian 2, dan penyempurnaan Tahap 14:
* Tabel `audit_logs` bersifat **append-only** (tidak memiliki endpoint `POST`/`PATCH`/`DELETE` publik; entri ditulis secara internal oleh layanan aplikasi maupun *exception handler* HTTP di luar transaksi yang *rollback* saat aksi bisnis gagal).
* Di level PostgreSQL (`007_append_only_guards.sql` & `014_enhance_audit_logs.sql`), dipasang *trigger* `trg_audit_logs_immutable` (`BEFORE UPDATE OR DELETE`) yang menolak segala upaya perubahan atau penghapusan baris (termasuk kolom `status`, `details`, `user_agent`, `request_id`), `CHECK CONSTRAINT ck_audit_logs_status` (`SUCCESS` / `FAILED`), serta pencabutan hak `UPDATE, DELETE, TRUNCATE` dari role aplikasi `wms_app`.
* Fungsi [`audit_service.record()`](../../app/services/audit_service.py) memanfaatkan `is_credential_key()` dan `sanitize_credential_text()` pada [`app/core/sanitizer.py`](../../app/core/sanitizer.py) untuk menyaring seluruh kredensial (`password`, `password_hash`, `current_password`, `new_password`, `token`, `secret`, `authorization`, `cookie`, Bearer/Basic/JWT, URL DB berkredensial, serta `input` sensitif pada galat validasi Pydantic) dari `old_values`, `new_values`, `details`, maupun `user_agent` — sekaligus tetap mempertahankan data operasional master seperti `email`, `phone`, dan `address`.

### 2.2 Daftar `action` yang Dihasilkan Saat Ini

Berdasarkan seluruh kode layanan yang telah diimplementasikan (`auth_service.py`, `user_service.py`, `master_service.py`, `warehouse_service.py`, `po_service.py`, `gr_service.py`, `transfer_service.py`, `opname_service.py`, dan `scripts/create_superadmin.py`), nilai `action` dan `entity_type` yang tercatat di `audit_logs` meliputi:

| `action` | `entity_type` | Pemicu | `user_id` |
| --- | --- | --- | --- |
| `SUPERADMIN_BOOTSTRAPPED` | `users` | Eksekusi awal `scripts/create_superadmin.py` | ID Super Admin baru |
| `AUTH_LOGIN_SUCCESS` | `users` | Login berhasil (`POST /api/v1/auth/login`) | ID pengguna |
| `AUTH_LOGIN_FAILED` | `users` | Login gagal (username tak dikenal, akun nonaktif, akun sedang terkunci, atau password salah ke-1 s.d. ke-4) | `null` bila username tak dikenal; ID pengguna bila dikenali |
| `AUTH_LOGIN_LOCKED` | `users` | Kegagalan login ke-5 berturut-turut yang memicu penguncian akun 15 menit | ID pengguna |
| `AUTH_TOKEN_REFRESHED` | `refresh_tokens` | Rotasi *Refresh Token* berhasil (`POST /api/v1/auth/refresh`) | ID pengguna |
| `AUTH_TOKEN_REFRESH_FAILED` | `refresh_tokens` | Rotasi *Refresh Token* ditolak (`TOKEN_EXPIRED`, `TOKEN_NOT_FOUND`, atau `USER_INACTIVE`) — `status=FAILED` | ID pengguna (atau `null` bila token tak dikenal) |
| `AUTH_REFRESH_TOKEN_REUSE_DETECTED` | `refresh_tokens` | Penggunaan ulang *Refresh Token* yang sudah dicabut (mencabut seluruh sesi aktif user) — `status=FAILED` | ID pengguna |
| `AUTH_LOGOUT` | `refresh_tokens` | Logout (`POST /api/v1/auth/logout`) | ID pengguna |
| `AUTH_LOGOUT_FAILED` | `refresh_tokens` | Upaya logout gagal (mis. refresh token tidak valid/kedaluwarsa) — `status=FAILED` | ID pengguna (bila ada) |
| `USER_PASSWORD_CHANGED` | `users` | Ganti kata sandi sendiri (`POST /api/v1/auth/change-password`) | ID pengguna |
| `USER_PASSWORD_CHANGE_FAILED` | `users` | Upaya ganti kata sandi ditolak (`INVALID_CURRENT_PASSWORD`) — `status=FAILED` | ID pengguna |
| `USER_CREATED` | `users` | Pembuatan pengguna baru (`POST /api/v1/users`) | ID pemanggil (*Super Admin*) |
| `USER_UPDATED` | `users` | Pembaruan data pengguna (`PATCH /api/v1/users/{id}`) | ID pemanggil |
| `USER_DEACTIVATED` | `users` | Penonaktifan pengguna (`is_active: true -> false` via `PATCH /api/v1/users/{id}`) | ID pemanggil |
| `USER_WAREHOUSES_UPDATED` | `user_warehouses` | Perubahan penugasan gudang (`PUT /api/v1/users/{id}/warehouses`) | ID pemanggil |
| `ROLE_PERMISSIONS_UPDATED` | `roles` | Perubahan daftar kode permission peran (`PUT /api/v1/users/roles/{id}/permissions`) | ID pemanggil |
| `CATEGORY_CREATED` / `CATEGORY_UPDATED` / `CATEGORY_DEACTIVATED` | `categories` | Pembuatan, pembaruan, atau penonaktifan kategori barang (`/api/v1/categories`) | ID pemanggil |
| `UOM_CREATED` / `UOM_UPDATED` / `UOM_DEACTIVATED` | `uoms` | Pembuatan, pembaruan, atau penonaktifan satuan ukur (`/api/v1/uoms`) | ID pemanggil |
| `SUPPLIER_CREATED` / `SUPPLIER_UPDATED` / `SUPPLIER_DEACTIVATED` | `suppliers` | Pembuatan, pembaruan, atau penonaktifan pemasok (`/api/v1/suppliers`) | ID pemanggil |
| `ITEM_CREATED` / `ITEM_UPDATED` / `ITEM_DEACTIVATED` | `items` | Pembuatan, pembaruan, atau penonaktifan barang (`/api/v1/items`) | ID pemanggil |
| `WAREHOUSE_CREATED` / `WAREHOUSE_UPDATED` / `WAREHOUSE_DEACTIVATED` | `warehouses` | Pembuatan, pembaruan (termasuk `allow_negative_stock`), atau penonaktifan gudang (`/api/v1/warehouses`) | ID pemanggil |
| `LOCATION_CREATED` / `LOCATION_UPDATED` / `LOCATION_DEACTIVATED` | `storage_locations` | Pembuatan, pembaruan, atau penonaktifan lokasi penyimpanan (`/api/v1/locations` & `/api/v1/warehouses/{id}/locations`) | ID pemanggil |
| `PO_CREATED` / `PO_UPDATED` / `PO_ISSUED` / `PO_CANCELLED` / `PO_CLOSED` | `purchase_orders` | Pembuatan, revisi `DRAFT`, penerbitan, pembatalan, penutupan, atau pembaruan pemenuhan PO (`/api/v1/purchase-orders`) | ID pemanggil |
| `GR_CREATED` / `GR_UPDATED` / `GR_POSTED` / `GR_CANCELLED` | `goods_receipts` | Pembuatan, revisi `DRAFT`, posting, atau pembatalan Goods Receipt (`/api/v1/goods-receipts`) | ID pemanggil |
| `TRANSFER_CREATED` / `TRANSFER_UPDATED` / `TRANSFER_APPROVED` / `TRANSFER_SHIPPED` / `TRANSFER_RECEIVED` / `TRANSFER_CANCELLED` | `stock_transfers` | Pembuatan, revisi `DRAFT`, persetujuan, pengiriman, penerimaan, atau pembatalan Transfer Stok (`/api/v1/stock-transfers`) | ID pemanggil |
| `OPNAME_CREATED` / `OPNAME_UPDATED` / `OPNAME_STARTED` / `OPNAME_COUNTED` / `OPNAME_SUBMITTED` / `OPNAME_APPROVED` / `OPNAME_REJECTED` / `OPNAME_CANCELLED` | `stock_opnames` | Pembuatan, revisi `DRAFT`, mulai (*snapshot*), input hitung fisik, ajukan, setujui, tolak, atau batalkan sesi Stock Opname (`/api/v1/stock-opnames`) | ID pemanggil |
| `<DOMAIN_ERROR_CODE>` (mis. `PERMISSION_DENIED`, `AUTH_TOKEN_INVALID`, `INVALID_STATE_TRANSITION`) / `VALIDATION_ERROR` | Sesuai path endpoint (`infer_entity_from_path`) | Kegagalan domain pada request mutasi (`POST`/`PUT`/`PATCH`/`DELETE`) atau error otentikasi/otorisasi (`401`/`403`), serta error validasi HTTP `422` pada request mutasi — dicatat *out-of-band* dengan `status=FAILED` | ID pengguna terautentikasi (atau `null` bila anonim/401) |

---

## 3. Autentikasi dan Otorisasi

* **Autentikasi:** Wajib menyertakan header `Authorization: Bearer <access_token>`.
* **Permission:** Wajib memiliki permission **`audit:read`** (`Depends(require_permission("audit:read"))`).
* Sesuai Matriks 3.1 PRD, peran yang memiliki izin `audit:read` secara bawaan adalah **`Super Admin`** dan **`Auditor`**. Peran lain ditolak dengan HTTP `403 PERMISSION_DENIED`.

---

## 4. Ringkasan Endpoint

| Method | Endpoint | Fungsi | Auth | Permission |
| --- | --- | --- | --- | --- |
| GET | `/api/v1/audit-logs` | Mengambil daftar entri audit log dengan filter dan pagination | Bearer | `audit:read` |

---

## 5. Detail Setiap Endpoint

### GET `/api/v1/audit-logs` — Daftar Audit Log

Mengambil daftar jejak audit secara kronologis beserta `username` pelaku (hasil `LEFT JOIN users`).

* **HTTP Method & URL:** `GET /api/v1/audit-logs`
* **Autentikasi & Permission:** Bearer Token, `audit:read`

**Query Parameter**

| Parameter | Tipe | Wajib | Default | Aturan & Keterangan |
| --- | --- | --- | --- | --- |
| `limit` | integer | Tidak | `50` | Rentang `1..200`. |
| `offset` | integer | Tidak | `0` | Minimal `0`. |
| `user_id` | integer | Tidak | `null` | Filter berdasarkan ID pengguna pelaku (`a.user_id = %s`). |
| `action` | string | Tidak | `null` | Filter pencocokan persis nama aksi (mis. `USER_UPDATED`). |
| `entity_type` | string | Tidak | `null` | Filter pencocokan persis jenis entitas (mis. `users`, `roles`, `user_warehouses`, `refresh_tokens`). |
| `entity_id` | string | Tidak | `null` | Filter ID entitas yang terdampak (disimpan sebagai string pada kolom `entity_id`). |
| `status` | string | Tidak | `null` | Filter status aktivitas: `"SUCCESS"` atau `"FAILED"` (case-insensitive dinormalisasi ke uppercase). |
| `date_from` | datetime (ISO 8601) | Tidak | `null` | Batas bawah waktu kejadian (`created_at >= date_from`). |
| `date_to` | datetime (ISO 8601) | Tidak | `null` | Batas atas waktu kejadian (`created_at <= date_to`). |
| `search` | string | Tidak | `null` | Pencarian substring (*case-insensitive* `ILIKE`) pada `u.username`, `a.action`, `a.entity_type`, `a.entity_id`, `a.ip_address`, dan `a.request_id`. |
| `sort_by` | string | Tidak | `"id"` | Whitelist kolom: `"id"`, `"created_at"`, `"action"`, `"entity_type"`, `"status"`, `"ip_address"`. |
| `sort_dir` | string | Tidak | `"desc"` | `"asc"` atau `"desc"` (bawaan terbaru di atas / `DESC`). |

**Contoh Request**

```http
GET /api/v1/audit-logs?limit=3&action=USER_WAREHOUSES_UPDATED HTTP/1.1
Host: localhost:8000
Authorization: Bearer <ACCESS_TOKEN>
```

**Contoh Response Berhasil (`200 OK` — `Page[AuditLogOut]`)**

```json
{
  "items": [
    {
      "id": 6,
      "user_id": 1,
      "username": "superadmin",
      "action": "USER_WAREHOUSES_UPDATED",
      "entity_type": "user_warehouses",
      "entity_id": "2",
      "status": "SUCCESS",
      "old_values": {
        "user_id": 2,
        "warehouse_ids": [1]
      },
      "new_values": {
        "user_id": 2,
        "warehouse_ids": [1, 2]
      },
      "details": null,
      "ip_address": "127.0.0.1",
      "user_agent": "Mozilla/5.0 ...",
      "request_id": "2d3c4e5f-1234-4abc-9def-0123456789ab",
      "created_at": "2026-10-21T14:13:09.033701+07:00"
    }
  ],
  "total": 1,
  "limit": 3,
  "offset": 0
}
```

**Kemungkinan Response Error**

| Status | Kode Error | Penyebab |
| --- | --- | --- |
| `401` | `AUTH_TOKEN_INVALID` | Bearer token tidak disertakan, tidak sah, atau kedaluwarsa. |
| `403` | `PERMISSION_DENIED` | Pemanggil tidak memiliki permission `audit:read`. |
| `422` | `VALIDATION_ERROR` | `limit` di luar `1..200`, `offset < 0`, `status` selain `SUCCESS`/`FAILED`, format `date_from`/`date_to` bukan ISO 8601 datetime valid, `sort_by` di luar *whitelist*, atau `sort_dir` selain `asc`/`desc`. |

Contoh `403` untuk pengguna tanpa `audit:read`:

```json
{
  "error": {
    "code": "PERMISSION_DENIED",
    "message": "Anda tidak memiliki izin 'audit:read' untuk melakukan aksi ini.",
    "details": {
      "required_permission": "audit:read"
    }
  }
}
```

---

## 6. Relasi dan Ketergantungan

| Komponen | Keterangan |
| --- | --- |
| Tabel `audit_logs` | Menyimpan `id` (`BIGINT GENERATED ALWAYS AS IDENTITY`), `user_id` (nullable, FK ke `users.id ON DELETE RESTRICT`), `action`, `entity_type`, `entity_id`, `status` (`SUCCESS` / `FAILED`, constraint `ck_audit_logs_status`), `old_values` (`JSONB`), `new_values` (`JSONB`), `details` (`JSONB`), `ip_address`, `user_agent` (`VARCHAR(512)`), `request_id` (`VARCHAR(128)`), `created_at`. |
| Indeks Database | `ix_audit_logs_entity (entity_type, entity_id)`, `ix_audit_logs_user_id (user_id)`, `ix_audit_logs_action (action)`, `ix_audit_logs_created_at (created_at DESC)`, `ix_audit_logs_status (status)`, `ix_audit_logs_request_id (request_id)`. |
| Imutabilitas (`007` & `014`) | Trigger `trg_audit_logs_immutable` menolak `UPDATE` dan `DELETE` dengan SQLSTATE `42501` (termasuk kolom baru Tahap 14). |

Alur lapisan: `routes/audit_logs.py` → `audit_service.list_audit_logs` → `audit_repo.list_audit_logs` → PostgreSQL. Untuk kegagalan mutasi/`401`/`403`, *exception handler* di `app/main.py` memanggil `audit_service.record_http_failure()` menggunakan koneksi terpisah agar catatan `status='FAILED'` tetap tersimpan meski transaksi bisnis di-*rollback*.

---

## 7. Contoh Penggunaan (cURL)

```bash
BASE=http://localhost:8000/api/v1

# 1. Ambil 20 audit log terbaru
curl -s "$BASE/audit-logs?limit=20&offset=0" \
  -H "Authorization: Bearer <ACCESS_TOKEN>"

# 2. Filter berdasarkan status kegagalan dan pencarian teks (IP/request_id/aksi)
curl -s "$BASE/audit-logs?status=FAILED&search=PERMISSION_DENIED" \
  -H "Authorization: Bearer <ACCESS_TOKEN>"

# 3. Filter berdasarkan rentang waktu UTC
curl -s "$BASE/audit-logs?date_from=2026-10-21T00:00:00Z&date_to=2026-10-21T23:59:59Z" \
  -H "Authorization: Bearer <ACCESS_TOKEN>"
```

---

## 8. Catatan dan Status Verifikasi

| # | Status | Catatan |
| --- | --- | --- |
| 1 | ✅ Terverifikasi | Pembatasan akses `audit:read` dan kelengkapan struktur `old_values`/`new_values` telah diverifikasi di `test_ac05_rbac_enforcement_and_audit_log_recording`. |
| 2 | ✅ Terverifikasi | Sanitasi otomatis atribut kata sandi dan token pada `audit_service._sanitize_payload()` telah diverifikasi di `test_login_lockout_after_5_failed_attempts_and_audit_log` dan `test_ac22_audit_log_completeness_secret_sanitization_and_filter`. |
| 3 | ✅ Terverifikasi | Enrichmen Tahap 14 (`ip_address` via `X-Forwarded-For` untuk `trusted_proxy_ips`, `user_agent`, `request_id`, `status=FAILED`, `details`, filter `status`/`search`, serta scrubbing `input` validasi 422) diverifikasi di `test_tahap14_comprehensive_audit_enrichment_failures_and_sanitization`. |
| 4 | ✅ Terverifikasi | Imutabilitas tabel append-only (`audit_logs` dan `stock_movements`) terhadap operasi `UPDATE` (termasuk kolom `status`) dan `DELETE` telah diuji secara otomatis di `tests/test_immutability.py` (`test_ac08_immutability_stock_movements_and_audit_logs` — **AC-08**) baik menggunakan koneksi role aplikasi `wms_app` maupun pemilik tabel. |

