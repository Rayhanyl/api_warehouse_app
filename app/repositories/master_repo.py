"""Repository SQL untuk Master Data: categories, uoms, suppliers, dan items (FR-02, PRD 6.8)."""

from typing import Any

from psycopg import Connection


# ============================================================================
# Categories
# ============================================================================
def list_categories(
    conn: Connection[dict[str, Any]],
    *,
    limit: int,
    offset: int,
    is_active: bool | None = None,
    search: str | None = None,
    order_by_sql: str = "c.id ASC",
) -> tuple[list[dict[str, Any]], int]:
    """Mengambil daftar kategori dengan filter, pencarian, dan pagination."""
    conditions: list[str] = []
    params: list[Any] = []

    if is_active is not None:
        conditions.append("c.is_active = %s")
        params.append(is_active)

    if search:
        kw = f"%{search.strip()}%"
        conditions.append("(c.name ILIKE %s OR COALESCE(c.description, '') ILIKE %s)")
        params.extend([kw, kw])

    where_sql = f"WHERE {' AND '.join(conditions)}" if conditions else ""

    count_row = conn.execute(
        f"SELECT COUNT(*) AS total FROM categories c {where_sql}",
        tuple(params),
    ).fetchone()
    total = int(count_row["total"]) if count_row else 0

    rows = conn.execute(
        f"""
        SELECT
            c.id,
            c.name,
            c.description,
            c.is_active,
            c.created_by,
            c.created_at,
            c.updated_at
        FROM categories c
        {where_sql}
        ORDER BY {order_by_sql}
        LIMIT %s OFFSET %s
        """,
        tuple([*params, limit, offset]),
    ).fetchall()
    return list(rows), total


def get_category_by_id(
    conn: Connection[dict[str, Any]], category_id: int
) -> dict[str, Any] | None:
    return conn.execute(
        """
        SELECT id, name, description, is_active, created_by, created_at, updated_at
        FROM categories
        WHERE id = %s
        """,
        (category_id,),
    ).fetchone()


def lock_category_by_id(
    conn: Connection[dict[str, Any]], category_id: int
) -> dict[str, Any] | None:
    return conn.execute(
        """
        SELECT id, name, description, is_active, created_by, created_at, updated_at
        FROM categories
        WHERE id = %s
        FOR UPDATE
        """,
        (category_id,),
    ).fetchone()


def get_category_by_name(
    conn: Connection[dict[str, Any]], name: str
) -> dict[str, Any] | None:
    return conn.execute(
        """
        SELECT id, name, description, is_active, created_by, created_at, updated_at
        FROM categories
        WHERE LOWER(name) = LOWER(%s)
        """,
        (name,),
    ).fetchone()


def insert_category(
    conn: Connection[dict[str, Any]],
    *,
    name: str,
    description: str | None,
    is_active: bool,
    created_by: int | None,
) -> dict[str, Any]:
    row = conn.execute(
        """
        INSERT INTO categories (name, description, is_active, created_by)
        VALUES (%s, %s, %s, %s)
        RETURNING id, name, description, is_active, created_by, created_at, updated_at
        """,
        (name, description, is_active, created_by),
    ).fetchone()
    assert row is not None
    return row


def update_category(
    conn: Connection[dict[str, Any]],
    category_id: int,
    *,
    name: str,
    description: str | None,
    is_active: bool,
) -> dict[str, Any]:
    row = conn.execute(
        """
        UPDATE categories
        SET
            name = %s,
            description = %s,
            is_active = %s,
            updated_at = CURRENT_TIMESTAMP
        WHERE id = %s
        RETURNING id, name, description, is_active, created_by, created_at, updated_at
        """,
        (name, description, is_active, category_id),
    ).fetchone()
    assert row is not None
    return row


def is_category_in_use(
    conn: Connection[dict[str, Any]], category_id: int
) -> bool:
    """Memeriksa apakah kategori masih dipakai oleh barang yang aktif."""
    row = conn.execute(
        """
        SELECT EXISTS (
            SELECT 1 FROM items
            WHERE category_id = %s AND is_active = TRUE
        ) AS in_use
        """,
        (category_id,),
    ).fetchone()
    return bool(row and row["in_use"])


