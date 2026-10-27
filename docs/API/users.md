# Manajemen Pengguna, Peran/Permission (RBAC) & Penugasan Gudang

## 1. Informasi Umum

| Atribut | Keterangan |
| --- | --- |
| **Modul** | Manajemen Pengguna, Peran (*Role*), Izin (*Permission*), dan Penugasan Gudang (*Warehouse Scoping*) |
| **Base path** | `/api/v1/users` |
| **Rujukan PRD** | Bagian 3, 3.1 (Matriks Permission), 3.2 (Warehouse Scoping), FR-01, FR-09, FR-11, AC-05, AC-12 |
| **Status implementasi** | ✅ Sudah diimplementasikan dan diuji (`tests/test_rbac_scoping.py`) |
| **Kode sumber** | [routes/users.py](../../app/api/routes/users.py), [user_service.py](../../app/services/user_service.py), [access_service.py](../../app/services/access_service.py), [user_repo.py](../../app/repositories/user_repo.py), [permission_repo.py](../../app/repositories/permission_repo.py), [schemas/user.py](../../app/schemas/user.py) |
| **Tabel terkait** | `users`, `roles`, `permissions`, `role_permissions`, `user_warehouses`, `warehouses`, `refresh_tokens`, `audit_logs` |
| **Modul terkait** | [Autentikasi & Otorisasi](authentication.md), [Audit Log](audit-logs.md) |

---

## 2. Penjelasan Fitur

### 2.1 Tujuan

Modul ini menyediakan pengelolaan terpusat untuk:

1. **Akun Pengguna (`users`):** Pendaftaran pengguna baru, pembaruan profil/peran/kata sandi, serta penonaktifan akun (*soft deactivate* melalui `is_active = false`).
2. **Peran & Permission (`roles`, `permissions`, `role_permissions`):** Pembacaan 5 peran dan 24 kode *permission* sistem serta penyesuaian pemetaan *permission* pada suatu peran.
3. **Penugasan Gudang (`user_warehouses`):** Pengaturan daftar gudang yang ditugaskan kepada pengguna operasional untuk menegakkan aturan *Warehouse Scoping* (PRD 3.2).

### 2.2 Alur Bisnis Utama

* **Pembuatan Pengguna:** Administrator membuat pengguna dengan menunjuk satu `role_id` dan opsional daftar `warehouse_ids` aktif. Email dinormalisasi menjadi huruf kecil (*lowercase*), kata sandi di-*hash* menggunakan Argon2id, dan entri `USER_CREATED` ditulis ke `audit_logs`.
* **Perubahan Peran / Penonaktifan Pengguna:** Perubahan peran atau status `is_active` langsung berlaku pada request berikutnya karena dependency `get_current_user` selalu membaca ulang konteks pengguna dari database (Invarian 14). Apabila pengguna dinonaktifkan (`is_active: true -> false`) atau kata sandinya direset, seluruh *Refresh Token* aktif milik pengguna tersebut otomatis dicabut (FR-01).
* **Penugasan Gudang (*Warehouse Scoping*):** Hanya *Super Admin* (`user:manage`) yang dapat menetapkan gudang ke pengguna. Seluruh gudang yang ditugaskan wajib ada di tabel `warehouses` dan berstatus `is_active = true`.

---

## 3. Autentikasi dan Otorisasi

* **Autentikasi:** Wajib menyertakan header `Authorization: Bearer <access_token>`.
* **Permission:** Seluruh endpoint pada modul `/api/v1/users` mewajibkan permission **`user:manage`** melalui dependency `Depends(require_permission("user:manage"))`.
* Berdasarkan *seed* awal Matriks 3.1 PRD (`008_seed_roles_permissions.sql`), hanya peran **`Super Admin`** yang memiliki izin `user:manage`. Pengguna dengan peran lain akan ditolak dengan HTTP `403` dan kode error `PERMISSION_DENIED`.

---

## 4. Ringkasan Endpoint

