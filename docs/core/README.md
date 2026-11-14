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
| [PRD_FRONTEND.md](PRD_FRONTEND.md) | Approved / spesifikasi antarmuka (`warehouse_app`) | Halaman, UX, state, permission UI, integrasi API |
| [DATABASE_DESIGN.md](DATABASE_DESIGN.md) | Approved / design map | Entitas, relasi, integritas, migration ownership |
| [SCHEMA_DATABASE.MD](SCHEMA_DATABASE.MD) | Approved / implementation detail | DDL, tipe kolom, constraint, dan query integrity |
| [FOLDER_STRUCTURE.MD](FOLDER_STRUCTURE.MD) | Approved / implementasi MVP | Arsitektur layer dan struktur repository |
| [DEPLOYMENT_GUIDE_CICD.md](DEPLOYMENT_GUIDE_CICD.md) | Approved / panduan operasional | Panduan deployment production, Git workflow, PR rules, dan CI/CD GitHub Actions |
| [environment-setup-guide.md](environment-setup-guide.md) | Approved / panduan environment | Panduan multi-environment lokal vs server dev, pemuatan `.env`, dan Vite proxy |
| [security-server-and-app.md](security-server-and-app.md) | Approved / standar keamanan | Hardening SSH, firewall UFW, isolasi DB, rotasi rahasia, audit log, dan backup otomatis |
| [telegram-monitoring-guide.md](telegram-monitoring-guide.md) | Approved / panduan observabilitas | Notifikasi real-time error aplikasi (HTTP 500) & status container Docker via Telegram |
| [API_CONTRACT.md](API_CONTRACT.md) | Ringkasan kontrak | Batas kontrak API dan rujukan detail aktual |
| [PRD Modular](PRD%20JejakStok%20%E2%80%94%20Sistem%20Manajemen%20Gudang%20%28Modular%29.md) | Draft / perlu konfirmasi | Usulan modular dan multi-tenant; bukan scope aktif |
| [DOCUMENTATION_AUDIT.md](DOCUMENTATION_AUDIT.md) | Audit | Temuan, asumsi, dan hal belum terverifikasi |
| [SSOT_MAPPING.md](SSOT_MAPPING.md) | Governance | Ownership dan pemetaan sumber kebenaran |

Requirement v2.0 telah diaudit dan diintegrasikan ke `PRD_GENERAL.md`; file legacy
tidak lagi dipertahankan sebagai sumber terpisah. Arsitektur Multi-Tenant SaaS
telah disahkan melalui `CONF-001` sebagai Fase 2 (M9) dan dispesifikasikan secara
resmi pada `PRD_GENERAL.md`, `DATABASE_DESIGN.md`, dan `API_CONTRACT.md`, sehingga
penerapannya mengacu pada dokumen-dokumen resmi tersebut (bukan draft modular lama).
