# Documentation Audit

**Tanggal audit:** 2026-11-03
**Status:** baseline audit; temuan yang memerlukan keputusan tetap terbuka.

## Temuan aktual

| ID | Kategori | Sumber | Temuan | Dampak | Prioritas | Status |
| --- | --- | --- | --- | --- | --- | --- |
| DOC-001 | Aktual | Audit sebelum restrukturisasi; `docs/CORE/PRD_GENERAL.md` dan `PRD_AUDIT_AND_RESTRUCTURING_REPORT.md` | Sebelumnya ada dua PRD dengan scope berbeda: MVP single-tenant versus usulan multi-tenant SaaS. | Developer dapat menambah fitur yang dilarang MVP. | Critical | Resolved |
| DOC-002 | Aktual | `docs/CORE/PRD_FRONTEND.md` dan `docs/CORE/PRD_GENERAL.md` | Sebelumnya rujukan `PRD_FRONTEND.md` belum tersedia di repository. Dokumen `docs/CORE/PRD_FRONTEND.md` kini tersedia dan terhubung ke RTM `PRD_GENERAL.md`. | Referensi target integrasi frontend kini dapat diverifikasi. | Medium | Resolved |
| DOC-003 | Aktual | `docs/QA/QA.MD`, `docs/STANDARDS/TECHNICAL_QUALITY_GATE.md` | QA dan quality gate telah memisahkan dengan tegas cakupan verifikasi backend aktual (`AC-01` s.d. `AC-22`) dari rencana checklist frontend masa depan. | Status rencana frontend tidak lagi tercampur dengan bukti pengujian backend. | Medium | Resolved |
| DOC-004 | Aktual | `docs/CORE/PRD_FRONTEND.md`, `docs/API/menus.md` | Kontrak resmi menu navigasi (`GET /api/v1/menus/my-menu` dan CRUD `/api/v1/menus`) serta daftar 23 icon canonical telah disatukan pada `PRD_FRONTEND.md` dan `docs/API/menus.md`. | Kontrak menu antara backend dan frontend konsisten. | Medium | Resolved |
| DOC-005 | Aktual | seluruh folder `docs` | Sebelum audit ini belum ada indeks lintas-folder, ownership map, atau workflow perubahan terpusat. | Navigasi dan pemeliharaan SSOT tidak konsisten. | High | Resolved |

## Asumsi

| ID | Asumsi | Alasan perlu konfirmasi | Dampak |
| --- | --- | --- | --- |
| AS-001 | Dikonfirmasi pemilik proyek (`CONF-001` Resolved): Fase 1 (M0–M8) adalah baseline Single-Tenant yang telah selesai, dan Fase 2 (M9) adalah transisi Multi-Tenant SaaS (`TNT`, `CFG`, `tenant_id` + RLS) sebelum modul `ISS`/`RPT`. | Telah dispesifikasikan secara resmi di `PRD_GENERAL.md` v2.3, `DATABASE_DESIGN.md`, `PRD_BACKEND.md`, `PRD_FRONTEND.md`, dan `API_CONTRACT.md`. | Menjadi acuan resmi tahap M9 berikutnya. |
| AS-002 | Frontend admin dikembangkan berdampingan dalam satu workspace (`warehouse_app/`). | Struktur monorepo memiliki backend di `api_warehouse_app/` dan frontend React di `warehouse_app/`. | Kontrak frontend dapat divalidasi langsung terhadap implementasi aktual. |
| AS-003 | Klaim hasil test di QA adalah snapshot run pada saat pengujian dijalankan. | QA mencatat 47 test lulus pada `wms_test`, mencakup skenario `AC-01` s.d. `AC-22`, `AC-30` (import barang), dan `AC-31` (import supplier). Setiap perubahan kode baru tetap harus diverifikasi ulang dengan run `pytest` terbaru. | Tidak boleh mengklaim perubahan baru lulus tanpa menjalankan test ulang. |

## Belum terverifikasi

- Kesesuaian seluruh contoh response API dengan run aktual terbaru.
- Desain detail dan alur Goods Issue (`ISS`) serta Pelaporan Operasional (`RPT`) yang ditangguhkan ke Fase 3 (M10).
- Validitas benchmark p95 terhadap dataset dan lingkungan produksi.

## Rekomendasi

1. Gunakan `PRD_GENERAL.md` (v2.3) sebagai acuan implementasi aktif.
2. Pertahankan baseline Fase 1 Single-Tenant yang stabil sebelum mengeksekusi migrasi Fase 2 (`012` dan `013`).
3. Pisahkan hasil test historis dari hasil run terbaru pada QA.
4. Jaga sinkronisasi tipe data API antara OpenAPI backend dan TypeScript frontend (`warehouse_app/`).
