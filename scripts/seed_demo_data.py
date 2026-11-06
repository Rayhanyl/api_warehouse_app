"""Menyiapkan data presentasi/demo lengkap untuk Fase 1 (M0-M8) WMS API.

Seluruh mutasi stok dijalankan melalui service resmi:
(po_service, gr_service, transfer_service, opname_service -> inventory_service.apply_movement)
sehingga buku besar stock_movements, inventory_balances, document_sequences,
dan audit_logs 100% konsisten sesuai aturan bisnis PRD & AGENTS.md.

Fitur Script:
- Idempotent: Aman dijalankan berulang kali tanpa membuat data duplikat kotor.
- Dukungan flag --reset / --clean: Membersihkan data operasional dan me-reseed dari awal.
- Master data lengkap & realistis (Users, Warehouses, Storage Locations, Categories, UoMs, Suppliers, Items).
- Dokumen mencakup 100% siklus hidup status PRD:
  * PO: DRAFT, ISSUED, PARTIALLY_RECEIVED, RECEIVED, CLOSED, CANCELLED
  * GR: DRAFT, POSTED, CANCELLED
  * Transfer: DRAFT, APPROVED, SHIPPED, RECEIVED (dengan variance reason), CANCELLED
  * Opname: DRAFT, IN_PROGRESS (lokasi beku), WAITING_APPROVAL (lokasi beku), COMPLETED, CANCELLED
- Seluruh 5 tipe pergerakan stok terbentuk di stock_movements ledger.
- Stok in-transit aktif dan terlihat di ringkasan agregat persediaan.
- Mencetak ringkasan kredensial akun demo dan panduan skenario aksi live presentasi.

Cara menjalankan:
    python scripts/seed_demo_data.py
    python scripts/seed_demo_data.py --password <password_demo>
    python scripts/seed_demo_data.py --reset --yes
"""

from __future__ import annotations

import argparse
from datetime import date, timedelta
from decimal import Decimal
import getpass
import os
from pathlib import Path
import sys
from typing import Any

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import psycopg
from psycopg.rows import dict_row

from app.core.config import settings
from app.core.permissions import (
    ROLE_AUDITOR,
    ROLE_PURCHASING_STAFF,
    ROLE_SUPER_ADMIN,
    ROLE_WAREHOUSE_MANAGER,
    ROLE_WAREHOUSE_STAFF,
)
from app.repositories import (
    gr_repo,
    master_repo,
    opname_repo,
    permission_repo,
    po_repo,
    transfer_repo,
    user_repo,
    warehouse_repo,
)
from app.services import (
    audit_service,
    gr_service,
    master_service,
    opname_service,
    po_service,
    stock_service,
    transfer_service,
    user_service,
    warehouse_service,
)
from db.migrate import run_migrations

# -----------------------------------------------------------------------------
# 1. Definisi Data Master Pengguna (Users) & Peran RBAC
# -----------------------------------------------------------------------------
DEMO_USERS_SPEC: tuple[dict[str, Any], ...] = (
    {
        "role": ROLE_SUPER_ADMIN,
        "username": "superadmin",
        "email": "superadmin@wms.local",
        "full_name": "Budi Santoso (Super Admin)",
        "warehouses": ["WH-JKT-01", "WH-SBY-01", "WH-BDG-01"],
        "is_active": True,
        "desc": "Akses penuh global lintas seluruh gudang & modul sistem",
    },
    {
        "role": ROLE_WAREHOUSE_MANAGER,
        "username": "warehouse.manager",
        "email": "warehouse.manager@wms.local",
        "full_name": "Andi Pratama (Manager Regional Barat)",
        "warehouses": ["WH-JKT-01", "WH-BDG-01"],
        "is_active": True,
        "desc": "Persetujuan transfer & opname gudang Jakarta & Bandung",
    },
    {
        "role": ROLE_WAREHOUSE_MANAGER,
        "username": "manager.surabaya",
        "email": "manager.surabaya@wms.local",
        "full_name": "Eko Prasetyo (Manager Regional Timur)",
        "warehouses": ["WH-SBY-01"],
        "is_active": True,
        "desc": "Persetujuan transfer & opname gudang distribusi Surabaya",
    },
    {
        "role": ROLE_PURCHASING_STAFF,
        "username": "purchasing.staff",
        "email": "purchasing.staff@wms.local",
        "full_name": "Siti Rahma (Buyer Elektronik & Jaringan)",
        "warehouses": ["WH-JKT-01", "WH-SBY-01"],
        "is_active": True,
        "desc": "Pengadaan master barang teknologi, issue & close PO",
    },
    {
        "role": ROLE_PURCHASING_STAFF,
        "username": "purchasing.supplies",
        "email": "purchasing.supplies@wms.local",
        "full_name": "Ahmad Fauzi (Buyer Material & APD)",
        "warehouses": ["WH-JKT-01", "WH-SBY-01", "WH-BDG-01"],
        "is_active": True,
        "desc": "Pengadaan kemasan, material logistik & perlengkapan K3",
    },
    {
        "role": ROLE_WAREHOUSE_STAFF,
        "username": "warehouse.staff",
        "email": "warehouse.staff@wms.local",
        "full_name": "Rizky Saputra (Lead Inbound Jakarta)",
        "warehouses": ["WH-JKT-01"],
        "is_active": True,
        "desc": "Penerimaan GR, pergerakan stok & opname Gudang Jakarta",
    },
    {
        "role": ROLE_WAREHOUSE_STAFF,
        "username": "staff.outbound",
        "email": "staff.outbound@wms.local",
        "full_name": "Bayu Anggara (Outbound & Staging Jakarta)",
        "warehouses": ["WH-JKT-01"],
        "is_active": True,
        "desc": "Pengiriman transfer stok (ship) & staging Gudang Jakarta",
    },
    {
        "role": ROLE_WAREHOUSE_STAFF,
        "username": "staff.surabaya",
        "email": "staff.surabaya@wms.local",
        "full_name": "Dewi Lestari (Staf Gudang Surabaya)",
        "warehouses": ["WH-SBY-01"],
        "is_active": True,
        "desc": "Penerimaan transfer & operasional gudang Surabaya",
    },
    {
        "role": ROLE_WAREHOUSE_STAFF,
        "username": "staff.bandung",
        "email": "staff.bandung@wms.local",
        "full_name": "Dian Permana (Operator Transit Bandung)",
        "warehouses": ["WH-BDG-01"],
        "is_active": True,
        "desc": "Penerimaan & rekonsiliasi stok hub transit Bandung",
    },
    {
        "role": ROLE_AUDITOR,
        "username": "auditor",
        "email": "auditor@wms.local",
        "full_name": "Hendra Wijaya (Internal Compliance Auditor)",
        "warehouses": ["WH-JKT-01", "WH-SBY-01", "WH-BDG-01"],
        "is_active": True,
        "desc": "Pemeriksaan audit trail, mutasi ledger & stok global",
    },
    {
        "role": ROLE_AUDITOR,
        "username": "auditor.inventory",
        "email": "auditor.inventory@wms.local",
        "full_name": "Ratna Juwita (External Stock Auditor)",
        "warehouses": ["WH-JKT-01", "WH-SBY-01", "WH-BDG-01"],
        "is_active": True,
        "desc": "Pemeriksaan rekonsiliasi fisik & riwayat dokumen PO/GR/TRF",
    },
    {
        "role": ROLE_WAREHOUSE_STAFF,
        "username": "user.inactive",
        "email": "user.inactive@wms.local",
        "full_name": "Doni Siswanto (Mantan Karyawan - Nonaktif)",
        "warehouses": ["WH-JKT-01"],
        "is_active": False,
        "desc": "Akun nonaktif untuk demo penolakan autentikasi",
    },
)

