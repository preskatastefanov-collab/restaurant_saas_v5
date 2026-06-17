from database import get_db
from services.translator import translate_to_english

VALID_PLANS = {"basic", "standard", "premium"}

VALID_BUSINESS_TYPES = {
    "restaurant", "cafe", "bar", "pub", "pizzeria",
    "fast_food", "bakery", "sweet_shop", "food_truck", "other",
}

BUSINESS_TYPE_LABELS = {
    "restaurant": "Ресторант",
    "cafe": "Кафене",
    "bar": "Бар",
    "pub": "Кръчма / Пъб",
    "pizzeria": "Пицария",
    "fast_food": "Бързо хранене",
    "bakery": "Пекарна",
    "sweet_shop": "Сладкарница",
    "food_truck": "Food Truck",
    "other": "Друг бизнес",
}

BUSINESS_TYPE_DEFAULTS = {
    "restaurant": {
        "widget_title": "Restaurant AI Chatbot",
        "welcome_message": "👋 Здравейте! Мога да помогна с меню, препоръки, контакти или резервация.",
        "ai_style": "Любезен ресторантски асистент. Помага с меню, ястия, напитки, десерти, препоръки и резервации.",
    },
    "cafe": {
        "widget_title": "Cafe AI Chatbot",
        "welcome_message": "👋 Здравейте! Мога да помогна с кафе, десерти, работно време или резервация.",
        "ai_style": "Любезен асистент за кафене. Препоръчва кафе, десерти, закуски, напитки и леки предложения.",
    },
    "bar": {
        "widget_title": "Bar AI Chatbot",
        "welcome_message": "👋 Здравейте! Мога да помогна с напитки, коктейли, меню, контакти или резервация.",
        "ai_style": "Асистент като барман. Препоръчва коктейли, бира, вино, мезета и подходящи комбинации.",
    },
    "pub": {
        "widget_title": "Pub AI Chatbot",
        "welcome_message": "👋 Здравейте! Мога да помогна с бира, мезета, храна, контакти или резервация.",
        "ai_style": "Асистент за пъб/кръчма. Препоръчва бира, мезета, хапки, скара, храна за компания и резервации.",
    },
    "pizzeria": {
        "widget_title": "Pizzeria AI Chatbot",
        "welcome_message": "👋 Здравейте! Мога да помогна с пици, меню, контакти или резервация.",
        "ai_style": "Асистент за пицария. Препоръчва пици, сосове, напитки, паста, десерти и комбо предложения.",
    },
    "fast_food": {
        "widget_title": "Fast Food AI Chatbot",
        "welcome_message": "👋 Здравейте! Мога да помогна с меню, цени и информация за поръчка.",
        "ai_style": "Асистент за fast food. Препоръчва бургери, картофки, напитки, сосове, менюта и комбо предложения.",
    },
    "bakery": {
        "widget_title": "Bakery AI Chatbot",
        "welcome_message": "👋 Здравейте! Мога да помогна с продукти, наличности, поръчки и работно време.",
        "ai_style": "Асистент за пекарна. Препоръчва хляб, закуски, печива, сладки продукти, кафе и свежи предложения.",
    },
    "sweet_shop": {
        "widget_title": "Dessert AI Chatbot",
        "welcome_message": "👋 Здравейте! Мога да помогна с торти, десерти, заявки и работно време.",
        "ai_style": "Асистент за сладкарница. Препоръчва торти, пасти, десерти, кафе, сладки предложения и поръчки за поводи.",
    },
    "food_truck": {
        "widget_title": "Food Truck AI Chatbot",
        "welcome_message": "👋 Здравейте! Мога да помогна с меню, локация и работно време.",
        "ai_style": "Асистент за food truck. Препоръчва бързи храни, комбо менюта, напитки, сосове, добавки и дава локация.",
    },
    "other": {
        "widget_title": "Business AI Chatbot",
        "welcome_message": "👋 Здравейте! С какво мога да помогна?",
        "ai_style": "Любезен бизнес асистент. Отговаря ясно, кратко, полезно и насочва клиента към правилната информация.",
    },
}

PLAN_FEATURES = {
    "basic": {
        "widget",
        "menu",
        "contacts",
        "reservations",
        "dashboard",
        "export",
        "menu_manager",
        "user_management_basic",
    },
    "standard": {
        "widget",
        "menu",
        "contacts",
        "reservations",
        "dashboard",
        "export",
        "menu_manager",
        "user_management_basic",

        "ai_chat",
        "smart_food_answers",
        "better_fallback",
        "smart_quick_replies",
        "blacklist",
        "email_notifications",
    },
    "premium": {
        "widget",
        "menu",
        "contacts",
        "reservations",
        "dashboard",
        "export",
        "menu_manager",
        "user_management_basic",

        "ai_chat",
        "smart_food_answers",
        "better_fallback",
        "smart_quick_replies",
        "blacklist",

        "upsell",
        "premium_analytics",
        "advanced_ai_logic",
        "recommended_dishes",
        "priority_features",
        "product_images",
        "sales_recommendations",

        "email_notifications",
        "reservation_reminders",
    },
}


