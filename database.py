import os
import sqlite3
from config import (
    DATABASE_PATH,
    DEFAULT_TENANT_NAME,
    DEFAULT_TENANT_CAPACITY,
    DEFAULT_ADMIN_USERNAME,
    DEFAULT_ADMIN_PASSWORD,
    DEFAULT_ADMIN_ROLE,
    DEFAULT_OPEN_HOUR,
    DEFAULT_CLOSE_HOUR,
)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))


def get_absolute_database_path():
    if os.path.isabs(DATABASE_PATH):
        return DATABASE_PATH
    return os.path.abspath(os.path.join(BASE_DIR, DATABASE_PATH))


def ensure_data_dir():
    db_path = get_absolute_database_path()
    data_dir = os.path.dirname(db_path)
    os.makedirs(data_dir, exist_ok=True)


def get_db():
    ensure_data_dir()
    db_path = get_absolute_database_path()
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def column_exists(cursor, table_name, column_name):
    rows = cursor.execute(f"PRAGMA table_info({table_name})").fetchall()
    return any(row[1] == column_name for row in rows)


def add_column_if_missing(cursor, table_name, column_name, column_sql):
    if not column_exists(cursor, table_name, column_name):
        cursor.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_sql}")


def init_db():
    conn = get_db()
    c = conn.cursor()

    c.execute("""
    CREATE TABLE IF NOT EXISTS tenants (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        slug TEXT UNIQUE,
        business_type TEXT DEFAULT 'restaurant',
        plan TEXT DEFAULT 'basic',
        is_active INTEGER DEFAULT 1,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    )
    """)

    c.execute("""
    CREATE TABLE IF NOT EXISTS tenant_settings (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        tenant_id INTEGER NOT NULL UNIQUE,
        restaurant_name TEXT,
        phone TEXT,
        email TEXT,
        address TEXT,
        website TEXT DEFAULT '',
        working_hours TEXT DEFAULT '',
        welcome_message TEXT,
        max_capacity INTEGER DEFAULT 20,
        open_hour INTEGER DEFAULT 10,
        close_hour INTEGER DEFAULT 22,
        primary_color TEXT DEFAULT '#1e88ff',
        widget_title TEXT DEFAULT 'Restaurant AI Chatbot',
        widget_enabled INTEGER DEFAULT 1,
        llm_enabled INTEGER DEFAULT 0,
        FOREIGN KEY (tenant_id) REFERENCES tenants(id)
    )
    """)

    c.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        tenant_id INTEGER NOT NULL,
        username TEXT NOT NULL UNIQUE,
        password TEXT NOT NULL,
        role TEXT NOT NULL DEFAULT 'staff',
        is_active INTEGER DEFAULT 1,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (tenant_id) REFERENCES tenants(id)
    )
    """)

    c.execute("""
    CREATE TABLE IF NOT EXISTS password_reset_requests (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT NOT NULL,
        contact TEXT NOT NULL,
        message TEXT DEFAULT '',
        status TEXT DEFAULT 'new',
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    )
    """)

    c.execute("""
    CREATE TABLE IF NOT EXISTS demo_requests (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        business_name TEXT NOT NULL,
        contact_name TEXT DEFAULT '',
        phone TEXT NOT NULL,
        email TEXT DEFAULT '',
        business_type TEXT DEFAULT '',
        message TEXT DEFAULT '',
        status TEXT DEFAULT 'new',
        plan_interest TEXT DEFAULT '',
        budget TEXT DEFAULT '',
        lead_source TEXT DEFAULT '',
        priority TEXT DEFAULT 'normal',
        admin_note TEXT DEFAULT '',
        handled_by TEXT DEFAULT '',
        next_contact TEXT DEFAULT '',
        updated_at TEXT DEFAULT '',
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
)
""")

    c.execute("""
    CREATE TABLE IF NOT EXISTS reservations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        tenant_id INTEGER NOT NULL,
        name TEXT NOT NULL,
        phone TEXT NOT NULL,
        date TEXT NOT NULL,
        time TEXT NOT NULL,
        people INTEGER NOT NULL,
        source TEXT DEFAULT 'chatbot',
        status TEXT DEFAULT 'confirmed',
        notes TEXT DEFAULT '',
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (tenant_id) REFERENCES tenants(id)
    )
    """)

    c.execute("""
    CREATE TABLE IF NOT EXISTS analytics (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        tenant_id INTEGER,
        event_type TEXT NOT NULL,
        payload TEXT DEFAULT '',
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (tenant_id) REFERENCES tenants(id)
    )
    """)

    c.execute("""
    CREATE TABLE IF NOT EXISTS conversation_state (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        session_key TEXT NOT NULL UNIQUE,
        tenant_id INTEGER NOT NULL,
        state_json TEXT NOT NULL,
        updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (tenant_id) REFERENCES tenants(id)
    )
    """)

    c.execute("""
    CREATE TABLE IF NOT EXISTS menu_categories (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        tenant_id INTEGER NOT NULL,
        name TEXT NOT NULL,
        sort_order INTEGER DEFAULT 0,
        is_active INTEGER DEFAULT 1,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (tenant_id) REFERENCES tenants(id)
    )
    """)

    c.execute("""
    CREATE TABLE IF NOT EXISTS menu_items (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        tenant_id INTEGER NOT NULL,
        category_id INTEGER NOT NULL,
        name TEXT NOT NULL,
        description TEXT DEFAULT '',
        price REAL DEFAULT 0,
        image_url TEXT DEFAULT '',
        upsell_drink TEXT DEFAULT '',
        upsell_dessert TEXT DEFAULT '',
        upsell_side TEXT DEFAULT '',
        is_active INTEGER DEFAULT 1,
        sort_order INTEGER DEFAULT 0,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (tenant_id) REFERENCES tenants(id),
        FOREIGN KEY (category_id) REFERENCES menu_categories(id)
    )
    """)

    add_column_if_missing(c, "tenants", "plan", "plan TEXT DEFAULT 'basic'")
    add_column_if_missing(c, "tenants", "business_type", "business_type TEXT DEFAULT 'restaurant'")
    add_column_if_missing(c, "tenants", "is_active", "is_active INTEGER DEFAULT 1")
    add_column_if_missing(c, "tenants", "is_demo", "is_demo INTEGER DEFAULT 0")


    add_column_if_missing(c, "tenant_settings", "website", "website TEXT DEFAULT ''")
    add_column_if_missing(c, "tenant_settings", "working_hours", "working_hours TEXT DEFAULT ''")
    add_column_if_missing(c, "tenant_settings", "primary_color", "primary_color TEXT DEFAULT '#1e88ff'")
    add_column_if_missing(c, "tenant_settings", "widget_title", "widget_title TEXT DEFAULT 'Restaurant AI Chatbot'")
    add_column_if_missing(c, "tenant_settings", "widget_enabled", "widget_enabled INTEGER DEFAULT 1")
    add_column_if_missing(c, "tenant_settings", "llm_enabled", "llm_enabled INTEGER DEFAULT 0")
    add_column_if_missing(c, "tenant_settings", "max_capacity", "max_capacity INTEGER DEFAULT 20")
    add_column_if_missing(c, "tenant_settings", "open_hour", "open_hour INTEGER DEFAULT 10")
    add_column_if_missing(c, "tenant_settings", "close_hour", "close_hour INTEGER DEFAULT 22")

    add_column_if_missing(c, "menu_items", "image_url", "image_url TEXT DEFAULT ''")
    add_column_if_missing(c, "menu_items", "upsell_drink", "upsell_drink TEXT DEFAULT ''")
    add_column_if_missing(c, "menu_items", "upsell_dessert", "upsell_dessert TEXT DEFAULT ''")
    add_column_if_missing(c, "menu_items", "upsell_side", "upsell_side TEXT DEFAULT ''")
    add_column_if_missing(c, "menu_items", "sort_order", "sort_order INTEGER DEFAULT 0")
    add_column_if_missing(c, "menu_items", "is_active", "is_active INTEGER DEFAULT 1")
    add_column_if_missing(c, "menu_categories", "name_en", "name_en TEXT DEFAULT ''")

    add_column_if_missing(c, "menu_items", "name_en", "name_en TEXT DEFAULT ''")
    add_column_if_missing(c, "menu_items", "description_en", "description_en TEXT DEFAULT ''")
    add_column_if_missing(c, "menu_items", "upsell_drink_en", "upsell_drink_en TEXT DEFAULT ''")
    add_column_if_missing(c, "menu_items", "upsell_dessert_en", "upsell_dessert_en TEXT DEFAULT ''")
    add_column_if_missing(c, "menu_items", "upsell_side_en", "upsell_side_en TEXT DEFAULT ''")
    add_column_if_missing(c, "password_reset_requests", "admin_note", "admin_note TEXT DEFAULT ''")
    add_column_if_missing(c, "password_reset_requests", "handled_by", "handled_by TEXT DEFAULT ''")
    add_column_if_missing(c, "password_reset_requests", "updated_at", "updated_at TEXT DEFAULT ''")
    add_column_if_missing(c, "demo_requests", "plan_interest", "plan_interest TEXT DEFAULT ''")
    add_column_if_missing(c, "demo_requests", "budget", "budget TEXT DEFAULT ''")
    add_column_if_missing(c, "demo_requests", "lead_source", "lead_source TEXT DEFAULT ''")
    add_column_if_missing(c, "demo_requests", "priority", "priority TEXT DEFAULT 'normal'")
    add_column_if_missing(c, "demo_requests", "admin_note", "admin_note TEXT DEFAULT ''")
    add_column_if_missing(c, "demo_requests", "handled_by", "handled_by TEXT DEFAULT ''")
    add_column_if_missing(c, "demo_requests", "next_contact", "next_contact TEXT DEFAULT ''")
    add_column_if_missing(c, "demo_requests", "updated_at", "updated_at TEXT DEFAULT ''")

    conn.commit()
    conn.close()

def seed_demo_tenants(c):
    demo_tenants = [
        {
            "name": "Demo Bar",
            "slug": "demo-bar",
            "business_type": "bar",
            "widget_title": "Bar AI Chatbot",
            "welcome": "👋 Здравейте! Мога да помогна с напитки, коктейли, мезета или резервация.",
            "color": "#7c3aed",
            "categories": {
                "Коктейли": [
                    ("Мохито", "Ром, лайм, мента, сода", 8.90, "Плато мезета", "", ""),
                    ("Aperol Spritz", "Aperol, prosecco и сода", 9.90, "Плато мезета", "", ""),
                ],
                "Бира": [
                    ("Наливна бира", "Студена наливна бира", 5.50, "", "", "Плато мезета"),
                    ("Крафт бира", "Подбрана крафт бира", 7.50, "", "", "Ядки"),
                ],
                "Мезета": [
                    ("Плато мезета", "Подбрани мезета за компания", 18.90, "Наливна бира", "", ""),
                    ("Ядки", "Микс печени ядки", 6.90, "Крафт бира", "", ""),
                ],
            }
        },
        {
            "name": "Demo Cafe",
            "slug": "demo-cafe",
            "business_type": "cafe",
            "widget_title": "Cafe AI Chatbot",
            "welcome": "👋 Здравейте! Мога да помогна с кафе, десерти, закуски или резервация.",
            "color": "#10b981",
            "categories": {
                "Кафе": [
                    ("Еспресо", "Класическо еспресо", 2.90, "", "Кроасан", ""),
                    ("Капучино", "Капучино с млечна пяна", 4.20, "", "Чийзкейк", ""),
                ],
                "Десерти": [
                    ("Чийзкейк", "Домашен чийзкейк", 7.50, "Капучино", "", ""),
                    ("Шоколадова торта", "Богата шоколадова торта", 8.50, "Лате", "", ""),
                ],
                "Закуски": [
                    ("Кроасан", "Маслен кроасан", 4.90, "Капучино", "", ""),
                    ("Сандвич", "Свеж сандвич със сирене и зеленчуци", 6.90, "Лимонада", "", ""),
                ],
            }
        }
    ]

    for demo in demo_tenants:
        existing = c.execute("""
            SELECT id FROM tenants
            WHERE slug = ?
            LIMIT 1
        """, (demo["slug"],)).fetchone()

        if existing:
            demo_tenant_id = existing["id"]

            c.execute("""
                UPDATE tenants
                SET is_demo = 1,
                    plan = 'premium',
                    business_type = ?,
                    is_active = 1
                WHERE id = ?
            """, (demo["business_type"], demo_tenant_id))
        else:
            c.execute("""
                INSERT INTO tenants (name, slug, business_type, plan, is_active, is_demo)
                VALUES (?, ?, ?, 'premium', 1, 1)
            """, (demo["name"], demo["slug"], demo["business_type"]))

            demo_tenant_id = c.lastrowid

        c.execute("""
            INSERT OR IGNORE INTO tenant_settings (
                tenant_id,
                restaurant_name,
                phone,
                email,
                address,
                website,
                working_hours,
                welcome_message,
                max_capacity,
                open_hour,
                close_hour,
                primary_color,
                widget_title,
                widget_enabled,
                llm_enabled
            )
            VALUES (?, ?, '+359 88 000 0000', 'demo@reservy.bg',
                    'Демо адрес, България',
                    'https://reservy.bg',
                    'Понеделник - Неделя: 09:00 - 23:00',
                    ?, 40, 9, 23, ?, ?, 1, 1)
        """, (
            demo_tenant_id,
            demo["name"],
            demo["welcome"],
            demo["color"],
            demo["widget_title"]
        ))

        c.execute("""
            UPDATE tenant_settings
            SET restaurant_name = ?,
                welcome_message = ?,
                primary_color = ?,
                widget_title = ?,
                llm_enabled = 1
            WHERE tenant_id = ?
        """, (
            demo["name"],
            demo["welcome"],
            demo["color"],
            demo["widget_title"],
            demo_tenant_id
        ))

        existing_categories = c.execute("""
            SELECT COUNT(*) AS total
            FROM menu_categories
            WHERE tenant_id = ?
        """, (demo_tenant_id,)).fetchone()["total"]

        if existing_categories == 0:
            for cat_index, (cat_name, items) in enumerate(demo["categories"].items(), start=1):
                c.execute("""
                    INSERT INTO menu_categories (tenant_id, name, sort_order, is_active, name_en)
                    VALUES (?, ?, ?, 1, '')
                """, (demo_tenant_id, cat_name, cat_index))

                category_id = c.lastrowid

                for item_index, item in enumerate(items, start=1):
                    name, description, price, upsell_drink, upsell_dessert, upsell_side = item

                    c.execute("""
                        INSERT INTO menu_items (
                            tenant_id, category_id, name, description, price,
                            image_url, upsell_drink, upsell_dessert, upsell_side,
                            is_active, sort_order
                        )
                        VALUES (?, ?, ?, ?, ?, '', ?, ?, ?, 1, ?)
                    """, (
                        demo_tenant_id,
                        category_id,
                        name,
                        description,
                        price,
                        upsell_drink,
                        upsell_dessert,
                        upsell_side,
                        item_index
                    ))

def seed_data():
    conn = get_db()
    c = conn.cursor()

    c.execute("""
    INSERT OR IGNORE INTO tenants (id, name, slug, business_type, plan, is_active, is_demo)
    VALUES (1, ?, 'demo-restaurant', 'restaurant', 'premium', 1, 1)
    """, (DEFAULT_TENANT_NAME,))
    
    c.execute("""
    UPDATE tenants
    SET is_demo = 1
    WHERE id = 1 OR slug = 'demo-restaurant'
    """)

    demo_tenants = [
    {
        "name": "Demo Bar",
        "slug": "demo-bar",
        "business_type": "bar",
        "widget_title": "Bar AI Chatbot",
        "welcome": "👋 Здравейте! Мога да помогна с напитки, коктейли, мезета или резервация.",
        "color": "#7c3aed",
        "categories": {
            "Коктейли": [
                ("Мохито", "Ром, лайм, мента, сода", 8.90, "Плато мезета", "", ""),
                ("Aperol Spritz", "Aperol, prosecco и сода", 9.90, "Плато мезета", "", ""),
            ],
            "Бира": [
                ("Наливна бира", "Студена наливна бира", 5.50, "", "", "Плато мезета"),
                ("Крафт бира", "Подбрана крафт бира", 7.50, "", "", "Ядки"),
            ],
            "Мезета": [
                ("Плато мезета", "Подбрани мезета за компания", 18.90, "Наливна бира", "", ""),
                ("Ядки", "Микс печени ядки", 6.90, "Крафт бира", "", ""),
            ],
        }
    },
    {
        "name": "Demo Cafe",
        "slug": "demo-cafe",
        "business_type": "cafe",
        "widget_title": "Cafe AI Chatbot",
        "welcome": "👋 Здравейте! Мога да помогна с кафе, десерти, закуски или резервация.",
        "color": "#10b981",
        "categories": {
            "Кафе": [
                ("Еспресо", "Класическо еспресо", 2.90, "", "Кроасан", ""),
                ("Капучино", "Капучино с млечна пяна", 4.20, "", "Чийзкейк", ""),
            ],
            "Десерти": [
                ("Чийзкейк", "Домашен чийзкейк", 7.50, "Капучино", "", ""),
                ("Шоколадова торта", "Богата шоколадова торта", 8.50, "Лате", "", ""),
            ],
            "Закуски": [
                ("Кроасан", "Маслен кроасан", 4.90, "Капучино", "", ""),
                ("Сандвич", "Свеж сандвич със сирене и зеленчуци", 6.90, "Лимонада", "", ""),
            ],
        }
    }
]



    c.execute("""
    INSERT OR IGNORE INTO tenant_settings (
        tenant_id,
        restaurant_name,
        phone,
        email,
        address,
        website,
        working_hours,
        welcome_message,
        max_capacity,
        open_hour,
        close_hour,
        primary_color,
        widget_title,
        widget_enabled,
        llm_enabled
    )
    VALUES (?, ?, '+359 88 123 4567', 'info@demorestaurant.bg',
            'ул. Витоша 123, София, България',
            'https://demorestaurant.bg',
            'Понеделник - Неделя: 09:00 - 23:00',
            ?, ?, ?, ?, '#1e88ff', 'Restaurant AI Chatbot', 1, 1)
    """, (
        1,
        DEFAULT_TENANT_NAME,
        "👋 Здравейте! Мога да помогна с напитки, резервации и информация.",
        DEFAULT_TENANT_CAPACITY,
        DEFAULT_OPEN_HOUR,
        DEFAULT_CLOSE_HOUR
    ))

    c.execute("""
    UPDATE tenant_settings
    SET restaurant_name = COALESCE(NULLIF(restaurant_name, ''), ?),
        phone = COALESCE(NULLIF(phone, ''), '+359 88 123 4567'),
        email = COALESCE(NULLIF(email, ''), 'info@demorestaurant.bg'),
        address = COALESCE(NULLIF(address, ''), 'ул. Витоша 123, София, България'),
        website = COALESCE(NULLIF(website, ''), 'https://demorestaurant.bg'),
        working_hours = COALESCE(NULLIF(working_hours, ''), 'Понеделник - Неделя: 09:00 - 23:00'),
        widget_title = COALESCE(NULLIF(widget_title, ''), 'Restaurant AI Chatbot'),
        llm_enabled = 1
    WHERE tenant_id = 1
    """, (DEFAULT_TENANT_NAME,))

    c.execute("""
    INSERT OR IGNORE INTO users (
        id, tenant_id, username, password, role, is_active
    )
    VALUES (1, 1, ?, ?, ?, 1)
    """, (
        DEFAULT_ADMIN_USERNAME,
        DEFAULT_ADMIN_PASSWORD,
        DEFAULT_ADMIN_ROLE
    ))

    c.execute("""
    UPDATE users
    SET role = 'super_admin'
    WHERE id = 1
    """)

    c.execute("INSERT OR IGNORE INTO menu_categories (id, tenant_id, name, sort_order, is_active) VALUES (1, 1, 'Салати', 1, 1)")
    c.execute("INSERT OR IGNORE INTO menu_categories (id, tenant_id, name, sort_order, is_active) VALUES (2, 1, 'Основни', 2, 1)")
    c.execute("INSERT OR IGNORE INTO menu_categories (id, tenant_id, name, sort_order, is_active) VALUES (3, 1, 'Десерти', 3, 1)")
    c.execute("INSERT OR IGNORE INTO menu_categories (id, tenant_id, name, sort_order, is_active) VALUES (4, 1, 'Напитки', 4, 1)")
    c.execute("INSERT OR IGNORE INTO menu_categories (id, tenant_id, name, sort_order, is_active) VALUES (5, 1, 'Upsell добавки', 5, 1)")

    items = [
        (1, 1, 1, 'Цезар', 'Класическа салата с пиле, крутони и пармезан', 12.90, '', 'Домашна лимонада', 'Чийзкейк', 'Пържени картофки', 1, 1),
        (2, 1, 1, 'Гръцка салата', 'Домати, краставици, сирене, маслини', 10.50, '', 'Домашна лимонада', 'Чийзкейк', 'Чеснов сос', 1, 2),
        (3, 1, 2, 'Пилешка пържола', 'С гарнитура по избор', 16.90, '', 'Домашна лимонада', 'Чийзкейк', 'Пържени картофки', 1, 1),
        (4, 1, 2, 'Паста Карбонара', 'Кремообразен сос, бекон и пармезан', 14.90, '', 'Чаша бяло вино', 'Тирамису', 'Чесново хлебче', 1, 2),
        (5, 1, 2, 'Пица Маргарита', 'Доматен сос, моцарела, босилек', 10.50, '', 'Домашна лимонада', 'Тирамису', 'Чеснов сос', 1, 3),
        (6, 1, 2, 'Бургер Класик', 'Телешко кюфте, салата, домати, сос', 12.90, '', 'Наливна бира', 'Чийзкейк', 'Пържени картофки', 1, 4),
        (7, 1, 3, 'Чийзкейк', 'Домашен чийзкейк', 7.50, '', 'Капучино', '', '', 1, 1),
        (8, 1, 3, 'Тирамису', 'Класическо италианско тирамису', 8.50, '', 'Капучино', '', '', 1, 2),
        (9, 1, 4, 'Домашна лимонада', 'Свежа домашна лимонада', 4.90, '', '', 'Чийзкейк', '', 1, 1),
        (10, 1, 4, 'Наливна бира', 'Студена наливна бира', 5.50, '', '', '', 'Плато мезета', 1, 2),
        (11, 1, 4, 'Капучино', 'Класическо капучино', 4.20, '', '', 'Чийзкейк', '', 1, 3),
        (12, 1, 5, 'Пържени картофки', 'Хрупкави картофки', 5.90, '', 'Наливна бира', '', 'Чеснов сос', 1, 1),
        (13, 1, 5, 'Чеснов сос', 'Домашен чеснов сос', 1.50, '', '', '', '', 1, 2),
        (14, 1, 5, 'Плато мезета', 'Подбрани мезета за компания', 18.90, '', 'Наливна бира', '', '', 1, 3),
    ]

    c.executemany("""
    INSERT OR IGNORE INTO menu_items (
        id, tenant_id, category_id, name, description, price,
        image_url, upsell_drink, upsell_dessert, upsell_side,
        is_active, sort_order
    )
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, items)

    category_translations = {
        "Салати": "Salads",
        "Основни": "Main dishes",
        "Десерти": "Desserts",
        "Напитки": "Drinks",
        "Upsell добавки": "Upsell extras",
    }

    for bg_name, en_name in category_translations.items():
        c.execute("""
            UPDATE menu_categories
            SET name_en = ?
            WHERE tenant_id = 1 AND name = ? AND (name_en IS NULL OR name_en = '')
        """, (en_name, bg_name))

    item_translations = {
        "Цезар": ("Caesar salad", "Classic Caesar salad with chicken, croutons and parmesan"),
        "Гръцка салата": ("Greek salad", "Tomatoes, cucumbers, cheese and olives"),
        "Пилешка пържола": ("Chicken steak", "Chicken fillet with side dish"),
        "Паста Карбонара": ("Pasta Carbonara", "Creamy sauce, bacon and parmesan"),
        "Пица Маргарита": ("Pizza Margherita", "Tomato sauce, mozzarella and basil"),
        "Бургер Класик": ("Classic burger", "Beef patty, lettuce, tomatoes and sauce"),
        "Чийзкейк": ("Cheesecake", "Homemade cheesecake"),
        "Тирамису": ("Tiramisu", "Classic Italian tiramisu"),
        "Домашна лимонада": ("Homemade lemonade", "Fresh homemade lemonade"),
        "Наливна бира": ("Draft beer", "Cold draft beer"),
        "Капучино": ("Cappuccino", "Classic cappuccino"),
        "Пържени картофки": ("French fries", "Crispy french fries"),
        "Чеснов сос": ("Garlic sauce", "Homemade garlic sauce"),
        "Плато мезета": ("Meat platter", "Selected appetizers for sharing"),
    }

    for bg_name, data in item_translations.items():
        en_name, en_description = data

        c.execute("""
            UPDATE menu_items
            SET name_en = ?,
                description_en = ?
            WHERE tenant_id = 1
              AND name = ?
              AND (name_en IS NULL OR name_en = '')
        """, (en_name, en_description, bg_name))

    upsell_translations = {
        "Домашна лимонада": "Homemade lemonade",
        "Чийзкейк": "Cheesecake",
        "Пържени картофки": "French fries",
        "Айрян": "Ayran",
        "Чеснов сос": "Garlic sauce",
        "Чаша бяло вино": "Glass of white wine",
        "Тирамису": "Tiramisu",
        "Чесново хлебче": "Garlic bread",
        "Наливна бира": "Draft beer",
        "Капучино": "Cappuccino",
        "Плато мезета": "Meat platter",
    }

    rows = c.execute("""
        SELECT id, upsell_drink, upsell_dessert, upsell_side
        FROM menu_items
        WHERE tenant_id = 1
    """).fetchall()

    for row in rows:
        drink_en = upsell_translations.get(row["upsell_drink"] or "", "")
        dessert_en = upsell_translations.get(row["upsell_dessert"] or "", "")
        side_en = upsell_translations.get(row["upsell_side"] or "", "")

        c.execute("""
            UPDATE menu_items
            SET upsell_drink_en = COALESCE(NULLIF(upsell_drink_en, ''), ?),
                upsell_dessert_en = COALESCE(NULLIF(upsell_dessert_en, ''), ?),
                upsell_side_en = COALESCE(NULLIF(upsell_side_en, ''), ?)
            WHERE id = ?
        """, (drink_en, dessert_en, side_en, row["id"]))

    seed_demo_tenants(c)

    conn.commit()
    conn.close()