# -----------------------------------------------------------------------------
# 2. Definisi Gudang & Lokasi Penyimpanan (Multi-Warehouse & Functional Bins)
# -----------------------------------------------------------------------------
WAREHOUSES_SPEC: tuple[dict[str, Any], ...] = (
    {
        "code": "WH-JKT-01",
        "name": "Gudang Pusat Jakarta",
        "address": "Kawasan Industri Pulogadung Blok J-12, Jakarta Timur",
        "allow_negative_stock": False,
        "locations": [
            ("JKT-RCV-01", "Area Receiving & Inbound Staging"),
            ("JKT-RAK-A1", "Rak Fast-Moving A1 - Komponen & Semikonduktor"),
            ("JKT-RAK-A2", "Rak Fast-Moving A2 - Sensor & Modul Komunikasi"),
            ("JKT-RAK-B1", "Rak Bulk Storage B1 - Kabel UTP & Fiber Optic"),
            ("JKT-RAK-B2", "Rak Medium B2 - Catu Daya & Router Jaringan"),
            ("JKT-RAK-C1", "Rak Material C1 - Box Kemasan & Perlengkapan"),
            ("JKT-STG-OUT", "Area Outbound Staging & Dispatching Jakarta"),
            ("JKT-QC-HOLD", "Area Karantina & QC Inspection Jakarta"),
        ],
    },
    {
        "code": "WH-SBY-01",
        "name": "Gudang Distribusi Surabaya",
        "address": "Kawasan Industri Rungkut SIER Kav. 8, Surabaya, Jawa Timur",
        "allow_negative_stock": False,
        "locations": [
            ("SBY-RCV-01", "Area Receiving Inbound Surabaya"),
            ("SBY-RAK-A1", "Rak Distribusi A1 - Komponen & Modul Jawa Timur"),
            ("SBY-RAK-A2", "Rak Distribusi A2 - Perangkat Jaringan & Server"),
            ("SBY-RAK-B1", "Rak Kemasan B1 - Material Box & Pallet Wrap"),
            ("SBY-STG-OUT", "Area Outbound Staging Pengiriman Cabang"),
        ],
    },
    {
        "code": "WH-BDG-01",
        "name": "Gudang Hub Transit Bandung",
        "address": "Jl. Soekarno-Hatta No. 412, Bandung, Jawa Barat",
        "allow_negative_stock": True,  # Menguji fitur izin negative stock sesuai PRD
        "locations": [
            ("BDG-STG-01", "Area Staging Inbound/Outbound Transit Bandung"),
            ("BDG-RAK-A1", "Rak Transit A1 - Komponen Cepat (Fast Moving)"),
            ("BDG-RAK-A2", "Rak Transit A2 - Perangkat Jaringan & Router"),
            ("BDG-RAK-B1", "Rak Penyangga B1 - Material Kemasan & Buffer Stock"),
            ("BDG-QC-HOLD", "Area Karantina & Pemeriksaan Transit Priangan"),
        ],
    },
)

# -----------------------------------------------------------------------------
# 3. Definisi Master Data: Kategori, UoM, Supplier, dan Items
# -----------------------------------------------------------------------------
CATEGORIES_SPEC: tuple[tuple[str, str], ...] = (
    (
        "Komponen Elektronik & Semikonduktor",
        "Microcontroller, IC driver, module sensor, relay board, dan komponen pasif industri",
    ),
    (
        "Perangkat Jaringan & Server",
        "Industrial switch DIN-Rail, router managed, gateway IoT, access point, dan server rackmount",
    ),
    (
        "Kabel, Fiber Optik & Aksesoris Instalasi",
        "Kabel UTP outdoor shielded, drop core fiber optic, patch cord, konektor RJ45 & fiber",
    ),
    (
        "Catu Daya & Kelistrikan Industri",
        "DIN-Rail switching power supply 24V/12V, surge arrester, mini UPS, dan terminal block",
    ),
    (
        "Material Kemasan & Perlengkapan Logistik",
        "Karton box heavy duty double-wall, pallet stretch film, bubble wrap, dan lakban segel",
    ),
    (
        "Perkakas, Instrumen & Pemindai Gudang",
        "Industrial wireless barcode scanner 2D, thermal label roll, ribbon barcode, dan alat ukur",
    ),
    (
        "Alat Pelindung Diri & K3 Gudang",
        "Sarung tangan safety cut-resistant, helm proyek ANSI, rompi visibilitas tinggi, dan kacamata",
    ),
)

UOMS_SPEC: tuple[tuple[str, str, bool], ...] = (
    ("PCS", "Pieces / Unit", False),
    ("BOX", "Karton Box", False),
    ("PACK", "Pak / Kantong", False),
    ("ROLL", "Gulungan / Roll", False),
    ("SET", "Set / Paket Lengkap", False),
    ("MTR", "Meter (UoM Desimal)", True),
    ("KG", "Kilogram (UoM Desimal)", True),
    ("LTR", "Liter (UoM Desimal)", True),
)

SUPPLIERS_SPEC: tuple[dict[str, str], ...] = (
    {
        "code": "SUP-001",
        "name": "PT Nusantara Elektronik Mandiri",
        "contact_person": "Irwan Setiawan",
        "phone": "021-8901234",
        "email": "sales@nusantara-elektronik.co.id",
        "address": "Kawasan Industri Jababeka Tahap II Blok EE-4, Cikarang, Jawa Barat",
    },
    {
        "code": "SUP-002",
        "name": "CV Mitra Kabel & Jaringan Presisi",
        "contact_person": "Lina Kusuma",
        "phone": "021-5544321",
        "email": "order@mitrakabel.co.id",
        "address": "Jl. Daan Mogot KM 14 No. 88, Cengkareng, Jakarta Barat",
    },
    {
        "code": "SUP-003",
        "name": "PT Global Kemasan & Solusi Gudang",
        "contact_person": "Dedi Kurniawan",
        "phone": "031-8439900",
        "email": "cs@globalkemasan.co.id",
        "address": "Jl. Berbek Industri III No. 15, Kawasan SIER, Sidoarjo, Jawa Timur",
    },
    {
        "code": "SUP-004",
        "name": "PT Delta Daya Elektrika",
        "contact_person": "Bambang Wijaya",
        "phone": "021-5912345",
        "email": "marketing@deltadaya.co.id",
        "address": "Kawasan Industri Manis Blok F No. 10, Tangerang, Banten",
    },
    {
        "code": "SUP-005",
        "name": "CV Sarana Instrumen & Logistik",
        "contact_person": "Maya Anggraeni",
        "phone": "031-7485500",
        "email": "sales@saranainstrumen.co.id",
        "address": "Jl. Margomulyo Indah Blok B-8, Tandes, Surabaya, Jawa Timur",
    },
    {
        "code": "SUP-006",
        "name": "PT Garda Prima Proteksi K3",
        "contact_person": "Rudi Hermawan",
        "phone": "021-8241122",
        "email": "contact@gardaprima.co.id",
        "address": "Jl. Raya Narogong KM 7 No. 45, Rawalumbu, Bekasi, Jawa Barat",
    },
)

