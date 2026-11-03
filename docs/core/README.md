# CORE — Spesifikasi Fundamental

CORE adalah sumber utama untuk apa yang dibangun dan batas fundamental sistem.
Detail endpoint, test case, dan pedoman engineering tetap berada di folder
masing-masing.

## Dokumen

| Dokumen | Status | Tanggung jawab |
| --- | --- | --- |
| [PRODUCT_REQUIREMENTS_DOCUMENT.MD](PRODUCT_REQUIREMENTS_DOCUMENT.MD) | Approved / implementasi MVP | PRD, FR, RBAC, status, AC, dan katalog error |
| [SCHEMA_DATABASE.MD](SCHEMA_DATABASE.MD) | Approved / implementasi MVP | Model data, relasi, constraint, dan pemetaan migrasi |
| [FOLDER_STRUCTURE.MD](FOLDER_STRUCTURE.MD) | Approved / implementasi MVP | Arsitektur layer dan struktur repository |
| [API_CONTRACT.md](API_CONTRACT.md) | Ringkasan kontrak | Batas kontrak API dan rujukan detail aktual |
| [PRD Modular](PRD%20JejakStok%20%E2%80%94%20Sistem%20Manajemen%20Gudang%20%28Modular%29.md) | Draft / perlu konfirmasi | Usulan modular dan multi-tenant; bukan acuan implementasi saat ini |
| [CATATAN_PERMASALAHAN_ADMIN.md](CATATAN_PERMASALAHAN_ADMIN.md) | Catatan integrasi | Temuan dan usulan untuk klien admin terpisah; bukan requirement backend |
| [DOCUMENTATION_AUDIT.md](DOCUMENTATION_AUDIT.md) | Audit | Temuan, asumsi, dan hal belum terverifikasi |
| [SSOT_MAPPING.md](SSOT_MAPPING.md) | Governance | Ownership dan pemetaan sumber kebenaran |

`PRODUCT_REQUIREMENTS_DOCUMENT.MD` dan `FOLDER_STRUCTURE.MD` adalah dokumen
yang dirujuk oleh `AGENTS.md`. Draft modular tidak boleh digunakan untuk
menambahkan tenant, platform admin, endpoint, tabel, atau permission sebelum
ada keputusan eksplisit.