def normalize_plan(plan):
    plan = (plan or "basic").strip().lower()
    return plan if plan in VALID_PLANS else "basic"

def can_use_ai(tenant_id):
    return tenant_has_feature(tenant_id, "ai_chat")


def can_use_upsell(tenant_id):
    return tenant_has_feature(tenant_id, "upsell")


def can_use_product_images(tenant_id):
    return tenant_has_feature(tenant_id, "product_images")


def can_use_premium_analytics(tenant_id):
    return tenant_has_feature(tenant_id, "premium_analytics")


def can_use_sales_recommendations(tenant_id):
    return tenant_has_feature(tenant_id, "sales_recommendations")

def normalize_business_type(business_type):
    business_type = (business_type or "restaurant").strip().lower()
    return business_type if business_type in VALID_BUSINESS_TYPES else "restaurant"


def safe_int(value, default=0):
    try:
        return int(value)
    except Exception:
        return default


def get_business_type_label(business_type):
    business_type = normalize_business_type(business_type)
    return BUSINESS_TYPE_LABELS.get(business_type, "Ресторант")


def get_business_type_defaults(business_type):
    business_type = normalize_business_type(business_type)
    return BUSINESS_TYPE_DEFAULTS.get(business_type, BUSINESS_TYPE_DEFAULTS["restaurant"])


def get_business_type_ai_style(business_type):
    defaults = get_business_type_defaults(business_type)
    return defaults.get("ai_style", BUSINESS_TYPE_DEFAULTS["restaurant"]["ai_style"])


def get_business_type_options():
    return [{"value": value, "label": label} for value, label in BUSINESS_TYPE_LABELS.items()]


def has_feature(plan, feature_name):
    plan = normalize_plan(plan)
    return feature_name in PLAN_FEATURES.get(plan, set())


def get_plan_features(plan):
    plan = normalize_plan(plan)
    return sorted(list(PLAN_FEATURES.get(plan, set())))


def get_plan_label(plan):
    plan = normalize_plan(plan)

    labels = {
        "basic": "Basic",
        "standard": "Standard",
        "premium": "Premium",
    }

    return labels.get(plan, "Basic")


def get_tenant(tenant_id):
    db = get_db()
    row = db.execute("SELECT * FROM tenants WHERE id = ?", (tenant_id,)).fetchone()
    db.close()
    return dict(row) if row else None


def get_tenant_plan(tenant_id):
    tenant = get_tenant(tenant_id)
    if not tenant:
        return "basic"
    return normalize_plan(tenant.get("plan"))


def get_tenant_business_type(tenant_id):
    tenant = get_tenant(tenant_id)
    if not tenant:
        return "restaurant"
    return normalize_business_type(tenant.get("business_type"))


def tenant_has_feature(tenant_id, feature_name):
    return has_feature(get_tenant_plan(tenant_id), feature_name)


def get_tenant_settings(tenant_id):
    db = get_db()
    row = db.execute("""
        SELECT * FROM tenant_settings
        WHERE tenant_id = ?
    """, (tenant_id,)).fetchone()
    db.close()
    return dict(row) if row else None


def get_tenant_profile(tenant_id):
    tenant = get_tenant(tenant_id)
    settings = get_tenant_settings(tenant_id)

    if not tenant:
        return None

    business_type = normalize_business_type(tenant.get("business_type"))
    plan = normalize_plan(tenant.get("plan"))

    return {
        "tenant": tenant,
        "settings": settings or {},
        "tenant_id": tenant_id,
        "name": tenant.get("name") or "",
        "slug": tenant.get("slug") or "",
        "plan": plan,
        "plan_label": get_plan_label(plan),
        "business_type": business_type,
        "business_type_label": get_business_type_label(business_type),
        "business_type_ai_style": get_business_type_ai_style(business_type),
        "features": get_plan_features(plan),
        "ai_enabled_by_plan": has_feature(plan, "ai_chat"),
        "upsell_enabled_by_plan": has_feature(plan, "upsell"),
        "product_images_enabled_by_plan": has_feature(plan, "product_images"),
        "sales_recommendations_enabled_by_plan": has_feature(plan, "sales_recommendations"),
    }


