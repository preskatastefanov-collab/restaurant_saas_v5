from database import get_db


def create_reservation(tenant_id, name, phone, date, time, people, source="dashboard", status="confirmed", notes=""):
    db = get_db()
    db.execute("""
        INSERT INTO reservations (
            tenant_id, name, phone, date, time, people, source, status, notes
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (tenant_id, name, phone, date, time, people, source, status, notes))
    db.commit()
    db.close()


def get_reservations_by_tenant(tenant_id):
    db = get_db()
    rows = db.execute("""
        SELECT * FROM reservations
        WHERE tenant_id = ?
        ORDER BY id DESC
    """, (tenant_id,)).fetchall()
    db.close()
    return [dict(r) for r in rows]


def get_reservation_by_id(reservation_id, tenant_id):
    db = get_db()
    row = db.execute("""
        SELECT * FROM reservations
        WHERE id = ? AND tenant_id = ?
    """, (reservation_id, tenant_id)).fetchone()
    db.close()
    return dict(row) if row else None


def update_reservation(reservation_id, tenant_id, name, phone, date, time, people, status="confirmed", notes=""):
    db = get_db()
    db.execute("""
        UPDATE reservations
        SET name = ?, phone = ?, date = ?, time = ?, people = ?, status = ?, notes = ?
        WHERE id = ? AND tenant_id = ?
    """, (name, phone, date, time, people, status, notes, reservation_id, tenant_id))
    db.commit()
    db.close()


def delete_reservation(reservation_id, tenant_id):
    db = get_db()
    db.execute("""
        DELETE FROM reservations
        WHERE id = ? AND tenant_id = ?
    """, (reservation_id, tenant_id))
    db.commit()
    db.close()


def get_reservations_for_date(tenant_id, date):
    db = get_db()
    rows = db.execute("""
        SELECT * FROM reservations
        WHERE tenant_id = ? AND date = ? AND status = 'confirmed'
        ORDER BY time ASC
    """, (tenant_id, date)).fetchall()
    db.close()
    return [dict(r) for r in rows]


def count_reserved_people_for_hour(tenant_id, date, hour):
    db = get_db()
    rows = db.execute("""
        SELECT people, time
        FROM reservations
        WHERE tenant_id = ? AND date = ? AND status = 'confirmed'
    """, (tenant_id, date)).fetchall()
    db.close()

    total = 0
    for row in rows:
        row_hour = int(str(row["time"]).split(":")[0])
        if row_hour == int(hour):
            total += int(row["people"])

    return total