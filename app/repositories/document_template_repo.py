"""Repository SQL untuk tabel `document_templates` (Tahap 17 / Poin 10)."""

from typing import Any

from psycopg import Connection
from psycopg.types.json import Jsonb

TEMPLATE_COLUMNS = """
    id,
    document_type,
    document_title,
    company_name,
    company_address,
    company_contact,
    logo_url,
    logo_position,
    logo_size,
    header_notes,
    footer_notes,
    paper_size,
    orientation,
    margin_mm,
    show_barcode,
    show_line_notes,
    show_company_contact,
    section_order,
    table_columns,
    signature_layout,
    updated_by,
    created_at,
    updated_at
"""


def list_templates(conn: Connection[dict[str, Any]]) -> list[dict[str, Any]]:
    """Mengambil seluruh template dokumen terurut konsisten."""
    rows = conn.execute(
        f"""
        SELECT {TEMPLATE_COLUMNS}
        FROM document_templates
        ORDER BY
            CASE document_type
                WHEN 'GOODS_RECEIPT' THEN 1
                WHEN 'STOCK_TRANSFER' THEN 2
                WHEN 'PURCHASE_ORDER' THEN 3
                ELSE 99
            END,
            id ASC
        """
    ).fetchall()
    return list(rows)


def get_template_by_type(
    conn: Connection[dict[str, Any]],
    document_type: str,
) -> dict[str, Any] | None:
    """Mengambil satu konfigurasi template berdasarkan jenis dokumen."""
    return conn.execute(
        f"""
        SELECT {TEMPLATE_COLUMNS}
        FROM document_templates
        WHERE document_type = %s
        """,
        (document_type,),
    ).fetchone()


def upsert_template(
    conn: Connection[dict[str, Any]],
    *,
    document_type: str,
    data: dict[str, Any],
    updated_by: int | None,
) -> dict[str, Any]:
    """Menyimpan atau memperbarui konfigurasi template dokumen secara modular."""
    row = conn.execute(
        f"""
        INSERT INTO document_templates (
            document_type,
            document_title,
            company_name,
            company_address,
            company_contact,
            logo_url,
            logo_position,
            logo_size,
            header_notes,
            footer_notes,
            paper_size,
            orientation,
            margin_mm,
            show_barcode,
            show_line_notes,
            show_company_contact,
            section_order,
            table_columns,
            signature_layout,
            updated_by
        )
        VALUES (
            %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
            %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
        )
        ON CONFLICT (document_type) DO UPDATE SET
            document_title = EXCLUDED.document_title,
            company_name = EXCLUDED.company_name,
            company_address = EXCLUDED.company_address,
            company_contact = EXCLUDED.company_contact,
            logo_url = EXCLUDED.logo_url,
            logo_position = EXCLUDED.logo_position,
            logo_size = EXCLUDED.logo_size,
            header_notes = EXCLUDED.header_notes,
            footer_notes = EXCLUDED.footer_notes,
            paper_size = EXCLUDED.paper_size,
            orientation = EXCLUDED.orientation,
            margin_mm = EXCLUDED.margin_mm,
            show_barcode = EXCLUDED.show_barcode,
            show_line_notes = EXCLUDED.show_line_notes,
            show_company_contact = EXCLUDED.show_company_contact,
            section_order = EXCLUDED.section_order,
            table_columns = EXCLUDED.table_columns,
            signature_layout = EXCLUDED.signature_layout,
            updated_by = EXCLUDED.updated_by,
            updated_at = CURRENT_TIMESTAMP
        RETURNING {TEMPLATE_COLUMNS}
        """,
        (
            document_type,
            data["document_title"],
            data["company_name"],
            data.get("company_address"),
            data.get("company_contact"),
            data.get("logo_url"),
            data["logo_position"],
            data["logo_size"],
            data.get("header_notes"),
            data.get("footer_notes"),
            data["paper_size"],
            data["orientation"],
            data["margin_mm"],
            data["show_barcode"],
            data["show_line_notes"],
            data["show_company_contact"],
            Jsonb(data["section_order"]),
            Jsonb(data["table_columns"]),
            Jsonb(data["signature_layout"]),
            updated_by,
        ),
    ).fetchone()
    assert row is not None
    return row


def is_logo_referenced_elsewhere(
    conn: Connection[dict[str, Any]],
    logo_url: str,
) -> bool:
    """Memeriksa apakah file logo masih dipakai oleh template dokumen mana pun."""
    row = conn.execute(
        """
        SELECT 1
        FROM document_templates
        WHERE logo_url = %s
        LIMIT 1
        """,
        (logo_url,),
    ).fetchone()
    return row is not None
