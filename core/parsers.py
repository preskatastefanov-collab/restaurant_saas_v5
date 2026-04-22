import re
from datetime import datetime, timedelta


def extract_people(text: str):
    if not text:
        return None

    text_l = text.lower().strip()

    match = re.search(r"(\d+)\s*(човека|човек|души|хора)", text_l)
    if match:
        return int(match.group(1))

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
    }

    for word, value in word_map.items():
        if re.search(rf"\b{word}\b", text_l):
            if any(x in text_l for x in ["човека", "човек", "души", "хора"]):
                return value

    return None


def extract_date(text: str):
    if not text:
        return None

    text_l = text.lower()

    match = re.search(r"\d{2}\.\d{2}\.\d{4}", text_l)
    if match:
        return match.group(0)

    match_short = re.search(r"\d{2}\.\d{2}", text_l)
    if match_short:
        return f"{match_short.group(0)}.{datetime.now().year}"

    if "утре" in text_l:
        return (datetime.now() + timedelta(days=1)).strftime("%d.%m.%Y")

    if "днес" in text_l:
        return datetime.now().strftime("%d.%m.%Y")

    if "другата седмица" in text_l:
        return (datetime.now() + timedelta(days=7)).strftime("%d.%m.%Y")

    return None


def extract_time(text: str):
    if not text:
        return None

    text_l = text.lower()

    match = re.search(r"(\d{1,2}):(\d{2})", text_l)
    if match:
        return match.group(0)

    match2 = re.search(r"към\s*(\d{1,2})\b", text_l)
    if match2:
        return f"{int(match2.group(1)):02d}:00"

    match3 = re.search(r"\bв\s*(\d{1,2})\b", text_l)
    if match3:
        hour = int(match3.group(1))
        if 0 <= hour <= 23:
            return f"{hour:02d}:00"

    if "вечер" in text_l or "довечера" in text_l:
        return "19:00"

    if "обяд" in text_l:
        return "13:00"

    if "след работа" in text_l:
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
        "резервация", "нова", "готово", "ок", "окей"
    }

    name = None
    for w in text.split():
        cleaned = w.strip(",.!?")

        if cleaned.lower() in blocked_words:
            continue

        if cleaned.istitle() and not cleaned.isdigit():
            name = cleaned
            break

    phone = phone_match.group(0) if phone_match else None
    return name, phone