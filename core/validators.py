import re
from datetime import datetime


def is_valid_people(people):
    return isinstance(people, int) and 1 <= people <= 20


def is_valid_phone(phone):
    return bool(re.fullmatch(r"08\d{8}", phone or ""))


def is_valid_time_range(time_str, open_hour=10, close_hour=22):
    try:
        hour = int(str(time_str).split(":")[0])
        return open_hour <= hour <= close_hour
    except Exception:
        return False


def is_valid_future_or_today_date(date_str):
    try:
        parsed = datetime.strptime(date_str, "%d.%m.%Y").date()
        return parsed >= datetime.now().date()
    except Exception:
        return False