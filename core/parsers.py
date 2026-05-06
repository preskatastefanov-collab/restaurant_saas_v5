import re
from datetime import datetime, timedelta


def extract_people(text: str):
    if not text:
        return None

    text_l = text.lower().strip()

    match = re.search(
        r"(\d+)\s*(човека|човек|души|хора|people|persons|person|guests|guest)",
        text_l
    )
    if match:
        return int(match.group(1))

    if text_l.isdigit():
        return int(text_l)

    word_map = {
        "един": 1, "една": 1,
        "двама": 2, "две": 2,
        "трима": 3, "три": 3,
        "четирима": 4, "четири": 4,
        "пет": 5,
        "шест": 6,
        "седем": 7,
        "осем": 8,
        "девет": 9,
        "десет": 10,

        "one": 1,
        "two": 2,
        "three": 3,
        "four": 4,
        "five": 5,
        "six": 6,
        "seven": 7,
        "eight": 8,
        "nine": 9,
        "ten": 10,
    }

    for word, value in word_map.items():
        if re.search(rf"\b{word}\b", text_l):
            if any(x in text_l for x in [
                "човека", "човек", "души", "хора",
                "people", "persons", "person", "guests", "guest"
            ]):
                return value

    return None


def extract_date(text: str):
    if not text:
        return None

    text_l = text.lower().strip()

    match = re.search(r"\d{2}\.\d{2}\.\d{4}", text_l)
    if match:
        return match.group(0)

    match_short = re.search(r"\d{2}\.\d{2}", text_l)
    if match_short:
        return f"{match_short.group(0)}.{datetime.now().year}"

    if any(x in text_l for x in ["утре", "tomorrow"]):
        return (datetime.now() + timedelta(days=1)).strftime("%d.%m.%Y")

    if any(x in text_l for x in ["днес", "today"]):
        return datetime.now().strftime("%d.%m.%Y")

    if any(x in text_l for x in ["другата седмица", "next week"]):
        return (datetime.now() + timedelta(days=7)).strftime("%d.%m.%Y")

    return None


def extract_time(text: str):
    if not text:
        return None

    text_l = text.lower().strip()

    match = re.search(r"(\d{1,2}):(\d{2})", text_l)
    if match:
        hour = int(match.group(1))
        minute = int(match.group(2))

        if 0 <= hour <= 23 and 0 <= minute <= 59:
            return f"{hour:02d}:{minute:02d}"

    match2 = re.search(r"към\s*(\d{1,2})\b", text_l)
    if match2:
        hour = int(match2.group(1))
        if 0 <= hour <= 23:
            return f"{hour:02d}:00"

    match3 = re.search(r"\bв\s*(\d{1,2})\b", text_l)
    if match3:
        hour = int(match3.group(1))
        if 0 <= hour <= 23:
            return f"{hour:02d}:00"

    match4 = re.search(r"\bat\s*(\d{1,2})\b", text_l)
    if match4:
        hour = int(match4.group(1))
        if 0 <= hour <= 23:
            return f"{hour:02d}:00"

    if any(x in text_l for x in ["вечер", "довечера", "evening", "tonight"]):
        return "19:00"

    if any(x in text_l for x in ["обяд", "lunch", "noon"]):
        return "13:00"

    if any(x in text_l for x in ["след работа", "after work"]):
        return "18:00"

    return None


def extract_contact(text: str):
    if not text:
        return None, None

    phone_match = re.search(r"08\d{8}", text)

    if not phone_match:
        return None, None

    blocked_words = {
        "да", "не", "отмени", "меню", "контакти",
        "резервация", "нова", "готово", "ок", "окей",
        "yes", "no", "cancel", "menu", "contact",
        "reservation", "new", "done", "ok", "okay",
        "phone", "number", "name", "for"
    }

    name = None

    for w in text.split():
        cleaned = w.strip(",.!?")

        if cleaned.lower() in blocked_words:
            continue

        if cleaned == phone_match.group(0):
            continue

        if cleaned.istitle() and not cleaned.isdigit():
            name = cleaned
            break

    phone = phone_match.group(0)
    return name, phone