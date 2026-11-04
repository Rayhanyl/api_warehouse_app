# Documentation Audit

**Tanggal audit:** 2026-11-03
**Status:** baseline audit; temuan yang memerlukan keputusan tetap terbuka.

## Temuan aktual

| ID | Kategori | Sumber | Temuan | Dampak | Prioritas | Status |
| --- | --- | --- | --- | --- | --- | --- |
| DOC-001 | Aktual | Audit sebelum restrukturisasi; `docs/CORE/PRD_GENERAL.md` dan `PRD_AUDIT_AND_RESTRUCTURING_REPORT.md` | Sebelumnya ada dua PRD dengan scope berbeda: MVP single-tenant versus usulan multi-tenant SaaS. | Developer dapat menambah fitur yang dilarang MVP. | Critical | Resolved |
| DOC-002 | Aktual | `docs/CORE/PRD_FRONTEND.md` dan `docs/CORE/PRD_GENERAL.md` | Sebelumnya rujukan `PRD_FRONTEND.md` belum tersedia di repository. Dokumen `docs/CORE/PRD_FRONTEND.md` kini tersedia dan terhubung ke RTM `PRD_GENERAL.md`. | Referensi target integrasi frontend kini dapat diverifikasi. | Medium | Resolved |
| DOC-003 | Aktual | `docs/QA/QA.MD`, `docs/STANDARDS/TECHNICAL_QUALITY_GATE.md` | QA dan quality gate telah memisahkan dengan tegas cakupan verifikasi backend aktual (`AC-01` s.d. `AC-22`) dari rencana checklist frontend masa depan. | Status rencana frontend tidak lagi tercampur dengan bukti pengujian backend. | Medium | Resolved |
| DOC-004 | Aktual | `docs/CORE/PRD_FRONTEND.md`, `docs/API/menus.md` | Kontrak resmi menu navigasi (`GET /api/v1/menus/my-menu` dan CRUD `/api/v1/menus`) serta daftar 19 icon canonical telah disatukan pada `PRD_FRONTEND.md` dan `docs/API/menus.md`. | Kontrak menu antara backend dan frontend konsisten. | Medium | Resolved |
| DOC-005 | Aktual | seluruh folder `docs` | Sebelum audit ini belum ada indeks lintas-folder, ownership map, atau workflow perubahan terpusat. | Navigasi dan pemeliharaan SSOT tidak konsisten. | High | Resolved |

## Asumsi

| ID | Asumsi | Alasan perlu konfirmasi | Dampak |
| --- | --- | --- | --- |
| AS-001 | Dikonfirmasi pemilik proyek (`CONF-001` Resolved): Fase 1 (M0–M8) adalah baseline Single-Tenant yang telah selesai, dan Fase 2 (M9) adalah transisi Multi-Tenant SaaS (`TNT`, `CFG`, `tenant_id` + RLS) sebelum modul `ISS`/`RPT`. | Telah dispesifikasikan secara resmi di `PRD_GENERAL.md` v2.1, `DATABASE_DESIGN.md`, `PRD_BACKEND.md`, `PRD_FRONTEND.md`, dan `API_CONTRACT.md`. | Menjadi acuan resmi tahap M9 berikutnya. |
| AS-002 | Frontend admin berada di repository terpisah. | Tidak ada source frontend di repository ini; catatan admin merujuk frontend. | Kontrak frontend tidak dapat divalidasi di sini. |
| AS-003 | Klaim hasil test di QA adalah snapshot run pada saat pengujian dijalankan. | QA mencatat 24 test lulus pada `wms_test`, tetapi setiap perubahan kode baru tetap harus diverifikasi ulang dengan run `pytest` terbaru. | Tidak boleh mengklaim perubahan baru lulus tanpa menjalankan test ulang. |

## Belum terverifikasi

- Kesesuaian seluruh contoh response API dengan run aktual terbaru.
- Status implementasi frontend dan kontrak menu pada repository lain.
- Keputusan pemilik proyek atas multi-tenant, platform admin, Goods Issue, dan
  Pelaporan.
- Validitas benchmark p95 terhadap dataset dan lingkungan produksi.

## Rekomendasi

1. Gunakan `PRD_GENERAL.md` sebagai acuan implementasi aktif.
2. Tandai dokumen modular sebagai draft dan jangan menambahkan migrasi atau
   endpoint dari dokumen tersebut tanpa persetujuan.
3. Pisahkan hasil test historis dari hasil run terbaru pada QA.
4. Pindahkan detail frontend ke dokumentasi repository frontend setelah
   repository dan kontraknya tersedia.
