# Template Dokumen Cetak Modular

## 1. Informasi Umum

| Atribut | Keterangan |
| --- | --- |
| **Modul** | Pengaturan Template Dokumen Cetak Modular & Upload Logo |
| **Base path** | `/api/v1/document-templates` |
| **Rute frontend** | `/admin/document-templates` |
| **Status implementasi** | ✅ Sudah diimplementasikan dan diuji (`tests/test_document_templates.py`) |
| **Kode sumber** | [routes/document_templates.py](../../app/api/routes/document_templates.py), [document_template_service.py](../../app/services/document_template_service.py), [document_template_repo.py](../../app/repositories/document_template_repo.py), [schemas/document_template.py](../../app/schemas/document_template.py) |
| **Tabel & migrasi** | `document_templates` (`db/migrations/015_create_document_templates_table.sql`) |
| **Modul terkait** | [Purchase Order](purchase-orders.md), [Goods Receipt](goods-receipts.md), [Transfer Stok](stock-transfers.md), [Audit Log](audit-logs.md) |

---

## 2. Penjelasan Fitur

Modul ini memungkinkan *Super Admin* menyesuaikan tata letak, identitas perusahaan, dan komponen visual dokumen cetak operasional WMS secara terpusat di PostgreSQL untuk tiga jenis dokumen:

1. `GOODS_RECEIPT` — Bukti Penerimaan Barang (GRN)
2. `STOCK_TRANSFER` — Surat Jalan Transfer Stok
3. `PURCHASE_ORDER` — Surat Pesanan Pembelian (PO)

**Kemampuan Konfigurasi:**
* **Identitas & Logo:** Judul dokumen, nama/alamat/kontak perusahaan, logo perusahaan (`logo_url`), posisi logo (`LEFT`, `CENTER`, `RIGHT`), ukuran logo (`SMALL`, `MEDIUM`, `LARGE`), serta catatan header/footer.
* **Kertas & Visibilitas:** Ukuran kertas (`A4`, `LETTER`, `F4`), orientasi (`PORTRAIT`, `LANDSCAPE`), margin halaman (`4.0..40.0` mm), toggle tampilkan barcode dokumen (`show_barcode`), catatan baris (`show_line_notes`), dan kontak perusahaan (`show_company_contact`).
* **Modular Section Order (`section_order`):** Urutan blok cetak (`HEADER`, `METADATA`, `TABLE`, `NOTES`, `SIGNATURES`) tanpa duplikasi, wajib minimal menyertakan `HEADER` dan `TABLE`.
* **Kolom Tabel Dinamis (`table_columns`):** Mengatur label dan visibilitas setiap kolom tabel sesuai whitelist per jenis dokumen (`ALLOWED_COLUMNS_BY_TYPE`), minimal 1 kolom tetap aktif.
* **Blok Tanda Tangan (`signature_layout`):** 0 hingga 4 kolom tanda tangan kustom (`title`, `subtitle`, `placeholder`).
* **Keamanan Upload Logo:** Berkas dicek ukurannya (maks. `2 MB`) dan dideteksi tipe nyatanya lewat **magic bytes** (hanya menerima PNG, JPEG, atau WEBP), diberi nama acak UUID (`logo-<hex>.<ext>`), disimpan di `UPLOAD_DIR/document_logos/`, dan disajikan dengan header `X-Content-Type-Options: nosniff`. Logo lokal lama otomatis dihapus bila tidak lagi dipakai template lain. Endpoint GET/PUT validasi `logo_url` menolak URL sembarangan untuk mencegah injeksi skema berbahaya.

---

## 3. Autentikasi dan Otorisasi

| Aksi | Autentikasi | Permission |
| --- | --- | --- |
| Membaca daftar & detail template (`GET`) | Bearer Token | – (semua pengguna terautentikasi agar modul cetak GRN/SJ/PO dapat merender template) |
| Mengunggah logo & mengubah template (`POST`/`PUT`) | Bearer Token | `user:manage` (*Super Admin*) |
| Mengakses berkas gambar logo (`/logos/{filename}`) | Publik (tanpa Bearer agar tag `<img>` & `@media print` memuat lancar) | – |

---

## 4. Ringkasan Endpoint

| # | Method | Endpoint | Fungsi | Auth | Permission |
| :-: | --- | --- | --- | --- | --- |
| 1 | GET | `/api/v1/document-templates` | Daftar seluruh template dokumen cetak (`GOODS_RECEIPT`, `STOCK_TRANSFER`, `PURCHASE_ORDER`) | Bearer | – |
| 2 | POST | `/api/v1/document-templates/upload-logo` | Unggah gambar logo perusahaan (PNG/JPG/WEBP maks. 2 MB) | Bearer | `user:manage` |
| 3 | GET | `/api/v1/document-templates/logos/{filename}` | Menyajikan file logo terunggah dengan validasi path traversal aman | Publik | – |
| 4 | GET | `/api/v1/document-templates/{document_type}` | Detail konfigurasi template untuk satu jenis dokumen | Bearer | – |
| 5 | PUT | `/api/v1/document-templates/{document_type}` | Memperbarui konfigurasi template & mencatat audit `UPDATE` | Bearer | `user:manage` |

---

## 5. Detail Kolom Tabel yang Diizinkan (`ALLOWED_COLUMNS_BY_TYPE`)

| `document_type` | Key Kolom yang Diizinkan |
| --- | --- |
| `GOODS_RECEIPT` | `no`, `sku_barcode`, `item_name`, `location`, `qty_received`, `uom`, `notes` |
| `STOCK_TRANSFER` | `no`, `sku_barcode`, `item_name`, `uom`, `qty_shipped`, `qty_received`, `variance` |
| `PURCHASE_ORDER` | `no`, `sku_barcode`, `item_name`, `uom`, `qty_ordered`, `qty_received`, `notes` |

---

## 6. Detail Endpoint Penting

### POST `/api/v1/document-templates/upload-logo`

* **Content-Type:** `multipart/form-data` dengan field `file`.
* **Response 200 (`LogoUploadOut`):**

```json
{
  "logo_url": "/api/v1/document-templates/logos/logo-a1b2c3d4e5f6...png",
  "filename": "logo-a1b2c3d4e5f6...png",
  "content_type": "image/png",
  "size_bytes": 48120
}
```

* Mencatat audit log `action = "UPLOAD_LOGO"`, `entity_type = "document_templates"`.

### PUT `/api/v1/document-templates/{document_type}`

* **Request Body (`DocumentTemplateUpdate`):** seluruh konfigurasi layout modular (`document_title`, `company_name`, `company_address`, `company_contact`, `logo_url`, `logo_position`, `logo_size`, `header_notes`, `footer_notes`, `paper_size`, `orientation`, `margin_mm`, `show_barcode`, `show_line_notes`, `show_company_contact`, `section_order`, `table_columns`, `signature_layout`).
* Mencatat audit log `action = "UPDATE"`, `entity_type = "document_templates"`, `entity_id = document_type` beserta diff `old_values`/`new_values`.
* **Kemungkinan Error:** `401 AUTH_TOKEN_INVALID`, `403 PERMISSION_DENIED`, `422 VALIDATION_ERROR` (jenis dokumen invalid, duplikasi section/key kolom, tidak ada kolom visible, `logo_url` tidak valid).
