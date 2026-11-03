# Single Source of Truth Mapping

Dokumen ini memetakan pemilik informasi. Dokumen turunan hanya merujuk dan
menjelaskan dampak implementasi; tidak menyalin requirement sebagai sumber
kedua.

| Informasi | Sumber utama | Dokumen turunan |
| --- | --- | --- |
| Tujuan, scope, role, permission, status, AC, error | [PRODUCT_REQUIREMENTS_DOCUMENT.MD](PRODUCT_REQUIREMENTS_DOCUMENT.MD) | RULE_SYSTEM, API, QA |
| Struktur layer dan urutan implementasi | [FOLDER_STRUCTURE.MD](FOLDER_STRUCTURE.MD) | STANDARDS, QA |
| Tabel, relasi, constraint, migrasi | [SCHEMA_DATABASE.MD](SCHEMA_DATABASE.MD) dan `db/migrations/` sebagai bukti | API, QA |
| Bentuk endpoint aktual | Route, schema, service, dan test | [API/README.md](../API/README.md) |
| Aturan bisnis operasional | PRD; aturan rinci bila sudah disetujui di RULE_SYSTEM | API, QA |
| Bukti perilaku teruji | `tests/` dan hasil run aktual | [QA/QA.MD](../QA/QA.MD) |
| Cara implementasi dan quality gate | STANDARDS | Kode, review, QA |

## Status sumber yang belum final

`PRD JejakStok — Sistem Manajemen Gudang (Modular).md` memperkenalkan
multi-tenant dan modul usulan yang bertentangan dengan MVP single-tenant.
Dokumen tersebut dipertahankan sebagai draft untuk traceability, tetapi tidak
menjadi sumber kebenaran sampai pertanyaan terbukanya diputuskan dan
`AGENTS.md` diperbarui oleh pemilik proyek.
