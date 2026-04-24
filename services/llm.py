from openai import OpenAI
from config import OPENAI_API_KEY, OPENAI_MODEL
from services.tenants import get_tenant_settings
from services.menu import get_full_menu, get_best_drink, get_best_dessert

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
            upsell_drink = item.get("upsell_drink") or ""
            upsell_dessert = item.get("upsell_dessert") or ""

            extra = []
            if upsell_drink:
                extra.append(f"подходяща напитка: {upsell_drink}")
            if upsell_dessert:
                extra.append(f"подходящ десерт: {upsell_dessert}")

            extra_text = f" | {'; '.join(extra)}" if extra else ""
            lines.append(f"- {item['name']} | {price:.2f} € | {description}{extra_text}")

    return "\n".join(lines)


def build_restaurant_context(tenant_id):
    settings = get_tenant_settings(tenant_id) or {}

    restaurant_name = settings.get("restaurant_name") or "Ресторант"
    phone = settings.get("phone") or "няма зададен телефон"
    address = settings.get("address") or "няма зададен адрес"
    open_hour = settings.get("open_hour", 10)
    close_hour = settings.get("close_hour", 22)
    menu_text = build_menu_text(tenant_id)

    best_drink = get_best_drink(tenant_id)
    best_dessert = get_best_dessert(tenant_id)

    drink_text = best_drink["name"] if best_drink else "няма зададена напитка"
    dessert_text = best_dessert["name"] if best_dessert else "няма зададен десерт"

    return f"""
Име на ресторанта: {restaurant_name}
Телефон: {phone}
Адрес: {address}
Работно време: {open_hour}:00 - {close_hour}:00

Най-подходяща напитка за upsell: {drink_text}
Най-подходящ десерт за upsell: {dessert_text}

Меню:
{menu_text}
""".strip()


def get_llm_reply(tenant_id, user_message):
    if not OPENAI_API_KEY:
        print("LLM ERROR: липсва OPENAI_API_KEY")
        return None

    restaurant_context = build_restaurant_context(tenant_id)

    instructions = f"""
Ти си любезен, естествен и продаващ AI асистент на ресторант.

Говори само на български.
Бъди кратък, приятелски и конкретен.
Не измисляй ястия, цени, адреси, телефони или работно време.
Използвай само информацията от контекста.

ОСНОВНА ЦЕЛ:
1. Да помогнеш на клиента да избере ястие.
2. Да увеличиш шанса за резервация.
3. Да предложиш подходяща напитка или десерт, когато има смисъл.

ВАЖНИ ПРАВИЛА:
- Ако клиентът пита за ястия с месо, сирене, яйца, паста, салата, десерт или напитка — предложи само налични артикули.
- Ако няма точно съвпадение — кажи честно и предложи най-близките налични варианти.
- Не казвай "има" без да дадеш конкретно име на артикул.
- Не прекалявай с дълги обяснения.
- Не използвай измислени твърдения като "най-продавано", ако го няма в данните.
- Може да кажеш "много подходящ избор", "добре се комбинира", "би вървяло добре с...".

UPSELL ЛОГИКА:
Когато предложиш основно ястие, НЕ завършвай само с:
"Искате ли десерт или напитка?"

По-добре:
"Към Паста Карбонара много добре върви домашна лимонада — да я добавим ли? 😊"

Или:
"След това много добре би паснал чийзкейк — искате ли да го разгледате? 😊"

Ако клиентът вече пита за напитки — предложи десерт.
Ако клиентът вече пита за десерт — предложи напитка.
Ако клиентът пита за резервация — помогни му с резервацията, не продавай агресивно.

ВИНАГИ завършвай с конкретен въпрос:
- "Да ви предложа ли и напитка към това?"
- "Искате ли да направим резервация?"
- "Да ви покажа ли още подобни опции?"

Контекст:
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