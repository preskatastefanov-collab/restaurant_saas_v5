from database import get_db


def get_tenant(tenant_id):
    db = get_db()
    row = db.execute("""
        SELECT * FROM tenants
        WHERE id = ?
    """, (tenant_id,)).fetchone()
    db.close()
    return dict(row) if row else None


def get_tenant_settings(tenant_id):
    db = get_db()
    row = db.execute("""
        SELECT * FROM tenant_settings
        WHERE tenant_id = ?
    """, (tenant_id,)).fetchone()
    db.close()
    return dict(row) if row else None


def create_tenant(name, slug, max_capacity=20, open_hour=10, close_hour=22):
    db = get_db()
    cursor = db.cursor()

    cursor.execute("""
        INSERT INTO tenants (name, slug, is_active)
        VALUES (?, ?, 1)
    """, (name, slug))

    tenant_id = cursor.lastrowid

    cursor.execute("""
        INSERT INTO tenant_settings (
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
        )
        VALUES (?, ?, '', '', '', ?, ?, ?, ?, '#1e88ff', ?, 1, 0)
    """, (
        tenant_id,
        name,
        "👋 Здравейте! С какво мога да помогна?",
        max_capacity,
        open_hour,
        close_hour,
        f"{name} ChatBot"
    ))

    db.commit()
    db.close()
    return tenant_id


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
    db = get_db()
    db.execute("""
        UPDATE tenant_settings
        SET restaurant_name = ?,
            phone = ?,
            email = ?,
            address = ?,
            welcome_message = ?,
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
        llm_enabled,
        tenant_id
    ))
    db.commit()
    db.close()


def list_tenants():
    db = get_db()
    rows = db.execute("""
        SELECT t.id, t.name, t.slug, t.is_active, t.created_at,
               ts.restaurant_name, ts.phone, ts.max_capacity
        FROM tenants t
        LEFT JOIN tenant_settings ts ON ts.tenant_id = t.id
        ORDER BY t.id DESC
    """).fetchall()
    db.close()
    return [dict(r) for r in rows]


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