ITEMS_SPEC: tuple[dict[str, str], ...] = (
    {
        "sku": "ELC-MCU-001",
        "name": "Microcontroller ESP32-S3 Industrial Dual-Core",
        "category": "Komponen Elektronik & Semikonduktor",
        "uom": "PCS",
        "description": "Modul kontroler IoT industri dengan Wi-Fi/BLE dan konektor antena eksternal IPEX",
    },
    {
        "sku": "ELC-PSU-002",
        "name": "Industrial Power Supply DIN-Rail 24V 10A 240W",
        "category": "Catu Daya & Kelistrikan Industri",
        "uom": "PCS",
        "description": "Catu daya switching DIN-Rail efisiensi tinggi 93% dengan proteksi overload & short circuit",
    },
    {
        "sku": "ELC-SNS-003",
        "name": "Sensor Suhu & Kelembaban RS485 Modbus RTU",
        "category": "Komponen Elektronik & Semikonduktor",
        "uom": "PCS",
        "description": "Sensor presisi pemantauan lingkungan gudang dan ruang server berprotokol Modbus RTU",
    },
    {
        "sku": "ELC-RLY-004",
        "name": "Modul Relay Industri 8-Channel Optocoupler 24V",
        "category": "Komponen Elektronik & Semikonduktor",
        "uom": "PCS",
        "description": "Modul driver relay isolasi optocoupler untuk kontrol aktuator beban industri",
    },
    {
        "sku": "NET-RTR-001",
        "name": "Industrial Gigabit Router 8-Port PoE+ Managed",
        "category": "Perangkat Jaringan & Server",
        "uom": "PCS",
        "description": "Router gigabit kelas industri dengan proteksi surge 6kV dan daya PoE+ 30W per port",
    },
    {
        "sku": "NET-SWT-002",
        "name": "Industrial Ethernet Switch 16-Port DIN-Rail",
        "category": "Perangkat Jaringan & Server",
        "uom": "PCS",
        "description": "Switch unmanaged 16-port 10/100/1000 Mbps tahan suhu ekstrem -40C hingga +75C",
    },
    {
        "sku": "NET-PTC-003",
        "name": "Cat6 Patch Cable Molded Snagless 2 Meter",
        "category": "Kabel, Fiber Optik & Aksesoris Instalasi",
        "uom": "PACK",
        "description": "Kabel patch RJ45 Cat6 tembaga murni isi 5 pcs per pack untuk interkoneksi rak server",
    },
    {
        "sku": "CBL-UTP-001",
        "name": "Kabel UTP Cat6 Shielded Outdoor Anti-UV",
        "category": "Kabel, Fiber Optik & Aksesoris Instalasi",
        "uom": "MTR",
        "description": "Kabel jaringan STP outdoor berlapis double jacket anti cuaca (UoM desimal meter)",
    },
    {
        "sku": "CBL-FBR-002",
        "name": "Drop Core Fiber Optic 2-Core Single Mode G657A",
        "category": "Kabel, Fiber Optik & Aksesoris Instalasi",
        "uom": "MTR",
        "description": "Kabel fiber optik outdoor berpelindung kawat baja messenger wire (UoM desimal meter)",
    },
    {
        "sku": "PKG-BOX-001",
        "name": "Karton Box Heavy Duty Double-Wall 60x40x40 cm",
        "category": "Material Kemasan & Perlengkapan Logistik",
        "uom": "BOX",
        "description": "Karton gelombang K150/M125x3/K150 daya tumpuk hingga 40 kg untuk distribusi antar-gudang",
    },
    {
        "sku": "PKG-BOX-002",
        "name": "Karton Box Medium Single-Wall 30x20x20 cm",
        "category": "Material Kemasan & Perlengkapan Logistik",
        "uom": "BOX",
        "description": "Karton kemasan pengiriman unit retail komponen elektronik",
    },
    {
        "sku": "PKG-WRP-003",
        "name": "Stretch Film / Pallet Wrap Clear 50cm x 300m",
        "category": "Material Kemasan & Perlengkapan Logistik",
        "uom": "ROLL",
        "description": "Plastik pembungkus pallet tebal 17 mikron elastisitas tinggi untuk kestabilan muatan",
    },
    {
        "sku": "WHS-SCN-001",
        "name": "Wireless Barcode Scanner 2D Rugged IP65",
        "category": "Perkakas, Instrumen & Pemindai Gudang",
        "uom": "SET",
        "description": "Pemindai barcode QR dan 1D nirkabel industri dengan dock pengisian daya dan baterai 2600mAh",
    },
    {
        "sku": "SAF-GLV-001",
        "name": "Sarung Tangan Safety PU Coated Cut-Resistant Level 5",
        "category": "Alat Pelindung Diri & K3 Gudang",
        "uom": "PACK",
        "description": "Sarung tangan anti-sayat serat HPPE berlapis poliuretan tahan abrasi (isi 3 pasang per pack)",
    },
    {
        "sku": "SAF-HLM-002",
        "name": "Helm Safety Proyek Fastrac ANSI Z89.1 Putih",
        "category": "Alat Pelindung Diri & K3 Gudang",
        "uom": "PCS",
        "description": "Helm keselamatan kerja standar ANSI dengan tali dagu 4-titik dan suspensi putar",
    },
)


# -----------------------------------------------------------------------------
# Helper Idempotent Master Data
# -----------------------------------------------------------------------------
def _ensure_category(
    conn: psycopg.Connection[dict[str, Any]],
    *,
    actor: dict[str, Any],
    name: str,
    description: str,
) -> dict[str, Any]:
    existing = master_repo.get_category_by_name(conn, name)
    if existing:
        if not existing["is_active"] or existing["description"] != description:
            return master_service.update_category(
                conn,
                actor=actor,
                category_id=int(existing["id"]),
                name=name,
                description=description,
                is_active=True,
                ip_address="127.0.0.1",
            )
        return existing
    return master_service.create_category(
        conn,
        actor=actor,
        name=name,
        description=description,
        is_active=True,
        ip_address="127.0.0.1",
    )


def _ensure_uom(
    conn: psycopg.Connection[dict[str, Any]],
    *,
    actor: dict[str, Any],
    code: str,
    name: str,
    allow_decimal: bool,
) -> dict[str, Any]:
    existing = master_repo.get_uom_by_code(conn, code)
    if existing:
        return existing
    return master_service.create_uom(
        conn,
        actor=actor,
        code=code,
        name=name,
        allow_decimal=allow_decimal,
        is_active=True,
        ip_address="127.0.0.1",
    )


def _ensure_supplier(
    conn: psycopg.Connection[dict[str, Any]],
    *,
    actor: dict[str, Any],
    code: str,
    name: str,
    contact_person: str,
    phone: str,
    email: str,
    address: str,
) -> dict[str, Any]:
    existing = master_repo.get_supplier_by_code(conn, code)
    if existing:
        return existing
    return master_service.create_supplier(
        conn,
        actor=actor,
        code=code,
        name=name,
        contact_person=contact_person,
        phone=phone,
        email=email,
        address=address,
        is_active=True,
        ip_address="127.0.0.1",
    )


def _ensure_item(
    conn: psycopg.Connection[dict[str, Any]],
    *,
    actor: dict[str, Any],
    sku: str,
    name: str,
    description: str,
    category_id: int,
    uom_id: int,
) -> dict[str, Any]:
    existing = master_repo.get_item_by_sku(conn, sku)
    if existing:
        return existing
    return master_service.create_item(
        conn,
        actor=actor,
        sku=sku,
        name=name,
        description=description,
        category_id=category_id,
        uom_id=uom_id,
        is_active=True,
        ip_address="127.0.0.1",
    )


def _ensure_warehouse(
    conn: psycopg.Connection[dict[str, Any]],
    *,
    actor: dict[str, Any],
    code: str,
    name: str,
    address: str,
    allow_negative_stock: bool,
) -> dict[str, Any]:
    existing = warehouse_repo.get_warehouse_by_code(conn, code)
    if existing:
        return existing
    return warehouse_service.create_warehouse(
        conn,
        actor=actor,
        code=code,
        name=name,
        address=address,
        allow_negative_stock=allow_negative_stock,
        is_active=True,
        ip_address="127.0.0.1",
    )


def _ensure_location(
    conn: psycopg.Connection[dict[str, Any]],
    *,
    actor: dict[str, Any],
    warehouse_id: int,
    code: str,
    name: str,
) -> dict[str, Any]:
    existing = warehouse_repo.get_location_by_warehouse_and_code(
        conn, warehouse_id, code
    )
    if existing:
        return existing
    return warehouse_service.create_location(
        conn,
        actor=actor,
        warehouse_id=warehouse_id,
        code=code,
        name=name,
        is_active=True,
        ip_address="127.0.0.1",
    )


# -----------------------------------------------------------------------------
# Reset Operasional (Truncate & Restart Identity)
# -----------------------------------------------------------------------------
def reset_operational_data(db_url: str | None = None) -> None:
    """Mereset data operasional dan tabel terkait untuk memulai dari kondisi bersih."""
    conninfo = db_url or settings.migration_database_url or settings.database_url
    print("[seed_demo_data] Membersihkan data operasional lama...")
    with psycopg.connect(conninfo, autocommit=True) as conn:
        conn.execute(
            """
            TRUNCATE TABLE
                audit_logs,
                document_sequences,
                stock_opname_lines,
                stock_opnames,
                stock_transfer_lines,
                stock_transfers,
                gr_lines,
                goods_receipts,
                po_lines,
                purchase_orders,
                stock_movements,
                inventory_balances,
                storage_locations,
                user_warehouses,
                warehouses,
                items,
                suppliers,
                uoms,
                categories,
                refresh_tokens,
                users
            RESTART IDENTITY CASCADE
            """
        )
    print("[seed_demo_data] Data operasional berhasil dibersihkan.")


