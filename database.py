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


def init_db():
    conn = get_db()
    c = conn.cursor()

    c.execute("""
    CREATE TABLE IF NOT EXISTS tenants (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        slug TEXT UNIQUE,
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
        welcome_message TEXT,
        max_capacity INTEGER DEFAULT 20,
        open_hour INTEGER DEFAULT 10,
        close_hour INTEGER DEFAULT 22,
        primary_color TEXT DEFAULT '#1e88ff',
        widget_title TEXT DEFAULT 'AI ChatBot - Ресторант',
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
        is_active INTEGER DEFAULT 1,
        sort_order INTEGER DEFAULT 0,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (tenant_id) REFERENCES tenants(id),
        FOREIGN KEY (category_id) REFERENCES menu_categories(id)
    )
    """)

    conn.commit()
    conn.close()


def seed_data():
    conn = get_db()
    c = conn.cursor()

    c.execute("""
    INSERT OR IGNORE INTO tenants (id, name, slug, is_active)
    VALUES (1, ?, 'demo-restaurant', 1)
    """, (DEFAULT_TENANT_NAME,))

    c.execute("""
    INSERT OR IGNORE INTO tenant_settings (
        tenant_id,
        restaurant_name,
        welcome_message,
        max_capacity,
        open_hour,
        close_hour
    )
    VALUES (?, ?, ?, ?, ?, ?)
    """, (
        1,
        DEFAULT_TENANT_NAME,
        "👋 Здравейте! С какво мога да помогна?",
        DEFAULT_TENANT_CAPACITY,
        DEFAULT_OPEN_HOUR,
        DEFAULT_CLOSE_HOUR
    ))

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
    INSERT OR IGNORE INTO menu_categories (id, tenant_id, name, sort_order, is_active)
    VALUES (1, 1, 'Салати', 1, 1)
    """)

    c.execute("""
    INSERT OR IGNORE INTO menu_categories (id, tenant_id, name, sort_order, is_active)
    VALUES (2, 1, 'Основни', 2, 1)
    """)

    c.execute("""
    INSERT OR IGNORE INTO menu_categories (id, tenant_id, name, sort_order, is_active)
    VALUES (3, 1, 'Десерти', 3, 1)
    """)

    c.execute("""
    INSERT OR IGNORE INTO menu_categories (id, tenant_id, name, sort_order, is_active)
    VALUES (4, 1, 'Напитки', 4, 1)
    """)

    c.execute("""
    INSERT OR IGNORE INTO menu_items (id, tenant_id, category_id, name, description, price, is_active, sort_order)
    VALUES (1, 1, 1, 'Цезар', 'Класическа салата Цезар', 12.90, 1, 1)
    """)

    c.execute("""
    INSERT OR IGNORE INTO menu_items (id, tenant_id, category_id, name, description, price, is_active, sort_order)
    VALUES (2, 1, 1, 'Гръцка салата', 'Домати, краставици, сирене, маслини', 10.50, 1, 2)
    """)

    c.execute("""
    INSERT OR IGNORE INTO menu_items (id, tenant_id, category_id, name, description, price, is_active, sort_order)
    VALUES (3, 1, 2, 'Пилешка пържола', 'С гарнитура по избор', 16.90, 1, 1)
    """)

    c.execute("""
    INSERT OR IGNORE INTO menu_items (id, tenant_id, category_id, name, description, price, is_active, sort_order)
    VALUES (4, 1, 2, 'Паста Карбонара', 'Кремообразен сос, бекон и пармезан', 14.90, 1, 2)
    """)

    c.execute("""
    INSERT OR IGNORE INTO menu_items (id, tenant_id, category_id, name, description, price, is_active, sort_order)
    VALUES (5, 1, 3, 'Чийзкейк', 'Домашен чийзкейк', 7.50, 1, 1)
    """)

    c.execute("""
    INSERT OR IGNORE INTO menu_items (id, tenant_id, category_id, name, description, price, is_active, sort_order)
    VALUES (6, 1, 4, 'Лимонада', 'Домашна лимонада', 4.90, 1, 1)
    """)

    conn.commit()
    conn.close()