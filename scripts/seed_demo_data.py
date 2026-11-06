"""Menyiapkan data presentasi/demo lengkap untuk Fase 1 (M0-M8) WMS API.

Seluruh mutasi stok dijalankan melalui service resmi (gr_service, transfer_service,
opname_service -> inventory_service.apply_movement) sehingga buku besar
stock_movements, inventory_balances, document_sequences, dan audit_logs
100% konsisten sesuai aturan bisnis PRD.

Script ini bersifat idempotent (aman dijalankan berulang kali).

Cara menjalankan:
    python scripts/seed_demo_data.py --password <password_demo>
    # atau menggunakan variabel lingkungan DEMO_PASSWORD:
    $env:DEMO_PASSWORD="<password_demo>"; python scripts/seed_demo_data.py
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

DEMO_USERS_SPEC: tuple[dict[str, str], ...] = (
    {
        "role": ROLE_SUPER_ADMIN,
        "username": "superadmin",
        "email": "superadmin@wms.local",
        "full_name": "Budi Santoso (Super Admin)",
    },
    {
        "role": ROLE_WAREHOUSE_MANAGER,
        "username": "warehouse.manager",
        "email": "warehouse.manager@wms.local",
        "full_name": "Andi Pratama (Warehouse Manager)",
    },
    {
        "role": ROLE_PURCHASING_STAFF,
        "username": "purchasing.staff",
        "email": "purchasing.staff@wms.local",
        "full_name": "Siti Rahma (Purchasing Staff)",
    },
    {
        "role": ROLE_WAREHOUSE_STAFF,
        "username": "warehouse.staff",
        "email": "warehouse.staff@wms.local",
        "full_name": "Rizky Saputra (Staff Gudang JKT & SBY)",
    },
    {
        "role": ROLE_WAREHOUSE_STAFF,
        "username": "staff.surabaya",
        "email": "staff.surabaya@wms.local",
        "full_name": "Dewi Lestari (Staff Khusus Gudang SBY)",
    },
    {
        "role": ROLE_AUDITOR,
        "username": "auditor",
        "email": "auditor@wms.local",
        "full_name": "Hendra Wijaya (Internal Auditor)",
    },
)


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


def seed_demo_data(password: str, db_url: str | None = None) -> dict[str, Any]:
    if len(password) < 8:
        raise ValueError("Kata sandi demo minimal harus terdiri dari 8 karakter.")

    run_migrations(db_url)
    conninfo = db_url or settings.database_url

    with psycopg.connect(conninfo, autocommit=True, row_factory=dict_row) as conn:
        roles = permission_repo.list_roles(conn)
        role_by_name = {r["name"]: int(r["id"]) for r in roles}

        # 1. Pastikan Super Admin tersedia terlebih dahulu sebagai actor awal
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

        # Perbarui password & nama lengkap Super Admin agar siap dipakai demo
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

        # 2. Pastikan seluruh akun role lainnya tersedia dan aktif
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
                    is_active=True,
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
                    is_active=True,
                    password=password,
                    ip_address="127.0.0.1",
                )
            ctx = user_repo.get_user_auth_context(conn, uid)
            assert ctx is not None
            users_by_username[spec["username"]] = ctx

        # 3. Buat 3 Gudang (JKT, SBY, BDG) & 7 Lokasi Penyimpanan
        wh_jkt = _ensure_warehouse(
            conn,
            actor=superadmin_actor,
            code="WH-JKT-01",
            name="Gudang Pusat Jakarta",
            address="Kawasan Industri Pulogadung Blok J-12, Jakarta Timur",
            allow_negative_stock=False,
        )
        wh_sby = _ensure_warehouse(
            conn,
            actor=superadmin_actor,
            code="WH-SBY-01",
            name="Gudang Distribusi Surabaya",
            address="Kawasan Industri Rungkut SIER Kav. 8, Surabaya",
            allow_negative_stock=False,
        )
        wh_bdg = _ensure_warehouse(
            conn,
            actor=superadmin_actor,
            code="WH-BDG-01",
            name="Gudang Transit Bandung",
            address="Jl. Soekarno-Hatta No. 412, Bandung",
            allow_negative_stock=True,
        )

        loc_jkt_rcv = _ensure_location(
            conn,
            actor=superadmin_actor,
            warehouse_id=int(wh_jkt["id"]),
            code="JKT-RCV-01",
            name="Area Receiving & Staging Jakarta",
        )
        loc_jkt_a1 = _ensure_location(
            conn,
            actor=superadmin_actor,
            warehouse_id=int(wh_jkt["id"]),
            code="JKT-RAK-A1",
            name="Rak A1 - Komponen & Modul Industri",
        )
        loc_jkt_b1 = _ensure_location(
            conn,
            actor=superadmin_actor,
            warehouse_id=int(wh_jkt["id"]),
            code="JKT-RAK-B1",
            name="Rak B1 - Jaringan, Kabel & Kemasan",
        )

        loc_sby_rcv = _ensure_location(
            conn,
            actor=superadmin_actor,
            warehouse_id=int(wh_sby["id"]),
            code="SBY-RCV-01",
            name="Area Receiving Surabaya",
        )
        loc_sby_a1 = _ensure_location(
            conn,
            actor=superadmin_actor,
            warehouse_id=int(wh_sby["id"]),
            code="SBY-RAK-A1",
            name="Rak Utama A1 Surabaya",
        )

        loc_bdg_stg = _ensure_location(
            conn,
            actor=superadmin_actor,
            warehouse_id=int(wh_bdg["id"]),
            code="BDG-STG-01",
            name="Area Staging Transit Bandung",
        )
        loc_bdg_a1 = _ensure_location(
            conn,
            actor=superadmin_actor,
            warehouse_id=int(wh_bdg["id"]),
            code="BDG-RAK-A1",
            name="Rak Transit A1 Bandung",
        )

        # 4. Tugaskan Gudang ke Pengguna (Warehouse Scoping PRD 3.2)
        user_service.set_user_warehouses(
            conn,
            actor=superadmin_actor,
            user_id=int(users_by_username["warehouse.manager"]["id"]),
            warehouse_ids=[
                int(wh_jkt["id"]),
                int(wh_sby["id"]),
                int(wh_bdg["id"]),
            ],
            ip_address="127.0.0.1",
        )
        user_service.set_user_warehouses(
            conn,
            actor=superadmin_actor,
            user_id=int(users_by_username["purchasing.staff"]["id"]),
            warehouse_ids=[int(wh_jkt["id"]), int(wh_sby["id"])],
            ip_address="127.0.0.1",
        )
        user_service.set_user_warehouses(
            conn,
            actor=superadmin_actor,
            user_id=int(users_by_username["warehouse.staff"]["id"]),
            warehouse_ids=[int(wh_jkt["id"]), int(wh_sby["id"])],
            ip_address="127.0.0.1",
        )
        user_service.set_user_warehouses(
            conn,
            actor=superadmin_actor,
            user_id=int(users_by_username["staff.surabaya"]["id"]),
            warehouse_ids=[int(wh_sby["id"])],
            ip_address="127.0.0.1",
        )

        # Refresh konteks actor setelah penugasan gudang
        for uname in list(users_by_username.keys()):
            refreshed = user_repo.get_user_auth_context(
                conn, int(users_by_username[uname]["id"])
            )
            assert refreshed is not None
            users_by_username[uname] = refreshed

        mgr_actor = users_by_username["warehouse.manager"]
        pur_actor = users_by_username["purchasing.staff"]
        stf_actor = users_by_username["warehouse.staff"]

        # 5. Master Data: Kategori, UoM, Pemasok, dan Barang
        # Rapikan kategori uji "asdfghjkl" bila ada agar daftar kategori terlihat profesional saat demo
        legacy_cat = master_repo.get_category_by_name(conn, "asdfghjkl")
        if legacy_cat:
            master_service.update_category(
                conn,
                actor=mgr_actor,
                category_id=int(legacy_cat["id"]),
                name="Perangkat Jaringan & Server",
                description="Switch industri, router, gateway IoT, dan perangkat rackmount",
                is_active=True,
                ip_address="127.0.0.1",
            )

        cat_elc = _ensure_category(
            conn,
            actor=mgr_actor,
            name="Komponent Elektronik",
            description="Microcontroller, power supply industri, modul sensor, dan aktuator",
        )
        cat_net = _ensure_category(
            conn,
            actor=mgr_actor,
            name="Perangkat Jaringan & Server",
            description="Switch industri, router, gateway IoT, dan perangkat rackmount",
        )
        cat_cbl = _ensure_category(
            conn,
            actor=mgr_actor,
            name="Kabel & Aksesoris Instalasi",
            description="Kabel UTP, fiber optik, konektor industri, dan pelindung kabel",
        )
        cat_pkg = _ensure_category(
            conn,
            actor=mgr_actor,
            name="Material Kemasan & Logistik",
            description="Karton box double-wall, pallet wrap, dan pelindung pengiriman",
        )

        uom_pcs = _ensure_uom(
            conn, actor=mgr_actor, code="PCS", name="Pieces / Unit", allow_decimal=False
        )
        uom_box = _ensure_uom(
            conn, actor=mgr_actor, code="BOX", name="Karton Box", allow_decimal=False
        )
        uom_mtr = _ensure_uom(
            conn, actor=mgr_actor, code="MTR", name="Meter", allow_decimal=True
        )
        uom_kg = _ensure_uom(
            conn, actor=mgr_actor, code="KG", name="Kilogram", allow_decimal=True
        )

        sup_1 = _ensure_supplier(
            conn,
            actor=mgr_actor,
            code="SUP-001",
            name="PT Nusantara Elektronik Mandiri",
            contact_person="Irwan Setiawan",
            phone="021-8901234",
            email="sales@nusantara-elektronik.co.id",
            address="Kawasan Industri Jababeka Tahap II Blok EE-4, Cikarang",
        )
        sup_2 = _ensure_supplier(
            conn,
            actor=mgr_actor,
            code="SUP-002",
            name="CV Mitra Kabel & Jaringan Presisi",
            contact_person="Lina Kusuma",
            phone="021-5544321",
            email="order@mitrakabel.co.id",
            address="Jl. Daan Mogot KM 14 No. 88, Jakarta Barat",
        )
        sup_3 = _ensure_supplier(
            conn,
            actor=mgr_actor,
            code="SUP-003",
            name="PT Global Kemasan & Solusi Gudang",
            contact_person="Dedi Kurniawan",
            phone="031-8439900",
            email="cs@globalkemasan.co.id",
            address="Jl. Berbek Industri III No. 15, Sidoarjo",
        )

        item_mcu = _ensure_item(
            conn,
            actor=mgr_actor,
            sku="ELC-MCU-001",
            name="Microcontroller ESP32-S3 Industrial Dual-Core",
            description="Modul kontroler IoT industri dengan Wi-Fi/BLE dan konektor antena eksternal",
            category_id=int(cat_elc["id"]),
            uom_id=int(uom_pcs["id"]),
        )
        item_psu = _ensure_item(
            conn,
            actor=mgr_actor,
            sku="ELC-PSU-002",
            name="Industrial Power Supply DIN-Rail 24V 10A",
            description="Catu daya switching industri 240W dengan proteksi short-circuit",
            category_id=int(cat_elc["id"]),
            uom_id=int(uom_pcs["id"]),
        )
        item_sns = _ensure_item(
            conn,
            actor=mgr_actor,
            sku="ELC-SNS-003",
            name="Sensor Suhu & Kelembaban RS485 Modbus RTU",
            description="Sensor presisi tinggi untuk pemantauan ruang server dan gudang",
            category_id=int(cat_elc["id"]),
            uom_id=int(uom_pcs["id"]),
        )
        item_rtr = _ensure_item(
            conn,
            actor=mgr_actor,
            sku="NET-RTR-001",
            name="Industrial Gigabit Router 8-Port PoE+",
            description="Router gigabit managed dengan dukungan PoE+ untuk perangkat gudang",
            category_id=int(cat_net["id"]),
            uom_id=int(uom_pcs["id"]),
        )
        item_cbl = _ensure_item(
            conn,
            actor=mgr_actor,
            sku="CBL-UTP-001",
            name="Kabel UTP Cat6 Shielded Outdoor (UoM Desimal Meter)",
            description="Kabel jaringan outdoor berlapis foil pelindung interferensi elektromagnetik",
            category_id=int(cat_cbl["id"]),
            uom_id=int(uom_mtr["id"]),
        )
        item_box = _ensure_item(
            conn,
            actor=mgr_actor,
            sku="PKG-BOX-001",
            name="Karton Box Heavy Duty Double Wall 60x40x40 cm",
            description="Karton pengiriman beban berat hingga 40 kg untuk distribusi antar-gudang",
            category_id=int(cat_pkg["id"]),
            uom_id=int(uom_box["id"]),
        )

        # 6a. Skenario Transaksi PO & GR (dijalankan bila belum ada PO)
        existing_pos, existing_po_total = po_repo.list_purchase_orders(
            conn, limit=5, offset=0, order_by_sql="po.id ASC"
        )
        if existing_po_total == 0:
            today = date.today()

            # ----------------------------------------------------------------
            # PO #1: Pengadaan Utama Gudang Pusat Jakarta -> Diterima Penuh (RECEIVED)
            # ----------------------------------------------------------------
            po1 = po_service.create_purchase_order(
                conn,
                actor=pur_actor,
                supplier_id=int(sup_1["id"]),
                warehouse_id=int(wh_jkt["id"]),
                order_date=today - timedelta(days=7),
                notes="Pengadaan stok awal kuartal komponen elektronik & router Gudang Pusat Jakarta",
                lines=[
                    {
                        "item_id": int(item_mcu["id"]),
                        "qty_ordered": Decimal("200.0000"),
                        "notes": "Batch produksi Q4",
                    },
                    {
                        "item_id": int(item_psu["id"]),
                        "qty_ordered": Decimal("80.0000"),
                        "notes": "Unit PSU DIN-Rail 24V",
                    },
                    {
                        "item_id": int(item_rtr["id"]),
                        "qty_ordered": Decimal("30.0000"),
                        "notes": "Router PoE+ gudang",
                    },
                ],
                ip_address="127.0.0.1",
            )
            po1 = po_service.issue_purchase_order(
                conn, actor=pur_actor, po_id=int(po1["id"]), ip_address="127.0.0.1"
            )
            po1_line_by_item = {
                int(ln["item_id"]): int(ln["id"]) for ln in po1["lines"]
            }

            gr1 = gr_service.create_goods_receipt(
                conn,
                actor=stf_actor,
                po_id=int(po1["id"]),
                received_date=today - timedelta(days=6),
                notes="Penerimaan penuh surat jalan SJ-NEM-2026-089 di Gudang Jakarta",
                lines=[
                    {
                        "po_line_id": po1_line_by_item[int(item_mcu["id"])],
                        "location_id": int(loc_jkt_a1["id"]),
                        "qty_received": Decimal("200.0000"),
                        "notes": "Kondisi segel baik, ditempatkan di Rak A1",
                    },
                    {
                        "po_line_id": po1_line_by_item[int(item_psu["id"])],
                        "location_id": int(loc_jkt_a1["id"]),
                        "qty_received": Decimal("80.0000"),
                        "notes": "Ditempatkan di Rak A1",
                    },
                    {
                        "po_line_id": po1_line_by_item[int(item_rtr["id"])],
                        "location_id": int(loc_jkt_b1["id"]),
                        "qty_received": Decimal("30.0000"),
                        "notes": "Ditempatkan di Rak B1",
                    },
                ],
                ip_address="127.0.0.1",
            )
            gr_service.post_goods_receipt(
                conn, actor=stf_actor, gr_id=int(gr1["id"]), ip_address="127.0.0.1"
            )

            # ----------------------------------------------------------------
            # PO #2: Pengadaan Kabel (Desimal) & Kemasan -> Diterima Sebagian (PARTIALLY_RECEIVED)
            #        + 1 GR berstatus DRAFT yang siap di-klik "Post" saat live demo!
            # ----------------------------------------------------------------
            po2 = po_service.create_purchase_order(
                conn,
                actor=pur_actor,
                supplier_id=int(sup_2["id"]),
                warehouse_id=int(wh_jkt["id"]),
                order_date=today - timedelta(days=4),
                notes="Pengadaan kabel UTP outdoor (UoM desimal meter), sensor RS485, dan karton box",
                lines=[
                    {
                        "item_id": int(item_cbl["id"]),
                        "qty_ordered": Decimal("300.5000"),
                        "notes": "Kabel UTP Cat6 outdoor 300.5 meter",
                    },
                    {
                        "item_id": int(item_sns["id"]),
                        "qty_ordered": Decimal("50.0000"),
                        "notes": "Sensor RS485 bertahap 2 pengiriman",
                    },
                    {
                        "item_id": int(item_box["id"]),
                        "qty_ordered": Decimal("100.0000"),
                        "notes": "Karton box double-wall",
                    },
                ],
                ip_address="127.0.0.1",
            )
            po2 = po_service.issue_purchase_order(
                conn, actor=pur_actor, po_id=int(po2["id"]), ip_address="127.0.0.1"
            )
            po2_line_by_item = {
                int(ln["item_id"]): int(ln["id"]) for ln in po2["lines"]
            }

            # GR #2 (POSTED): menerima sebagian PO #2
            gr2 = gr_service.create_goods_receipt(
                conn,
                actor=stf_actor,
                po_id=int(po2["id"]),
                received_date=today - timedelta(days=3),
                notes="Penerimaan tahap pertama PO #2 (kabel 150.25m, sensor 20 pcs, box 60 pcs)",
                lines=[
                    {
                        "po_line_id": po2_line_by_item[int(item_cbl["id"])],
                        "location_id": int(loc_jkt_b1["id"]),
                        "qty_received": Decimal("150.2500"),
                        "notes": "Roll pertama 150.25 meter",
                    },
                    {
                        "po_line_id": po2_line_by_item[int(item_sns["id"])],
                        "location_id": int(loc_jkt_a1["id"]),
                        "qty_received": Decimal("20.0000"),
                        "notes": "Tahap 1: 20 unit sensor",
                    },
                    {
                        "po_line_id": po2_line_by_item[int(item_box["id"])],
                        "location_id": int(loc_jkt_b1["id"]),
                        "qty_received": Decimal("60.0000"),
                        "notes": "Tahap 1: 60 box",
                    },
                ],
                ip_address="127.0.0.1",
            )
            gr_service.post_goods_receipt(
                conn, actor=stf_actor, gr_id=int(gr2["id"]), ip_address="127.0.0.1"
            )

            # GR #3 (DRAFT): siap diposting secara live saat presentasi
            gr_service.create_goods_receipt(
                conn,
                actor=stf_actor,
                po_id=int(po2["id"]),
                received_date=today,
                notes="[SIAP POSTING SAAT DEMO] Penerimaan tahap kedua sisa pengiriman PO #2",
                lines=[
                    {
                        "po_line_id": po2_line_by_item[int(item_cbl["id"])],
                        "location_id": int(loc_jkt_rcv["id"]),
                        "qty_received": Decimal("150.2500"),
                        "notes": "Roll kedua 150.25 meter di area receiving",
                    },
                    {
                        "po_line_id": po2_line_by_item[int(item_sns["id"])],
                        "location_id": int(loc_jkt_rcv["id"]),
                        "qty_received": Decimal("30.0000"),
                        "notes": "Pelunasan 30 unit sensor RS485",
                    },
                ],
                ip_address="127.0.0.1",
            )

            # ----------------------------------------------------------------
            # PO #3: Berstatus DRAFT untuk Gudang Surabaya -> siap di-klik "Issue" saat demo
            # ----------------------------------------------------------------
            po_service.create_purchase_order(
                conn,
                actor=pur_actor,
                supplier_id=int(sup_3["id"]),
                warehouse_id=int(wh_sby["id"]),
                order_date=today,
                notes="[SIAP ISSUE SAAT DEMO] Pengadaan kemasan & router cabang Surabaya",
                lines=[
                    {
                        "item_id": int(item_box["id"]),
                        "qty_ordered": Decimal("120.0000"),
                        "notes": "Stok kemasan distribusi Jawa Timur",
                    },
                    {
                        "item_id": int(item_rtr["id"]),
                        "qty_ordered": Decimal("15.0000"),
                        "notes": "Cadangan router cabang",
                    },
                ],
                ip_address="127.0.0.1",
            )

        # 6b. Skenario Stock Transfer (dijalankan bila jumlah transfer < 3)
        existing_trfs, existing_trf_total = transfer_repo.list_transfers(
            conn,
            limit=10,
            offset=0,
            scoped_warehouse_ids=None,
            warehouse_id=None,
            source_warehouse_id=None,
            destination_warehouse_id=None,
            status=None,
            date_from=None,
            date_to=None,
            search=None,
            order_by_sql="st.id ASC",
        )
        if existing_trf_total < 3:
            if existing_trf_total == 0:
                # Buat Transfer #1: Jakarta -> Surabaya
                trf1 = transfer_service.create_stock_transfer(
                    conn,
                    actor=stf_actor,
                    source_warehouse_id=int(wh_jkt["id"]),
                    source_location_id=int(loc_jkt_a1["id"]),
                    destination_warehouse_id=int(wh_sby["id"]),
                    destination_location_id=int(loc_sby_a1["id"]),
                    notes="Distribusi komponen ESP32 & PSU dari Gudang Pusat Jakarta ke Cabang Surabaya",
                    lines=[
                        {
                            "item_id": int(item_mcu["id"]),
                            "qty": Decimal("50.0000"),
                            "notes": "Alokasi stok cabang Surabaya",
                        },
                        {
                            "item_id": int(item_psu["id"]),
                            "qty": Decimal("20.0000"),
                            "notes": "PSU 24V untuk pelanggan Jawa Timur",
                        },
                    ],
                    ip_address="127.0.0.1",
                )
                transfer_service.approve_transfer(
                    conn,
                    actor=mgr_actor,
                    transfer_id=int(trf1["id"]),
                    ip_address="127.0.0.1",
                )
                trf1 = transfer_service.ship_transfer(
                    conn,
                    actor=stf_actor,
                    transfer_id=int(trf1["id"]),
                    ip_address="127.0.0.1",
                )
            else:
                trf1 = transfer_repo.get_transfer_by_id(
                    conn, int(existing_trfs[0]["id"])
                )
                assert trf1 is not None

            if trf1["status"] == "SHIPPED":
                trf1_line_by_item = {
                    int(ln["item_id"]): int(ln["id"]) for ln in trf1["lines"]
                }
                sby_staff_actor = users_by_username["staff.surabaya"]
                transfer_service.receive_transfer(
                    conn,
                    actor=sby_staff_actor,
                    transfer_id=int(trf1["id"]),
                    lines=[
                        {
                            "line_id": trf1_line_by_item[int(item_mcu["id"])],
                            "qty_received": Decimal("50.0000"),
                            "variance_reason": None,
                        },
                        {
                            "line_id": trf1_line_by_item[int(item_psu["id"])],
                            "qty_received": Decimal("19.0000"),
                            "variance_reason": "1 unit kemasan penyok saat ekspedisi darat, dikarantina untuk klaim asuransi",
                        },
                    ],
                    ip_address="127.0.0.1",
                )

            # ----------------------------------------------------------------
            # Stock Transfer #2: Jakarta -> Surabaya berstatus SHIPPED (In-Transit)
            # Menampilkan angka in_transit pada Ringkasan Stok & siap di-klik "Receive" saat demo!
            # ----------------------------------------------------------------
            trf2 = transfer_service.create_stock_transfer(
                conn,
                actor=stf_actor,
                source_warehouse_id=int(wh_jkt["id"]),
                source_location_id=int(loc_jkt_b1["id"]),
                destination_warehouse_id=int(wh_sby["id"]),
                destination_location_id=int(loc_sby_rcv["id"]),
                notes="[SEDANG IN-TRANSIT / SIAP RECEIVE SAAT DEMO] Pengiriman Router & Kabel UTP ke Surabaya",
                lines=[
                    {
                        "item_id": int(item_rtr["id"]),
                        "qty": Decimal("8.0000"),
                        "notes": "Router PoE+ dalam perjalanan",
                    },
                    {
                        "item_id": int(item_cbl["id"]),
                        "qty": Decimal("45.5000"),
                        "notes": "Potongan kabel 45.5 meter",
                    },
                ],
                ip_address="127.0.0.1",
            )
            transfer_service.approve_transfer(
                conn,
                actor=mgr_actor,
                transfer_id=int(trf2["id"]),
                ip_address="127.0.0.1",
            )
            transfer_service.ship_transfer(
                conn,
                actor=stf_actor,
                transfer_id=int(trf2["id"]),
                ip_address="127.0.0.1",
            )

            # ----------------------------------------------------------------
            # Stock Transfer #3: Jakarta -> Bandung berstatus APPROVED (siap di-klik "Ship" saat demo)
            # ----------------------------------------------------------------
            trf3 = transfer_service.create_stock_transfer(
                conn,
                actor=stf_actor,
                source_warehouse_id=int(wh_jkt["id"]),
                source_location_id=int(loc_jkt_b1["id"]),
                destination_warehouse_id=int(wh_bdg["id"]),
                destination_location_id=int(loc_bdg_stg["id"]),
                notes="[SIAP SHIP SAAT DEMO] Alokasi karton box ke Gudang Transit Bandung",
                lines=[
                    {
                        "item_id": int(item_box["id"]),
                        "qty": Decimal("15.0000"),
                        "notes": "Karton box transit Bandung",
                    },
                ],
                ip_address="127.0.0.1",
            )
            transfer_service.approve_transfer(
                conn,
                actor=mgr_actor,
                transfer_id=int(trf3["id"]),
                ip_address="127.0.0.1",
            )

        # 6c. Skenario Stock Opname (dijalankan bila belum ada Opname)
        existing_opns, existing_opn_total = opname_repo.list_opnames(
            conn,
            limit=5,
            offset=0,
            scoped_warehouse_ids=None,
            warehouse_id=None,
            location_id=None,
            status=None,
            date_from=None,
            date_to=None,
            search=None,
            order_by_sql="so.id ASC",
        )
        if existing_opn_total == 0:
            # ----------------------------------------------------------------
            # Stock Opname #1: Gudang Jakarta Rak A1 -> COMPLETED (menghasilkan ADJUSTMENT_PLUS & ADJUSTMENT_MINUS)
            # ----------------------------------------------------------------
            opn1 = opname_service.create_stock_opname(
                conn,
                actor=mgr_actor,
                warehouse_id=int(wh_jkt["id"]),
                location_id=int(loc_jkt_a1["id"]),
                notes="Audit fisik bulanan Rak A1 Gudang Pusat Jakarta (Selesai & Disetujui)",
                ip_address="127.0.0.1",
            )
            opn1 = opname_service.start_stock_opname(
                conn,
                actor=mgr_actor,
                opname_id=int(opn1["id"]),
                ip_address="127.0.0.1",
            )
            count_payload_1: list[dict[str, Any]] = []
            for ln in opn1["lines"]:
                iid = int(ln["item_id"])
                if iid == int(item_mcu["id"]):
                    count_payload_1.append(
                        {
                            "line_id": int(ln["id"]),
                            "qty_physical": Decimal("152.0000"),
                            "notes": "Ditemukan 2 unit tambahan dari sampel QC yang belum tercatat",
                        }
                    )
                elif iid == int(item_psu["id"]):
                    count_payload_1.append(
                        {
                            "line_id": int(ln["id"]),
                            "qty_physical": Decimal("59.0000"),
                            "notes": "1 unit PSU ditemukan pecah casing di sudut rak",
                        }
                    )
                else:
                    count_payload_1.append(
                        {
                            "line_id": int(ln["id"]),
                            "qty_physical": Decimal(str(ln["qty_system"])),
                            "notes": "Jumlah fisik sesuai sistem",
                        }
                    )
            opname_service.record_opname_counts(
                conn,
                actor=stf_actor,
                opname_id=int(opn1["id"]),
                lines=count_payload_1,
                ip_address="127.0.0.1",
            )
            opname_service.submit_stock_opname(
                conn,
                actor=stf_actor,
                opname_id=int(opn1["id"]),
                ip_address="127.0.0.1",
            )
            opname_service.approve_stock_opname(
                conn,
                actor=mgr_actor,
                opname_id=int(opn1["id"]),
                ip_address="127.0.0.1",
            )

            # ----------------------------------------------------------------
            # Stock Opname #2: Gudang Bandung Rak A1 -> WAITING_APPROVAL
            # Membekukan lokasi BDG-RAK-A1 (LOCATION_FROZEN) & siap di-klik "Approve" saat live demo!
            # ----------------------------------------------------------------
            opn2 = opname_service.create_stock_opname(
                conn,
                actor=mgr_actor,
                warehouse_id=int(wh_bdg["id"]),
                location_id=int(loc_bdg_a1["id"]),
                notes="[SIAP APPROVE SAAT DEMO] Temuan stok fisik awal pada Rak Transit A1 Bandung",
                ip_address="127.0.0.1",
            )
            opname_service.start_stock_opname(
                conn,
                actor=mgr_actor,
                opname_id=int(opn2["id"]),
                ip_address="127.0.0.1",
            )
            opname_service.record_opname_counts(
                conn,
                actor=mgr_actor,
                opname_id=int(opn2["id"]),
                lines=[
                    {
                        "location_id": int(loc_bdg_a1["id"]),
                        "item_id": int(item_box["id"]),
                        "qty_physical": Decimal("25.0000"),
                        "notes": "Stok fisik karton box eksisting di Rak Transit Bandung",
                    },
                    {
                        "location_id": int(loc_bdg_a1["id"]),
                        "item_id": int(item_mcu["id"]),
                        "qty_physical": Decimal("10.0000"),
                        "notes": "Cadangan modul kontroler di Bandung",
                    },
                ],
                ip_address="127.0.0.1",
            )
            opname_service.submit_stock_opname(
                conn,
                actor=mgr_actor,
                opname_id=int(opn2["id"]),
                ip_address="127.0.0.1",
            )

        # Ringkasan akhir isi database melalui fungsi service resmi
        summary = {
            "users": user_service.list_users(conn)["total"],
            "warehouses": warehouse_service.list_warehouses(conn, actor=superadmin_actor)["total"],
            "storage_locations": warehouse_service.list_locations(conn, actor=superadmin_actor)["total"],
            "categories_active": master_service.list_categories(conn, is_active=True)["total"],
            "uoms": master_service.list_uoms(conn)["total"],
            "suppliers": master_service.list_suppliers(conn)["total"],
            "items": master_service.list_items(conn)["total"],
            "purchase_orders": po_service.list_purchase_orders(conn, actor=superadmin_actor)["total"],
            "goods_receipts": gr_service.list_goods_receipts(conn, actor=superadmin_actor)["total"],
            "stock_transfers": transfer_service.list_stock_transfers(conn, actor=superadmin_actor)["total"],
            "stock_opnames": opname_service.list_stock_opnames(conn, actor=superadmin_actor)["total"],
            "stock_by_location": stock_service.list_stock_by_location(conn, actor=superadmin_actor)["total"],
            "stock_movements": stock_service.list_stock_movements(conn, actor=superadmin_actor)["total"],
            "audit_logs": audit_service.list_audit_logs(conn)["total"],
        }
        return summary


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Seed data demo lengkap Fase 1 (M0-M8) untuk presentasi aplikasi WMS."
    )
    parser.add_argument(
        "--password",
        help="Kata sandi seragam untuk seluruh akun demo (minimal 8 karakter). Bisa juga lewat env DEMO_PASSWORD.",
        default=os.environ.get("DEMO_PASSWORD"),
    )
    args = parser.parse_args()

    password = args.password
    if not password:
        password = getpass.getpass(
            "Masukkan kata sandi untuk seluruh akun demo (minimal 8 karakter): "
        )

    try:
        summary = seed_demo_data(password=password)
    except Exception as exc:
        print(f"[seed_demo_data] Gagal menyiapkan data demo: {exc}", file=sys.stderr)
        return 1

    print("[seed_demo_data] Data demo Fase 1 berhasil disiapkan:")
    for table_name, count in summary.items():
        print(f"  - {table_name:20s}: {count}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
