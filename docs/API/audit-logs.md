# Audit Log

## 1. Informasi Umum

| Atribut | Keterangan |
| --- | --- |
| **Modul** | Audit Log (Jejak Audit Aktivitas & Perubahan Data) |
| **Base path** | `/api/v1/audit-logs` |
| **Rujukan PRD** | FR-09, FR-11, Bagian 3.1, 6.4 (Imutabilitas), AC-05, AC-08 |
| **Status implementasi** | ✅ Sudah diimplementasikan dan diuji (`tests/test_auth.py`, `tests/test_rbac_scoping.py`, `tests/test_immutability.py`) |
| **Kode sumber** | [routes/audit_logs.py](../../app/api/routes/audit_logs.py), [audit_service.py](../../app/services/audit_service.py), [audit_repo.py](../../app/repositories/audit_repo.py), [schemas/audit_log.py](../../app/schemas/audit_log.py) |
| **Tabel terkait** | `audit_logs`, `users` |
| **Modul terkait** | [Autentikasi & Otorisasi](authentication.md), [Pengguna & RBAC](users.md), [Master Data](master-data.md), [Gudang & Lokasi](warehouses.md) |

---

## 2. Penjelasan Fitur

### 2.1 Tujuan & Karakteristik Append-Only

Modul Audit Log menyediakan akses **baca-saja (*read-only*)** terhadap tabel `audit_logs` untuk menelusuri siapa melakukan aksi apa, kapan, dari alamat IP mana, serta nilai sebelum (`old_values`) dan sesudah (`new_values`) perubahan.

Sesuai PRD 6.4 dan AGENTS.md Invarian 2:
* Tabel `audit_logs` bersifat **append-only** (tidak memiliki endpoint `POST`/`PATCH`/`DELETE` publik; entri hanya ditulis secara internal oleh layanan aplikasi di dalam transaksi yang sama dengan aksi bisnis).
* Di level PostgreSQL (`007_append_only_guards.sql`), dipasang *trigger* `trg_audit_logs_immutable` (`BEFORE UPDATE OR DELETE`) yang menolak segala upaya perubahan atau penghapusan baris, serta pencabutan hak `UPDATE, DELETE, TRUNCATE` dari role aplikasi `wms_app`.
* Fungsi [`audit_service.record()`](../../app/services/audit_service.py) secara otomatis menyaring atribut sensitif (`password`, `password_hash`, `current_password`, `new_password`, `token`, `token_hash`, `access_token`, `refresh_token`) agar tidak pernah tersimpan di kolom JSONB `old_values` maupun `new_values`.

### 2.2 Daftar `action` yang Dihasilkan Saat Ini

Berdasarkan kode layanan yang telah diimplementasikan saat ini (`auth_service.py`, `user_service.py`, `master_service.py`, `warehouse_service.py`, dan `scripts/create_superadmin.py`), nilai `action` dan `entity_type` yang tercatat di `audit_logs` meliputi:

