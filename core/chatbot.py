from core.intents import detect_intent
from core.parsers import extract_people, extract_date, extract_time, extract_contact
from core.validators import (
    is_valid_people,
    is_valid_phone,
    is_valid_time_range,
    is_valid_future_or_today_date,
)
from services.tenants import get_tenant_settings, tenant_has_feature
from services.reservations import get_reservations_for_date
from services.analytics import log_event
from services.menu import get_menu_categories, get_menu_items_by_category, find_menu_category_match
from services.llm import get_llm_reply
from database import get_db
import random


class ChatBot:
    def __init__(self, tenant_id):
        self.tenant_id = tenant_id
        self.context = {}

    def empty_context(self):
        return {
            "people": None,
            "date": None,
            "time": None,
            "name": None,
            "phone": None,
            "confirmed": False,
            "last_question": None,
            "last_topic": None,
        }

    def default_buttons(self):
        return ["Нова резервация", "Меню", "Контакти"]

    def is_menu_category_message(self, text):
        category = find_menu_category_match(self.tenant_id, text)
        return category is not None

    def is_reservation_in_progress(self):
        c = self.context
        return any([
            c.get("people"),
            c.get("date"),
            c.get("time"),
            c.get("name"),
            c.get("phone"),
            c.get("last_question") in ["people", "date", "time", "contact", "confirm"]
        ])

    def looks_like_food_question(self, text):
        text = (text or "").lower().strip()

        food_keywords = [
            "какво препоръч",
            "какво да ям",
            "какво имате",
            "има ли нещо",
            "има ли",
            "сирене",
            "яйца",
            "яйце",
            "с пиле",
            "пиле",
            "телешко",
            "салата",
            "десерт",
            "десерти",
            "напит",
            "напитки",
            "веган",
            "вегетариан",
            "без глутен",
            "люто",
            "месо",
            "риба",
            "паста",
            "бургер",
            "пица",
            "леко",
            "препоръчваш",
            "меню",
            "ястие",
            "ястия",
            "по-леко",
            "по-засищащо",
            "нещо с",
            "опции с",
            "за пиене",
        ]

        return any(k in text for k in food_keywords)

    def clear_reservation_context_if_needed(self, text, intent):
        if intent == "reservation":
            return

        if self.is_menu_category_message(text) or self.looks_like_food_question(text) or intent == "menu":
            old_topic = self.context.get("last_topic")
            self.context = self.empty_context()
            self.context["last_topic"] = old_topic

    def update_topic_context(self, text, intent):
        if self.looks_like_food_question(text) or intent == "menu" or self.is_menu_category_message(text):
            self.context["last_topic"] = "food"
        elif intent == "contact":
            self.context["last_topic"] = "contact"
        elif intent == "reservation":
            self.context["last_topic"] = "reservation"

    def should_use_llm_for_menu_question(self, original_message, intent, llm_enabled):
        if llm_enabled != 1:
            return False

        if self.looks_like_food_question(original_message):
            return True

        if self.context.get("last_topic") == "food" and intent == "general":
            return True

        return False

    def add_upsell_if_needed(self, text, original_message="", upsell_enabled=False):
        if not upsell_enabled:
            return text

        lower_text = (text or "").lower()
        user_text = (original_message or "").lower()

        upsell_triggers = [
            "мога да ви предложа",
            "бих ви препоръчал",
            "бих ви препоръчала",
            "имаме",
            "опции с",
            "подходящ избор",
            "много добър избор",
            "любимо на клиентите",
            "пилешка пържола",
            "паста карбонара",
            "гръцка салата",
            "чийзкейк",
            "лимонада",
        ]

        if any(trigger in lower_text for trigger in upsell_triggers):
            if "десерт" not in lower_text and "напит" not in lower_text:
                if not any(x in user_text for x in ["десерт", "напит", "пиене"]):
                    return text.rstrip() + "\n\n👉 Искате ли да добавим и нещо за пиене или десерт? 😊"

        return text

    def llm_buttons(self, text, upsell_enabled=False):
        text = (text or "").lower()

        if upsell_enabled and any(word in text for word in ["десерт", "сладко", "чийзкейк"]):
            return ["Напитки", "Нова резервация", "Контакти"]

        if upsell_enabled and any(word in text for word in ["напит", "за пиене", "лимонада"]):
            return ["Десерти", "Нова резервация", "Контакти"]

        if any(word in text for word in ["препоръч", "меню", "сирене", "месо", "пиле", "ястие", "яйца"]):
            return ["Нова резервация", "Меню", "Контакти"]

        return self.default_buttons()

    def get_response(self, message, context=None):
        try:
            if context:
                self.context = context
            elif not self.context:
                self.context = self.empty_context()

            original_message = (message or "").strip()
            text = original_message.lower().strip()

            settings = get_tenant_settings(self.tenant_id) or {}
            intent = detect_intent(text)

            tenant_has_ai_chat = tenant_has_feature(self.tenant_id, "ai_chat")
            tenant_has_upsell = tenant_has_feature(self.tenant_id, "upsell")

            llm_enabled = 1 if (tenant_has_ai_chat and int(settings.get("llm_enabled", 0)) == 1) else 0

            print("DEBUG MESSAGE:", original_message)
            print("DEBUG INTENT:", intent)
            print("DEBUG LLM ENABLED:", llm_enabled)
            print("DEBUG TENANT HAS AI CHAT:", tenant_has_ai_chat)
            print("DEBUG TENANT HAS UPSELL:", tenant_has_upsell)

            if intent == "cancel":
                self.context = self.empty_context()
                return {
                    "text": "❌ Добре, отмених текущата резервация.",
                    "buttons": self.default_buttons()
                }

            self.clear_reservation_context_if_needed(original_message, intent)
            self.update_topic_context(original_message, intent)

            if self.is_menu_category_message(original_message):
                return self.handle_menu(original_message)

            if intent == "menu":
                print("DEBUG FOOD QUESTION:", self.looks_like_food_question(original_message))

                if self.should_use_llm_for_menu_question(original_message, intent, llm_enabled):
                    llm_reply = get_llm_reply(self.tenant_id, original_message)
                    if llm_reply:
                        llm_reply = self.add_upsell_if_needed(
                            llm_reply,
                            original_message,
                            upsell_enabled=tenant_has_upsell
                        )
                        return {
                            "text": llm_reply,
                            "buttons": self.llm_buttons(original_message, upsell_enabled=tenant_has_upsell)
                        }

                return self.handle_menu(original_message)

            if intent == "contact":
                phone = settings.get("phone") or "0888 123 456"
                address = settings.get("address") or "Центъра на града"
                return {
                    "text": f"📞 Телефон: {phone}\n📍 Адрес: {address}\n\n👉 Искате ли и да направим резервация? 😊",
                    "buttons": ["Нова резервация", "Меню"]
                }

            people = extract_people(original_message)
            date = extract_date(original_message)
            time = extract_time(original_message)
            name, phone = extract_contact(original_message)

            if people:
                self.context["people"] = people

            if date:
                self.context["date"] = date

            if time:
                self.context["time"] = time

            if name:
                self.context["name"] = name

            if phone:
                self.context["phone"] = phone

            if text.isdigit():
                num = int(text)

                if self.context.get("last_question") == "people":
                    self.context["people"] = num
                elif self.context.get("last_question") == "time" and 0 <= num <= 23:
                    self.context["time"] = f"{num:02d}:00"

            if intent == "confirm" and self.is_ready_for_confirmation():
                self.context["confirmed"] = True
                return self.finalize_reservation()

            if self.is_reservation_in_progress():
                return self.handle_reservation(settings)

            if intent == "reservation":
                return self.handle_reservation(settings)

            print("DEBUG FOOD QUESTION:", self.looks_like_food_question(original_message))

            if self.should_use_llm_for_menu_question(original_message, intent, llm_enabled):
                llm_reply = get_llm_reply(self.tenant_id, original_message)
                if llm_reply:
                    llm_reply = self.add_upsell_if_needed(
                        llm_reply,
                        original_message,
                        upsell_enabled=tenant_has_upsell
                    )
                    return {
                        "text": llm_reply,
                        "buttons": self.llm_buttons(original_message, upsell_enabled=tenant_has_upsell)
                    }

            if llm_enabled == 1:
                llm_reply = get_llm_reply(self.tenant_id, original_message)
                if llm_reply:
                    llm_reply = self.add_upsell_if_needed(
                        llm_reply,
                        original_message,
                        upsell_enabled=tenant_has_upsell
                    )
                    return {
                        "text": llm_reply,
                        "buttons": self.default_buttons()
                    }

            return {
                "text": settings.get("welcome_message") or "👋 Здравейте! Добре дошли 😊\nМога да помогна с менюто, контактите или резервация.\n\n👉 Какво ви интересува?",
                "buttons": self.default_buttons()
            }

        except Exception as e:
            print("ERROR:", e)
            return {
                "text": "⚠️ Възникна грешка. Опитайте отново.\n\n👉 Можете да разгледате менюто или да започнем резервация.",
                "buttons": self.default_buttons()
            }

    def handle_menu(self, text):
        categories = get_menu_categories(self.tenant_id)

        if not categories:
            return {
                "text": "📋 В момента менюто не е налично.\n👉 Може да направите резервация или да се свържете с ресторанта.",
                "buttons": ["Нова резервация", "Контакти"]
            }

        wanted_category = find_menu_category_match(self.tenant_id, text)

        if not wanted_category:
            category_names = [c["name"] for c in categories]
            return {
                "text": "🍽️ Разбира се 😊 Какво ви интересува от менюто?\n\n👉 Изберете категория:",
                "buttons": category_names
            }

        items = get_menu_items_by_category(self.tenant_id, wanted_category["id"])

        if not items:
            return {
                "text": f"📋 В категория „{wanted_category['name']}“ все още няма добавени артикули.",
                "buttons": ["Меню", "Нова резервация", "Контакти"]
            }

        lines = [f"🍽️ {wanted_category['name']}:"]

        for item in items:
            description = f" – {item['description']}" if item["description"] else ""
            lines.append(f"- {item['name']} – {float(item['price']):.2f} €{description}")

        lines.append("\n👉 Искате ли след това да направим резервация? 😊")

        category_names = [c["name"] for c in categories]

        return {
            "text": "\n".join(lines),
            "buttons": ["Нова резервация"] + category_names + ["Контакти"]
        }

    def handle_reservation(self, settings):
        c = self.context
        max_capacity = int(settings.get("max_capacity", 20))
        open_hour = int(settings.get("open_hour", 10))
        close_hour = int(settings.get("close_hour", 22))

        if not c.get("people"):
            c["last_question"] = "people"
            c["last_topic"] = "reservation"
            log_event(self.tenant_id, "reservation_started", {"step": "people"})
            return {
                "text": "С удоволствие 😊 За колко човека е резервацията?",
                "buttons": ["2", "4", "6"]
            }

        if not is_valid_people(c["people"]):
            c["people"] = None
            c["last_question"] = "people"
            return {
                "text": "Моля, въведете валиден брой хора от 1 до 20 😊",
                "buttons": ["2", "4", "6"]
            }

        if not c.get("date"):
            c["last_question"] = "date"
            return {
                "text": f"Чудесно 😊 За {c['people']} човека — коя дата предпочитате?",
                "buttons": ["Днес", "Утре"]
            }

        if not is_valid_future_or_today_date(c["date"]):
            c["date"] = None
            c["last_question"] = "date"
            return {
                "text": "Моля, въведете днешна или бъдеща дата 😊",
                "buttons": ["Днес", "Утре"]
            }

        if not c.get("time"):
            c["last_question"] = "time"
            return {
                "text": f"Супер 😊 За {c['people']} човека на {c['date']} — в колко часа?",
                "buttons": ["18:00", "19:00", "20:00"]
            }

        if not is_valid_time_range(c["time"], open_hour, close_hour):
            c["time"] = None
            c["last_question"] = "time"
            return {
                "text": f"🕒 Работим от {open_hour}:00 до {close_hour}:00.\nМоля, изберете час в този интервал 😊",
                "buttons": ["18:00", "19:00", "20:00"]
            }

        availability = self.check_availability(c["date"], c["time"], c["people"], max_capacity)

        if not availability["available"]:
            suggestions = self.get_suggestions(c["date"], max_capacity)
            c["last_question"] = "time"

            if suggestions:
                return {
                    "text": f"❌ За {c['people']} човека няма достатъчно места около {c['time']}.\n\n👉 Свободни варианти за тази дата:\n{', '.join(suggestions)}",
                    "buttons": suggestions
                }

            self.context = self.empty_context()
            return {
                "text": "❌ За тази дата няма свободни места.\n👉 Може да опитаме друг ден или да разгледате менюто 😊",
                "buttons": ["Утре", "Меню", "Контакти"]
            }

        responses = [
            f"Да, има свободна маса за {c['people']} човека 😊",
            f"Разбира се! Имаме място за {c['people']} души 👍",
            f"Да, можем да ви настаним за {c['people']} човека 🍽️"
        ]

        if not c.get("name") or not c.get("phone"):
            c["last_question"] = "contact"
            return {
                "text": random.choice(responses) + f"""

📅 {c['date']}
⏰ около {c['time']}
👥 {c['people']} човека
🟢 Свободни места за този час: {availability['free_places_after']}

👉 Кажете име и телефон за резервацията 😊""",
                "buttons": []
            }

        if not is_valid_phone(c["phone"]):
            c["phone"] = None
            c["last_question"] = "contact"
            return {
                "text": "📞 Моля, изпратете валиден телефон, например 0898123456",
                "buttons": []
            }

        if not c.get("confirmed"):
            c["last_question"] = "confirm"
            return {
                "text": f"""📌 Моля, потвърдете резервацията:

Име: {c['name']}
Телефон: {c['phone']}
Дата: {c['date']}
Час: {c['time']}
Хора: {c['people']}

👉 Напишете 'да' за потвърждение или 'отмени'.""",
                "buttons": ["Да", "Отмени"]
            }

        return self.finalize_reservation()

    def is_ready_for_confirmation(self):
        c = self.context
        return all([
            c.get("people"),
            c.get("date"),
            c.get("time"),
            c.get("name"),
            c.get("phone")
        ])

    def check_availability(self, date, time, people, max_capacity):
        rows = get_reservations_for_date(self.tenant_id, date)
        requested_hour = int(str(time).split(":")[0])

        occupied = sum(
            int(r["people"])
            for r in rows
            if int(str(r["time"]).split(":")[0]) == requested_hour
        )

        requested_people = int(people)
        available = (occupied + requested_people) <= max_capacity
        free_places_before = max(max_capacity - occupied, 0)
        free_places_after = max(max_capacity - (occupied + requested_people), 0)

        return {
            "available": available,
            "occupied": occupied,
            "free_places_before": free_places_before,
            "free_places_after": free_places_after
        }

    def get_suggestions(self, date, max_capacity):
        rows = get_reservations_for_date(self.tenant_id, date)
        hours = [f"{str(h).zfill(2)}:00" for h in range(12, 22)]
        free = []

        for t in hours:
            current_hour = int(t.split(":")[0])
            occupied = sum(
                int(r["people"])
                for r in rows
                if int(str(r["time"]).split(":")[0]) == current_hour
            )

            if occupied < max_capacity:
                free.append(t)

        return free[:4]

    def finalize_reservation(self):
        c = self.context

        db = get_db()
        db.execute("""
            INSERT INTO reservations (
                tenant_id, name, phone, date, time, people, source, status, notes
            )
            VALUES (?, ?, ?, ?, ?, ?, 'chatbot', 'confirmed', '')
        """, (
            self.tenant_id,
            c["name"],
            c["phone"],
            c["date"],
            c["time"],
            c["people"]
        ))
        db.commit()
        db.close()

        log_event(self.tenant_id, "reservation_created", {
            "name": c["name"],
            "date": c["date"],
            "time": c["time"],
            "people": c["people"]
        })

        data = {
            "name": c["name"],
            "phone": c["phone"],
            "date": c["date"],
            "time": c["time"],
            "people": c["people"]
        }

        self.context = self.empty_context()

        return {
            "text": f"""✅ Готово!

📌 {data['name']}
📅 {data['date']}
⏰ {data['time']}
👥 {data['people']} човека

Очакваме ви 😊""",
            "buttons": ["Меню", "Контакти", "Нова резервация"]
        }