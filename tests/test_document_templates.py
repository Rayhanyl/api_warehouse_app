"""Pengujian template dokumen cetak modular & unggah logo aman (Tahap 17 / Poin 10)."""

from collections.abc import Generator
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient
import psycopg
import pytest

from app.core.config import settings

# PNG 1x1 valid minimal
_VALID_PNG_BYTES = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
    b"\x08\x06\x00\x00\x00\x1f\x15c4\x00\x00\x00\rIDATx\x9cc`\x00\x00\x00"
    b"\x02\x00\x01H\xaf\xa4q\x00\x00\x00\x00IEND\xaeB`\x82"
)


@pytest.fixture(autouse=True)
def _restore_document_templates(
    db_conn: psycopg.Connection[dict[str, Any]],
) -> Generator[None, None, None]:
    snapshot = db_conn.execute(
        """
        SELECT document_type, document_title, company_name, company_address,
               company_contact, logo_url, logo_position, logo_size,
               header_notes, footer_notes, paper_size, orientation, margin_mm,
               show_barcode, show_line_notes, show_company_contact,
               section_order, table_columns, signature_layout
        FROM document_templates
        """
    ).fetchall()
    yield
    from psycopg.types.json import Jsonb

    for row in snapshot:
        db_conn.execute(
            """
            UPDATE document_templates SET
                document_title = %s,
                company_name = %s,
                company_address = %s,
                company_contact = %s,
                logo_url = %s,
                logo_position = %s,
                logo_size = %s,
                header_notes = %s,
                footer_notes = %s,
                paper_size = %s,
                orientation = %s,
                margin_mm = %s,
                show_barcode = %s,
                show_line_notes = %s,
                show_company_contact = %s,
                section_order = %s,
                table_columns = %s,
                signature_layout = %s,
                updated_by = NULL
            WHERE document_type = %s
            """,
            (
                row["document_title"],
                row["company_name"],
                row["company_address"],
                row["company_contact"],
                row["logo_url"],
                row["logo_position"],
                row["logo_size"],
                row["header_notes"],
                row["footer_notes"],
                row["paper_size"],
                row["orientation"],
                row["margin_mm"],
                row["show_barcode"],
                row["show_line_notes"],
                row["show_company_contact"],
                Jsonb(row["section_order"]),
                Jsonb(row["table_columns"]),
                Jsonb(row["signature_layout"]),
                row["document_type"],
            ),
        )


def test_tahap17_list_and_get_document_templates_and_rbac(
    client: TestClient,
    superadmin_user: dict[str, Any],
    staff_user: dict[str, Any],
) -> None:
    unauth = client.get("/api/v1/document-templates")
    assert unauth.status_code == 401

    staff_list = client.get(
        "/api/v1/document-templates",
        headers=staff_user["auth_headers"],
    )
    assert staff_list.status_code == 200
    types = [item["document_type"] for item in staff_list.json()]
    assert types == ["GOODS_RECEIPT", "STOCK_TRANSFER", "PURCHASE_ORDER"]

    po_tpl = client.get(
        "/api/v1/document-templates/purchase_order",
        headers=staff_user["auth_headers"],
    )
    assert po_tpl.status_code == 200
    assert po_tpl.json()["document_type"] == "PURCHASE_ORDER"

    invalid_type = client.get(
        "/api/v1/document-templates/INVOICE",
        headers=superadmin_user["auth_headers"],
    )
    assert invalid_type.status_code == 422

    # Non-admin ditolak untuk update & upload logo
    forbidden_put = client.put(
        "/api/v1/document-templates/GOODS_RECEIPT",
        headers=staff_user["auth_headers"],
        json=po_tpl.json(),
    )
    assert forbidden_put.status_code == 403
    assert forbidden_put.json()["error"]["code"] == "PERMISSION_DENIED"


