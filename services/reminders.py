from datetime import datetime

from database import get_db
from services.tenants import tenant_has_feature
from services.email import send_customer_reminder_email


def parse_reservation_datetime(date_value, time_value):
    try:
        return datetime.strptime(
            f"{date_value} {time_value}",
            "%d.%m.%Y %H:%M"
        )
    except Exception:
        return None


def run_reservation_reminders():
    try:
        now = datetime.now()

        db = get_db()
        rows = db.execute("""
            SELECT *
            FROM reservations
            WHERE status = 'confirmed'
        """).fetchall()

        for row in rows:
            r = dict(row)

            tenant_id = r.get("tenant_id")

            if not tenant_has_feature(
                tenant_id,
                "reservation_reminders"
            ):
                continue

            customer_email = (r.get("customer_email") or "").strip()

            if not customer_email:
                continue

            reservation_dt = parse_reservation_datetime(
                r.get("date"),
                r.get("time")
            )

            if not reservation_dt:
                continue

            minutes_left = int(
                (reservation_dt - now).total_seconds() / 60
            )

            if 1430 <= minutes_left <= 1450 and int(r.get("reminder_24_sent") or 0) == 0:
                sent = send_customer_reminder_email(
                    tenant_id=tenant_id,
                    customer_email=customer_email,
                    name=r.get("name"),
                    date=r.get("date"),
                    time=r.get("time"),
                    people=r.get("people"),
                    reminder_type="24h"
                )

                if sent:
                    db.execute("""
                        UPDATE reservations
                        SET reminder_24_sent = 1
                        WHERE id = ?
                    """, (r.get("id"),))
                    db.commit()

            if 110 <= minutes_left <= 130 and int(r.get("reminder_2_sent") or 0) == 0:
                sent = send_customer_reminder_email(
                    tenant_id=tenant_id,
                    customer_email=customer_email,
                    name=r.get("name"),
                    date=r.get("date"),
                    time=r.get("time"),
                    people=r.get("people"),
                    reminder_type="2h"
                )

                if sent:
                    db.execute("""
                        UPDATE reservations
                        SET reminder_2_sent = 1
                        WHERE id = ?
                    """, (r.get("id"),))
                    db.commit()

        db.close()

    except Exception as e:
        print("RESERVATION REMINDERS ERROR:", e)