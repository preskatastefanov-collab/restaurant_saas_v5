import re


def _normalize_text(message: str) -> str:
    text = (message or "").lower().strip()

    replacements = {
        "ё": "е",
        "ѝ": "и",
    }

    for old, new in replacements.items():
        text = text.replace(old, new)

    text = re.sub(r"\s+", " ", text)
    return text


def _contains_any(text, words):
    return any(word in text for word in words)


def _equals_any(text, words):
    return text in words


def detect_intent(message: str) -> str:
    text = _normalize_text(message)

    if not text:
        return "general"

    language_bg_words = [
        "български",
        "на български",
        "bulgarian",
        "bg",
        "🇧🇬",
        "🇧🇬 български",
        "bg български",
    ]

    language_en_words = [
        "english",
        "английски",
        "на английски",
        "en",
        "🇬🇧",
        "🇬🇧 english",
        "gb english",
    ]

    cancel_phrases = [
        "отмени", "стоп", "прекрати", "отказ", "откажи",
        "няма нужда", "не искам", "не благодаря",
        "cancel", "stop", "no thanks", "no, thanks", "never mind",
    ]

    confirm_words = [
        "да", "ок", "окей", "добре", "супер", "става",
        "потвърди", "потвърждавам",
        "yes", "yeah", "yep", "ok", "okay", "sure", "confirm",
    ]

    reservation_words = [
        "резервация", "нова резервация", "резервирам",
        "искам маса", "искам да резервирам",
        "искам резервация", "свободна маса",
        "свободни места", "маса за", "места за",
        "запазя маса", "запазване",

        "reservation", "new reservation", "book",
        "booking", "book a table",
        "reserve", "reserve a table",
        "table for", "free table",
        "available table", "available seats",
    ]

    contact_words = [
        "контакт", "контакти", "телефон", "номер",
        "адрес", "къде сте", "къде се намирате",
        "локация", "работно време",
        "отворени ли сте", "до колко работите",
        "имейл", "email", "website", "site",

        "contact", "contacts", "phone",
        "number", "address", "location",
        "where are you", "where are you located",
        "opening hours", "working hours",
        "are you open", "when are you open",
    ]

    order_words = [
        "поръчка", "поръчам", "искам да поръчам",
        "за вкъщи", "за взимане",
        "доставка", "доставяте ли",

        "order", "i want to order",
        "take away", "takeaway",
        "takeout", "delivery",
        "do you deliver",
    ]

    menu_words = [
        "меню", "ястия", "храна",
        "салати", "основни", "десерти",
        "напитки", "пица", "бургер",
        "кафе", "чай", "коктейл",
        "бира", "вино", "торта",
        "сладкиш", "кроасан",
        "закуски", "какво предлагате",
        "какво имате", "какво препоръч",
        "какво да ям", "цени", "цените",
        "колко струва",

        "menu", "food", "dishes",
        "meals", "salads", "main dishes",
        "desserts", "drinks", "beverages",
        "pizza", "burger",
        "coffee", "tea",
        "cocktail", "beer", "wine",
        "cake", "croissant",
        "breakfast", "what do you have",
        "what do you offer",
        "what do you recommend",
        "recommend", "prices",
        "price", "how much",
    ]

    image_words = [
        "снимка", "покажи снимка", "покажи ми снимка",
        "как изглежда", "покажи ми го",
        "фото", "изображение",

        "photo", "image", "picture",
        "show photo", "show image",
        "what does it look like",
    ]

    more_info_words = [
        "повече информация",
        "още информация",
        "детайли",
        "подробности",
        "кажи повече",
        "more info",
        "more information",
        "details",
        "tell me more",
    ]

    if _equals_any(text, language_bg_words):
        return "language_bg"

    if _equals_any(text, language_en_words):
        return "language_en"

    if _equals_any(text, cancel_phrases):
        return "cancel"

    if _equals_any(text, confirm_words):
        return "confirm"

    if _contains_any(text, image_words):
        return "image"

    if _contains_any(text, more_info_words):
        return "more_info"

    if _contains_any(text, order_words):
        return "order"

    if _contains_any(text, reservation_words):
        return "reservation"

    if _contains_any(text, contact_words):
        return "contact"

    if _contains_any(text, menu_words):
        return "menu"

    if re.fullmatch(r"\d{1,2}:\d{2}", text):
        return "reservation"

    if text.isdigit():
        return "reservation"

    return "general"