| Method | Endpoint | Fungsi | Auth | Permission |
| --- | --- | --- | --- | --- |
| GET | `/api/v1/users` | Mengambil daftar pengguna (terpaginasi, filter & cari) | Bearer | `user:manage` |
| POST | `/api/v1/users` | Membuat akun pengguna baru (+ opsional penugasan gudang) | Bearer | `user:manage` |
| GET | `/api/v1/users/roles` | Mengambil daftar seluruh peran beserta kode permission-nya | Bearer | `user:manage` |
| GET | `/api/v1/users/permissions` | Mengambil daftar seluruh kode permission yang terdaftar | Bearer | `user:manage` |
| PUT | `/api/v1/users/roles/{role_id}/permissions` | Mengatur ulang daftar kode permission untuk satu peran | Bearer | `user:manage` |
| GET | `/api/v1/users/{user_id}` | Mengambil detail satu pengguna berdasarkan ID | Bearer | `user:manage` |
| PATCH | `/api/v1/users/{user_id}` | Memperbarui profil, peran, status aktif, atau kata sandi pengguna | Bearer | `user:manage` |
| GET | `/api/v1/users/{user_id}/warehouses` | Mengambil daftar detail gudang yang ditugaskan ke pengguna | Bearer | `user:manage` |
| PUT | `/api/v1/users/{user_id}/warehouses` | Mengganti daftar penugasan gudang untuk pengguna | Bearer | `user:manage` |

---

## 5. Detail Setiap Endpoint

### GET `/api/v1/users` — Daftar Pengguna

Mengambil daftar pengguna secara terpaginasi beserta nama peran dan daftar ID gudang yang ditugaskan.

* **HTTP Method & URL:** `GET /api/v1/users`
* **Autentikasi & Permission:** Bearer Token, `user:manage`

**Query Parameter**

| Parameter | Tipe | Wajib | Default | Aturan & Keterangan |
| --- | --- | --- | --- | --- |
| `limit` | integer | Tidak | `50` | Rentang `1..200` (`normalize_pagination`). |
| `offset` | integer | Tidak | `0` | Minimal `0`. |
| `role_id` | integer | Tidak | `null` | Filter berdasarkan ID peran. |
| `is_active` | boolean | Tidak | `null` | Filter status aktif (`true` / `false`). |
| `search` | string | Tidak | `null` | Pencarian *case-insensitive* (`ILIKE`) pada `username`, `full_name`, atau `email`. |
| `sort_by` | string | Tidak | `"id"` | Whitelist kolom: `"id"`, `"username"`, `"email"`, `"full_name"`, `"created_at"`. |
| `sort_dir` | string | Tidak | `"asc"` | `"asc"` atau `"desc"` (*case-insensitive*). |

**Contoh Request**

```http
GET /api/v1/users?limit=2&offset=0&sort_by=username&sort_dir=asc HTTP/1.1
Host: localhost:8000
Authorization: Bearer <ACCESS_TOKEN>
```

**Contoh Response Berhasil (`200 OK` — `Page[UserOut]`)**

```json
{
  "items": [
    {
      "id": 2,
      "username": "staff.jkt",
      "email": "staff.jkt@wms.local",
      "full_name": "Budi Operator",
      "role_id": 4,
      "role_name": "Warehouse Staff",
      "is_active": true,
      "warehouse_ids": [1],
      "failed_login_count": 0,
      "locked_until": null,
      "last_login_at": null,
      "created_by": 1,
      "created_at": "2026-10-21T14:13:08.757507+07:00",
      "updated_at": "2026-10-21T14:13:08.757507+07:00"
    },
    {
      "id": 1,
      "username": "superadmin",
      "email": "superadmin@wms.local",
      "full_name": "System Super Admin",
      "role_id": 1,
      "role_name": "Super Admin",
      "is_active": true,
      "warehouse_ids": [],
      "failed_login_count": 0,
      "locked_until": null,
      "last_login_at": "2026-10-21T14:13:08.259663+07:00",
      "created_by": null,
      "created_at": "2026-10-21T14:13:08.083175+07:00",
      "updated_at": "2026-10-21T14:13:08.459216+07:00"
    }
  ],
  "total": 2,
  "limit": 2,
  "offset": 0
}
```

