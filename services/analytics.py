from database import get_db
import json


def log_event(tenant_id, event_type, payload=None):
    payload_text = ""
    if payload is not None:
        try:
            payload_text = json.dumps(payload, ensure_ascii=False)
        except Exception:
            payload_text = str(payload)

    db = get_db()
    db.execute("""
        INSERT INTO analytics (tenant_id, event_type, payload)
        VALUES (?, ?, ?)
    """, (tenant_id, event_type, payload_text))
    db.commit()
    db.close()


def get_analytics_summary(tenant_id):
    db = get_db()

    total_events = db.execute("""
        SELECT COUNT(*) AS count
        FROM analytics
        WHERE tenant_id = ?
    """, (tenant_id,)).fetchone()["count"]

    total_chat_messages = db.execute("""
        SELECT COUNT(*) AS count
        FROM analytics
        WHERE tenant_id = ? AND event_type = 'chat_message'
    """, (tenant_id,)).fetchone()["count"]

    total_reservation_started = db.execute("""
        SELECT COUNT(*) AS count
        FROM analytics
        WHERE tenant_id = ? AND event_type = 'reservation_started'
    """, (tenant_id,)).fetchone()["count"]

    total_reservation_created = db.execute("""
        SELECT COUNT(*) AS count
        FROM analytics
        WHERE tenant_id = ? AND event_type = 'reservation_created'
    """, (tenant_id,)).fetchone()["count"]

    db.close()

    conversion_rate = 0
    if total_reservation_started > 0:
        conversion_rate = round((total_reservation_created / total_reservation_started) * 100, 2)

    return {
        "total_events": total_events,
        "total_chat_messages": total_chat_messages,
        "reservation_started": total_reservation_started,
        "reservation_created": total_reservation_created,
        "conversion_rate": conversion_rate
    }


def get_recent_events(tenant_id, limit=20):
    db = get_db()
    rows = db.execute("""
        SELECT * FROM analytics
        WHERE tenant_id = ?
        ORDER BY id DESC
        LIMIT ?
    """, (tenant_id, limit)).fetchall()
    db.close()
    return [dict(r) for r in rows]