# ============================================================================
# Units of Measure (UoMs)
# ============================================================================
def list_uoms(
    conn: Connection[dict[str, Any]],
    *,
    limit: int,
    offset: int,
    is_active: bool | None = None,
    search: str | None = None,
    order_by_sql: str = "u.id ASC",
) -> tuple[list[dict[str, Any]], int]:
    """Mengambil daftar UoM dengan filter, pencarian, dan pagination."""
    conditions: list[str] = []
    params: list[Any] = []

    if is_active is not None:
        conditions.append("u.is_active = %s")
        params.append(is_active)

    if search:
        kw = f"%{search.strip()}%"
        conditions.append("(u.code ILIKE %s OR u.name ILIKE %s)")
        params.extend([kw, kw])

    where_sql = f"WHERE {' AND '.join(conditions)}" if conditions else ""

    count_row = conn.execute(
        f"SELECT COUNT(*) AS total FROM uoms u {where_sql}",
        tuple(params),
    ).fetchone()
    total = int(count_row["total"]) if count_row else 0

    rows = conn.execute(
        f"""
        SELECT
            u.id,
            u.code,
            u.name,
            u.allow_decimal,
            u.is_active,
            u.created_by,
            u.created_at,
            u.updated_at
        FROM uoms u
        {where_sql}
        ORDER BY {order_by_sql}
        LIMIT %s OFFSET %s
        """,
        tuple([*params, limit, offset]),
    ).fetchall()
    return list(rows), total


def get_uom_by_id(
    conn: Connection[dict[str, Any]], uom_id: int
) -> dict[str, Any] | None:
    return conn.execute(
        """
        SELECT id, code, name, allow_decimal, is_active, created_by, created_at, updated_at
        FROM uoms
        WHERE id = %s
        """,
        (uom_id,),
    ).fetchone()


def lock_uom_by_id(
    conn: Connection[dict[str, Any]], uom_id: int
) -> dict[str, Any] | None:
    return conn.execute(
        """
        SELECT id, code, name, allow_decimal, is_active, created_by, created_at, updated_at
        FROM uoms
        WHERE id = %s
        FOR UPDATE
        """,
        (uom_id,),
    ).fetchone()


def get_uom_by_code(
    conn: Connection[dict[str, Any]], code: str
) -> dict[str, Any] | None:
    return conn.execute(
        """
        SELECT id, code, name, allow_decimal, is_active, created_by, created_at, updated_at
        FROM uoms
        WHERE LOWER(code) = LOWER(%s)
        """,
        (code,),
    ).fetchone()


def insert_uom(
    conn: Connection[dict[str, Any]],
    *,
    code: str,
    name: str,
    allow_decimal: bool,
    is_active: bool,
    created_by: int | None,
) -> dict[str, Any]:
    row = conn.execute(
        """
        INSERT INTO uoms (code, name, allow_decimal, is_active, created_by)
        VALUES (%s, %s, %s, %s, %s)
        RETURNING id, code, name, allow_decimal, is_active, created_by, created_at, updated_at
        """,
        (code, name, allow_decimal, is_active, created_by),
    ).fetchone()
    assert row is not None
    return row


def update_uom(
    conn: Connection[dict[str, Any]],
    uom_id: int,
    *,
    code: str,
    name: str,
    allow_decimal: bool,
    is_active: bool,
) -> dict[str, Any]:
    row = conn.execute(
        """
        UPDATE uoms
        SET
            code = %s,
            name = %s,
            allow_decimal = %s,
            is_active = %s,
            updated_at = CURRENT_TIMESTAMP
        WHERE id = %s
        RETURNING id, code, name, allow_decimal, is_active, created_by, created_at, updated_at
        """,
        (code, name, allow_decimal, is_active, uom_id),
    ).fetchone()
    assert row is not None
    return row


def is_uom_in_use(
    conn: Connection[dict[str, Any]], uom_id: int
) -> bool:
    """Memeriksa apakah UoM masih dipakai oleh barang yang aktif."""
    row = conn.execute(
        """
        SELECT EXISTS (
            SELECT 1 FROM items
            WHERE uom_id = %s AND is_active = TRUE
        ) AS in_use
        """,
        (uom_id,),
    ).fetchone()
    return bool(row and row["in_use"])