**Kemungkinan Response Error**

| Status | Kode Error | Penyebab |
| --- | --- | --- |
| `401` | `AUTH_TOKEN_INVALID` | Token tidak disertakan, tidak valid, atau akun pemanggil nonaktif. |
| `403` | `PERMISSION_DENIED` | Pemanggil tidak memiliki izin `user:manage`. |
| `422` | `VALIDATION_ERROR` | `limit` di luar `1..200`, `offset < 0`, `sort_by` di luar *whitelist*, atau `sort_dir` selain `asc`/`desc`. |

Contoh `422` saat `sort_by` di luar *whitelist*:

```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Kolom pengurutan 'password_hash' tidak diizinkan.",
    "details": {
      "sort_by": "password_hash",
      "allowed_columns": ["created_at", "email", "full_name", "id", "username"]
    }
  }
}
```

---

### POST `/api/v1/users` — Buat Pengguna Baru

Membuat pengguna baru, menetapkan penugasan gudang awal (bila `warehouse_ids` diisi), dan mencatat audit log `USER_CREATED`.

* **HTTP Method & URL:** `POST /api/v1/users`
* **Autentikasi & Permission:** Bearer Token, `user:manage`

**Request Body (`UserCreate`)**

| Field | Tipe | Wajib | Default | Validasi |
| --- | --- | --- | --- | --- |
| `username` | string | Ya | – | 3–64 karakter; di-*trim* di service; harus unik. |
| `email` | string | Ya | – | 3–255 karakter; di-*trim*, diubah ke huruf kecil (*lowercase*), divalidasi dengan pola format email (`EMAIL_REGEX`), dan harus unik. |
| `password` | string | Ya | – | 8–255 karakter (PRD 7.2). |
| `full_name` | string | Ya | – | 1–150 karakter; di-*trim*. |
| `role_id` | integer | Ya | – | Harus merujuk ke `roles.id` yang valid. |
| `is_active` | boolean | Tidak | `true` | Status aktif awal pengguna. |
| `warehouse_ids` | array[integer] | Tidak | `[]` | Daftar ID gudang yang ditugaskan; seluruhnya harus ada dan `is_active = true`. |

**Contoh Request**

```json
{
  "username": "staff.jkt",
  "email": "staff.jkt@wms.local",
  "password": "<PASSWORD_MIN_8_KARAKTER>",
  "full_name": "Budi Operator",
  "role_id": 4,
  "is_active": true,
  "warehouse_ids": [1]
}
```

**Contoh Response Berhasil (`201 Created` — `UserOut`)**

```json
{
  "id": 2,
  "username": "staff.jkt",
  "email": "staff.jkt@wms.local",
  "full_name": "Budi Operator",
  "role_id": 4,
  "role_name": "Warehouse Staff",
  "is_active": true,
  "warehouse_ids": [1],
  "failed_login_count": 0,
  "locked_until": null,
  "last_login_at": null,
  "created_by": 1,
  "created_at": "2026-10-21T14:13:08.757507+07:00",
  "updated_at": "2026-10-21T14:13:08.757507+07:00"
}
```

**Kemungkinan Response Error**

| Status | Kode Error | Penyebab | Contoh `details` |
| --- | --- | --- | --- |
| `401` | `AUTH_TOKEN_INVALID` | Token tidak sah/kedaluwarsa. | `{}` |
| `403` | `PERMISSION_DENIED` | Pemanggil tidak memiliki `user:manage`. | `{"required_permission": "user:manage"}` |
| `404` | `NOT_FOUND` | `role_id` tidak ditemukan, atau salah satu ID di `warehouse_ids` tidak ditemukan. | `{"role_id": 999}` atau `{"missing_warehouse_ids": [999]}` |
| `409` | `DUPLICATE` | `username` atau `email` sudah terdaftar. | `{"field": "username", "value": "staff.jkt"}` |
| `422` | `INACTIVE_REFERENCE` | Salah satu gudang pada `warehouse_ids` berstatus `is_active = false`. | `{"inactive_warehouse_ids": [1]}` |
| `422` | `VALIDATION_ERROR` | Panjang field tidak memenuhi syarat Pydantic (`username < 3`, `password < 8`, dll.). | `{"errors": [...]}` |

