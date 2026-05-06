from openai import OpenAI
from config import OPENAI_API_KEY, OPENAI_MODEL
from services.tenants import get_tenant_ai_profile
from services.menu import (
    get_menu_summary_for_ai,
    get_menu_context_for_chatbot,
    get_best_drink,
    get_best_dessert,
    get_best_side,
)

client = OpenAI(api_key=OPENAI_API_KEY) if OPENAI_API_KEY else None


def translate_to_english(text):
    text = (text or "").strip()

    if not text:
        return ""

    if not OPENAI_API_KEY or not client:
        return text

    try:
        response = client.responses.create(
            model=OPENAI_MODEL,
            instructions=(
                "Translate the text to natural English for a restaurant menu. "
                "Return ONLY the translated text. No quotes. No explanation."
            ),
            input=text,
            max_output_tokens=120,
        )

        translated = (response.output_text or "").strip()
        return translated if translated else text

    except Exception as e:
        print("TRANSLATE ERROR:", e)
        return text


def build_chat_history_text(chat_history=None):
    if not chat_history:
        return "Няма предишен разговор."

    lines = []

    for msg in chat_history[-10:]:
        role = msg.get("role", "")
        text = (msg.get("text", "") or "").strip()

        if not text:
            continue

        if role == "user":
            lines.append(f"Клиент: {text}")
        elif role == "assistant":
            lines.append(f"Асистент: {text}")

    return "\n".join(lines) if lines else "Няма предишен разговор."


def detect_language(user_message, chat_history=None):
    text = (user_message or "").lower()

    en_words = [
        "hello", "hi", "menu", "price", "reservation", "book",
        "contact", "where", "address", "recommend", "what do you",
        "how much", "english"
    ]

    bg_words = [
        "здравей", "меню", "цена", "резервация", "контакт",
        "къде", "адрес", "препоръчай", "колко", "български"
    ]

    if any(w in text for w in en_words):
        return "en"

    if any(w in text for w in bg_words):
        return "bg"

    if chat_history:
        for msg in reversed(chat_history[-6:]):
            old_text = (msg.get("text", "") or "").lower()
            if "sure" in old_text or "how can i help" in old_text:
                return "en"
            if "разбира се" in old_text or "с какво" in old_text:
                return "bg"

    return "bg"


def build_business_context(tenant_id, user_message=""):
    ai_profile = get_tenant_ai_profile(tenant_id) or {}

    business_name = ai_profile.get("business_name", "Бизнес")
    business_type = ai_profile.get("business_type", "restaurant")
    business_type_label = ai_profile.get("business_type_label", "Ресторант")
    ai_style = ai_profile.get("business_type_ai_style", "")
    phone = ai_profile.get("phone") or "няма зададен телефон"
    email = ai_profile.get("email") or "няма зададен имейл"
    address = ai_profile.get("address") or "няма зададен адрес"
    website = ai_profile.get("website") or "няма зададен уебсайт"
    open_hour = ai_profile.get("open_hour") or 10
    close_hour = ai_profile.get("close_hour") or 22

    menu_context = get_menu_context_for_chatbot(
        tenant_id=tenant_id,
        business_type=business_type,
        user_text=user_message,
        limit=8
    )

    full_menu_text = get_menu_summary_for_ai(tenant_id)
    recommendations_text = menu_context.get("recommendations_text", "")

    best_drink = get_best_drink(tenant_id, business_type)
    best_dessert = get_best_dessert(tenant_id, business_type)
    best_side = get_best_side(tenant_id, business_type)

    drink_text = best_drink["name"] if best_drink else "няма подходяща напитка"
    dessert_text = best_dessert["name"] if best_dessert else "няма подходящ десерт"
    side_text = best_side["name"] if best_side else "няма подходяща добавка/мезе/гарнитура"

    return f"""
Име на бизнеса: {business_name}
Тип бизнес: {business_type_label}
Business type код: {business_type}
Стил на асистента: {ai_style}

Телефон: {phone}
Имейл: {email}
Адрес/локация: {address}
Уебсайт: {website}
Работно време: {open_hour}:00 - {close_hour}:00

Най-подходяща напитка за upsell: {drink_text}
Най-подходящ десерт за upsell: {dessert_text}
Най-подходяща добавка/мезе/гарнитура за upsell: {side_text}

Най-подходящи предложения според въпроса на клиента:
{recommendations_text}

Пълно меню:
{full_menu_text}
""".strip()


def build_business_type_rules(business_type):
    rules = {
        "restaurant": """
- Фокус: меню, ястия, препоръки, резервации, контакт.
- Подходящ upsell: напитка, десерт, салата, гарнитура.
""",
        "cafe": """
- Фокус: кафе, напитки, десерти, закуски, работно време, резервации.
- Подходящ upsell: десерт към кафе, кроасан, торта, студена напитка.
""",
        "bar": """
- Фокус: напитки, коктейли, бира, вино, мезета, резервации.
- Подходящ upsell: мезе към бира, ядки към коктейл, плато към компания.
""",
        "pub": """
- Фокус: бира, мезета, храна за споделяне, спортни вечери, резервации.
- Подходящ upsell: плато мезета, картофки, ядки, бургер.
""",
        "pizzeria": """
- Фокус: пици, добавки, напитки, поръчки, резервации.
- Подходящ upsell: сос, напитка, десерт, допълнителна добавка.
""",
        "fast_food": """
- Фокус: бързо меню, цени, комбо предложения, поръчки.
- Подходящ upsell: картофки, напитка, сос, десерт.
- Не натискай за резервация, освен ако системата изрично я поддържа.
""",
        "bakery": """
- Фокус: хляб, закуски, печива, наличности, поръчки, работно време.
- Подходящ upsell: кафе, напитка, сладко печиво.
""",
        "sweet_shop": """
- Фокус: торти, десерти, поръчки, наличности, поводи.
- Подходящ upsell: свещички, напитка, допълнителен десерт.
""",
        "food_truck": """
- Фокус: меню, локация, работно време, бърза поръчка.
- Подходящ upsell: напитка, сос, добавка.
- Когато питат къде се намира, дай локацията от контекста.
""",
    }

    return rules.get(business_type, "- Фокус: меню, контакт, информация и полезни кратки отговори.")


