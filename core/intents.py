def detect_intent(message: str) -> str:
    text = (message or "").lower().strip()

    reservation_words = [
        "резервация",
        "нова резервация",
        "резервирам",
        "искам маса",
        "искам да резервирам",
        "искам резервация",
        "свободна маса",
        "свободни места",
        "маса за",
        "места за"
    ]

    menu_words = [
        "меню",
        "ястия",
        "храна",
        "салати",
        "основни",
        "десерти",
        "напитки",
        "какво предлагате",
        "какво имате",
        "какво препоръч",
        "какво да ям"
    ]

    contact_words = ["контакт", "телефон", "адрес", "къде сте"]
    cancel_words = ["отмени", "стоп", "прекрати", "отказ"]
    confirm_words = ["да", "ок", "окей", "потвърди", "потвърждавам"]

    # 1. Cancel
    if any(word in text for word in cancel_words):
        return "cancel"

    # 2. Confirm
    if text in confirm_words:
        return "confirm"

    # 3. MENU (важно: преди reservation)
    if any(word in text for word in menu_words):
        return "menu"

    # 4. CONTACT
    if any(word in text for word in contact_words):
        return "contact"

    # 5. RESERVATION (по-строги думи)
    if any(word in text for word in reservation_words):
        return "reservation"

    # 6. ВСИЧКО ДРУГО
    return "general"