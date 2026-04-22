from database import get_db


def get_user_by_username(username):
    db = get_db()
    user = db.execute("""
        SELECT * FROM users
        WHERE username = ? AND is_active = 1
    """, (username,)).fetchone()
    db.close()
    return dict(user) if user else None


def get_any_user_by_username(username):
    db = get_db()
    user = db.execute("""
        SELECT * FROM users
        WHERE username = ?
    """, (username,)).fetchone()
    db.close()
    return dict(user) if user else None


def get_user_by_id(user_id):
    db = get_db()
    user = db.execute("""
        SELECT * FROM users
        WHERE id = ?
    """, (user_id,)).fetchone()
    db.close()
    return dict(user) if user else None


def authenticate_user(username, password):
    db = get_db()
    user = db.execute("""
        SELECT * FROM users
        WHERE username = ? AND password = ? AND is_active = 1
    """, (username, password)).fetchone()
    db.close()
    return dict(user) if user else None


def create_user(tenant_id, username, password, role="staff"):
    db = get_db()
    db.execute("""
        INSERT INTO users (tenant_id, username, password, role, is_active)
        VALUES (?, ?, ?, ?, 1)
    """, (tenant_id, username, password, role))
    db.commit()
    db.close()


def list_users_by_tenant(tenant_id):
    db = get_db()
    rows = db.execute("""
        SELECT id, tenant_id, username, role, is_active, created_at
        FROM users
        WHERE tenant_id = ?
        ORDER BY id DESC
    """, (tenant_id,)).fetchall()
    db.close()
    return [dict(r) for r in rows]


def update_user_role(user_id, tenant_id, role):
    db = get_db()
    db.execute("""
        UPDATE users
        SET role = ?
        WHERE id = ? AND tenant_id = ?
    """, (role, user_id, tenant_id))
    db.commit()
    db.close()


def update_user(user_id, tenant_id, username, password=None, role=None):
    db = get_db()

    if password and role:
        db.execute("""
            UPDATE users
            SET username = ?, password = ?, role = ?
            WHERE id = ? AND tenant_id = ?
        """, (username, password, role, user_id, tenant_id))

    elif password:
        db.execute("""
            UPDATE users
            SET username = ?, password = ?
            WHERE id = ? AND tenant_id = ?
        """, (username, password, user_id, tenant_id))

    elif role:
        db.execute("""
            UPDATE users
            SET username = ?, role = ?
            WHERE id = ? AND tenant_id = ?
        """, (username, role, user_id, tenant_id))

    else:
        db.execute("""
            UPDATE users
            SET username = ?
            WHERE id = ? AND tenant_id = ?
        """, (username, user_id, tenant_id))

    db.commit()
    db.close()


def deactivate_user(user_id, tenant_id):
    db = get_db()
    db.execute("""
        UPDATE users
        SET is_active = 0
        WHERE id = ? AND tenant_id = ?
    """, (user_id, tenant_id))
    db.commit()
    db.close()


def activate_user(user_id, tenant_id):
    db = get_db()
    db.execute("""
        UPDATE users
        SET is_active = 1
        WHERE id = ? AND tenant_id = ?
    """, (user_id, tenant_id))
    db.commit()
    db.close()


def delete_user(user_id, tenant_id):
    db = get_db()
    db.execute("""
        DELETE FROM users
        WHERE id = ? AND tenant_id = ?
    """, (user_id, tenant_id))
    db.commit()
    db.close()