| `action` | `entity_type` | Pemicu | `user_id` |
| --- | --- | --- | --- |
| `SUPERADMIN_BOOTSTRAPPED` | `users` | Eksekusi awal `scripts/create_superadmin.py` | ID Super Admin baru |
| `AUTH_LOGIN_SUCCESS` | `users` | Login berhasil (`POST /api/v1/auth/login`) | ID pengguna |
| `AUTH_LOGIN_FAILED` | `users` | Login gagal (username tak dikenal, akun nonaktif, akun sedang terkunci, atau password salah ke-1 s.d. ke-4) | `null` bila username tak dikenal; ID pengguna bila dikenali |
| `AUTH_LOGIN_LOCKED` | `users` | Kegagalan login ke-5 berturut-turut yang memicu penguncian akun 15 menit | ID pengguna |
| `AUTH_TOKEN_REFRESHED` | `refresh_tokens` | Rotasi *Refresh Token* berhasil (`POST /api/v1/auth/refresh`) | ID pengguna |
| `AUTH_TOKEN_REFRESH_FAILED` | `refresh_tokens` | Rotasi *Refresh Token* ditolak karena token sudah kedaluwarsa (`TOKEN_EXPIRED`) atau pemilik token sudah nonaktif (`USER_INACTIVE`) | ID pengguna |
| `AUTH_REFRESH_TOKEN_REUSE_DETECTED` | `refresh_tokens` | Penggunaan ulang *Refresh Token* yang sudah dicabut (mencabut seluruh sesi aktif user) | ID pengguna |
| `AUTH_LOGOUT` | `refresh_tokens` | Logout (`POST /api/v1/auth/logout`) | ID pengguna |
| `USER_PASSWORD_CHANGED` | `users` | Ganti kata sandi sendiri (`POST /api/v1/auth/change-password`) | ID pengguna |
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
| `date_from` | datetime (ISO 8601) | Tidak | `null` | Batas bawah waktu kejadian (`created_at >= date_from`). |
| `date_to` | datetime (ISO 8601) | Tidak | `null` | Batas atas waktu kejadian (`created_at <= date_to`). |
| `sort_by` | string | Tidak | `"id"` | Whitelist kolom: `"id"`, `"created_at"`, `"action"`, `"entity_type"`. |
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
      "old_values": {
        "user_id": 2,
        "warehouse_ids": [1]
      },
      "new_values": {
        "user_id": 2,
        "warehouse_ids": [1, 2]
      },
      "ip_address": "127.0.0.1",
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
| `422` | `VALIDATION_ERROR` | `limit` di luar `1..200`, `offset < 0`, format `date_from`/`date_to` bukan ISO 8601 datetime valid, `sort_by` di luar *whitelist*, atau `sort_dir` selain `asc`/`desc`. |

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
| Tabel `audit_logs` | Menyimpan `id` (`BIGINT GENERATED ALWAYS AS IDENTITY`), `user_id` (nullable, FK ke `users.id ON DELETE RESTRICT`), `action`, `entity_type`, `entity_id`, `old_values` (`JSONB`), `new_values` (`JSONB`), `ip_address`, `created_at`. |
| Indeks Database | `ix_audit_logs_entity (entity_type, entity_id)`, `ix_audit_logs_user_id (user_id)`, `ix_audit_logs_action (action)`, `ix_audit_logs_created_at (created_at DESC)`. |
| Imutabilitas (`007`) | Trigger `trg_audit_logs_immutable` menolak `UPDATE` dan `DELETE` dengan SQLSTATE `42501`. |

Alur lapisan: `routes/audit_logs.py` → `audit_service.list_audit_logs` → `audit_repo.list_audit_logs` → PostgreSQL.

---

## 7. Contoh Penggunaan (cURL)

```bash
BASE=http://localhost:8000/api/v1

# 1. Ambil 20 audit log terbaru
curl -s "$BASE/audit-logs?limit=20&offset=0" \
  -H "Authorization: Bearer <ACCESS_TOKEN>"

# 2. Filter berdasarkan entitas users dan aksi tertentu
curl -s "$BASE/audit-logs?entity_type=users&action=USER_UPDATED" \
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
| 2 | ✅ Terverifikasi | Sanitasi otomatis atribut kata sandi dan token pada `audit_service._sanitize_payload()` telah diverifikasi di `test_login_lockout_after_5_failed_attempts_and_audit_log`. |
| 3 | ✅ Terverifikasi | Imutabilitas tabel append-only (`audit_logs` dan `stock_movements`) terhadap operasi `UPDATE` dan `DELETE` telah diuji secara otomatis di `tests/test_immutability.py` (`test_ac08_immutability_stock_movements_and_audit_logs` — **AC-08**) baik menggunakan koneksi role aplikasi `wms_app` maupun pemilik tabel. |

