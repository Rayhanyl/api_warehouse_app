# CORE — Spesifikasi Fundamental

CORE adalah sumber utama untuk apa yang dibangun dan batas fundamental sistem.
Detail endpoint, test case, dan pedoman engineering tetap berada di folder
masing-masing.

## Hierarki dokumen

`PRD_GENERAL.md` adalah sumber utama kebutuhan produk. Dokumen layer mengacu
padanya dan tidak boleh menambah business requirement.

| Dokumen | Status | Tanggung jawab |
| --- | --- | --- |
| [PRD_GENERAL.md](PRD_GENERAL.md) | Approved / master product requirements | Tujuan, scope, role, FR, NFR, workflow, AC |
| [PRD_BACKEND.md](PRD_BACKEND.md) | Approved / layer specification | API, service, validation, security, transaction, error |
| [PRD_FRONTEND.md](PRD_FRONTEND.md) | Draft / target layer | Halaman, UX, state, permission UI, integrasi API |
| [DATABASE_DESIGN.md](DATABASE_DESIGN.md) | Approved / design map | Entitas, relasi, integritas, migration ownership |
| [SCHEMA_DATABASE.MD](SCHEMA_DATABASE.MD) | Approved / implementation detail | DDL, tipe kolom, constraint, dan query integrity |
| [FOLDER_STRUCTURE.MD](FOLDER_STRUCTURE.MD) | Approved / implementasi MVP | Arsitektur layer dan struktur repository |
| [API_CONTRACT.md](API_CONTRACT.md) | Ringkasan kontrak | Batas kontrak API dan rujukan detail aktual |
| [PRD Modular](PRD%20JejakStok%20%E2%80%94%20Sistem%20Manajemen%20Gudang%20%28Modular%29.md) | Draft / perlu konfirmasi | Usulan modular dan multi-tenant; bukan scope aktif |
| [DOCUMENTATION_AUDIT.md](DOCUMENTATION_AUDIT.md) | Audit | Temuan, asumsi, dan hal belum terverifikasi |
| [SSOT_MAPPING.md](SSOT_MAPPING.md) | Governance | Ownership dan pemetaan sumber kebenaran |

Requirement v2.0 telah diaudit dan diintegrasikan ke `PRD_GENERAL.md`; file legacy
tidak lagi dipertahankan sebagai sumber terpisah. Draft modular tidak boleh
digunakan untuk menambahkan tenant, platform admin, endpoint, tabel, atau
permission sebelum ada keputusan eksplisit.