def is_uom_referenced_by_any_item(
    conn: Connection[dict[str, Any]], uom_id: int
) -> bool:
    """Memeriksa apakah UoM sudah direferensikan oleh barang mana pun (PRD 6.4 MST-F02)."""
    row = conn.execute(
        """
        SELECT EXISTS (
            SELECT 1 FROM items
            WHERE uom_id = %s
        ) AS referenced
        """,
        (uom_id,),
    ).fetchone()
    return bool(row and row["referenced"])


# ============================================================================
# Suppliers
# ============================================================================
def list_suppliers(
    conn: Connection[dict[str, Any]],
    *,
    limit: int,
    offset: int,
    is_active: bool | None = None,
    search: str | None = None,
    order_by_sql: str = "s.id ASC",
) -> tuple[list[dict[str, Any]], int]:
    """Mengambil daftar pemasok dengan filter, pencarian, dan pagination."""
    conditions: list[str] = []
    params: list[Any] = []

    if is_active is not None:
        conditions.append("s.is_active = %s")
        params.append(is_active)

    if search:
        kw = f"%{search.strip()}%"
        conditions.append(
            "(s.code ILIKE %s OR s.name ILIKE %s OR COALESCE(s.contact_person, '') ILIKE %s)"
        )
        params.extend([kw, kw, kw])

    where_sql = f"WHERE {' AND '.join(conditions)}" if conditions else ""

    count_row = conn.execute(
        f"SELECT COUNT(*) AS total FROM suppliers s {where_sql}",
        tuple(params),
    ).fetchone()
    total = int(count_row["total"]) if count_row else 0

    rows = conn.execute(
        f"""
        SELECT
            s.id,
            s.code,
            s.name,
            s.contact_person,
            s.phone,
            s.email,
            s.address,
            s.is_active,
            s.created_by,
            s.created_at,
            s.updated_at
        FROM suppliers s
        {where_sql}
        ORDER BY {order_by_sql}
        LIMIT %s OFFSET %s
        """,
        tuple([*params, limit, offset]),
    ).fetchall()
    return list(rows), total


def get_supplier_by_id(
    conn: Connection[dict[str, Any]], supplier_id: int
) -> dict[str, Any] | None:
    return conn.execute(
        """
        SELECT
            id, code, name, contact_person, phone, email, address,
            is_active, created_by, created_at, updated_at
        FROM suppliers
        WHERE id = %s
        """,
        (supplier_id,),
    ).fetchone()


def lock_supplier_by_id(
    conn: Connection[dict[str, Any]], supplier_id: int
) -> dict[str, Any] | None:
    return conn.execute(
        """
        SELECT
            id, code, name, contact_person, phone, email, address,
            is_active, created_by, created_at, updated_at
        FROM suppliers
        WHERE id = %s
        FOR UPDATE
        """,
        (supplier_id,),
    ).fetchone()


def get_supplier_by_code(
    conn: Connection[dict[str, Any]], code: str
) -> dict[str, Any] | None:
    return conn.execute(
        """
        SELECT
            id, code, name, contact_person, phone, email, address,
            is_active, created_by, created_at, updated_at
        FROM suppliers
        WHERE LOWER(code) = LOWER(%s)
        """,
        (code,),
    ).fetchone()


def list_existing_supplier_code_keys(
    conn: Connection[dict[str, Any]], code_keys: list[str]
) -> set[str]:
    """Mengambil seluruh kode supplier yang sudah terdaftar dalam satu query."""
    if not code_keys:
        return set()
    rows = conn.execute(
        """
        SELECT LOWER(code) AS code_key
        FROM suppliers
        WHERE LOWER(code) = ANY(%s)
        """,
        (code_keys,),
    ).fetchall()
    return {str(row["code_key"]) for row in rows}