**Aturan Bisnis & Dampak Data**

* Seluruh langkah pembuatan pengguna, penugasan `user_warehouses`, dan pencatatan `audit_logs` (`action = "USER_CREATED"`, `entity_type = "users"`) dijalankan dalam satu transaksi atomik (`with conn.transaction():`).
* Kolom `created_by` diisi dengan `id` pengguna pemanggil.

---

### GET `/api/v1/users/roles` — Daftar Peran

Mengambil seluruh peran yang ada di sistem beserta daftar kode *permission* yang dimiliki masing-masing peran.

* **HTTP Method & URL:** `GET /api/v1/users/roles`
* **Autentikasi & Permission:** Bearer Token, `user:manage`

**Contoh Response Berhasil (`200 OK` — `list[RoleOut]`)**

```json
[
  {
    "id": 1,
    "name": "Super Admin",
    "description": "Administrator sistem TI dengan akses penuh ke seluruh modul dan seluruh gudang",
    "permissions": [
      "audit:read", "gr:manage", "gr:read", "ledger:read", "location:manage",
      "master:manage", "master:read", "opname:approve", "opname:count", "opname:manage",
      "opname:read", "po:cancel", "po:close", "po:create", "po:issue", "po:read",
      "stock:read", "transfer:approve", "transfer:create", "transfer:read",
      "transfer:receive", "transfer:ship", "user:manage", "warehouse:manage"
    ],
    "created_at": "2026-10-21T13:47:03.960479+07:00",
    "updated_at": "2026-10-21T13:47:03.960479+07:00"
  }
]
```

---

### GET `/api/v1/users/permissions` — Daftar Kode Permission

Mengambil seluruh 24 kode *permission* yang terdaftar pada tabel `permissions`.

* **HTTP Method & URL:** `GET /api/v1/users/permissions`
* **Autentikasi & Permission:** Bearer Token, `user:manage`

**Contoh Response Berhasil (`200 OK` — `list[PermissionOut]`)**

```json
[
  {
    "id": 1,
    "code": "user:manage",
    "description": "Kelola pengguna, role/permission, penugasan gudang",
    "created_at": "2026-10-21T13:47:03.960479+07:00",
    "updated_at": "2026-10-21T13:47:03.960479+07:00"
  },
  {
    "id": 2,
    "code": "warehouse:manage",
    "description": "Kelola gudang & konfigurasinya",
    "created_at": "2026-10-21T13:47:03.960479+07:00",
    "updated_at": "2026-10-21T13:47:03.960479+07:00"
  }
]
```

---

### PUT `/api/v1/users/roles/{role_id}/permissions` — Atur Permission untuk Peran

Mengganti daftar *permission* yang dimiliki oleh suatu peran (`role_id`).

* **HTTP Method & URL:** `PUT /api/v1/users/roles/{role_id}/permissions`
* **Autentikasi & Permission:** Bearer Token, `user:manage`
* **Path Parameter:** `role_id` (integer, wajib) — ID peran pada tabel `roles`.

**Request Body (`RolePermissionSet`)**

| Field | Tipe | Wajib | Default | Validasi |
| --- | --- | --- | --- | --- |
| `permissions` | array[string] | Tidak | `[]` | Daftar kode *permission* yang terdaftar di tabel `permissions`. Duplikat dan spasi di tepi otomatis dibersihkan. |

**Contoh Request**

```json
{
  "permissions": [
    "master:read",
    "po:read",
    "gr:read",
    "transfer:read",
    "opname:read",
    "stock:read",
    "ledger:read",
    "audit:read"
  ]
}
```

**Contoh Response Berhasil (`200 OK` — `RoleOut`)**

