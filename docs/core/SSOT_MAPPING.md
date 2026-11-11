# Single Source of Truth Mapping

Dokumen ini memetakan pemilik informasi. Dokumen turunan hanya merujuk dan
menjelaskan dampak implementasi; tidak menyalin requirement sebagai sumber
kedua.

| Informasi | Sumber utama | Dokumen turunan |
| --- | --- | --- |
| Tujuan, scope, role, FR, NFR, workflow, AC | [PRD_GENERAL.md](PRD_GENERAL.md) | Backend, Frontend, Database, RULE_SYSTEM, QA |
| Kebutuhan implementasi backend | [PRD_BACKEND.md](PRD_BACKEND.md) | Kode backend, API, QA |
| Kebutuhan pengalaman frontend | [PRD_FRONTEND.md](PRD_FRONTEND.md) | Frontend dan API integration |
| Desain persistence | [DATABASE_DESIGN.md](DATABASE_DESIGN.md) | `SCHEMA_DATABASE.MD`, migrations, backend |
| DDL, tipe kolom, constraint, migrasi | [SCHEMA_DATABASE.MD](SCHEMA_DATABASE.MD) dan `db/migrations/` sebagai bukti | API, QA |
| Bentuk endpoint aktual | Route, schema, service, dan test | [API/README.md](../API/README.md) |
| Aturan bisnis operasional | PRD; aturan rinci bila sudah disetujui di RULE_SYSTEM | API, QA |
| Bukti perilaku teruji | `tests/` dan hasil run aktual | [QA/QA.MD](../QA/QA.MD) |
| Cara implementasi dan quality gate | STANDARDS | Kode, review, QA |

## Status sumber yang belum final

Requirement v2.0 telah diaudit dan dipetakan ke `PRD_GENERAL.md`. Dokumen legacy
tidak lagi menjadi sumber terpisah.

Arsitektur Multi-Tenant SaaS telah ditetapkan secara resmi pada `CONF-001` sebagai
Fase 2 (M9) di dalam `PRD_GENERAL.md` v2.3, `DATABASE_DESIGN.md`, dan `API_CONTRACT.md`.
Draft modular lama tetap diarsipkan hanya untuk pelacakan historis dan bukan lagi
sumber kebenaran yang berdiri sendiri.