# -----------------------------------------------------------------------------
# Fungsi Utama Seeding Data Demo
# -----------------------------------------------------------------------------
def seed_demo_data(
    password: str,
    db_url: str | None = None,
    reset: bool = False,
) -> dict[str, Any]:
    if len(password) < 8:
        raise ValueError("Kata sandi demo minimal harus terdiri dari 8 karakter.")

    if reset:
        reset_operational_data(db_url)

    # Pastikan migrasi terbaru telah terpasang
    run_migrations(db_url)
    conninfo = db_url or settings.database_url

    with psycopg.connect(conninfo, autocommit=True, row_factory=dict_row) as conn:
        roles = permission_repo.list_roles(conn)
        role_by_name = {r["name"]: int(r["id"]) for r in roles}

        # ---------------------------------------------------------------------
        # 1. Pastikan Akun Super Admin Tersedia Pertama Kali
        # ---------------------------------------------------------------------
        sa_spec = DEMO_USERS_SPEC[0]
        sa_existing = user_repo.get_user_by_username(conn, sa_spec["username"])
        if sa_existing is None:
            from app.core.security import hash_password

            with conn.transaction():
                sa_created = user_repo.insert_user(
                    conn,
                    username=sa_spec["username"],
                    email=sa_spec["email"],
                    password_hash=hash_password(password),
                    full_name=sa_spec["full_name"],
                    role_id=role_by_name[ROLE_SUPER_ADMIN],
                    is_active=True,
                    created_by=None,
                )
            sa_id = int(sa_created["id"])
        else:
            sa_id = int(sa_existing["id"])

        superadmin_actor = user_repo.get_user_auth_context(conn, sa_id)
        assert superadmin_actor is not None

        # Perbarui profil Super Admin
        user_service.update_user(
            conn,
            actor=superadmin_actor,
            user_id=sa_id,
            full_name=sa_spec["full_name"],
            is_active=True,
            password=password,
            ip_address="127.0.0.1",
        )
        superadmin_actor = user_repo.get_user_auth_context(conn, sa_id)
        assert superadmin_actor is not None

        # ---------------------------------------------------------------------
        # 2. Pastikan Gudang & Lokasi Penyimpanan Terdaftar
        # ---------------------------------------------------------------------
        warehouses: dict[str, dict[str, Any]] = {}
        locations: dict[str, dict[str, Any]] = {}

        for w_spec in WAREHOUSES_SPEC:
            wh = _ensure_warehouse(
                conn,
                actor=superadmin_actor,
                code=w_spec["code"],
                name=w_spec["name"],
                address=w_spec["address"],
                allow_negative_stock=w_spec["allow_negative_stock"],
            )
            warehouses[w_spec["code"]] = wh
            w_id = int(wh["id"])

            for loc_code, loc_name in w_spec["locations"]:
                loc = _ensure_location(
                    conn,
                    actor=superadmin_actor,
                    warehouse_id=w_id,
                    code=loc_code,
                    name=loc_name,
                )
                locations[loc_code] = loc

        wh_jkt = warehouses["WH-JKT-01"]
        wh_sby = warehouses["WH-SBY-01"]
        wh_bdg = warehouses["WH-BDG-01"]

        # ---------------------------------------------------------------------
        # 3. Buat / Perbarui Seluruh Akun Pengguna Demo & Penugasan Gudang
        # ---------------------------------------------------------------------
        users_by_username: dict[str, dict[str, Any]] = {
            "superadmin": superadmin_actor
        }

        for spec in DEMO_USERS_SPEC[1:]:
            existing_u = user_repo.get_user_by_username(conn, spec["username"])
            role_id = role_by_name[spec["role"]]
            if existing_u is None:
                created_u = user_service.create_user(
                    conn,
                    actor=superadmin_actor,
                    username=spec["username"],
                    email=spec["email"],
                    password=password,
                    full_name=spec["full_name"],
                    role_id=role_id,
                    is_active=spec.get("is_active", True),
                    ip_address="127.0.0.1",
                )
                uid = int(created_u["id"])
            else:
                uid = int(existing_u["id"])
                user_service.update_user(
                    conn,
                    actor=superadmin_actor,
                    user_id=uid,
                    email=spec["email"],
                    full_name=spec["full_name"],
                    role_id=role_id,
                    is_active=spec.get("is_active", True),
                    password=password,
                    ip_address="127.0.0.1",
                )

            # Tugaskan gudang ke user (Warehouse Scoping PRD 3.2)
            assigned_w_ids = [
                int(warehouses[w_code]["id"])
                for w_code in spec.get("warehouses", [])
                if w_code in warehouses
            ]
            user_service.set_user_warehouses(
                conn,
                actor=superadmin_actor,
                user_id=uid,
                warehouse_ids=assigned_w_ids,
                ip_address="127.0.0.1",
            )

            ctx = user_repo.get_user_auth_context(conn, uid)
            assert ctx is not None
            users_by_username[spec["username"]] = ctx

        # Refresh konteks Super Admin
        user_service.set_user_warehouses(
            conn,
            actor=superadmin_actor,
            user_id=sa_id,
            warehouse_ids=[
                int(wh_jkt["id"]),
                int(wh_sby["id"]),
                int(wh_bdg["id"]),
            ],
            ip_address="127.0.0.1",
        )
        superadmin_actor = user_repo.get_user_auth_context(conn, sa_id)
        assert superadmin_actor is not None
        users_by_username["superadmin"] = superadmin_actor

        # Shortcut aktor representatif untuk transaksi
        mgr_jkt_actor = users_by_username["warehouse.manager"]
        mgr_sby_actor = users_by_username["manager.surabaya"]
        pur_elc_actor = users_by_username["purchasing.staff"]
        pur_sup_actor = users_by_username["purchasing.supplies"]
        stf_jkt_actor = users_by_username["warehouse.staff"]
        stf_out_actor = users_by_username["staff.outbound"]
        stf_sby_actor = users_by_username["staff.surabaya"]
        stf_bdg_actor = users_by_username["staff.bandung"]

        # ---------------------------------------------------------------------
        # 4. Master Data: Kategori, UoM, Pemasok, dan Barang
        # ---------------------------------------------------------------------
        categories: dict[str, dict[str, Any]] = {}
        for cat_name, cat_desc in CATEGORIES_SPEC:
            cat = _ensure_category(
                conn, actor=superadmin_actor, name=cat_name, description=cat_desc
            )
            categories[cat_name] = cat

        uoms: dict[str, dict[str, Any]] = {}
        for uom_code, uom_name, uom_allow_dec in UOMS_SPEC:
            u = _ensure_uom(
                conn,
                actor=superadmin_actor,
                code=uom_code,
                name=uom_name,
                allow_decimal=uom_allow_dec,
            )
            uoms[uom_code] = u

        suppliers: dict[str, dict[str, Any]] = {}
        for sup_spec in SUPPLIERS_SPEC:
            s = _ensure_supplier(
                conn,
                actor=superadmin_actor,
                code=sup_spec["code"],
                name=sup_spec["name"],
                contact_person=sup_spec["contact_person"],
                phone=sup_spec["phone"],
                email=sup_spec["email"],
                address=sup_spec["address"],
            )
            suppliers[sup_spec["code"]] = s

        items: dict[str, dict[str, Any]] = {}
        for item_spec in ITEMS_SPEC:
            it = _ensure_item(
                conn,
                actor=superadmin_actor,
                sku=item_spec["sku"],
                name=item_spec["name"],
                description=item_spec["description"],
                category_id=int(categories[item_spec["category"]]["id"]),
                uom_id=int(uoms[item_spec["uom"]]["id"]),
            )
            items[item_spec["sku"]] = it

        # ---------------------------------------------------------------------
        # Helper untuk mendeteksi keberadaan dokumen demo
        # ---------------------------------------------------------------------
        def _get_po_by_notes_tag(tag: str) -> dict[str, Any] | None:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT id, po_number, status, notes FROM purchase_orders WHERE notes LIKE %s LIMIT 1",
                    (f"{tag}%",),
                )
                row = cur.fetchone()
                return dict(row) if row else None

        def _get_gr_by_notes_tag(tag: str) -> dict[str, Any] | None:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT id, gr_number, status, notes FROM goods_receipts WHERE notes LIKE %s LIMIT 1",
                    (f"{tag}%",),
                )
                row = cur.fetchone()
                return dict(row) if row else None

        def _get_transfer_by_notes_tag(tag: str) -> dict[str, Any] | None:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT id, transfer_number, status, notes FROM stock_transfers WHERE notes LIKE %s LIMIT 1",
                    (f"{tag}%",),
                )
                row = cur.fetchone()
                return dict(row) if row else None

        def _get_opname_by_notes_tag(tag: str) -> dict[str, Any] | None:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT id, opname_number, status, notes FROM stock_opnames WHERE notes LIKE %s LIMIT 1",
                    (f"{tag}%",),
                )
                row = cur.fetchone()
                return dict(row) if row else None

        today = date.today()

        # ---------------------------------------------------------------------
        # 5. Skenario Transaksi PO & GR (Semua Status: RECEIVED, PARTIALLY_RECEIVED,
        #    ISSUED, DRAFT, CLOSED, CANCELLED)
        # ---------------------------------------------------------------------

        # [DEMO-PO-01] -> Status: RECEIVED (Penerimaan Penuh)
        if not _get_po_by_notes_tag("[DEMO-PO-01]"):
            po1 = po_service.create_purchase_order(
                conn,
                actor=pur_elc_actor,
                supplier_id=int(suppliers["SUP-001"]["id"]),
                warehouse_id=int(wh_jkt["id"]),
                order_date=today - timedelta(days=7),
                notes="[DEMO-PO-01] Pengadaan stok awal kuartal komponen ESP32, PSU 24V & router Gudang Jakarta",
                lines=[
                    {
                        "item_id": int(items["ELC-MCU-001"]["id"]),
                        "qty_ordered": Decimal("200.0000"),
                        "notes": "ESP32-S3 batch produksi Q4",
                    },
                    {
                        "item_id": int(items["ELC-PSU-002"]["id"]),
                        "qty_ordered": Decimal("80.0000"),
                        "notes": "PSU DIN-Rail 24V 10A",
                    },
                    {
                        "item_id": int(items["NET-RTR-001"]["id"]),
                        "qty_ordered": Decimal("30.0000"),
                        "notes": "Router Gigabit PoE+ 8-Port",
                    },
                ],
                ip_address="127.0.0.1",
            )
            po1 = po_service.issue_purchase_order(
                conn,
                actor=pur_elc_actor,
                po_id=int(po1["id"]),
                ip_address="127.0.0.1",
            )
            po1_ln_map = {
                int(ln["item_id"]): int(ln["id"]) for ln in po1["lines"]
            }

            # GR #1 (POSTED): Menerima penuh seluruh pesanan PO #1
            gr1 = gr_service.create_goods_receipt(
                conn,
                actor=stf_jkt_actor,
                po_id=int(po1["id"]),
                received_date=today - timedelta(days=6),
                notes="[DEMO-GR-01] Penerimaan penuh surat jalan SJ-NEM-2026-089 di Gudang Jakarta",
                lines=[
                    {
                        "po_line_id": po1_ln_map[int(items["ELC-MCU-001"]["id"])],
                        "location_id": int(locations["JKT-RAK-A1"]["id"]),
                        "qty_received": Decimal("200.0000"),
                        "notes": "Ditempatkan di Rak A1 (Komponen)",
                    },
                    {
                        "po_line_id": po1_ln_map[int(items["ELC-PSU-002"]["id"])],
                        "location_id": int(locations["JKT-RAK-A1"]["id"]),
                        "qty_received": Decimal("80.0000"),
                        "notes": "Ditempatkan di Rak A1 (Power Supply)",
                    },
                    {
                        "po_line_id": po1_ln_map[int(items["NET-RTR-001"]["id"])],
                        "location_id": int(locations["JKT-RAK-B2"]["id"]),
                        "qty_received": Decimal("30.0000"),
                        "notes": "Ditempatkan di Rak B2 (Networking)",
                    },
                ],
                ip_address="127.0.0.1",
            )
            gr_service.post_goods_receipt(
                conn,
                actor=stf_jkt_actor,
                gr_id=int(gr1["id"]),
                ip_address="127.0.0.1",
            )

        # [DEMO-PO-02] -> Status: PARTIALLY_RECEIVED (Parsial + 1 GR DRAFT Siap Posting)
        if not _get_po_by_notes_tag("[DEMO-PO-02]"):
            po2 = po_service.create_purchase_order(
                conn,
                actor=pur_elc_actor,
                supplier_id=int(suppliers["SUP-002"]["id"]),
                warehouse_id=int(wh_jkt["id"]),
                order_date=today - timedelta(days=5),
                notes="[DEMO-PO-02] Pengadaan kabel UTP outdoor (UoM desimal), sensor suhu RS485, dan karton box",
                lines=[
                    {
                        "item_id": int(items["CBL-UTP-001"]["id"]),
                        "qty_ordered": Decimal("300.5000"),
                        "notes": "Kabel UTP outdoor 300.5 meter",
                    },
                    {
                        "item_id": int(items["ELC-SNS-003"]["id"]),
                        "qty_ordered": Decimal("50.0000"),
                        "notes": "Sensor RS485 Modbus RTU",
                    },
                    {
                        "item_id": int(items["PKG-BOX-001"]["id"]),
                        "qty_ordered": Decimal("100.0000"),
                        "notes": "Karton box heavy-duty double wall",
                    },
                ],
                ip_address="127.0.0.1",
            )
            po2 = po_service.issue_purchase_order(
                conn,
                actor=pur_elc_actor,
                po_id=int(po2["id"]),
                ip_address="127.0.0.1",
            )
            po2_ln_map = {
                int(ln["item_id"]): int(ln["id"]) for ln in po2["lines"]
            }

            # GR #2 (POSTED): Penerimaan parsial tahap pertama
            gr2 = gr_service.create_goods_receipt(
                conn,
                actor=stf_jkt_actor,
                po_id=int(po2["id"]),
                received_date=today - timedelta(days=4),
                notes="[DEMO-GR-02] Penerimaan tahap 1 PO #2 (kabel 150.25m, sensor 20 pcs, box 60 pcs)",
                lines=[
                    {
                        "po_line_id": po2_ln_map[int(items["CBL-UTP-001"]["id"])],
                        "location_id": int(locations["JKT-RAK-B1"]["id"]),
                        "qty_received": Decimal("150.2500"),
                        "notes": "Roll 1 kabel UTP 150.25 meter",
                    },
                    {
                        "po_line_id": po2_ln_map[int(items["ELC-SNS-003"]["id"])],
                        "location_id": int(locations["JKT-RAK-A2"]["id"]),
                        "qty_received": Decimal("20.0000"),
                        "notes": "Tahap 1: 20 unit sensor suhu",
                    },
                    {
                        "po_line_id": po2_ln_map[int(items["PKG-BOX-001"]["id"])],
                        "location_id": int(locations["JKT-RAK-C1"]["id"]),
                        "qty_received": Decimal("60.0000"),
                        "notes": "Tahap 1: 60 box kemasan",
                    },
                ],
                ip_address="127.0.0.1",
            )
            gr_service.post_goods_receipt(
                conn,
                actor=stf_jkt_actor,
                gr_id=int(gr2["id"]),
                ip_address="127.0.0.1",
            )

            # GR #3 (DRAFT): Siap diposting secara live saat presentasi demo!
            gr_service.create_goods_receipt(
                conn,
                actor=stf_jkt_actor,
                po_id=int(po2["id"]),
                received_date=today,
                notes="[DEMO-GR-03] [SIAP POSTING SAAT LIVE DEMO] Penerimaan tahap 2 sisa PO #2 (Kabel 150.25m & Sensor 30 pcs)",
                lines=[
                    {
                        "po_line_id": po2_ln_map[int(items["CBL-UTP-001"]["id"])],
                        "location_id": int(locations["JKT-RCV-01"]["id"]),
                        "qty_received": Decimal("150.2500"),
                        "notes": "Roll kedua 150.25 meter di area receiving",
                    },
                    {
                        "po_line_id": po2_ln_map[int(items["ELC-SNS-003"]["id"])],
                        "location_id": int(locations["JKT-RCV-01"]["id"]),
                        "qty_received": Decimal("30.0000"),
                        "notes": "Pelunasan sisa 30 unit sensor suhu",
                    },
                    {
                        "po_line_id": po2_ln_map[int(items["PKG-BOX-001"]["id"])],
                        "location_id": int(locations["JKT-RCV-01"]["id"]),
                        "qty_received": Decimal("40.0000"),
                        "notes": "Pelunasan sisa 40 box karton",
                    },
                ],
                ip_address="127.0.0.1",
            )

        # [DEMO-PO-03] -> Status: ISSUED (Siap Dibuatkan Goods Receipt dari Menu Receiving Surabaya)
        if not _get_po_by_notes_tag("[DEMO-PO-03]"):
            po3 = po_service.create_purchase_order(
                conn,
                actor=pur_sup_actor,
                supplier_id=int(suppliers["SUP-003"]["id"]),
                warehouse_id=int(wh_sby["id"]),
                order_date=today - timedelta(days=2),
                notes="[DEMO-PO-03] [SIAP BUAT GR SAAT LIVE DEMO] Pengadaan stok kemasan & switch jaringan cabang Surabaya",
                lines=[
                    {
                        "item_id": int(items["PKG-BOX-001"]["id"]),
                        "qty_ordered": Decimal("120.0000"),
                        "notes": "Karton box pengiriman Jawa Timur",
                    },
                    {
                        "item_id": int(items["PKG-WRP-003"]["id"]),
                        "qty_ordered": Decimal("30.0000"),
                        "notes": "Pallet stretch film 30 roll",
                    },
                    {
                        "item_id": int(items["NET-SWT-002"]["id"]),
                        "qty_ordered": Decimal("10.0000"),
                        "notes": "Industrial switch 16-port",
                    },
                ],
                ip_address="127.0.0.1",
            )
            po3 = po_service.issue_purchase_order(
                conn,
                actor=pur_sup_actor,
                po_id=int(po3["id"]),
                ip_address="127.0.0.1",
            )

            # GR #4 (CANCELLED): Menguji pembatalan draft GR
            po3_ln_map = {
                int(ln["item_id"]): int(ln["id"]) for ln in po3["lines"]
            }
            gr4 = gr_service.create_goods_receipt(
                conn,
                actor=stf_sby_actor,
                po_id=int(po3["id"]),
                received_date=today - timedelta(days=1),
                notes="[DEMO-GR-04] Draft penerimaan Surabaya yang dibatalkan karena salah input nomor surat jalan vendor",
                lines=[
                    {
                        "po_line_id": po3_ln_map[int(items["PKG-BOX-001"]["id"])],
                        "location_id": int(locations["SBY-RCV-01"]["id"]),
                        "qty_received": Decimal("20.0000"),
                        "notes": "Salah entry",
                    }
                ],
                ip_address="127.0.0.1",
            )
            gr_service.cancel_goods_receipt(
                conn,
                actor=stf_sby_actor,
                gr_id=int(gr4["id"]),
                ip_address="127.0.0.1",
            )

        # [DEMO-PO-04] -> Status: DRAFT (Siap Di-klik "Issue Purchase Order" saat Demo)
        if not _get_po_by_notes_tag("[DEMO-PO-04]"):
            po_service.create_purchase_order(
                conn,
                actor=pur_elc_actor,
                supplier_id=int(suppliers["SUP-004"]["id"]),
                warehouse_id=int(wh_jkt["id"]),
                order_date=today,
                notes="[DEMO-PO-04] [SIAP ISSUE SAAT LIVE DEMO] Pengadaan cadangan PSU DIN-Rail & modul relay industri",
                lines=[
                    {
                        "item_id": int(items["ELC-PSU-002"]["id"]),
                        "qty_ordered": Decimal("40.0000"),
                        "notes": "PSU 24V 10A batch darurat",
                    },
                    {
                        "item_id": int(items["ELC-RLY-004"]["id"]),
                        "qty_ordered": Decimal("60.0000"),
                        "notes": "Relay module 8-ch 24V",
                    },
                ],
                ip_address="127.0.0.1",
            )

        # [DEMO-PO-05] -> Status: CLOSED (Ditutup Lebih Awal dengan Closed Reason Resmi)
        if not _get_po_by_notes_tag("[DEMO-PO-05]"):
            po5 = po_service.create_purchase_order(
                conn,
                actor=pur_sup_actor,
                supplier_id=int(suppliers["SUP-005"]["id"]),
                warehouse_id=int(wh_jkt["id"]),
                order_date=today - timedelta(days=10),
                notes="[DEMO-PO-05] Pengadaan pemindai barcode wireless & kabel patch rackmount",
                lines=[
                    {
                        "item_id": int(items["WHS-SCN-001"]["id"]),
                        "qty_ordered": Decimal("25.0000"),
                        "notes": "Scanner 2D Rugged IP65",
                    },
                    {
                        "item_id": int(items["NET-PTC-003"]["id"]),
                        "qty_ordered": Decimal("50.0000"),
                        "notes": "Patch cable Cat6 2m",
                    },
                ],
                ip_address="127.0.0.1",
            )
            po5 = po_service.issue_purchase_order(
                conn,
                actor=pur_sup_actor,
                po_id=int(po5["id"]),
                ip_address="127.0.0.1",
            )
            po_service.close_purchase_order(
                conn,
                actor=mgr_jkt_actor,
                po_id=int(po5["id"]),
                closed_reason="Prinsipal menghentikan produksi model scanner seri ini; pesanan ditutup resmi atas kesepakatan kedua belah pihak.",
                ip_address="127.0.0.1",
            )

        # [DEMO-PO-06] -> Status: CANCELLED (Dibatalkan saat Masih DRAFT)
        if not _get_po_by_notes_tag("[DEMO-PO-06]"):
            po6 = po_service.create_purchase_order(
                conn,
                actor=pur_sup_actor,
                supplier_id=int(suppliers["SUP-006"]["id"]),
                warehouse_id=int(wh_bdg["id"]),
                order_date=today - timedelta(days=3),
                notes="[DEMO-PO-06] Estimasi awal perlengkapan APD gudang transit Bandung (Dibatalkan karena revisi spesifikasi safety)",
                lines=[
                    {
                        "item_id": int(items["SAF-GLV-001"]["id"]),
                        "qty_ordered": Decimal("40.0000"),
                        "notes": "Sarung tangan cut-resistant",
                    },
                    {
                        "item_id": int(items["SAF-HLM-002"]["id"]),
                        "qty_ordered": Decimal("20.0000"),
                        "notes": "Helm safety fastrac putih",
                    },
                ],
                ip_address="127.0.0.1",
            )
            po_service.cancel_purchase_order(
                conn,
                actor=pur_sup_actor,
                po_id=int(po6["id"]),
                ip_address="127.0.0.1",
            )

        # ---------------------------------------------------------------------
        # 6. Skenario Transaksi Stock Transfer (Semua Status: RECEIVED dg Variance,
        #    SHIPPED in-transit, APPROVED siap ship, DRAFT siap approve, CANCELLED)
        # ---------------------------------------------------------------------

        # [DEMO-TRF-01] -> Status: RECEIVED dengan Variance Reason Resmi
        if not _get_transfer_by_notes_tag("[DEMO-TRF-01]"):
            trf1 = transfer_service.create_stock_transfer(
                conn,
                actor=stf_jkt_actor,
                source_warehouse_id=int(wh_jkt["id"]),
                source_location_id=int(locations["JKT-RAK-A1"]["id"]),
                destination_warehouse_id=int(wh_sby["id"]),
                destination_location_id=int(locations["SBY-RAK-A1"]["id"]),
                notes="[DEMO-TRF-01] Alokasi komponen ESP32 & PSU dari Gudang Pusat Jakarta ke Cabang Surabaya",
                lines=[
                    {
                        "item_id": int(items["ELC-MCU-001"]["id"]),
                        "qty": Decimal("50.0000"),
                        "notes": "Alokasi MCU cabang Surabaya",
                    },
                    {
                        "item_id": int(items["ELC-PSU-002"]["id"]),
                        "qty": Decimal("20.0000"),
                        "notes": "PSU 24V kebutuhan Jawa Timur",
                    },
                ],
                ip_address="127.0.0.1",
            )
            transfer_service.approve_transfer(
                conn,
                actor=mgr_jkt_actor,
                transfer_id=int(trf1["id"]),
                ip_address="127.0.0.1",
            )
            trf1 = transfer_service.ship_transfer(
                conn,
                actor=stf_out_actor,
                transfer_id=int(trf1["id"]),
                ip_address="127.0.0.1",
            )
            trf1_ln_map = {
                int(ln["item_id"]): int(ln["id"]) for ln in trf1["lines"]
            }
            transfer_service.receive_transfer(
                conn,
                actor=stf_sby_actor,
                transfer_id=int(trf1["id"]),
                lines=[
                    {
                        "line_id": trf1_ln_map[int(items["ELC-MCU-001"]["id"])],
                        "qty_received": Decimal("50.0000"),
                        "variance_reason": None,
                    },
                    {
                        "line_id": trf1_ln_map[int(items["ELC-PSU-002"]["id"])],
                        "qty_received": Decimal("19.0000"),
                        "variance_reason": "1 unit kemasan penyok parah saat ekspedisi darat, dikarantina untuk klaim asuransi logistik",
                    },
                ],
                ip_address="127.0.0.1",
            )

        # [DEMO-TRF-02] -> Status: SHIPPED (IN-TRANSIT, Siap di-klik "Receive" saat Demo!)
        if not _get_transfer_by_notes_tag("[DEMO-TRF-02]"):
            trf2 = transfer_service.create_stock_transfer(
                conn,
                actor=stf_jkt_actor,
                source_warehouse_id=int(wh_jkt["id"]),
                source_location_id=int(locations["JKT-RAK-B2"]["id"]),
                destination_warehouse_id=int(wh_sby["id"]),
                destination_location_id=int(locations["SBY-RAK-A2"]["id"]),
                notes="[DEMO-TRF-02] [SEDANG IN-TRANSIT / SIAP RECEIVE SAAT LIVE DEMO] Pengiriman 8 unit Router PoE+ ke Surabaya",
                lines=[
                    {
                        "item_id": int(items["NET-RTR-001"]["id"]),
                        "qty": Decimal("8.0000"),
                        "notes": "Router PoE+ dalam perjalanan darat via truk logistik",
                    },
                ],
                ip_address="127.0.0.1",
            )
            transfer_service.approve_transfer(
                conn,
                actor=mgr_jkt_actor,
                transfer_id=int(trf2["id"]),
                ip_address="127.0.0.1",
            )
            transfer_service.ship_transfer(
                conn,
                actor=stf_out_actor,
                transfer_id=int(trf2["id"]),
                ip_address="127.0.0.1",
            )

        # [DEMO-TRF-03] -> Status: APPROVED (Siap di-klik "Ship Transfer" saat Demo!)
        if not _get_transfer_by_notes_tag("[DEMO-TRF-03]"):
            trf3 = transfer_service.create_stock_transfer(
                conn,
                actor=stf_jkt_actor,
                source_warehouse_id=int(wh_jkt["id"]),
                source_location_id=int(locations["JKT-RAK-C1"]["id"]),
                destination_warehouse_id=int(wh_bdg["id"]),
                destination_location_id=int(locations["BDG-STG-01"]["id"]),
                notes="[DEMO-TRF-03] [SIAP SHIP SAAT LIVE DEMO] Alokasi 15 box karton double-wall ke Gudang Transit Bandung",
                lines=[
                    {
                        "item_id": int(items["PKG-BOX-001"]["id"]),
                        "qty": Decimal("15.0000"),
                        "notes": "Karton box logistik Bandung",
                    },
                ],
                ip_address="127.0.0.1",
            )
            transfer_service.approve_transfer(
                conn,
                actor=mgr_jkt_actor,
                transfer_id=int(trf3["id"]),
                ip_address="127.0.0.1",
            )

        # [DEMO-TRF-04] -> Status: DRAFT (Siap di-klik "Approve" oleh Manager Surabaya saat Demo!)
        if not _get_transfer_by_notes_tag("[DEMO-TRF-04]"):
            transfer_service.create_stock_transfer(
                conn,
                actor=stf_sby_actor,
                source_warehouse_id=int(wh_sby["id"]),
                source_location_id=int(locations["SBY-RAK-A1"]["id"]),
                destination_warehouse_id=int(wh_jkt["id"]),
                destination_location_id=int(locations["JKT-RCV-01"]["id"]),
                notes="[DEMO-TRF-04] [SIAP APPROVE SAAT LIVE DEMO] Pengembalian internal cadangan 10 unit MCU dari Surabaya ke Jakarta",
                lines=[
                    {
                        "item_id": int(items["ELC-MCU-001"]["id"]),
                        "qty": Decimal("10.0000"),
                        "notes": "Re-alokasi kelebihan stok MCU Surabaya",
                    },
                ],
                ip_address="127.0.0.1",
            )

        # [DEMO-TRF-05] -> Status: CANCELLED (Dibatalkan Setelah Disetujui)
        if not _get_transfer_by_notes_tag("[DEMO-TRF-05]"):
            trf5 = transfer_service.create_stock_transfer(
                conn,
                actor=stf_jkt_actor,
                source_warehouse_id=int(wh_jkt["id"]),
                source_location_id=int(locations["JKT-RAK-A1"]["id"]),
                destination_warehouse_id=int(wh_bdg["id"]),
                destination_location_id=int(locations["BDG-RAK-A1"]["id"]),
                notes="[DEMO-TRF-05] Alokasi darurat MCU ke Bandung yang dibatalkan karena revisi jadwal instalasi proyek",
                lines=[
                    {
                        "item_id": int(items["ELC-MCU-001"]["id"]),
                        "qty": Decimal("5.0000"),
                        "notes": "Batal kirim",
                    },
                ],
                ip_address="127.0.0.1",
            )
            transfer_service.approve_transfer(
                conn,
                actor=mgr_jkt_actor,
                transfer_id=int(trf5["id"]),
                ip_address="127.0.0.1",
            )
            transfer_service.cancel_transfer(
                conn,
                actor=mgr_jkt_actor,
                transfer_id=int(trf5["id"]),
                ip_address="127.0.0.1",
            )

        # ---------------------------------------------------------------------
        # 7. Skenario Transaksi Stock Opname (Semua Status: COMPLETED,
        #    WAITING_APPROVAL, IN_PROGRESS, DRAFT, CANCELLED)
        # ---------------------------------------------------------------------

        # [DEMO-OPN-01] -> Status: COMPLETED (Menghasilkan Penyesuaian ADJUSTMENT_PLUS & ADJUSTMENT_MINUS)
        if not _get_opname_by_notes_tag("[DEMO-OPN-01]"):
            opn1 = opname_service.create_stock_opname(
                conn,
                actor=mgr_jkt_actor,
                warehouse_id=int(wh_jkt["id"]),
                location_id=int(locations["JKT-RAK-A1"]["id"]),
                notes="[DEMO-OPN-01] Audit fisik bulanan Rak A1 Gudang Jakarta (Selesai & Disetujui)",
                ip_address="127.0.0.1",
            )
            opn1 = opname_service.start_stock_opname(
                conn,
                actor=mgr_jkt_actor,
                opname_id=int(opn1["id"]),
                ip_address="127.0.0.1",
            )
            count_payload_1: list[dict[str, Any]] = []
            for ln in opn1["lines"]:
                iid = int(ln["item_id"])
                if iid == int(items["ELC-MCU-001"]["id"]):
                    count_payload_1.append(
                        {
                            "line_id": int(ln["id"]),
                            "qty_physical": Decimal("152.0000"),
                            "notes": "Ditemukan 2 unit tambahan bonus sampel QC vendor yang belum tercatat (ADJUSTMENT_PLUS)",
                        }
                    )
                elif iid == int(items["ELC-PSU-002"]["id"]):
                    count_payload_1.append(
                        {
                            "line_id": int(ln["id"]),
                            "qty_physical": Decimal("59.0000"),
                            "notes": "1 unit PSU rusak pecah casing di sudut rak penyimpanan (ADJUSTMENT_MINUS)",
                        }
                    )
                else:
                    count_payload_1.append(
                        {
                            "line_id": int(ln["id"]),
                            "qty_physical": Decimal(str(ln["qty_system"])),
                            "notes": "Jumlah fisik sesuai catatan sistem",
                        }
                    )
            opname_service.record_opname_counts(
                conn,
                actor=stf_jkt_actor,
                opname_id=int(opn1["id"]),
                lines=count_payload_1,
                ip_address="127.0.0.1",
            )
            opname_service.submit_stock_opname(
                conn,
                actor=stf_jkt_actor,
                opname_id=int(opn1["id"]),
                ip_address="127.0.0.1",
            )
            opname_service.approve_stock_opname(
                conn,
                actor=mgr_jkt_actor,
                opname_id=int(opn1["id"]),
                ip_address="127.0.0.1",
            )

        # [DEMO-OPN-02] -> Status: WAITING_APPROVAL (Opening Balance Saldo Awal, Lokasi Saat Ini BEKU)
        if not _get_opname_by_notes_tag("[DEMO-OPN-02]"):
            opn2 = opname_service.create_stock_opname(
                conn,
                actor=mgr_jkt_actor,
                warehouse_id=int(wh_bdg["id"]),
                location_id=int(locations["BDG-RAK-A1"]["id"]),
                notes="[DEMO-OPN-02] [SIAP APPROVE SAAT LIVE DEMO] Input saldo awal fisik Rak Transit Bandung (Lokasi Saat Ini Beku)",
                ip_address="127.0.0.1",
            )
            opname_service.start_stock_opname(
                conn,
                actor=mgr_jkt_actor,
                opname_id=int(opn2["id"]),
                ip_address="127.0.0.1",
            )
            opname_service.record_opname_counts(
                conn,
                actor=mgr_jkt_actor,
                opname_id=int(opn2["id"]),
                lines=[
                    {
                        "location_id": int(locations["BDG-RAK-A1"]["id"]),
                        "item_id": int(items["PKG-BOX-001"]["id"]),
                        "qty_physical": Decimal("25.0000"),
                        "notes": "Saldo awal fisik karton box di Rak Transit Bandung",
                    },
                    {
                        "location_id": int(locations["BDG-RAK-A1"]["id"]),
                        "item_id": int(items["ELC-MCU-001"]["id"]),
                        "qty_physical": Decimal("10.0000"),
                        "notes": "Cadangan modul MCU di Bandung",
                    },
                ],
                ip_address="127.0.0.1",
            )
            opname_service.submit_stock_opname(
                conn,
                actor=mgr_jkt_actor,
                opname_id=int(opn2["id"]),
                ip_address="127.0.0.1",
            )

        # [DEMO-OPN-03] -> Status: IN_PROGRESS (Lokasi JKT-RAK-A2 Sedang BEKU, Siap Input Hitung Fisik)
        if not _get_opname_by_notes_tag("[DEMO-OPN-03]"):
            opn3 = opname_service.create_stock_opname(
                conn,
                actor=mgr_jkt_actor,
                warehouse_id=int(wh_jkt["id"]),
                location_id=int(locations["JKT-RAK-A2"]["id"]),
                notes="[DEMO-OPN-03] [SIAP INPUT HITUNG FISIK SAAT LIVE DEMO] Sesi audit fisik aktif Rak A2 Sensor Jakarta (Lokasi Saat Ini Beku)",
                ip_address="127.0.0.1",
            )
            opname_service.start_stock_opname(
                conn,
                actor=mgr_jkt_actor,
                opname_id=int(opn3["id"]),
                ip_address="127.0.0.1",
            )

        # [DEMO-OPN-04] -> Status: DRAFT (Sesi Terjadwal, Siap di-klik "Start Opname" saat Demo!)
        if not _get_opname_by_notes_tag("[DEMO-OPN-04]"):
            opname_service.create_stock_opname(
                conn,
                actor=mgr_sby_actor,
                warehouse_id=int(wh_sby["id"]),
                location_id=int(locations["SBY-RAK-A1"]["id"]),
                notes="[DEMO-OPN-04] [SIAP START OPNAME SAAT LIVE DEMO] Jadwal audit persediaan akhir bulan Rak Elektronik Surabaya",
                ip_address="127.0.0.1",
            )

        # [DEMO-OPN-05] -> Status: CANCELLED (Sesi yang Dibatalkan Sebelum Mulai)
        if not _get_opname_by_notes_tag("[DEMO-OPN-05]"):
            opn5 = opname_service.create_stock_opname(
                conn,
                actor=mgr_jkt_actor,
                warehouse_id=int(wh_jkt["id"]),
                location_id=int(locations["JKT-QC-HOLD"]["id"]),
                notes="[DEMO-OPN-05] Sesi opname area karantina yang dibatalkan karena penjadwalan ulang teknis",
                ip_address="127.0.0.1",
            )
            opname_service.cancel_stock_opname(
                conn,
                actor=mgr_jkt_actor,
                opname_id=int(opn5["id"]),
                ip_address="127.0.0.1",
            )

        # ---------------------------------------------------------------------
        # 8. Ringkasan Statistik Database
        # ---------------------------------------------------------------------
        summary = {
            "users": user_service.list_users(conn)["total"],
            "warehouses": warehouse_service.list_warehouses(
                conn, actor=superadmin_actor
            )["total"],
            "storage_locations": warehouse_service.list_locations(
                conn, actor=superadmin_actor
            )["total"],
            "categories": master_service.list_categories(conn)["total"],
            "uoms": master_service.list_uoms(conn)["total"],
            "suppliers": master_service.list_suppliers(conn)["total"],
            "items": master_service.list_items(conn)["total"],
            "purchase_orders": po_service.list_purchase_orders(
                conn, actor=superadmin_actor
            )["total"],
            "goods_receipts": gr_service.list_goods_receipts(
                conn, actor=superadmin_actor
            )["total"],
            "stock_transfers": transfer_service.list_stock_transfers(
                conn, actor=superadmin_actor
            )["total"],
            "stock_opnames": opname_service.list_stock_opnames(
                conn, actor=superadmin_actor
            )["total"],
            "stock_balances": stock_service.list_stock_by_location(
                conn, actor=superadmin_actor
            )["total"],
            "stock_movements": stock_service.list_stock_movements(
                conn, actor=superadmin_actor
            )["total"],
            "audit_logs": audit_service.list_audit_logs(conn)["total"],
        }
        return summary