def insert_suppliers_batch(
    conn: Connection[dict[str, Any]],
    *,
    suppliers: list[dict[str, Any]],
    created_by: int,
) -> list[dict[str, Any]]:
    """Membuat supplier valid dalam satu statement; konflik kode konkuren diabaikan per baris."""
    if not suppliers:
        return []
    rows = conn.execute(
        """
        INSERT INTO suppliers (
            code, name, contact_person, phone, email, address, is_active, created_by
        )
        SELECT
            source.code,
            source.name,
            source.contact_person,
            source.phone,
            source.email,
            source.address,
            source.is_active,
            %s
        FROM UNNEST(
            %s::text[],
            %s::text[],
            %s::text[],
            %s::text[],
            %s::text[],
            %s::text[],
            %s::boolean[]
        ) AS source(code, name, contact_person, phone, email, address, is_active)
        ON CONFLICT DO NOTHING
        RETURNING
            id,
            code,
            LOWER(code) AS code_key,
            name,
            contact_person,
            phone,
            email,
            address,
            is_active
        """,
        (
            created_by,
            [supplier["code"] for supplier in suppliers],
            [supplier["name"] for supplier in suppliers],
            [supplier["contact_person"] for supplier in suppliers],
            [supplier["phone"] for supplier in suppliers],
            [supplier["email"] for supplier in suppliers],
            [supplier["address"] for supplier in suppliers],
            [supplier["is_active"] for supplier in suppliers],
        ),
    ).fetchall()
    return list(rows)


def insert_supplier(
    conn: Connection[dict[str, Any]],
    *,
    code: str,
    name: str,
    contact_person: str | None,
    phone: str | None,
    email: str | None,
    address: str | None,
    is_active: bool,
    created_by: int | None,
) -> dict[str, Any]:
    row = conn.execute(
        """
        INSERT INTO suppliers (
            code, name, contact_person, phone, email, address, is_active, created_by
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        RETURNING
            id, code, name, contact_person, phone, email, address,
            is_active, created_by, created_at, updated_at
        """,
        (code, name, contact_person, phone, email, address, is_active, created_by),
    ).fetchone()
    assert row is not None
    return row


def update_supplier(
    conn: Connection[dict[str, Any]],
    supplier_id: int,
    *,
    code: str,
    name: str,
    contact_person: str | None,
    phone: str | None,
    email: str | None,
    address: str | None,
    is_active: bool,
) -> dict[str, Any]:
    row = conn.execute(
        """
        UPDATE suppliers
        SET
            code = %s,
            name = %s,
            contact_person = %s,
            phone = %s,
            email = %s,
            address = %s,
            is_active = %s,
            updated_at = CURRENT_TIMESTAMP
        WHERE id = %s
        RETURNING
            id, code, name, contact_person, phone, email, address,
            is_active, created_by, created_at, updated_at
        """,
        (code, name, contact_person, phone, email, address, is_active, supplier_id),
    ).fetchone()
    assert row is not None
    return row


def is_supplier_in_use(
    conn: Connection[dict[str, Any]], supplier_id: int
) -> bool:
    """Memeriksa apakah pemasok masih memiliki PO yang belum final atau GR berstatus DRAFT (PRD 6.4, 6.8)."""
    row = conn.execute(
        """
        SELECT (
            EXISTS (
                SELECT 1 FROM purchase_orders
                WHERE supplier_id = %s
                  AND status IN ('DRAFT', 'ISSUED', 'PARTIALLY_RECEIVED')
            )
            OR EXISTS (
                SELECT 1
                FROM goods_receipts gr
                JOIN purchase_orders po ON po.id = gr.po_id
                WHERE po.supplier_id = %s
                  AND gr.status = 'DRAFT'
            )
        ) AS in_use
        """,
        (supplier_id, supplier_id),
    ).fetchone()
    return bool(row and row["in_use"])