def get_llm_reply(tenant_id, user_message, chat_history=None):
    if not OPENAI_API_KEY or not client:
        print("LLM ERROR: липсва OPENAI_API_KEY")
        return None

    ai_profile = get_tenant_ai_profile(tenant_id) or {}

    if not ai_profile.get("llm_enabled"):
        print("LLM DEBUG: AI е изключен за този бизнес или планът не позволява AI.")
        return None

    business_type = ai_profile.get("business_type", "restaurant")
    business_type_label = ai_profile.get("business_type_label", "Ресторант")
    business_name = ai_profile.get("business_name", "Бизнес")
    upsell_enabled = ai_profile.get("upsell_enabled", False)

    language = detect_language(user_message, chat_history)
    business_context = build_business_context(tenant_id, user_message)
    history_text = build_chat_history_text(chat_history)
    business_type_rules = build_business_type_rules(business_type)

    if language == "en":
        language_rule = "Reply in English. Keep the same polite, natural style."
    else:
        language_rule = "Отговаряй на български. Пиши естествено, учтиво и кратко."

    upsell_rule = """
UPSELL:
- Позволено е да правиш upsell.
- Когато е естествено, предложи конкретна напитка, десерт, сос, мезе, добавка или комбо от менюто.
- Не казвай общо "искате ли нещо друго", а предложи конкретно име от менюто.
- Не прави upsell във всеки отговор. Само когато има смисъл.
""".strip() if upsell_enabled else """
UPSELL:
- Не продавай агресивно.
- Може само леко да предложиш да се види менюто или да се направи резервация.
""".strip()

    instructions = f"""
Ти си клиентски AI асистент за продажбен SaaS chatbot продукт.
Работиш за бизнес тип: {business_type_label}.
Името на бизнеса е: {business_name}.

ЕЗИК:
{language_rule}

ОБЩ СТИЛ:
- Бъди кратък, човешки, любезен и полезен.
- Отговаряй като реален служител на заведението, не като робот.
- Не казвай, че си изкуствен интелект, освен ако клиентът директно не попита.
- Не използвай прекалено дълги обяснения.
- При меню/препоръки използвай кратък списък.
- Завършвай с кратък въпрос, когато е естествено.
- Използвай emoji умерено.

ЗАБРАНЕНО:
- Не измисляй артикули, цени, адреси, телефони, имейли, уебсайт или работно време.
- Не твърди, че има снимка, ако не е посочено от системата.
- Не създавай резервация сам.
- Не обещавай доставка, онлайн плащане или поръчка, ако не е ясно от контекста.
- Не отговаряй дълго на въпроси извън бизнеса.

ПРАВИЛА СПОРЕД ТИПА БИЗНЕС:
{business_type_rules}

ВАЖНО ЗА МЕНЮТО:
- Използвай само артикулите и цените от менюто.
- Ако клиентът пита за конкретен артикул, кажи дали го има и цената му.
- Ако клиентът пита "какво имате", покажи няколко категории или подходящи предложения.
- Ако клиентът пита за бюджет, предложи само подходящи артикули, ако има такива.
- Ако няма точен вариант, кажи честно и предложи най-близките налични.
- Ако има подходящи предложения в контекста, предпочитай тях пред цялото меню.

ВАЖНО ЗА РЕЗЕРВАЦИИ:
- Ако клиентът иска резервация, кажи му да използва бутона/flow за резервация или да даде: име, телефон, дата, час и брой хора.
- Не финализирай резервация в AI текста. Това се прави от основната система.

ВАЖНО ЗА КОНТАКТИ:
- Ако клиентът пита за телефон, адрес, имейл, уебсайт или работно време, използвай само данните от контекста.
- Ако липсват данни, кажи честно, че не са зададени.

ВАЖНО ЗА ВЪПРОСИ ИЗВЪН БИЗНЕСА:
- Ако въпросът не е свързан с меню, напитки, храна, резервации, контакт, работно време или бизнеса, отговори кратко и върни разговора към заведението.

{upsell_rule}

ФОРМАТ:
- Без markdown таблици.
- Без много дълги абзаци.
- Цените ги изписвай така, както са в менюто.
- Ако валутата е евро, използвай "€".
- Не споменавай вътрешни системи, планове, tenant_id, контекст или debug.

КОНТЕКСТ НА БИЗНЕСА:
{business_context}

КОНТЕКСТ НА РАЗГОВОРА:
{history_text}
""".strip()

    try:
        print("LLM DEBUG: изпращам към OpenAI:", user_message)

        response = client.responses.create(
            model=OPENAI_MODEL,
            instructions=instructions,
            input=user_message,
            temperature=0.4,
            max_output_tokens=450,
        )

        answer = (response.output_text or "").strip()

        print("LLM DEBUG: отговор от OpenAI:", answer)

        return answer if answer else None

    except Exception as e:
        print("LLM ERROR:", e)
        return None