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

from app.repositories import master_repo
from app.services import master_service
from tests import factories

HEADERS = [
    "code",
    "name",
    "contact_person",
    "phone",
    "email",
    "address",
    "is_active",
]
XLSX_MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def make_workbook(
    rows: list[tuple[Any, ...]],
    *,
    headers: list[str] | None = None,
    sheet_name: str = "Suppliers",
) -> bytes:
    workbook = Workbook()
    worksheet = workbook.active
    assert worksheet is not None
    worksheet.title = sheet_name
    worksheet.append(headers or HEADERS)
    for row in rows:
        worksheet.append(list(row))
    output = BytesIO()
    workbook.save(output)
    workbook.close()
    return output.getvalue()


def upload(
    client: TestClient,
    content: bytes,
    headers: dict[str, str],
    *,
    filename: str = "suppliers.xlsx",
):
    return client.post(
        "/api/v1/suppliers/import",
        headers=headers,
        files={"file": (filename, content, XLSX_MIME)},
    )


def test_ac31_template_contract_and_permission(client, purchasing_user, staff_user):
    response = client.get(
        "/api/v1/suppliers/import-template",
        headers=purchasing_user["auth_headers"],
    )
    assert response.status_code == 200
    assert response.headers["content-type"] == XLSX_MIME
    assert "template_import_supplier.xlsx" in response.headers["content-disposition"]

    workbook = load_workbook(BytesIO(response.content))
    assert workbook.sheetnames == ["Suppliers"]
    assert list(workbook["Suppliers"].values)[0] == tuple(HEADERS)
    assert workbook["Suppliers"]["A2"].number_format == "@"
    assert len(workbook["Suppliers"].data_validations.dataValidation) == 1
    workbook.close()

    no_manage = upload(client, make_workbook([]), staff_user["auth_headers"])
    assert no_manage.status_code == 403
    assert no_manage.json()["error"]["code"] == "PERMISSION_DENIED"


def test_ac31_partial_import_validates_and_audits_rows(
    client, db_conn, purchasing_user
):
    content = make_workbook(
        [
            (
                "SUP-001",
                "Pemasok Satu",
                "Budi",
                "+62 812-3456",
                "SALES@EXAMPLE.COM",
                "Jl. Gudang 1",
                "active",
            ),
            ("sup-001", "Kode Duplikat", None, None, None, None, True),
            (None, None, None, None, None, None, None),
            ("SUP-002", "Email salah", None, "123", "email-salah", None, True),
            ("SUP-003", "Pemasok Nonaktif", None, None, None, None, "inactive"),
        ]
    )

    response = upload(client, content, purchasing_user["auth_headers"])
    assert response.status_code == 200
    result = response.json()
    assert result["total_rows"] == 4
    assert result["imported_count"] == 1
    assert result["failed_count"] == 3
    assert {error["row"] for error in result["errors"]} == {2, 3, 5}
    assert any(error["field"] == "code" and error["code"] == "DUPLICATE" for error in result["errors"])
    assert any(error["field"] == "email" for error in result["errors"])
    assert any(error["field"] == "phone" for error in result["errors"])

    rows = db_conn.execute(
        "SELECT code, email, is_active FROM suppliers ORDER BY code"
    ).fetchall()
    assert rows == [
        {"code": "SUP-003", "email": None, "is_active": False},
    ]
    audit_count = db_conn.execute(
        "SELECT COUNT(*) AS total FROM audit_logs WHERE action = 'SUPPLIER_CREATED'"
    ).fetchone()["total"]
    assert audit_count == 1


def test_ac31_existing_duplicate_is_reported_without_insert(
    client, db_conn, purchasing_user
):
    factories.create_supplier(db_conn, code="SUP-EXIST", name="Sudah Ada")

    response = upload(
        client,
        make_workbook(
            [("sup-exist", "Duplikat", None, None, None, None, True)]
        ),
        purchasing_user["auth_headers"],
    )

    assert response.status_code == 200
    result = response.json()
    assert result["imported_count"] == 0
    assert result["failed_count"] == 1
    assert result["errors"][0]["field"] == "code"
    assert result["errors"][0]["code"] == "DUPLICATE"
    assert db_conn.execute("SELECT COUNT(*) AS total FROM suppliers").fetchone()["total"] == 1