def print_demo_guide(password: str) -> None:
    """Mencetak panduan lengkap akun demo dan skenario aksi live presentasi."""
    print("\n" + "=" * 90)
    print(" " * 26 + "PANDUAN LENGKAP DEMO DATA WMS API")
    print("=" * 90)

    print("\n[1] DAFTAR AKUN PENGGUNA DEMO:")
    print(f"    Kata Sandi Seragam : {password}")
    print("-" * 90)
    print(f"{'Username':<22} {'Role':<20} {'Gudang Akses':<24} {'Keterangan'}")
    print("-" * 90)
    for u in DEMO_USERS_SPEC:
        wh_str = ", ".join(u["warehouses"])
        if len(wh_str) > 22:
            wh_str = "Global (Semua)"
        print(f"{u['username']:<22} {u['role']:<20} {wh_str:<24} {u['full_name']}")

    print("\n[2] SKENARIO SIAP KLIK SAAT LIVE DEMO / PRESENTASI:")
    print("-" * 90)
    print("Modul               | Status Saat Ini     | Aksi Live Demo yang Disiapkan")
    print("-" * 90)
    print("Purchase Order      | DRAFT               | [PO #4] Klik 'Issue Purchase Order'")
    print("Goods Receipt       | DRAFT               | [GR #3] Klik 'Post Goods Receipt' (PO #2 tahap 2)")
    print("Stock Transfer      | APPROVED            | [TRF #3] Klik 'Ship Transfer' (Jakarta -> Bandung)")
    print("Stock Transfer      | SHIPPED (In-Transit)| [TRF #2] Klik 'Receive Transfer' di Surabaya")
    print("Stock Transfer      | DRAFT               | [TRF #4] Klik 'Approve Transfer' oleh Manager Surabaya")
    print("Stock Opname        | WAITING_APPROVAL    | [OPN #2] Klik 'Approve Opname' (Lokasi BDG-RAK-A1 beku)")
    print("Stock Opname        | IN_PROGRESS         | [OPN #3] Klik 'Record Counts' lalu Submit (JKT-RAK-A2 beku)")
    print("Stock Opname        | DRAFT               | [OPN #4] Klik 'Start Opname' di Surabaya")
    print("-" * 90)

    print("\n[3] FITUR & INVARIAN PRD YANG SUDAH TERVERIFIKASI DALAM DATA:")
    print("  * Seluruh 6 status PO (DRAFT, ISSUED, PARTIALLY_RECEIVED, RECEIVED, CLOSED, CANCELLED)")
    print("  * Seluruh 3 status GR (DRAFT, POSTED, CANCELLED)")
    print("  * Seluruh 5 status Transfer (DRAFT, APPROVED, SHIPPED, RECEIVED dg variance, CANCELLED)")
    print("  * Seluruh 5 status Opname (DRAFT, IN_PROGRESS, WAITING_APPROVAL, COMPLETED, CANCELLED)")
    print("  * Seluruh 5 tipe pergerakan stok (IN_PURCHASE, OUT_TRANSFER, IN_TRANSFER, ADJUSTMENT_PLUS, ADJUSTMENT_MINUS)")
    print("  * Kuantitas desimal teruji pada kabel (UoM meter desimal: 300.5m -> 150.25m)")
    print("  * Selisih penerimaan transfer tercatat resmi dengan variance_reason")
    print("  * Penutupan PO resmi dengan closed_reason wajib")
    print("  * Pembekuan lokasi aktif (LOCATION_FROZEN) pada sesi opname OPN #2 & OPN #3")
    print("  * Stok in-transit aktif dan dapat dipantau pada Router NET-RTR-001")
    print("=" * 90 + "\n")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Seed data demo komprehensif Fase 1 (M0-M8) untuk presentasi aplikasi WMS."
    )
    parser.add_argument(
        "--password",
        help="Kata sandi seragam untuk seluruh akun demo (minimal 8 karakter). Bisa juga lewat env DEMO_PASSWORD.",
        default=os.environ.get("DEMO_PASSWORD"),
    )
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Bersihkan seluruh data operasional (TRUNCATE) dan buat ulang data demo dari nol.",
    )
    parser.add_argument(
        "--yes",
        "-y",
        action="store_true",
        help="Lewati konfirmasi interaktif saat menggunakan opsi --reset.",
    )
    parser.add_argument(
        "--db-url",
        help="URL koneksi database alternatif (default: membaca dari .env DATABASE_URL).",
        default=None,
    )
    args = parser.parse_args()

    password = args.password
    if not password:
        password = getpass.getpass(
            "Masukkan kata sandi untuk seluruh akun demo (minimal 8 karakter): "
        )

    if args.reset and not args.yes:
        confirm = input(
            "PERINGATAN: Opsi --reset akan menghapus seluruh data operasional di database. Lanjutkan? (y/N): "
        )
        if confirm.lower() not in ("y", "yes"):
            print("Operasi dibatalkan.")
            return 0

    try:
        summary = seed_demo_data(
            password=password, db_url=args.db_url, reset=args.reset
        )
    except Exception as exc:
        import traceback

        print(
            f"[seed_demo_data] Gagal menyiapkan data demo: {exc}",
            file=sys.stderr,
        )
        traceback.print_exc()
        return 1

    print("\n[seed_demo_data] Data demo Fase 1 berhasil disiapkan:")
    for table_name, count in summary.items():
        print(f"  - {table_name:22s}: {count}")

    print_demo_guide(password)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
