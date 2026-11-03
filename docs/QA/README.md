# QA — Quality Assurance

QA menggunakan PRD, skema database, kontrak API, dan aturan bisnis sebagai
input. QA tidak menambah requirement baru.

## Dokumen

| Dokumen | Fungsi |
| --- | --- |
| [QA.MD](QA.MD) | Rencana, acceptance criteria, test map, dan catatan hasil historis |

Implementasi test berada di [tests](../../tests) dan dijalankan terhadap
PostgreSQL nyata pada database test. Jangan menyebut test lulus tanpa
menjalankan command yang relevan.

Untuk perubahan dokumentasi, periksa juga
[Documentation Audit](../core/DOCUMENTATION_AUDIT.md) agar temuan, asumsi, dan
hasil verifikasi tidak tercampur.