def get_tenant_ai_profile(tenant_id):
    profile = get_tenant_profile(tenant_id)

    if not profile:
        return {
            "business_name": "Бизнес",
            "business_type": "restaurant",
            "business_type_label": "Ресторант",
            "business_type_ai_style": get_business_type_ai_style("restaurant"),
            "plan": "basic",
            "plan_label": "Basic",
            "llm_enabled": False,
            "upsell_enabled": False,
            "phone": "",
            "email": "",
            "address": "",
            "website": "",
            "welcome_message": "",
            "widget_title": "",
            "open_hour": 10,
            "close_hour": 22,
            "max_capacity": 20,
        }

    settings = profile.get("settings") or {}
    business_type = profile["business_type"]
    defaults = get_business_type_defaults(business_type)

    business_name = (
        settings.get("restaurant_name")
        or profile.get("name")
        or "Бизнес"
    )

    llm_enabled_setting = safe_int(settings.get("llm_enabled"), 0)

    return {
        "business_name": business_name,
        "business_type": business_type,
        "business_type_label": profile["business_type_label"],
        "business_type_ai_style": profile["business_type_ai_style"],
        "plan": profile["plan"],
        "plan_label": profile["plan_label"],
        "llm_enabled": bool(profile["ai_enabled_by_plan"] and llm_enabled_setting == 1),
        "upsell_enabled": bool(profile["upsell_enabled_by_plan"]),
        "product_images_enabled": bool(profile["product_images_enabled_by_plan"]),
        "sales_recommendations_enabled": bool(profile["sales_recommendations_enabled_by_plan"]),
        "phone": settings.get("phone") or "",
        "email": settings.get("email") or "",
        "address": settings.get("address") or "",
        "website": settings.get("website") or "",
        "working_hours": settings.get("working_hours") or "",
        "welcome_message": settings.get("welcome_message") or defaults["welcome_message"],
        "widget_title": settings.get("widget_title") or defaults["widget_title"],
        "open_hour": safe_int(settings.get("open_hour"), 10),
        "close_hour": safe_int(settings.get("close_hour"), 22),
        "max_capacity": safe_int(settings.get("max_capacity"), 20),
    }


def create_tenant(
    name,
    slug,
    max_capacity=20,
    open_hour=10,
    close_hour=22,
    plan="basic",
    business_type="restaurant"
):
    db = get_db()
    cursor = db.cursor()

    plan = normalize_plan(plan)
    business_type = normalize_business_type(business_type)
    defaults = get_business_type_defaults(business_type)

    cursor.execute("""
        INSERT INTO tenants (name, slug, business_type, plan, is_active)
        VALUES (?, ?, ?, ?, 1)
    """, (name, slug, business_type, plan))

    tenant_id = cursor.lastrowid
    default_llm_enabled = 1 if has_feature(plan, "ai_chat") else 0
    restaurant_name_en = translate_to_english(name)
    welcome_message_en = translate_to_english(defaults["welcome_message"])

    cursor.execute("""
        INSERT INTO tenant_settings (
            tenant_id,
            restaurant_name,
            restaurant_name_en,
            phone,
            email,
            address,
            address_en,
            welcome_message,
            welcome_message_en,
            max_capacity,
            open_hour,
            close_hour,
            primary_color,
            widget_title,
            widget_enabled,
            llm_enabled
        )
        VALUES (?, ?, ?, '', '', '', '', ?, ?, ?, ?, ?, '#1e88ff', ?, 1, ?)
    """, (
        tenant_id,
        name,
        restaurant_name_en,
        defaults["welcome_message"],
        welcome_message_en,
        max_capacity,
        open_hour,
        close_hour,
        defaults["widget_title"],
        default_llm_enabled,
    ))

    db.commit()
    db.close()
    return tenant_id


def update_tenant(
    tenant_id,
    name,
    slug,
    plan="basic",
    business_type="restaurant"
):
    plan = normalize_plan(plan)
    business_type = normalize_business_type(business_type)

    db = get_db()
    db.execute("""
        UPDATE tenants
        SET name = ?,
            slug = ?,
            plan = ?,
            business_type = ?
        WHERE id = ?
    """, (name, slug, plan, business_type, tenant_id))

    default_llm_enabled = 1 if has_feature(plan, "ai_chat") else 0

    db.execute("""
        UPDATE tenant_settings
        SET llm_enabled = ?
        WHERE tenant_id = ?
    """, (default_llm_enabled, tenant_id))

    db.commit()
    db.close()


def update_tenant_business_type(tenant_id, business_type):
    business_type = normalize_business_type(business_type)
    defaults = get_business_type_defaults(business_type)

    db = get_db()
    db.execute("""
        UPDATE tenants
        SET business_type = ?
        WHERE id = ?
    """, (business_type, tenant_id))

    current_settings = db.execute("""
        SELECT welcome_message, widget_title
        FROM tenant_settings
        WHERE tenant_id = ?
    """, (tenant_id,)).fetchone()

    if current_settings:
        current_settings = dict(current_settings)

        if not current_settings.get("welcome_message"):
            db.execute("""
                UPDATE tenant_settings
                SET welcome_message = ?
                WHERE tenant_id = ?
            """, (defaults["welcome_message"], tenant_id))

        if not current_settings.get("widget_title"):
            db.execute("""
                UPDATE tenant_settings
                SET widget_title = ?
                WHERE tenant_id = ?
            """, (defaults["widget_title"], tenant_id))

    db.commit()
    db.close()


