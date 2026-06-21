import requests
import shutil
import cloudinary.uploader
from datetime import datetime
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

def create_database_backup():
    db_path = get_absolute_database_path()

    if not os.path.exists(db_path):
        return ""

    timestamp = datetime.now().strftime("%Y_%m_%d_%H_%M_%S")
    backup_name = f"reservy_backup_{timestamp}.db"

    local_backup_dir = os.path.join(BASE_DIR, "backups")
    os.makedirs(local_backup_dir, exist_ok=True)

    local_backup_path = os.path.join(local_backup_dir, backup_name)

    shutil.copy2(db_path, local_backup_path)

    try:
        result = cloudinary.uploader.upload(
            local_backup_path,
            folder="reservy/database_backups",
            resource_type="raw",
            public_id=backup_name
        )

        return result.get("secure_url", "")

    except Exception as e:
        print("DATABASE BACKUP ERROR:", e)
        return local_backup_path
    
def list_database_backups():
    try:
        result = cloudinary.api.resources(
            type="upload",
            resource_type="raw",
            prefix="reservy/database_backups",
            max_results=50
        )

        backups = []

        for item in result.get("resources", []):
            backups.append({
                "public_id": item.get("public_id", ""),
                "name": item.get("public_id", "").split("/")[-1],
                "url": item.get("secure_url", ""),
                "created_at": item.get("created_at", ""),
                "bytes": item.get("bytes", 0),
            })

        backups.sort(key=lambda x: x["created_at"], reverse=True)
        return backups

    except Exception as e:
        print("LIST BACKUPS ERROR:", e)
        return []


def format_backup_size(bytes_value):
    try:
        size = int(bytes_value or 0)

        if size >= 1024 * 1024:
            return f"{round(size / (1024 * 1024), 2)} MB"

        if size >= 1024:
            return f"{round(size / 1024, 2)} KB"

        return f"{size} B"

    except Exception:
        return "—"
    
def restore_database_from_url(backup_url):
    if not backup_url:
        return False

    db_path = get_absolute_database_path()

    try:
        # защитен backup преди restore
        create_database_backup()

        response = requests.get(backup_url, timeout=60)

        if response.status_code != 200:
            print("RESTORE DOWNLOAD ERROR:", response.status_code)
            return False

        temp_restore_path = db_path + ".restore_tmp"

        with open(temp_restore_path, "wb") as f:
            f.write(response.content)

        # проверка дали файлът е валидна SQLite база
        test_conn = sqlite3.connect(temp_restore_path)
        test_conn.execute("SELECT name FROM sqlite_master LIMIT 1")
        test_conn.close()

        shutil.copy2(temp_restore_path, db_path)
        os.remove(temp_restore_path)

        return True

    except Exception as e:
        print("RESTORE DATABASE ERROR:", e)
        return False
    
def delete_database_backup(public_id):
    if not public_id:
        return False

    try:
        result = cloudinary.uploader.destroy(
            public_id,
            resource_type="raw"
        )

        return result.get("result") in ["ok", "not found"]

    except Exception as e:
        print("DELETE BACKUP ERROR:", e)
        return False

