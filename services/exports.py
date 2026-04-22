import os
from openpyxl import Workbook
from database import get_db


def export_reservations_to_excel(tenant_id, output_dir="data"):
    db = get_db()
    rows = db.execute("""
        SELECT name, phone, date, time, people, source, status, created_at
        FROM reservations
        WHERE tenant_id = ?
        ORDER BY id DESC
    """, (tenant_id,)).fetchall()
    db.close()

    if not rows:
        return None

    os.makedirs(output_dir, exist_ok=True)

    wb = Workbook()
    ws = wb.active
    ws.title = "Reservations"

    ws.append(["name", "phone", "date", "time", "people", "source", "status", "created_at"])

    for row in rows:
        ws.append([
            row["name"],
            row["phone"],
            row["date"],
            row["time"],
            row["people"],
            row["source"],
            row["status"],
            row["created_at"]
        ])

    file_path = os.path.join(output_dir, f"tenant_{tenant_id}_reservations.xlsx")
    wb.save(file_path)

    return file_path