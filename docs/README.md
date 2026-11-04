# Dokumentasi WMS

Dokumentasi ini adalah pintu masuk untuk pengembangan, pengujian, review, dan
pemeliharaan Warehouse Management System (WMS).

## Hierarki sumber informasi

1. **CORE** — spesifikasi fundamental yang disetujui dan kontrak sistem.
2. **API** — perilaku endpoint yang dapat diverifikasi dari implementasi.
3. **RULE_SYSTEM** — aturan bisnis dan workflow operasional.
4. **QA** — strategi, skenario, dan bukti pengujian.
5. **STANDARDS** — cara mengembangkan, meninjau, dan memelihara sistem.

Jika sumber berbeda, perilaku implementasi harus dilaporkan sebagai
discrepancy; perubahan requirement hanya boleh dilakukan melalui proses
perubahan yang terdokumentasi.

## Navigasi

| Area | Tanggung jawab | Pintu masuk |
| --- | --- | --- |
| CORE | PRD, skema, arsitektur, dan kontrak fundamental | [core/README.md](core/README.md) |
| API | Endpoint REST dan kontrak teknis aktual | [API/README.md](API/README.md) |
| RULE_SYSTEM | Aturan bisnis dan workflow | [RULE_SYSTEM/README.md](RULE_SYSTEM/README.md) |
| QA | Rencana dan bukti pengujian | [QA/README.md](QA/README.md) |
| STANDARDS | Standar engineering dan quality gate | [STANDARDS/README.md](STANDARDS/README.md) |

## Cara menemukan informasi

- Kebutuhan atau batas fitur: mulai dari [core/README.md](core/README.md).
- Endpoint, request, response, dan error: gunakan [API/README.md](API/README.md).
- Acuan lengkap validasi form & UI di sisi Frontend: gunakan [FRONTEND_VALIDATION_GUIDE.md](FRONTEND_VALIDATION_GUIDE.md).
- Transisi status atau aturan transaksi: gunakan
  [RULE_SYSTEM/README.md](RULE_SYSTEM/README.md), lalu PRD.
- Test yang wajib dijalankan: gunakan [QA/README.md](QA/README.md).
- Aturan implementasi dan review: gunakan
  [STANDARDS/README.md](STANDARDS/README.md).

## Aturan pemeliharaan

Sebelum mengubah spesifikasi, baca
[Documentation Change Management](STANDARDS/DOCUMENTATION_CHANGE_MANAGEMENT.md).
Audit dan keputusan yang belum dikonfirmasi dicatat di
[Documentation Audit](core/DOCUMENTATION_AUDIT.md), bukan disamarkan sebagai
requirement.