def test_ac31_rejects_invalid_workbooks_and_limits_without_writes(
    client, db_conn, purchasing_user
):
    invalid = upload(client, b"not an xlsx", purchasing_user["auth_headers"])
    assert invalid.status_code == 422
    assert invalid.json()["error"]["code"] == "VALIDATION_ERROR"

    wrong_extension = upload(
        client,
        make_workbook([]),
        purchasing_user["auth_headers"],
        filename="suppliers.csv",
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
        make_workbook([], sheet_name="Pemasok"),
        purchasing_user["auth_headers"],
    )
    assert wrong_sheet.status_code == 422
    assert wrong_sheet.json()["error"]["code"] == "VALIDATION_ERROR"

    oversized = upload(
        client,
        b"0" * (master_service.SUPPLIER_IMPORT_MAX_BYTES + 1),
        purchasing_user["auth_headers"],
    )
    assert oversized.status_code == 422
    assert oversized.json()["error"]["code"] == "VALIDATION_ERROR"

    too_many_rows = upload(
        client,
        make_workbook(
            [
                (f"SUP-{i:04}", f"Supplier {i}", None, None, None, None, True)
                for i in range(1, 1002)
            ]
        ),
        purchasing_user["auth_headers"],
    )
    assert too_many_rows.status_code == 422
    assert too_many_rows.json()["error"]["code"] == "VALIDATION_ERROR"
    assert db_conn.execute("SELECT COUNT(*) AS total FROM suppliers").fetchone()["total"] == 0


def test_ac31_concurrent_same_code_import_only_creates_one(
    setup_test_database, db_conn, purchasing_user, monkeypatch
):
    content = make_workbook(
        [("RACE-SUP-01", "Pemasok Konkuren", None, None, None, None, True)]
    )
    original_lookup = master_repo.list_existing_supplier_code_keys
    barrier = Barrier(2)

    def synchronized_lookup(conn, code_keys):
        found = original_lookup(conn, code_keys)
        if "race-sup-01" in code_keys:
            barrier.wait(timeout=10)
        return found

    monkeypatch.setattr(
        master_repo, "list_existing_supplier_code_keys", synchronized_lookup
    )

    def run_import():
        with psycopg.connect(
            setup_test_database, autocommit=True, row_factory=dict_row
        ) as conn:
            return master_service.import_suppliers_from_excel(
                conn,
                file_name="suppliers.xlsx",
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
    assert db_conn.execute("SELECT COUNT(*) AS total FROM suppliers").fetchone()["total"] == 1
    assert db_conn.execute(
        "SELECT COUNT(*) AS total FROM audit_logs WHERE action = 'SUPPLIER_CREATED'"
    ).fetchone()["total"] == 1


def test_ac31_infrastructure_failure_rolls_back_supplier_and_audit(
    setup_test_database, db_conn, purchasing_user, monkeypatch
):
    def fail_audit(*args, **kwargs):
        raise RuntimeError("forced audit insertion failure")

    monkeypatch.setattr(master_service.audit_service, "record_many", fail_audit)
    with psycopg.connect(
        setup_test_database, autocommit=True, row_factory=dict_row
    ) as conn:
        with pytest.raises(RuntimeError, match="forced audit insertion failure"):
            master_service.import_suppliers_from_excel(
                conn,
                file_name="suppliers.xlsx",
                file_bytes=make_workbook(
                    [("ROLLBACK-SUP", "Rollback", None, None, None, None, True)]
                ),
                actor=purchasing_user,
            )
    assert db_conn.execute("SELECT COUNT(*) AS total FROM suppliers").fetchone()["total"] == 0
    assert db_conn.execute(
        "SELECT COUNT(*) AS total FROM audit_logs WHERE action = 'SUPPLIER_CREATED'"
    ).fetchone()["total"] == 0
