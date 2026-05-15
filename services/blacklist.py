from database import get_db


def normalize_phone(phone):
    value = str(phone or "").strip()

    allowed = []
    for ch in value:
        if ch.isdigit() or ch == "+":
            allowed.append(ch)

    cleaned = "".join(allowed)

    if cleaned.startswith("00"):
        cleaned = "+" + cleaned[2:]

    return cleaned


def list_banned_customers(tenant_id):
    db = get_db()
    rows = db.execute("""
        SELECT *
        FROM banned_customers
        WHERE tenant_id = ?
        ORDER BY is_active DESC, id DESC
    """, (tenant_id,)).fetchall()
    db.close()

    return [dict(row) for row in rows]


def is_phone_banned(tenant_id, phone):
    normalized = normalize_phone(phone)

    if not normalized:
        return False

    db = get_db()
    row = db.execute("""
        SELECT id
        FROM banned_customers
        WHERE tenant_id = ?
          AND phone = ?
          AND is_active = 1
        LIMIT 1
    """, (tenant_id, normalized)).fetchone()
    db.close()

    return row is not None


def add_banned_customer(tenant_id, phone, reason="", created_by=""):
    normalized = normalize_phone(phone)

    if not normalized:
        return None

    db = get_db()

    existing = db.execute("""
        SELECT id
        FROM banned_customers
        WHERE tenant_id = ?
          AND phone = ?
        LIMIT 1
    """, (tenant_id, normalized)).fetchone()

    if existing:
        db.execute("""
            UPDATE banned_customers
            SET reason = ?,
                created_by = ?,
                is_active = 1,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (reason, created_by, existing["id"]))

        ban_id = existing["id"]
    else:
        cursor = db.execute("""
            INSERT INTO banned_customers (
                tenant_id,
                phone,
                reason,
                created_by,
                is_active
            )
            VALUES (?, ?, ?, ?, 1)
        """, (tenant_id, normalized, reason, created_by))

        ban_id = cursor.lastrowid

    db.commit()
    db.close()

    return ban_id


def unban_customer(ban_id, tenant_id):
    db = get_db()
    db.execute("""
        UPDATE banned_customers
        SET is_active = 0,
            updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
          AND tenant_id = ?
    """, (ban_id, tenant_id))
    db.commit()
    db.close()