# ============================================================================
# Items
# ============================================================================
def list_items(
    conn: Connection[dict[str, Any]],
    *,
    limit: int,
    offset: int,
    category_id: int | None = None,
    uom_id: int | None = None,
    is_active: bool | None = None,
    barcode: str | None = None,
    search: str | None = None,
    order_by_sql: str = "i.id ASC",
) -> tuple[list[dict[str, Any]], int]:
    """Mengambil daftar barang beserta nama kategori dan informasi UoM."""
    conditions: list[str] = []
    params: list[Any] = []

    if category_id is not None:
        conditions.append("i.category_id = %s")
        params.append(category_id)

    if uom_id is not None:
        conditions.append("i.uom_id = %s")
        params.append(uom_id)

    if is_active is not None:
        conditions.append("i.is_active = %s")
        params.append(is_active)

    if barcode:
        clean_bc = barcode.strip()
        conditions.append(
            "(LOWER(i.barcode) = LOWER(%s) OR LOWER(i.sku) = LOWER(%s))"
        )
        params.extend([clean_bc, clean_bc])

    if search:
        kw = f"%{search.strip()}%"
        conditions.append(
            "(i.sku ILIKE %s OR COALESCE(i.barcode, '') ILIKE %s OR i.name ILIKE %s OR COALESCE(i.description, '') ILIKE %s)"
        )
        params.extend([kw, kw, kw, kw])

    where_sql = f"WHERE {' AND '.join(conditions)}" if conditions else ""

    count_row = conn.execute(
        f"SELECT COUNT(*) AS total FROM items i {where_sql}",
        tuple(params),
    ).fetchone()
    total = int(count_row["total"]) if count_row else 0

    rows = conn.execute(
        f"""
        SELECT
            i.id,
            i.sku,
            i.barcode,
            i.name,
            i.description,
            i.category_id,
            c.name AS category_name,
            i.uom_id,
            u.code AS uom_code,
            u.name AS uom_name,
            u.allow_decimal,
            i.is_active,
            i.created_by,
            i.created_at,
            i.updated_at
        FROM items i
        JOIN categories c ON c.id = i.category_id
        JOIN uoms u ON u.id = i.uom_id
        {where_sql}
        ORDER BY {order_by_sql}
        LIMIT %s OFFSET %s
        """,
        tuple([*params, limit, offset]),
    ).fetchall()
    return list(rows), total


def get_item_by_id(
    conn: Connection[dict[str, Any]], item_id: int
) -> dict[str, Any] | None:
    return conn.execute(
        """
        SELECT
            i.id,
            i.sku,
            i.barcode,
            i.name,
            i.description,
            i.category_id,
            c.name AS category_name,
            i.uom_id,
            u.code AS uom_code,
            u.name AS uom_name,
            u.allow_decimal,
            i.is_active,
            i.created_by,
            i.created_at,
            i.updated_at
        FROM items i
        JOIN categories c ON c.id = i.category_id
        JOIN uoms u ON u.id = i.uom_id
        WHERE i.id = %s
        """,
        (item_id,),
    ).fetchone()


def lock_item_by_id(
    conn: Connection[dict[str, Any]], item_id: int
) -> dict[str, Any] | None:
    row = conn.execute(
        """
        SELECT
            id, sku, barcode, name, description, category_id, uom_id,
            is_active, created_by, created_at, updated_at
        FROM items
        WHERE id = %s
        FOR UPDATE
        """,
        (item_id,),
    ).fetchone()
    return row


def get_item_by_sku(
    conn: Connection[dict[str, Any]], sku: str
) -> dict[str, Any] | None:
    return conn.execute(
        """
        SELECT id, sku, barcode, name, category_id, uom_id, is_active
        FROM items
        WHERE LOWER(sku) = LOWER(%s)
        """,
        (sku,),
    ).fetchone()


def get_item_by_barcode(
    conn: Connection[dict[str, Any]], barcode: str
) -> dict[str, Any] | None:
    return conn.execute(
        """
        SELECT id, sku, barcode, name, category_id, uom_id, is_active
        FROM items
        WHERE barcode IS NOT NULL AND LOWER(barcode) = LOWER(%s)
        """,
        (barcode,),
    ).fetchone()


def list_item_import_categories(
    conn: Connection[dict[str, Any]], names: list[str]
) -> list[dict[str, Any]]:
    """Mencari kategori impor sekaligus dan mengunci status aktif sampai transaksi selesai."""
    if not names:
        return []
    rows = conn.execute(
        """
        SELECT id, name, is_active
        FROM categories
        WHERE LOWER(name) = ANY(%s)
        ORDER BY id
        FOR SHARE
        """,
        (names,),
    ).fetchall()
    return list(rows)