```json
{
  "id": 5,
  "name": "Auditor",
  "description": "Pemeriksa internal / manajemen dengan akses baca ke seluruh modul dan Audit Log",
  "permissions": [
    "audit:read", "gr:read", "ledger:read", "master:read",
    "opname:read", "po:read", "stock:read", "transfer:read"
  ],
  "created_at": "2026-10-21T13:47:03.960479+07:00",
  "updated_at": "2026-10-21T14:13:09.500000+07:00"
}
```

**Kemungkinan Response Error**

| Status | Kode Error | Penyebab | Contoh `details` |
| --- | --- | --- | --- |
| `404` | `NOT_FOUND` | `role_id` tidak ditemukan. | `{"role_id": 999}` |
| `422` | `VALIDATION_ERROR` | Terdapat kode *permission* yang tidak dikenal di tabel `permissions`, atau mencoba menghapus izin `user:manage` dari peran `Super Admin`. | `{"unknown_permissions": ["tidak:ada"]}` atau `{"role_name": "Super Admin", "required_permission": "user:manage"}` |

**Aturan Bisnis & Dampak Data**

* Perubahan langsung berdampak pada seluruh pengguna yang memiliki peran tersebut pada request berikutnya.
* Mencatat `ROLE_PERMISSIONS_UPDATED` ke `audit_logs` dengan daftar permission lama (`old_values`) dan baru (`new_values`).

---

### GET `/api/v1/users/{user_id}` — Detail Pengguna

Mengambil informasi detail satu pengguna berdasarkan ID.

* **HTTP Method & URL:** `GET /api/v1/users/{user_id}`
* **Autentikasi & Permission:** Bearer Token, `user:manage`
* **Path Parameter:** `user_id` (integer, wajib).

**Contoh Response Berhasil (`200 OK` — `UserOut`)**

```json
{
  "id": 2,
  "username": "staff.jkt",
  "email": "staff.jkt@wms.local",
  "full_name": "Budi Operator",
  "role_id": 4,
  "role_name": "Warehouse Staff",
  "is_active": true,
  "warehouse_ids": [1],
  "failed_login_count": 0,
  "locked_until": null,
  "last_login_at": null,
  "created_by": 1,
  "created_at": "2026-10-21T14:13:08.757507+07:00",
  "updated_at": "2026-10-21T14:13:08.757507+07:00"
}
```

**Kemungkinan Response Error**

| Status | Kode Error | Penyebab |
| --- | --- | --- |
| `404` | `NOT_FOUND` | `user_id` tidak ditemukan (`details: {"user_id": 9999}`). |
| `422` | `VALIDATION_ERROR` | `user_id` bukan bilangan bulat. |

---

### PATCH `/api/v1/users/{user_id}` — Perbarui / Nonaktifkan Pengguna

Memperbarui sebagian atribut pengguna (`email`, `full_name`, `role_id`, `is_active`, atau `password`). Karena tidak ada *hard delete* (PRD FR-02 & AGENTS.MD Invarian 9), penonaktifan pengguna dilakukan melalui endpoint ini dengan mengirim `{"is_active": false}`.

* **HTTP Method & URL:** `PATCH /api/v1/users/{user_id}`
* **Autentikasi & Permission:** Bearer Token, `user:manage`
* **Path Parameter:** `user_id` (integer, wajib).

**Request Body (`UserUpdate`)**

Seluruh field bersifat opsional; hanya field yang dikirim (tidak `null`) yang diperbarui:

| Field | Tipe | Wajib | Validasi |
| --- | --- | --- | --- |
| `email` | string | Tidak | 3–255 karakter; di-*trim* dan diubah ke *lowercase*; harus unik. |
| `full_name` | string | Tidak | 1–150 karakter; di-*trim*. |
| `role_id` | integer | Tidak | Harus merujuk ke `roles.id` yang ada. |
| `is_active` | boolean | Tidak | `true` atau `false`. |
| `password` | string | Tidak | 8–255 karakter; mereset kata sandi pengguna. |

*(Catatan: `username` tidak dapat diubah melalui `UserUpdate`).*

**Contoh Request**

