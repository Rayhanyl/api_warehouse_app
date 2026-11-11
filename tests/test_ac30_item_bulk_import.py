from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from io import BytesIO
from threading import Barrier
from typing import Any

import psycopg
import pytest
from fastapi.testclient import TestClient
from openpyxl import Workbook, load_workbook
from psycopg.rows import dict_row

from app.main import app
from app.repositories import master_repo
from app.services import master_service
from tests import factories

HEADERS = [
    "sku",
    "barcode",
    "name",
    "description",
    "category_name",
    "uom_name",
    "is_active",
]
REFERENCE_HEADERS = ["category_name", "uom_name", "uom_code"]
XLSX_MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def make_workbook(
    rows: list[tuple[Any, ...]],
    *,
    headers: list[str] | None = None,
    sheet_name: str = "Items",
) -> bytes:
    workbook = Workbook()
    worksheet = workbook.active
    assert worksheet is not None
    worksheet.title = sheet_name
    worksheet.append(headers or HEADERS)
    for row in rows:
        worksheet.append(list(row))
    reference_sheet = workbook.create_sheet("Referensi")
    reference_sheet.append(REFERENCE_HEADERS)
    reference_sheet.append(["Kategori Referensi", "Unit Referensi", "REF"])
    output = BytesIO()
    workbook.save(output)
    workbook.close()
    return output.getvalue()


def upload(
    client: TestClient,
    content: bytes,
    headers: dict[str, str],
    *,
    filename: str = "items.xlsx",
):
    return client.post(
        "/api/v1/items/import",
        headers=headers,
        files={"file": (filename, content, XLSX_MIME)},
    )


def test_ac30_template_contract_and_permission(
    client, db_conn, purchasing_user, staff_user
):
    category = factories.create_category(db_conn, name="Kategori Template")
    uom = factories.create_uom(db_conn, code="TMP", name="Unit Template")
    factories.create_category(
        db_conn, name="Kategori Nonaktif Template", is_active=False
    )
    factories.create_uom(
        db_conn, code="INACTIVE-TMP", name="Unit Nonaktif Template", is_active=False
    )
    response = client.get(
        "/api/v1/items/import-template", headers=purchasing_user["auth_headers"]
    )
    assert response.status_code == 200
    assert response.headers["content-type"] == XLSX_MIME
    assert "template_import_barang.xlsx" in response.headers["content-disposition"]

    workbook = load_workbook(BytesIO(response.content))
    assert workbook.sheetnames == ["Items", "Referensi"]
    assert list(workbook["Items"].values)[0] == tuple(HEADERS)
    assert workbook["Items"]["A2"].number_format == "@"
    assert workbook["Items"]["B2"].number_format == "@"
    assert workbook["Referensi"].cell(2, 1).value == category["name"]
    assert workbook["Referensi"].cell(2, 2).value == uom["name"]
    assert workbook["Referensi"].cell(2, 3).value == uom["code"]
    assert "Kategori Nonaktif Template" not in [
        row[0] for row in workbook["Referensi"].iter_rows(min_row=2, values_only=True)
    ]
    assert "Unit Nonaktif Template" not in [
        row[1] for row in workbook["Referensi"].iter_rows(min_row=2, values_only=True)
    ]
    assert len(workbook["Items"].data_validations.dataValidation) == 3
    assert "ActiveCategories" in workbook.defined_names
    assert "ActiveUomNames" in workbook.defined_names
    workbook.close()

    no_manage = upload(client, make_workbook([]), staff_user["auth_headers"])
    assert no_manage.status_code == 403
    assert no_manage.json()["error"]["code"] == "PERMISSION_DENIED"


