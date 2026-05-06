from database import get_db
import json
from datetime import datetime, timedelta


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


def parse_payload(payload_text):
    if not payload_text:
        return {}

    try:
        return json.loads(payload_text)
    except Exception:
        return {"raw": payload_text}


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


def get_recent_events(tenant_id, event_type=None, limit=20):
    db = get_db()

    if event_type:
        rows = db.execute("""
            SELECT *
            FROM analytics
            WHERE tenant_id = ? AND event_type = ?
            ORDER BY id DESC
            LIMIT ?
        """, (tenant_id, event_type, limit)).fetchall()
    else:
        rows = db.execute("""
            SELECT *
            FROM analytics
            WHERE tenant_id = ?
            ORDER BY id DESC
            LIMIT ?
        """, (tenant_id, limit)).fetchall()

    db.close()

    events = []

    for row in rows:
        item = dict(row)
        item["payload_data"] = parse_payload(item.get("payload", ""))
        events.append(item)

    return events


def count_events_between(tenant_id, event_type, start_date, end_date):
    db = get_db()

    row = db.execute("""
        SELECT COUNT(*) AS count
        FROM analytics
        WHERE tenant_id = ?
          AND event_type = ?
          AND datetime(created_at) >= datetime(?)
          AND datetime(created_at) < datetime(?)
    """, (tenant_id, event_type, start_date, end_date)).fetchone()

    db.close()
    return row["count"] if row else 0


def get_analytics_page_data(tenant_id):
    now = datetime.now()

    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    tomorrow_start = today_start + timedelta(days=1)

    week_start = today_start - timedelta(days=today_start.weekday())
    last_week_start = week_start - timedelta(days=7)
    last_week_end = week_start

    month_start = today_start.replace(day=1)

    if month_start.month == 1:
        last_month_start = month_start.replace(year=month_start.year - 1, month=12)
    else:
        last_month_start = month_start.replace(month=month_start.month - 1)

    last_month_end = month_start

    year_start = today_start.replace(month=1, day=1)

    chat_today = count_events_between(tenant_id, "chat_message", today_start, tomorrow_start)
    chat_week = count_events_between(tenant_id, "chat_message", week_start, tomorrow_start)
    chat_last_week = count_events_between(tenant_id, "chat_message", last_week_start, last_week_end)
    chat_month = count_events_between(tenant_id, "chat_message", month_start, tomorrow_start)

    started_week = count_events_between(tenant_id, "reservation_started", week_start, tomorrow_start)
    started_last_week = count_events_between(tenant_id, "reservation_started", last_week_start, last_week_end)
    started_month = count_events_between(tenant_id, "reservation_started", month_start, tomorrow_start)

    created_week = count_events_between(tenant_id, "reservation_created", week_start, tomorrow_start)
    created_last_week = count_events_between(tenant_id, "reservation_created", last_week_start, last_week_end)
    created_month = count_events_between(tenant_id, "reservation_created", month_start, tomorrow_start)

    created_year = count_events_between(tenant_id, "reservation_created", year_start, tomorrow_start)

    conversion_week = 0
    if started_week > 0:
        conversion_week = round((created_week / started_week) * 100, 2)

    conversion_last_week = 0
    if started_last_week > 0:
        conversion_last_week = round((created_last_week / started_last_week) * 100, 2)

    conversion_month = 0
    if started_month > 0:
        conversion_month = round((created_month / started_month) * 100, 2)

    return {
        "chat_today": chat_today,
        "chat_week": chat_week,
        "chat_last_week": chat_last_week,
        "chat_month": chat_month,

        "started_week": started_week,
        "started_last_week": started_last_week,
        "started_month": started_month,

        "created_week": created_week,
        "created_last_week": created_last_week,
        "created_month": created_month,
        "created_year": created_year,

        "conversion_week": conversion_week,
        "conversion_last_week": conversion_last_week,
        "conversion_month": conversion_month,
    }