```json
{
  "full_name": "Operator Gudang Senior",
  "role_id": 2
}
```

**Contoh Response Berhasil (`200 OK` — `UserOut`)**

```json
{
  "id": 2,
  "username": "staff.jkt",
  "email": "staff.jkt@wms.local",
  "full_name": "Operator Gudang Senior",
  "role_id": 2,
  "role_name": "Warehouse Manager",
  "is_active": true,
  "warehouse_ids": [1],
  "failed_login_count": 0,
  "locked_until": null,
  "last_login_at": null,
  "created_by": 1,
  "created_at": "2026-10-21T14:13:08.757507+07:00",
  "updated_at": "2026-10-21T14:13:09.017929+07:00"
}
```

**Kemungkinan Response Error**

| Status | Kode Error | Penyebab |
| --- | --- | --- |
| `404` | `NOT_FOUND` | `user_id` atau `role_id` baru tidak ditemukan. |
| `409` | `DUPLICATE` | `email` baru sudah dipakai pengguna lain. |
| `422` | `VALIDATION_ERROR` | Panjang `password < 8`, format `email` tidak valid, pengguna mencoba menonaktifkan dirinya sendiri (`is_active: false`), atau pengguna mencoba mengubah `role_id` miliknya sendiri. |

**Aturan Bisnis & Dampak Data**

* Baris `users` dikunci dengan `SELECT ... FOR UPDATE` selama transaksi pembaruan.
* Apabila `is_active` berubah dari `true` menjadi `false`, **atau** apabila `password` diubah:
  * Seluruh *Refresh Token* aktif milik pengguna tersebut dicabut (`update_revoke_all_user_tokens`).
  * Jika `password` diubah, `failed_login_count` direset ke `0` dan `locked_until` diatur menjadi `NULL`.
* Mencatat audit log dengan `action = "USER_DEACTIVATED"` (bila dinonaktifkan dari aktif ke nonaktif) atau `action = "USER_UPDATED"` beserta `old_values` dan `new_values` (tanpa menyertakan kata sandi/hash).

---

### GET `/api/v1/users/{user_id}/warehouses` — Daftar Gudang yang Ditugaskan ke Pengguna

Mengambil daftar detail gudang yang saat ini ditugaskan kepada pengguna (`user_warehouses`).

* **HTTP Method & URL:** `GET /api/v1/users/{user_id}/warehouses`
* **Autentikasi & Permission:** Bearer Token, `user:manage`
* **Path Parameter:** `user_id` (integer, wajib).

**Contoh Response Berhasil (`200 OK` — `list[UserWarehouseOut]`)**

```json
[
  {
    "warehouse_id": 1,
    "warehouse_code": "WH-JKT",
    "warehouse_name": "Gudang Pusat Jakarta",
    "is_active": true,
    "created_by": 1,
    "created_at": "2026-10-21T14:13:09.033701+07:00"
  },
  {
    "warehouse_id": 2,
    "warehouse_code": "WH-SBY",
    "warehouse_name": "Gudang Cabang Surabaya",
    "is_active": true,
    "created_by": 1,
    "created_at": "2026-10-21T14:13:09.033701+07:00"
  }
]
```

**Kemungkinan Response Error**

| Status | Kode Error | Penyebab |
| --- | --- | --- |
| `404` | `NOT_FOUND` | `user_id` tidak ditemukan. |

---

### PUT `/api/v1/users/{user_id}/warehouses` — Atur Penugasan Gudang

Mengganti secara penuh (*replace*) daftar gudang yang ditugaskan kepada seorang pengguna pada tabel `user_warehouses` (PRD 3.2). Mengirim `{"warehouse_ids": []}` akan mencabut seluruh penugasan gudang pengguna tersebut.

* **HTTP Method & URL:** `PUT /api/v1/users/{user_id}/warehouses`
* **Autentikasi & Permission:** Bearer Token, `user:manage`
* **Path Parameter:** `user_id` (integer, wajib).

**Request Body (`UserWarehouseSet`)**