def test_ac30_partial_import_validation_duplicates_and_audit(
    client, db_conn, purchasing_user
):
    category = factories.create_category(db_conn, name="Kategori Impor")
    uom = factories.create_uom(db_conn, code="IMP", name="Unit Impor")
    workbook = make_workbook(
        [
            ("ITEM-01", "8991002101012", "Barang pertama", None, "kategori impor", "unit impor", "active"),
            ("item-01", None, "SKU duplikat", None, "Kategori Impor", "Unit Impor", True),
            (None, None, None, None, None, None, None),
            ("ITEM-02", "8991002101029", "Barang kedua", "Catatan", "Kategori Impor", "Unit Impor", "inactive"),
            ("ITEM-03", None, "", None, "Tidak ada", "None", "yes"),
        ]
    )

    response = upload(client, workbook, purchasing_user["auth_headers"])
    assert response.status_code == 200
    result = response.json()
    assert result["total_rows"] == 4
    assert result["imported_count"] == 1
    assert result["failed_count"] == 3
    assert {error["row"] for error in result["errors"]} == {2, 3, 6}
    assert any(error["code"] == "DUPLICATE" for error in result["errors"])
    assert any(error["field"] == "name" for error in result["errors"])
    assert any(error["code"] == "NOT_FOUND" for error in result["errors"])
    assert any(error["field"] == "is_active" for error in result["errors"])

    created = db_conn.execute(
        "SELECT sku, barcode, category_id, uom_id, is_active FROM items"
    ).fetchall()
    assert created == [
        {
            "sku": "ITEM-02",
            "barcode": "8991002101029",
            "category_id": category["id"],
            "uom_id": uom["id"],
            "is_active": False,
        }
    ]
    audit_count = db_conn.execute(
        "SELECT COUNT(*) AS total FROM audit_logs WHERE action = 'ITEM_CREATED'"
    ).fetchone()["total"]
    assert audit_count == 1


def test_ac30_existing_duplicate_and_inactive_references_are_row_errors(
    client, db_conn, purchasing_user
):
    active_category = factories.create_category(db_conn, name="Kategori Aktif")
    active_uom = factories.create_uom(db_conn, code="AKT", name="Aktif")
    inactive_category = factories.create_category(
        db_conn, name="Kategori Nonaktif", is_active=False
    )
    inactive_uom = factories.create_uom(
        db_conn, code="NON", name="Nonaktif", is_active=False
    )
    factories.create_item(
        db_conn,
        sku="DB-ITEM-01",
        barcode="8990001112223",
        name="Item Existing",
        category_id=active_category["id"],
        uom_id=active_uom["id"],
    )

    response = upload(
        client,
        make_workbook(
            [
                ("db-item-01", None, "SKU sudah ada", None, "Kategori Aktif", "Aktif", True),
                (
                    "ITEM-BARCODE-DUP",
                    "8990001112223",
                    "Barcode sudah ada",
                    None,
                    "Kategori Aktif",
                    "Aktif",
                    True,
                ),
                (
                    "ITEM-INACTIVE",
                    None,
                    "Referensi nonaktif",
                    None,
                    "Kategori Nonaktif",
                    "Nonaktif",
                    True,
                ),
            ]
        ),
        purchasing_user["auth_headers"],
    )
    assert response.status_code == 200
    result = response.json()
    assert result["imported_count"] == 0
    assert result["failed_count"] == 3
    assert sum(error["code"] == "DUPLICATE" for error in result["errors"]) == 2
    assert any(error["field"] == "barcode" and error["code"] == "DUPLICATE" for error in result["errors"])
    assert sum(error["code"] == "INACTIVE_REFERENCE" for error in result["errors"]) == 2
    assert db_conn.execute("SELECT COUNT(*) AS total FROM items").fetchone()["total"] == 1


def test_ac30_rejects_invalid_workbook_and_limits_without_writes(
    client, db_conn, purchasing_user
):
    invalid = upload(client, b"not an xlsx", purchasing_user["auth_headers"])
    assert invalid.status_code == 422
    assert invalid.json()["error"]["code"] == "VALIDATION_ERROR"

    wrong_extension = upload(
        client,
        make_workbook([]),
        purchasing_user["auth_headers"],
        filename="items.csv",
    )
    assert wrong_extension.status_code == 422
    assert wrong_extension.json()["error"]["code"] == "VALIDATION_ERROR"

    wrong_header = upload(
        client,
        make_workbook([], headers=HEADERS[:-1] + ["active"]),
        purchasing_user["auth_headers"],
    )
    assert wrong_header.status_code == 422
    assert wrong_header.json()["error"]["code"] == "VALIDATION_ERROR"

    wrong_sheet = upload(
        client,
        make_workbook([], sheet_name="Barang"),
        purchasing_user["auth_headers"],
    )
    assert wrong_sheet.status_code == 422
    assert wrong_sheet.json()["error"]["code"] == "VALIDATION_ERROR"

    oversized = upload(
        client,
        b"0" * (master_service.ITEM_IMPORT_MAX_BYTES + 1),
        purchasing_user["auth_headers"],
    )
    assert oversized.status_code == 422
    assert oversized.json()["error"]["code"] == "VALIDATION_ERROR"

    too_many_rows = upload(
        client,
        make_workbook(
            [
                (f"ITEM-{i:04}", None, f"Barang {i}", None, "X", "Y", True)
                for i in range(1, 1002)
            ]
        ),
        purchasing_user["auth_headers"],
    )
    assert too_many_rows.status_code == 422
    assert too_many_rows.json()["error"]["code"] == "VALIDATION_ERROR"
    assert db_conn.execute("SELECT COUNT(*) AS total FROM items").fetchone()["total"] == 0