def list_active_item_import_categories(
    conn: Connection[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Mengambil kategori aktif untuk sheet referensi template import."""
    rows = conn.execute(
        """
        SELECT name
        FROM categories
        WHERE is_active = TRUE
        ORDER BY LOWER(name), id
        """
    ).fetchall()
    return list(rows)


def list_active_item_import_uoms(
    conn: Connection[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Mengambil nama dan kode UoM aktif untuk sheet referensi template import."""
    rows = conn.execute(
        """
        SELECT name, code
        FROM uoms
        WHERE is_active = TRUE
        ORDER BY LOWER(name), code, id
        """
    ).fetchall()
    return list(rows)


def list_item_import_uoms(
    conn: Connection[dict[str, Any]], names: list[str]
) -> list[dict[str, Any]]:
    """Mencari UoM impor berdasarkan nama dan mengunci status sampai transaksi selesai."""
    if not names:
        return []
    rows = conn.execute(
        """
        SELECT id, name, code, is_active
        FROM uoms
        WHERE LOWER(name) = ANY(%s)
        ORDER BY id
        FOR SHARE
        """,
        (names,),
    ).fetchall()
    return list(rows)


def list_existing_item_sku_keys(
    conn: Connection[dict[str, Any]], sku_keys: list[str]
) -> set[str]:
    """Mengambil seluruh SKU yang sudah terdaftar dengan satu query."""
    if not sku_keys:
        return set()
    rows = conn.execute(
        """
        SELECT LOWER(sku) AS sku_key
        FROM items
        WHERE LOWER(sku) = ANY(%s)
        """,
        (sku_keys,),
    ).fetchall()
    return {str(row["sku_key"]) for row in rows}


def list_existing_item_barcode_keys(
    conn: Connection[dict[str, Any]], barcode_keys: list[str]
) -> set[str]:
    """Mengambil seluruh barcode yang sudah terdaftar dengan satu query."""
    if not barcode_keys:
        return set()
    rows = conn.execute(
        """
        SELECT LOWER(barcode) AS barcode_key
        FROM items
        WHERE barcode IS NOT NULL AND LOWER(barcode) = ANY(%s)
        """,
        (barcode_keys,),
    ).fetchall()
    return {str(row["barcode_key"]) for row in rows}


def insert_items_batch(
    conn: Connection[dict[str, Any]],
    *,
    items: list[dict[str, Any]],
    created_by: int,
) -> list[dict[str, Any]]:
    """Membuat item valid dalam satu statement; konflik SKU/barcode konkuren diabaikan per item."""
    if not items:
        return []
    rows = conn.execute(
        """
        INSERT INTO items (
            sku, barcode, name, description, category_id, uom_id, is_active, created_by
        )
        SELECT
            source.sku,
            source.barcode,
            source.name,
            source.description,
            source.category_id,
            source.uom_id,
            source.is_active,
            %s
        FROM UNNEST(
            %s::text[],
            %s::text[],
            %s::text[],
            %s::text[],
            %s::bigint[],
            %s::bigint[],
            %s::boolean[]
        ) AS source(sku, barcode, name, description, category_id, uom_id, is_active)
        ON CONFLICT DO NOTHING
        RETURNING
            id,
            sku,
            LOWER(sku) AS sku_key,
            barcode,
            LOWER(barcode) AS barcode_key,
            name,
            description,
            category_id,
            uom_id,
            is_active
        """,
        (
            created_by,
            [item["sku"] for item in items],
            [item["barcode"] for item in items],
            [item["name"] for item in items],
            [item["description"] for item in items],
            [item["category_id"] for item in items],
            [item["uom_id"] for item in items],
            [item["is_active"] for item in items],
        ),
    ).fetchall()
    return list(rows)


def insert_item(
    conn: Connection[dict[str, Any]],
    *,
    sku: str,
    barcode: str | None = None,
    name: str,
    description: str | None,
    category_id: int,
    uom_id: int,
    is_active: bool,
    created_by: int | None,
) -> dict[str, Any]:
    row = conn.execute(
        """
        INSERT INTO items (
            sku, barcode, name, description, category_id, uom_id, is_active, created_by
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        RETURNING id
        """,
        (sku, barcode, name, description, category_id, uom_id, is_active, created_by),
    ).fetchone()
    assert row is not None
    detail = get_item_by_id(conn, int(row["id"]))
    assert detail is not None
    return detail


def update_item(
    conn: Connection[dict[str, Any]],
    item_id: int,
    *,
    sku: str,
    barcode: str | None = None,
    name: str,
    description: str | None,
    category_id: int,
    uom_id: int,
    is_active: bool,
) -> dict[str, Any]:
    conn.execute(
        """
        UPDATE items
        SET
            sku = %s,
            barcode = %s,
            name = %s,
            description = %s,
            category_id = %s,
            uom_id = %s,
            is_active = %s,
            updated_at = CURRENT_TIMESTAMP
        WHERE id = %s
        """,
        (sku, barcode, name, description, category_id, uom_id, is_active, item_id),
    )
    detail = get_item_by_id(conn, item_id)
    assert detail is not None
    return detail


def is_item_used_in_transactions(
    conn: Connection[dict[str, Any]], item_id: int
) -> bool:
    """Memeriksa apakah barang sudah pernah dipakai pada transaksi apa pun (PRD FR-02 & 6.8: SKU tak dapat diubah)."""
    row = conn.execute(
        """
        SELECT (
            EXISTS (SELECT 1 FROM po_lines WHERE item_id = %s)
            OR EXISTS (SELECT 1 FROM gr_lines gl JOIN po_lines pl ON pl.id = gl.po_line_id WHERE pl.item_id = %s)
            OR EXISTS (SELECT 1 FROM stock_transfer_lines WHERE item_id = %s)
            OR EXISTS (SELECT 1 FROM stock_opname_lines WHERE item_id = %s)
            OR EXISTS (SELECT 1 FROM stock_movements WHERE item_id = %s)
            OR EXISTS (SELECT 1 FROM inventory_balances WHERE item_id = %s AND qty_on_hand <> 0)
        ) AS used
        """,
        (item_id, item_id, item_id, item_id, item_id, item_id),
    ).fetchone()
    return bool(row and row["used"])


def is_item_in_use(
    conn: Connection[dict[str, Any]], item_id: int
) -> bool:
    """Memeriksa apakah barang tidak dapat dinonaktifkan karena bersaldo != 0 atau ada di dokumen belum final (PRD 6.8)."""
    row = conn.execute(
        """
        SELECT (
            EXISTS (
                SELECT 1 FROM inventory_balances
                WHERE item_id = %s AND qty_on_hand <> 0
            )
            OR EXISTS (
                SELECT 1
                FROM po_lines pl
                JOIN purchase_orders po ON po.id = pl.po_id
                WHERE pl.item_id = %s
                  AND po.status IN ('DRAFT', 'ISSUED', 'PARTIALLY_RECEIVED')
            )
            OR EXISTS (
                SELECT 1
                FROM gr_lines gl
                JOIN po_lines pl ON pl.id = gl.po_line_id
                JOIN goods_receipts gr ON gr.id = gl.gr_id
                WHERE pl.item_id = %s
                  AND gr.status = 'DRAFT'
            )
            OR EXISTS (
                SELECT 1
                FROM stock_transfer_lines stl
                JOIN stock_transfers st ON st.id = stl.transfer_id
                WHERE stl.item_id = %s
                  AND st.status IN ('DRAFT', 'APPROVED', 'SHIPPED')
            )
            OR EXISTS (
                SELECT 1
                FROM stock_opname_lines sol
                JOIN stock_opnames so ON so.id = sol.opname_id
                WHERE sol.item_id = %s
                  AND so.status IN ('DRAFT', 'IN_PROGRESS', 'WAITING_APPROVAL')
            )
        ) AS in_use
        """,
        (item_id, item_id, item_id, item_id, item_id),
    ).fetchone()
    return bool(row and row["in_use"])

