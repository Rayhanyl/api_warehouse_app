# Dashboard Operasional

## 1. Informasi Umum

| Atribut | Keterangan |
| --- | --- |
| **Modul** | Dashboard Operasional (*KPI Stok, Tugas Tertunda & Mutasi Terkini*) |
| **Base path** | `/api/v1/dashboard` |
| **Rujukan PRD & AC** | `FR-DSH-001`, `DSH-F01`, `AC-38` |
| **Status implementasi** | ✅ Sudah diimplementasikan dan diuji (`tests/test_dashboard.py`) |
| **Kode sumber** | [routes/dashboard.py](../../app/api/routes/dashboard.py), [dashboard_service.py](../../app/services/dashboard_service.py), [dashboard_repo.py](../../app/repositories/dashboard_repo.py), [schemas/dashboard.py](../../app/schemas/dashboard.py) |
| **Tabel terkait** | `inventory_balances`, `stock_movements`, `purchase_orders`, `goods_receipts`, `stock_transfers`, `stock_opnames`, `warehouses`, `user_warehouses` |
| **Modul terkait** | [Autentikasi & Otorisasi](authentication.md), [Stok & Buku Besar](stock-ledger.md), [Gudang & Lokasi](warehouses.md) |

---

## 2. Penjelasan Fitur & Warehouse Scoping

Endpoint Dashboard menyediakan ringkasan data operasional real-time dalam satu pemanggilan API untuk halaman utama ruang kerja (`/dashboard`):

1. **Ringkasan Stok (`stock_summary`):**
   * `total_active_items`: jumlah seluruh SKU barang aktif di katalog saat mode global (*Super Admin*/*Auditor* tanpa filter gudang), atau jumlah SKU barang aktif yang tercatat memiliki saldo (`inventory_balances`) maupun transfer `SHIPPED` masuk pada cakupan gudang aktif.
   * `total_qty_on_hand`: total kuantitas fisik `qty_on_hand` barang aktif pada gudang aktif dalam cakupan.
   * `total_qty_in_transit`: total kuantitas barang aktif pada transfer berstatus `SHIPPED` yang menuju (`destination_warehouse_id`) gudang aktif dalam cakupan.
   * `low_stock_items_count`: jumlah baris `(warehouse_id, item_id)` pada gudang aktif untuk barang aktif yang memiliki batas minimum (`min_stock > 0`) dan `qty_on_hand <= min_stock` (selaras 1:1 dengan `GET /api/v1/stock/by-warehouse?critical_only=true` baik saat memilih seluruh gudang maupun per gudang).
2. **Antrean Tugas Tertunda (`pending_actions`):**
   * `pending_po_receipt_count`: PO berstatus `ISSUED` atau `PARTIALLY_RECEIVED` yang siap diterima.
   * `draft_gr_count`: Goods Receipt berstatus `DRAFT`.
   * `pending_transfer_ship_count`: Transfer stok berstatus `APPROVED` siap kirim.
   * `pending_transfer_receive_count`: Transfer stok berstatus `SHIPPED` menunggu penerimaan tujuan.
   * `active_opname_count`: Sesi Stock Opname aktif (`IN_PROGRESS`, `WAITING_L1_APPROVAL`, `WAITING_L2_APPROVAL`, atau `WAITING_APPROVAL`).
3. **Aktivitas Mutasi Terkini (`recent_activities`):** Hingga 8 pergerakan stok terakhir (`stock_movements`) lengkap dengan referensi dokumen, gudang, item, kuantitas, dan nama pelaku.
4. **Gudang Terakses (`assigned_warehouses`):** Daftar gudang aktif yang dapat diakses oleh pengguna (digunakan frontend sebagai opsi filter gudang di Dashboard & Topbar).

**Aturan Isolasi *Warehouse Scoping*:**
* *Super Admin* dan *Auditor* dapat melihat agregasi seluruh gudang aktif secara global, atau menyaring satu gudang tertentu lewat `?warehouse_id=`.
* Peran operasional (*Warehouse Manager*, *Purchasing Staff*, *Warehouse Staff*) otomatis dibatasi pada gudang yang ditugaskan (`user_warehouses`). Jika mengirim `?warehouse_id=` untuk gudang yang tidak ditugaskan, sistem menolak dengan `403 WAREHOUSE_NOT_ASSIGNED`.
* Jika pengguna operasional belum ditugaskan ke gudang mana pun, metrik mengembalikan nilai nol (`0` / `"0.0000"`) dan list kosong secara aman tanpa error.

---

## 3. Autentikasi dan Otorisasi

* **Autentikasi:** Wajib menyertakan `Authorization: Bearer <access_token>`.
* **Permission:** Tidak membutuhkan izin khusus selain pengguna terautentikasi aktif (`get_current_user`).

---

## 4. Ringkasan Endpoint

| Method | Endpoint | Fungsi | Auth | Permission |
| --- | --- | --- | --- | --- |
| GET | `/api/v1/dashboard/summary` | Mengambil ringkasan metrik stok, tugas tertunda, mutasi terkini, & gudang terakses | Bearer | – (`(g)` opsional via `?warehouse_id=`) |

---

## 5. Detail Endpoint

### GET `/api/v1/dashboard/summary` — Ringkasan Dashboard Operasional

* **Query Parameter:**
  * `warehouse_id` (`integer`, opsional) — Menyaring seluruh metrik stok, tugas tertunda, dan mutasi terkini ke satu gudang tertentu (tetap menjaga `assigned_warehouses` milik pengguna).

**Contoh Response Berhasil (`200 OK` — `DashboardSummaryOut`)**

```json
{
  "stock_summary": {
    "total_active_items": 42,
    "total_qty_on_hand": "1250.0000",
    "total_qty_in_transit": "30.0000",
    "low_stock_items_count": 3
  },
  "pending_actions": {
    "pending_po_receipt_count": 2,
    "draft_gr_count": 1,
    "pending_transfer_ship_count": 1,
    "pending_transfer_receive_count": 1,
    "active_opname_count": 0
  },
  "recent_activities": [
    {
      "id": 105,
      "created_at": "2026-11-14T10:15:00+00:00",
      "movement_type": "GR_IN",
      "reference_type": "GOODS_RECEIPT",
      "reference_id": 14,
      "reference_number": "GR-202611-0014",
      "warehouse_id": 1,
      "warehouse_code": "WH-JKT-01",
      "warehouse_name": "Gudang Utama Jakarta",
      "item_id": 7,
      "item_sku": "SKU-007",
      "item_name": "Karton Box Sedang",
      "qty_change": "50.0000",
      "qty_after": "150.0000",
      "actor_name": "Budi Operator"
    }
  ],
  "assigned_warehouses": [
    {
      "id": 1,
      "code": "WH-JKT-01",
      "name": "Gudang Utama Jakarta"
    }
  ]
}
```

**Kemungkinan Error:**
* `401 AUTH_TOKEN_INVALID` — Token tidak valid atau kedaluwarsa.
* `403 WAREHOUSE_NOT_ASSIGNED` — Pengguna operasional meminta `warehouse_id` di luar daftar penugasannya.
* `422 VALIDATION_ERROR` — `warehouse_id` bukan integer positif yang valid.