def test_ac30_ambiguous_uom_name_is_reported_without_insert(
    client, db_conn, purchasing_user
):
    factories.create_category(db_conn, name="Kategori Unit Ambigu")
    factories.create_uom(db_conn, code="PCS", name="Unit Ambigu")
    factories.create_uom(db_conn, code="PKT", name="Unit Ambigu")

    response = upload(
        client,
        make_workbook(
            [("AMBIGUOUS-ITEM", None, "Barang ambigu", None, "Kategori Unit Ambigu", "Unit Ambigu", True)]
        ),
        purchasing_user["auth_headers"],
    )

    assert response.status_code == 200
    result = response.json()
    assert result["imported_count"] == 0
    assert result["failed_count"] == 1
    assert result["errors"] == [
        {
            "row": 2,
            "field": "uom_name",
            "code": "VALIDATION_ERROR",
            "message": "Nama satuan ambigu; kode yang cocok: PCS, PKT.",
        }
    ]
    assert db_conn.execute("SELECT COUNT(*) AS total FROM items").fetchone()["total"] == 0


def test_ac30_concurrent_same_sku_import_only_creates_one(
    setup_test_database, db_conn, purchasing_user, monkeypatch
):
    category = factories.create_category(db_conn, name="Kategori Concurrent")
    uom = factories.create_uom(db_conn, code="CON", name="Concurrent")
    content = make_workbook(
        [("RACE-ITEM-01", None, "Barang Konkuren", None, "Kategori Concurrent", "Concurrent", True)]
    )
    original_lookup = master_repo.list_existing_item_sku_keys
    barrier = Barrier(2)

    def synchronized_lookup(conn, sku_keys):
        found = original_lookup(conn, sku_keys)
        if "race-item-01" in sku_keys:
            barrier.wait(timeout=10)
        return found

    monkeypatch.setattr(master_repo, "list_existing_item_sku_keys", synchronized_lookup)

    def run_import():
        with psycopg.connect(
            setup_test_database, autocommit=True, row_factory=dict_row
        ) as conn:
            return master_service.import_items_from_excel(
                conn,
                file_name="items.xlsx",
                file_bytes=content,
                actor=purchasing_user,
            )

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: run_import(), range(2)))

    assert sorted(result["imported_count"] for result in results) == [0, 1]
    assert sorted(result["failed_count"] for result in results) == [0, 1]
    assert sum(
        error["code"] == "DUPLICATE"
        for result in results
        for error in result["errors"]
    ) == 1
    assert db_conn.execute("SELECT COUNT(*) AS total FROM items").fetchone()["total"] == 1
    assert db_conn.execute(
        "SELECT COUNT(*) AS total FROM audit_logs WHERE action = 'ITEM_CREATED'"
    ).fetchone()["total"] == 1
    assert category["id"] and uom["id"]


def test_ac30_infrastructure_failure_rolls_back_item_and_audit(
    setup_test_database, db_conn, purchasing_user, monkeypatch
):
    category = factories.create_category(db_conn, name="Kategori Rollback")
    uom = factories.create_uom(db_conn, code="ROLL", name="Rollback")

    def fail_audit(*args, **kwargs):
        raise RuntimeError("forced audit insertion failure")

    monkeypatch.setattr(master_service.audit_service, "record_many", fail_audit)
    with psycopg.connect(
        setup_test_database, autocommit=True, row_factory=dict_row
    ) as conn:
        with pytest.raises(RuntimeError, match="forced audit insertion failure"):
            master_service.import_items_from_excel(
                conn,
                file_name="items.xlsx",
                file_bytes=make_workbook(
                    [
                        (
                            "ROLLBACK-01",
                            None,
                            "Barang rollback",
                            None,
                            "Kategori Rollback",
                            "Rollback",
                            True,
                        )
                    ]
                ),
                actor=purchasing_user,
            )
    assert db_conn.execute(
        "SELECT COUNT(*) AS total FROM items WHERE category_id = %s AND uom_id = %s",
        (category["id"], uom["id"]),
    ).fetchone()["total"] == 0
    assert db_conn.execute(
        "SELECT COUNT(*) AS total FROM audit_logs WHERE action = 'ITEM_CREATED'"
    ).fetchone()["total"] == 0