| Field | Tipe | Wajib | Default | Validasi |
| --- | --- | --- | --- | --- |
| `warehouse_ids` | array[integer] | Tidak | `[]` | Daftar ID gudang yang ada dan aktif (`is_active = true`). Nilai duplikat otomatis disaring. |

**Contoh Request**

```json
{
  "warehouse_ids": [1, 2]
}
```

**Contoh Response Berhasil (`200 OK` — `list[UserWarehouseOut]`)**

Mengembalikan daftar detail gudang yang baru ditugaskan (format sama dengan `GET /api/v1/users/{user_id}/warehouses`).

**Kemungkinan Response Error**

| Status | Kode Error | Penyebab | Contoh `details` |
| --- | --- | --- | --- |
| `404` | `NOT_FOUND` | `user_id` tidak ditemukan, atau salah satu `warehouse_id` tidak ada di tabel `warehouses`. | `{"missing_warehouse_ids": [9999]}` |
| `422` | `INACTIVE_REFERENCE` | Salah satu gudang yang dipilih berstatus `is_active = false`. | `{"inactive_warehouse_ids": [3]}` |

**Aturan Bisnis & Dampak Data**

* Baris pengguna dikunci dengan `SELECT ... FOR UPDATE`.
* Mencatat `USER_WAREHOUSES_UPDATED` pada `audit_logs` dengan `old_values: {"user_id": ..., "warehouse_ids": [...]}` dan `new_values: {"user_id": ..., "warehouse_ids": [...]}`.
* Diuji pada `test_ac12_warehouse_scoping_assignment_and_access_enforcement` (**AC-12**).

---

## 6. Relasi dan Ketergantungan

### 6.1 Tabel Database & Constraint Utama (`001_create_auth_tables.sql`, `002_create_master_tables.sql`)

| Tabel | Kunci & Constraint Utama | Relasi & Dampak |
| --- | --- | --- |
| `users` | `pk_users (id)`, `uq_users_username (username)`, `uq_users_email (email)`, `fk_users_role_id (role_id -> roles.id ON DELETE RESTRICT)` | Menyimpan profil pengguna, status aktif (`is_active`), serta penghitung gagal login (`failed_login_count`, `locked_until`). Penonaktifan pengguna mencabut seluruh `refresh_tokens` aktif milik pengguna tersebut. |
| `roles` & `permissions` | `pk_roles (id)`, `uq_roles_name (name)`, `pk_permissions (id)`, `uq_permissions_code (code)` | Dipetakan secara *many-to-many* melalui tabel `role_permissions (role_id, permission_id)`. |
| `user_warehouses` | `pk_user_warehouses (user_id, warehouse_id)` | Menentukan daftar gudang yang ditugaskan kepada pengguna untuk pemeriksaan `access_service.ensure_warehouse_access()` dan `resolve_read_warehouse_scope()`. |

Alur lapisan: `routes/users.py` → `user_service.py` (`with conn.transaction():` + `audit_service.record()`) → `user_repo.py` & `permission_repo.py` → PostgreSQL.

### 6.2 Matriks Peran & Permission (Hasil Seed)

Tabel berikut merangkum 24 kode *permission* yang di-*seed* oleh `008_seed_roles_permissions.sql` sesuai Matriks 3.1 PRD:

