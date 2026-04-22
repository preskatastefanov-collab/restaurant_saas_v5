from database import get_db


def normalize_text(value):
    return " ".join((value or "").strip().lower().split())


def get_menu_categories(tenant_id):
    db = get_db()
    rows = db.execute("""
        SELECT *
        FROM menu_categories
        WHERE tenant_id = ? AND is_active = 1
        ORDER BY sort_order ASC, id ASC
    """, (tenant_id,)).fetchall()
    db.close()
    return [dict(r) for r in rows]


def get_menu_items_by_category(tenant_id, category_id):
    db = get_db()
    rows = db.execute("""
        SELECT *
        FROM menu_items
        WHERE tenant_id = ? AND category_id = ? AND is_active = 1
        ORDER BY sort_order ASC, id ASC
    """, (tenant_id, category_id)).fetchall()
    db.close()
    return [dict(r) for r in rows]


def get_category_by_name(tenant_id, category_name):
    db = get_db()
    row = db.execute("""
        SELECT *
        FROM menu_categories
        WHERE tenant_id = ? AND LOWER(name) = LOWER(?) AND is_active = 1
        LIMIT 1
    """, (tenant_id, category_name)).fetchone()
    db.close()
    return dict(row) if row else None


def find_menu_category_match(tenant_id, text):
    categories = get_menu_categories(tenant_id)
    text_clean = normalize_text(text)

    if not text_clean:
        return None

    # 1. точен match
    for category in categories:
        cat_name = normalize_text(category["name"])
        if text_clean == cat_name:
            return category

    # 2. ако съобщението съдържа името на категорията
    for category in categories:
        cat_name = normalize_text(category["name"])
        if cat_name and cat_name in text_clean:
            return category

    return None


def get_full_menu(tenant_id):
    categories = get_menu_categories(tenant_id)
    result = []

    for category in categories:
        items = get_menu_items_by_category(tenant_id, category["id"])
        result.append({
            "category": category,
            "items": items
        })

    return result


def create_menu_category(tenant_id, name, sort_order=0):
    db = get_db()
    db.execute("""
        INSERT INTO menu_categories (tenant_id, name, sort_order, is_active)
        VALUES (?, ?, ?, 1)
    """, (tenant_id, name, sort_order))
    db.commit()
    db.close()


def create_menu_item(tenant_id, category_id, name, description="", price=0, sort_order=0):
    db = get_db()
    db.execute("""
        INSERT INTO menu_items (
            tenant_id, category_id, name, description, price, is_active, sort_order
        )
        VALUES (?, ?, ?, ?, ?, 1, ?)
    """, (tenant_id, category_id, name, description, price, sort_order))
    db.commit()
    db.close()


def delete_menu_category(category_id, tenant_id):
    db = get_db()
    db.execute("""
        DELETE FROM menu_items
        WHERE category_id = ? AND tenant_id = ?
    """, (category_id, tenant_id))

    db.execute("""
        DELETE FROM menu_categories
        WHERE id = ? AND tenant_id = ?
    """, (category_id, tenant_id))
    db.commit()
    db.close()


def delete_menu_item(item_id, tenant_id):
    db = get_db()
    db.execute("""
        DELETE FROM menu_items
        WHERE id = ? AND tenant_id = ?
    """, (item_id, tenant_id))
    db.commit()
    db.close()