def update_tenant_plan(tenant_id, plan):
    plan = normalize_plan(plan)
    default_llm_enabled = 1 if has_feature(plan, "ai_chat") else 0

    db = get_db()
    db.execute("""
        UPDATE tenants
        SET plan = ?
        WHERE id = ?
    """, (plan, tenant_id))

    db.execute("""
        UPDATE tenant_settings
        SET llm_enabled = ?
        WHERE tenant_id = ?
    """, (default_llm_enabled, tenant_id))

    db.commit()
    db.close()


def update_tenant_settings(
    tenant_id,
    restaurant_name,
    phone,
    email,
    address,
    welcome_message,
    max_capacity,
    open_hour,
    close_hour,
    primary_color,
    widget_title,
    widget_enabled,
    llm_enabled
):
    restaurant_name_en = translate_to_english(restaurant_name)
    address_en = translate_to_english(address)
    welcome_message_en = translate_to_english(welcome_message)

    db = get_db()
    db.execute("""
        UPDATE tenant_settings
        SET restaurant_name = ?,
            restaurant_name_en = ?,
            phone = ?,
            email = ?,
            address = ?,
            address_en = ?,
            welcome_message = ?,
            welcome_message_en = ?,
            max_capacity = ?,
            open_hour = ?,
            close_hour = ?,
            primary_color = ?,
            widget_title = ?,
            widget_enabled = ?,
            llm_enabled = ?
        WHERE tenant_id = ?
    """, (
        restaurant_name,
        restaurant_name_en,
        phone,
        email,
        address,
        address_en,
        welcome_message,
        welcome_message_en,
        max_capacity,
        open_hour,
        close_hour,
        primary_color,
        widget_title,
        widget_enabled,
        llm_enabled,
        tenant_id
    ))
    db.commit()
    db.close()


def list_tenants():
    db = get_db()
    rows = db.execute("""
        SELECT t.id,
               t.name,
               t.slug,
               t.business_type,
               t.plan,
               t.status,
               t.trial_end_date,
               t.is_active,
               t.created_at,
               ts.restaurant_name,
               ts.phone,
               ts.max_capacity,
               ts.llm_enabled
        FROM tenants t
        LEFT JOIN tenant_settings ts ON ts.tenant_id = t.id
        ORDER BY t.id DESC
    """).fetchall()
    db.close()

    result = []

    for r in rows:
        item = dict(r)
        item["business_type"] = normalize_business_type(item.get("business_type"))
        item["business_type_label"] = get_business_type_label(item["business_type"])
        item["plan"] = normalize_plan(item.get("plan"))
        item["status"] = (item.get("status") or "trial").strip().lower()
        item["trial_end_date"] = item.get("trial_end_date") or ""
        item["plan_label"] = get_plan_label(item["plan"])
        item["ai_enabled_by_plan"] = has_feature(item["plan"], "ai_chat")
        item["upsell_enabled_by_plan"] = has_feature(item["plan"], "upsell")
        item["product_images_enabled_by_plan"] = has_feature(item["plan"], "product_images")
        item["sales_recommendations_enabled_by_plan"] = has_feature(item["plan"], "sales_recommendations")
        result.append(item)

    return result


def deactivate_tenant(tenant_id):
    db = get_db()
    db.execute("""
        UPDATE tenants
        SET is_active = 0
        WHERE id = ?
    """, (tenant_id,))
    db.commit()
    db.close()


def activate_tenant(tenant_id):
    db = get_db()
    db.execute("""
        UPDATE tenants
        SET is_active = 1
        WHERE id = ?
    """, (tenant_id,))
    db.commit()
    db.close()


def delete_tenant(tenant_id):
    db = get_db()

    db.execute("DELETE FROM menu_items WHERE tenant_id = ?", (tenant_id,))
    db.execute("DELETE FROM menu_categories WHERE tenant_id = ?", (tenant_id,))
    db.execute("DELETE FROM reservations WHERE tenant_id = ?", (tenant_id,))
    db.execute("DELETE FROM analytics WHERE tenant_id = ?", (tenant_id,))
    db.execute("DELETE FROM conversation_state WHERE tenant_id = ?", (tenant_id,))
    db.execute("DELETE FROM users WHERE tenant_id = ?", (tenant_id,))
    db.execute("DELETE FROM tenant_settings WHERE tenant_id = ?", (tenant_id,))
    db.execute("DELETE FROM tenants WHERE id = ?", (tenant_id,))

    db.commit()
    db.close()