def test_tahap17_upload_logo_validation_serving_and_cleanup(
    client: TestClient,
    superadmin_user: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(settings, "upload_dir", str(tmp_path))

    # Tolak file SVG (potensi XSS) dan file kosong
    bad_svg = client.post(
        "/api/v1/document-templates/upload-logo",
        headers=superadmin_user["auth_headers"],
        files={"file": ("evil.svg", b"<svg onload=alert(1)></svg>", "image/svg+xml")},
    )
    assert bad_svg.status_code == 422

    empty_file = client.post(
        "/api/v1/document-templates/upload-logo",
        headers=superadmin_user["auth_headers"],
        files={"file": ("empty.png", b"", "image/png")},
    )
    assert empty_file.status_code == 422

    # Upload PNG sah
    uploaded = client.post(
        "/api/v1/document-templates/upload-logo",
        headers=superadmin_user["auth_headers"],
        files={"file": ("company-logo.png", _VALID_PNG_BYTES, "image/png")},
    )
    assert uploaded.status_code == 200, uploaded.text
    payload = uploaded.json()
    logo_url = payload["logo_url"]
    filename = payload["filename"]
    assert logo_url.startswith("/api/v1/document-templates/logos/logo-")
    assert filename.endswith(".png")
    stored_path = tmp_path / "document_logos" / filename
    assert stored_path.is_file()

    # Sajikan file logo dengan nosniff
    served = client.get(logo_url)
    assert served.status_code == 200
    assert served.headers["content-type"].startswith("image/png")
    assert served.headers["x-content-type-options"] == "nosniff"
    assert served.content == _VALID_PNG_BYTES

    # Path traversal aman ditolak
    traversal = client.get("/api/v1/document-templates/logos/../../pyproject.toml")
    assert traversal.status_code == 404

    # Pasang logo ke template GOODS_RECEIPT lalu bersihkan dengan logo_url=None -> file ikut terhapus
    current = client.get(
        "/api/v1/document-templates/GOODS_RECEIPT",
        headers=superadmin_user["auth_headers"],
    ).json()
    attach_payload = {**current, "logo_url": logo_url}
    attached = client.put(
        "/api/v1/document-templates/GOODS_RECEIPT",
        headers=superadmin_user["auth_headers"],
        json=attach_payload,
    )
    assert attached.status_code == 200
    assert attached.json()["logo_url"] == logo_url

    cleared = client.put(
        "/api/v1/document-templates/GOODS_RECEIPT",
        headers=superadmin_user["auth_headers"],
        json={**current, "logo_url": None},
    )
    assert cleared.status_code == 200
    assert not stored_path.exists()


def test_tahap17_update_modular_layout_validation_and_audit(
    client: TestClient,
    db_conn: psycopg.Connection[dict[str, Any]],
    superadmin_user: dict[str, Any],
) -> None:
    current = client.get(
        "/api/v1/document-templates/PURCHASE_ORDER",
        headers=superadmin_user["auth_headers"],
    ).json()

    # Tolak key kolom ilegal, margin di luar batas, atau semua kolom disembunyikan
    bad_column = {
        **current,
        "table_columns": [{"key": "bogus_col", "label": "Ilegal", "visible": True}],
    }
    assert (
        client.put(
            "/api/v1/document-templates/PURCHASE_ORDER",
            headers=superadmin_user["auth_headers"],
            json=bad_column,
        ).status_code
        == 422
    )

    all_hidden = {
        **current,
        "table_columns": [{**col, "visible": False} for col in current["table_columns"]],
    }
    assert (
        client.put(
            "/api/v1/document-templates/PURCHASE_ORDER",
            headers=superadmin_user["auth_headers"],
            json=all_hidden,
        ).status_code
        == 422
    )

    unsafe_logo = {**current, "logo_url": "javascript:alert(1)"}
    assert (
        client.put(
            "/api/v1/document-templates/PURCHASE_ORDER",
            headers=superadmin_user["auth_headers"],
            json=unsafe_logo,
        ).status_code
        == 422
    )

    # Update sah: ganti judul, orientasi, margin, kolom, tanda tangan 2 kolom, urutan bagian
    updated_payload = {
        "document_title": "SURAT PESANAN RESMI PT MAJU LOGISTIK",
        "company_name": "PT MAJU LOGISTIK NUSANTARA",
        "company_address": "Kawasan Industri MM2100 Blok B3, Bekasi",
        "company_contact": "Telp: (021) 8998-1122 | po@majulogistik.id",
        "logo_url": "https://cdn.example.com/logo-maju.png",
        "logo_position": "RIGHT",
        "logo_size": "LARGE",
        "header_notes": "Harap kirim sesuai jadwal.",
        "footer_notes": "PO sah tanpa tanda tangan basah bila disetujui secara elektronik.",
        "paper_size": "LETTER",
        "orientation": "LANDSCAPE",
        "margin_mm": 15.5,
        "show_barcode": False,
        "show_line_notes": False,
        "show_company_contact": True,
        "section_order": ["HEADER", "NOTES", "METADATA", "TABLE", "SIGNATURES"],
        "table_columns": [
            {"key": "no", "label": "No.", "visible": True},
            {"key": "item_name", "label": "Deskripsi Barang", "visible": True},
            {"key": "sku_barcode", "label": "SKU", "visible": True},
            {"key": "qty_ordered", "label": "Jumlah Order", "visible": True},
            {"key": "uom", "label": "Unit", "visible": True},
            {"key": "qty_received", "label": "Diterima", "visible": False},
            {"key": "notes", "label": "Catatan", "visible": False},
        ],
        "signature_layout": [
            {
                "title": "Diajukan Oleh",
                "subtitle": "Purchasing Lead",
                "placeholder": "( Tanda Tangan & Nama )",
            },
            {
                "title": "Disetujui Oleh",
                "subtitle": "Direktur Operasional",
                "placeholder": "( Tanda Tangan & Stempel )",
            },
        ],
    }

    res = client.put(
        "/api/v1/document-templates/PURCHASE_ORDER",
        headers=superadmin_user["auth_headers"],
        json=updated_payload,
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["company_name"] == "PT MAJU LOGISTIK NUSANTARA"
    assert body["logo_position"] == "RIGHT"
    assert body["paper_size"] == "LETTER"
    assert body["orientation"] == "LANDSCAPE"
    assert body["margin_mm"] == 15.5
    assert body["show_barcode"] is False
    assert body["section_order"] == ["HEADER", "NOTES", "METADATA", "TABLE", "SIGNATURES"]
    assert len(body["signature_layout"]) == 2

    # Audit log tercatat lengkap
    audit_row = db_conn.execute(
        """
        SELECT action, entity_type, entity_id, old_values, new_values
        FROM audit_logs
        WHERE entity_type = 'document_templates' AND entity_id = 'PURCHASE_ORDER'
        ORDER BY id DESC
        LIMIT 1
        """
    ).fetchone()
    assert audit_row is not None
    assert audit_row["action"] == "UPDATE"
    assert audit_row["old_values"]["paper_size"] == "A4"
    assert audit_row["new_values"]["paper_size"] == "LETTER"