def delete_old_backups(limit=30):
    try:
        backups = list_database_backups()

        old_backups = backups[limit:]

        for backup in old_backups:
            public_id = backup.get("public_id", "")

            if public_id:
                delete_database_backup(public_id)

        return True

    except Exception as e:
        print("DELETE OLD BACKUPS ERROR:", e)
        return False

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
CREATE TABLE IF NOT EXISTS dismissed_notifications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tenant_id INTEGER NOT NULL,
    reservation_id INTEGER NOT NULL,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
)
""")

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
        customer_email TEXT DEFAULT '',
        date TEXT NOT NULL,
        time TEXT NOT NULL,
        people INTEGER NOT NULL,
        source TEXT DEFAULT 'chatbot',
        status TEXT DEFAULT 'confirmed',
        notes TEXT DEFAULT '',
        reminder_24_sent INTEGER DEFAULT 0,
        reminder_2_sent INTEGER DEFAULT 0,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (tenant_id) REFERENCES tenants(id)
    )
    """)

    c.execute("""
    CREATE TABLE IF NOT EXISTS banned_customers (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        tenant_id INTEGER NOT NULL,
        phone TEXT NOT NULL,
        reason TEXT DEFAULT '',
        created_by TEXT DEFAULT '',
        is_active INTEGER DEFAULT 1,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        updated_at TEXT DEFAULT '',
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
    add_column_if_missing(c, "tenants", "status", "status TEXT DEFAULT 'trial'")
    add_column_if_missing(c, "tenants", "trial_end_date", "trial_end_date TEXT DEFAULT ''")

    add_column_if_missing(c, "tenant_settings", "website", "website TEXT DEFAULT ''")
    add_column_if_missing(c, "tenant_settings", "working_hours", "working_hours TEXT DEFAULT ''")
    add_column_if_missing(c, "tenant_settings", "restaurant_name_en", "restaurant_name_en TEXT DEFAULT ''")
    add_column_if_missing(c, "tenant_settings", "address_en", "address_en TEXT DEFAULT ''")
    add_column_if_missing(c, "tenant_settings", "working_hours_en", "working_hours_en TEXT DEFAULT ''")
    add_column_if_missing(c, "tenant_settings", "welcome_message_en", "welcome_message_en TEXT DEFAULT ''")
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

    add_column_if_missing(c, "banned_customers", "reason", "reason TEXT DEFAULT ''")
    add_column_if_missing(c, "banned_customers", "created_by", "created_by TEXT DEFAULT ''")
    add_column_if_missing(c, "banned_customers", "is_active", "is_active INTEGER DEFAULT 1")
    add_column_if_missing(c, "banned_customers", "updated_at", "updated_at TEXT DEFAULT ''")
    add_column_if_missing(
    c,
    "reservations",
    "customer_email",
    "customer_email TEXT DEFAULT ''"
)
    
    add_column_if_missing(
        c,
        "reservations",
        "reminder_24_sent",
        "reminder_24_sent INTEGER DEFAULT 0"
)

    add_column_if_missing(
        c,
        "reservations",
        "reminder_2_sent",
        "reminder_2_sent INTEGER DEFAULT 0"
)

    conn.commit()
    conn.close()

def seed_demo_tenants(c):
    demo_tenants = [
        {
            "name": "Sea Lounge",
        "slug": "sea-lounge",
        "business_type": "bar",
        "widget_title": "Sea Lounge AI Chatbot",
        "welcome": "👋 Здравейте! Добре дошли в Sea Lounge. Мога да помогна с напитки, меню или резервация.",
        "color": "#2563eb",
        "categories": {
            "Коктейли": [
                ("Sea Mojito", "Ром, лайм, мента и сода", 9.90, "Плато мезета", "", ""),
                ("Blue Lagoon", "Водка, синьо кюрасо и лимонада", 10.90, "Плато мезета", "", ""),
            ],
            "Бира": [
                ("Наливна бира", "Студена наливна бира", 5.50, "", "", "Плато мезета"),
                ("Крафт бира", "Подбрана крафт бира", 7.90, "", "", "Ядки"),
            ],
            "Бар хапки": [
                ("Плато мезета", "Подбрани мезета за компания", 18.90, "Наливна бира", "", ""),
                ("Ядки", "Микс печени ядки", 6.90, "Крафт бира", "", ""),
            ],
        }
    },
    {
        "name": "Coffee Corner",
        "slug": "coffee-corner",
        "business_type": "cafe",
        "widget_title": "Coffee Corner AI Chatbot",
        "welcome": "👋 Здравейте! Добре дошли в Coffee Corner. Мога да помогна с кафе, десерти или резервация.",
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
    },
    {
        "name": "Varna Grill",
        "slug": "varna-grill",
        "business_type": "restaurant",
        "widget_title": "Varna Grill AI Chatbot",
        "welcome": "👋 Здравейте! Добре дошли във Varna Grill. Мога да помогна с меню, препоръки или резервация.",
        "color": "#f97316",
        "categories": {
            "Скара": [
                ("Пилешка пържола", "С гарнитура по избор", 16.90, "Наливна бира", "", "Пържени картофки"),
                ("Свински ребра", "Бавно печени ребра с BBQ сос", 22.90, "Наливна бира", "", "Чеснов сос"),
            ],
            "Салати": [
                ("Шопска салата", "Домати, краставици, сирене и чушка", 9.90, "Ракия", "", ""),
                ("Овчарска салата", "Богата салата със сирене, яйце и шунка", 11.90, "Ракия", "", ""),
            ],
            "Десерти": [
                ("Домашна торта", "Домашна торта с крем", 7.90, "Капучино", "", ""),
                ("Палачинка", "Палачинка с шоколад", 6.90, "Капучино", "", ""),
            ],
        }
    },
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
    INSERT OR IGNORE INTO tenants
    (id, name, slug, business_type, plan, is_active, is_demo, status)
    VALUES (1, ?, 'demo-restaurant', 'restaurant', 'premium', 1, 1, 'active')
    """, (DEFAULT_TENANT_NAME,))
    
    c.execute("""
    UPDATE tenants
    SET is_demo = 1
    WHERE id = 1 OR slug = 'demo-restaurant'
    """)

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