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


def get_all_menu_items(tenant_id):
    db = get_db()
    rows = db.execute("""
        SELECT 
            mi.*,
            mc.name AS category_name
        FROM menu_items mi
        LEFT JOIN menu_categories mc ON mc.id = mi.category_id
        WHERE mi.tenant_id = ? AND mi.is_active = 1
        ORDER BY mi.sort_order ASC, mi.id ASC
    """, (tenant_id,)).fetchall()
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

    for category in categories:
        cat_name = normalize_text(category["name"])
        if text_clean == cat_name:
            return category

    for category in categories:
        cat_name = normalize_text(category["name"])
        if cat_name and cat_name in text_clean:
            return category

    return None


def find_item_mentioned_in_text(tenant_id, text):
    text_clean = normalize_text(text)
    if not text_clean:
        return None

    items = get_all_menu_items(tenant_id)

    for item in items:
        item_name = normalize_text(item.get("name"))
        if item_name and item_name in text_clean:
            return item

    return None


def get_items_by_category_keywords(tenant_id, keywords):
    items = get_all_menu_items(tenant_id)
    result = []

    for item in items:
        category_name = normalize_text(item.get("category_name"))
        item_name = normalize_text(item.get("name"))
        description = normalize_text(item.get("description"))

        combined = f"{category_name} {item_name} {description}"

        if any(k in combined for k in keywords):
            result.append(item)

    return result


def get_best_drink(tenant_id):
    drinks = get_items_by_category_keywords(tenant_id, [
        "напит", "лимонада", "вода", "сок", "айрян", "кола", "кафе", "чай"
    ])
    return drinks[0] if drinks else None


def get_best_dessert(tenant_id):
    desserts = get_items_by_category_keywords(tenant_id, [
        "десерт", "слад", "чийзкейк", "торта", "крем", "сладолед"
    ])
    return desserts[0] if desserts else None


def get_smart_upsell_for_item(tenant_id, item=None, user_text=""):
    user_text_clean = normalize_text(user_text)

    if any(x in user_text_clean for x in ["десерт", "напит", "пиене", "пия", "вода", "лимонада"]):
        return None

    item_name = item.get("name") if item else None
    custom_drink_name = (item.get("upsell_drink") or "").strip() if item else ""
    custom_dessert_name = (item.get("upsell_dessert") or "").strip() if item else ""

    drink = None
    dessert = None

    if custom_drink_name:
        drink = {"name": custom_drink_name}
    else:
        drink = get_best_drink(tenant_id)

    if custom_dessert_name:
        dessert = {"name": custom_dessert_name}
    else:
        dessert = get_best_dessert(tenant_id)

    if not drink and not dessert:
        return None

    if item_name and drink:
        return {
            "text": f"🥤 Към „{item_name}“ най-добре върви {drink['name']} — да добавим ли и него? 😊",
            "buttons": [drink["name"], "Десерти", "Нова резервация"]
        }

    if item_name and dessert:
        return {
            "text": f"🍰 След „{item_name}“ много добре пасва {dessert['name']} — да ви го предложа ли? 😊",
            "buttons": [dessert["name"], "Напитки", "Нова резервация"]
        }

    if drink and dessert:
        return {
            "text": f"🥤🍰 Към храната клиентите често добавят {drink['name']} или {dessert['name']} — искате ли да разгледате?",
            "buttons": [drink["name"], dessert["name"], "Нова резервация"]
        }

    if drink:
        return {
            "text": f"🥤 Към това много добре върви {drink['name']} — да добавим ли? 😊",
            "buttons": [drink["name"], "Нова резервация", "Меню"]
        }

    if dessert:
        return {
            "text": f"🍰 За финал мога да предложа {dessert['name']} — искате ли? 😊",
            "buttons": [dessert["name"], "Нова резервация", "Меню"]
        }

    return None


def create_menu_category(tenant_id, name, sort_order=0):
    db = get_db()
    db.execute("""
        INSERT INTO menu_categories (tenant_id, name, sort_order, is_active)
        VALUES (?, ?, ?, 1)
    """, (tenant_id, name, sort_order))
    db.commit()
    db.close()


def create_menu_item(
    tenant_id,
    category_id,
    name,
    description="",
    price=0,
    sort_order=0,
    upsell_drink="",
    upsell_dessert=""
):
    db = get_db()
    db.execute("""
        INSERT INTO menu_items (
            tenant_id,
            category_id,
            name,
            description,
            price,
            upsell_drink,
            upsell_dessert,
            is_active,
            sort_order
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, 1, ?)
    """, (
        tenant_id,
        category_id,
        name,
        description,
        price,
        upsell_drink,
        upsell_dessert,
        sort_order
    ))
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