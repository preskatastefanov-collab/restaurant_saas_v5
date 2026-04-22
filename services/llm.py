from openai import OpenAI
from config import OPENAI_API_KEY, OPENAI_MODEL
from services.tenants import get_tenant_settings
from services.menu import get_full_menu

client = OpenAI(api_key=OPENAI_API_KEY)


def build_menu_text(tenant_id):
    menu_data = get_full_menu(tenant_id)
    if not menu_data:
        return "Няма налично меню."

    lines = []
    for block in menu_data:
        category = block["category"]["name"]
        lines.append(f"\nКатегория: {category}")
        for item in block["items"]:
            description = item.get("description") or ""
            price = float(item.get("price") or 0)
            lines.append(f"- {item['name']} | {price:.2f} € | {description}")

    return "\n".join(lines)


def build_restaurant_context(tenant_id):
    settings = get_tenant_settings(tenant_id) or {}

    restaurant_name = settings.get("restaurant_name") or "Ресторант"
    phone = settings.get("phone") or "няма зададен телефон"
    address = settings.get("address") or "няма зададен адрес"
    open_hour = settings.get("open_hour", 10)
    close_hour = settings.get("close_hour", 22)
    menu_text = build_menu_text(tenant_id)

    return f"""
Име на ресторанта: {restaurant_name}
Телефон: {phone}
Адрес: {address}
Работно време: {open_hour}:00 - {close_hour}:00

Меню:
{menu_text}
""".strip()


def get_llm_reply(tenant_id, user_message):
    if not OPENAI_API_KEY:
        print("LLM ERROR: липсва OPENAI_API_KEY")
        return None

    restaurant_context = build_restaurant_context(tenant_id)

    instructions = f"""
Ти си любезен и продаващ чат асистент на ресторант.

Говори на български.
Бъди кратък, естествен и приятелски.
Не бъди роботизиран.

ОСНОВНА ЦЕЛ:
👉 Да помогнеш на клиента да избере ястие и да направи резервация.

ПРАВИЛА:
- НЕ измисляй информация.
- Използвай САМО менюто по-долу.
- Ако клиентът пита за нещо (напр. "с месо", "сирене") → предложи 2-3 подходящи ястия.
- Ако има описание → използвай го, за да звучи по-вкусно.
- Ако няма точно такова ястие → предложи най-близките варианти.

СТИЛ:
- Говори като човек, не като система
- Използвай кратки изречения
- Може леко да „продаваш“ (напр. "много вкусно", "любимо на клиентите")

ПРИМЕР:
Вместо:
"Имаме пилешко."
кажи:
"Мога да ви предложа пилешка пържола – много сочна и с гарнитура по избор 🍽️"

- Ако клиентът избере ястие:
  👉 предложи допълнение:
     - напитка
     - десерт

Пример:
"Искате ли да добавим и нещо за пиене или десерт? 😊"

ВАЖНО:
- ВИНАГИ завършвай с въпрос:
  👉 "Искате ли препоръка?"
  👉 "Да резервирам ли маса за вас?"

Контекст за ресторанта:
{restaurant_context}
""".strip()

    try:
        print("LLM DEBUG: изпращам към OpenAI:", user_message)

        response = client.responses.create(
            model=OPENAI_MODEL,
            instructions=instructions,
            input=user_message,
        )

        answer = (response.output_text or "").strip()
        print("LLM DEBUG: отговор от OpenAI:", answer)

        return answer if answer else None

    except Exception as e:
        print("LLM ERROR:", e)
        return None