| Kode Permission | Super Admin | Warehouse Manager | Purchasing Staff | Warehouse Staff | Auditor |
| --- | :---: | :---: | :---: | :---: | :---: |
| `user:manage` | ✓ | – | – | – | – |
| `warehouse:manage` | ✓ | – | – | – | – |
| `location:manage` | ✓ | ✓ (g) | – | – | – |
| `master:manage` | ✓ | – | ✓ | – | – |
| `master:read` | ✓ | ✓ | ✓ | ✓ | ✓ |
| `po:create` | ✓ | – | ✓ | – | – |
| `po:issue` | ✓ | – | ✓ | – | – |
| `po:cancel` | ✓ | – | ✓ | – | – |
| `po:close` | ✓ | ✓ | ✓ | – | – |
| `po:read` | ✓ | ✓ | ✓ | ✓ | ✓ |
| `gr:manage` | ✓ | – | – | ✓ (g) | – |
| `gr:read` | ✓ | ✓ | ✓ | ✓ (g) | ✓ |
| `transfer:create` | ✓ | – | – | ✓ (g) | – |
| `transfer:approve` | ✓ | ✓ (g) | – | – | – |
| `transfer:ship` | ✓ | – | – | ✓ (g) | – |
| `transfer:receive` | ✓ | – | – | ✓ (g) | – |
| `transfer:read` | ✓ | ✓ | – | ✓ (g) | ✓ |
| `opname:manage` | ✓ | ✓ (g) | – | – | – |
| `opname:count` | ✓ | – | – | ✓ (g) | – |
| `opname:approve` | ✓ | ✓ (g) | – | – | – |
| `opname:read` | ✓ | ✓ | – | ✓ (g) | ✓ |
| `stock:read` | ✓ | ✓ | ✓ | ✓ (g) | ✓ |
| `ledger:read` | ✓ | ✓ | – | ✓ (g) | ✓ |
| `audit:read` | ✓ | – | – | – | ✓ |

*(Keterangan: tanda **(g)** menunjukkan aksi yang pada modul operasionalnya dibatasi oleh penugasan gudang di `user_warehouses`).*

---

## 7. Contoh Penggunaan (cURL)

```bash
BASE=http://localhost:8000/api/v1

# 1. Ambil daftar role
curl -s "$BASE/users/roles" -H "Authorization: Bearer <ACCESS_TOKEN>"

# 2. Buat pengguna baru dengan penugasan ke gudang ID 1
curl -s -X POST "$BASE/users" \
  -H "Authorization: Bearer <ACCESS_TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{
    "username": "staff.jkt",
    "email": "staff.jkt@wms.local",
    "password": "<PASSWORD_MIN_8>",
    "full_name": "Budi Operator",
    "role_id": 4,
    "warehouse_ids": [1]
  }'

# 3. Cari & ambil daftar pengguna
curl -s "$BASE/users?search=budi&limit=10&sort_by=username&sort_dir=asc" \
  -H "Authorization: Bearer <ACCESS_TOKEN>"

# 4. Perbarui penugasan gudang pengguna ID 2
curl -s -X PUT "$BASE/users/2/warehouses" \
  -H "Authorization: Bearer <ACCESS_TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{"warehouse_ids": [1, 2]}'

# 5. Nonaktifkan pengguna ID 2
curl -s -X PATCH "$BASE/users/2" \
  -H "Authorization: Bearer <ACCESS_TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{"is_active": false}'
```

---

## 8. Catatan dan Status Verifikasi

| # | Status | Catatan |
| --- | --- | --- |
| 1 | ✅ Terverifikasi | Penolakan akses `403 PERMISSION_DENIED` untuk pengguna tanpa `user:manage` serta pencatatan `old_values`/`new_values` di `audit_logs` telah diuji di `test_ac05_rbac_enforcement_and_audit_log_recording` (**AC-05**). |
| 2 | ✅ Terverifikasi | Penugasan gudang lewat `PUT /api/v1/users/{id}/warehouses` dan pemeriksaan `access_service.ensure_warehouse_access()` telah diuji di `test_ac12_warehouse_scoping_assignment_and_access_enforcement` (**AC-12**). |
| 3 | ✅ Terverifikasi | Pencegahan *self-lockout*: `PATCH /api/v1/users/{user_id}` menolak pengguna menonaktifkan dirinya sendiri (`is_active: false`) atau mengubah `role_id` miliknya sendiri, serta `PUT /api/v1/users/roles/{role_id}/permissions` menolak pencabutan `user:manage` dari peran `Super Admin` (`422 VALIDATION_ERROR`, diuji di `test_ac05_rbac_enforcement_and_audit_log_recording`). |
| 4 | ✅ Terverifikasi | Validasi format `email` menggunakan pola `EMAIL_REGEX` disertai normalisasi *lowercase* pada pembuatan dan pembaruan pengguna. |

