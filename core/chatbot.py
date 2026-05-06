from core.intents import detect_intent
from core.parsers import extract_people, extract_date, extract_time, extract_contact
from core.validators import (
    is_valid_people,
    is_valid_phone,
    is_valid_time_range,
    is_valid_future_or_today_date,
)
from services.tenants import (
    get_tenant_settings,
    tenant_has_feature,
    get_tenant_business_type,
    get_business_type_label,
)
from services.reservations import get_reservations_for_date, create_reservation
from services.analytics import log_event
from services.menu import (
    get_menu_categories,
    get_menu_items_by_category,
    find_menu_category_match,
    find_item_mentioned_in_text,
    get_smart_upsell_for_item,
    get_smart_recommendations,
)
from services.llm import get_llm_reply
import random


class ChatBot:
    def __init__(self, tenant_id):
        self.tenant_id = tenant_id
        self.business_type = get_tenant_business_type(tenant_id)
        self.business_label = get_business_type_label(self.business_type)
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
            "last_recommended_item": None,
            "last_suggested_upsell": None,
            "last_seen_category": None,
            "language": "bg",
            "chat_history": [],
        }

    def get_lang(self):
        return self.context.get("language", "bg")

    def get_language(self):
        return self.get_lang()

    def is_en(self):
        return self.get_lang() == "en"

    def tr(self, bg, en):
        return en if self.is_en() else bg

    def format_price_eur(self, price):
        try:
            value = float(price or 0)
        except (TypeError, ValueError):
            value = 0

        if value <= 0:
            return self.tr("без цена", "no price")

        return f"{value:.2f} €"

    def supports_reservations(self):
        return self.business_type in ["restaurant", "cafe", "bar", "pub", "pizzeria"]

    def default_buttons(self):
        if self.is_en():
            if self.supports_reservations():
                return ["New reservation", "Menu", "Contact", "🇧🇬 Български"]
            if self.business_type == "food_truck":
                return ["Menu", "Location", "Contact", "🇧🇬 Български"]
            return ["Menu", "Contact", "🇧🇬 Български"]

        if self.supports_reservations():
            return ["Нова резервация", "Меню", "Контакти", "🇬🇧 English"]

        if self.business_type == "food_truck":
            return ["Меню", "Локация", "Контакти", "🇬🇧 English"]

        return ["Меню", "Контакти", "🇬🇧 English"]

    def welcome_fallback(self):
        if self.is_en():
            return {
                "restaurant": "👋 Hello! I can help with the menu, recommendations, contact details or reservations.",
                "cafe": "👋 Hello! I can help with coffee, desserts, opening hours or reservations.",
                "bar": "👋 Hello! I can help with drinks, cocktails, menu, contact details or reservations.",
                "pub": "👋 Hello! I can help with beer, appetizers, food, contact details or reservations.",
                "pizzeria": "👋 Hello! I can help with pizzas, menu, contact details or reservations.",
                "fast_food": "👋 Hello! I can help with the menu, prices and order information.",
                "bakery": "👋 Hello! I can help with products, availability, orders and opening hours.",
                "sweet_shop": "👋 Hello! I can help with cakes, desserts, requests and opening hours.",
                "food_truck": "👋 Hello! I can help with the menu, location and opening hours.",
            }.get(self.business_type, "👋 Hello! How can I help?")

        return {
            "restaurant": "👋 Здравейте! Мога да помогна с меню, препоръки, контакти или резервация.",
            "cafe": "👋 Здравейте! Мога да помогна с кафе, десерти, работно време или резервация.",
            "bar": "👋 Здравейте! Мога да помогна с напитки, коктейли, меню, контакти или резервация.",
            "pub": "👋 Здравейте! Мога да помогна с бира, мезета, храна, контакти или резервация.",
            "pizzeria": "👋 Здравейте! Мога да помогна с пици, меню, контакти или резервация.",
            "fast_food": "👋 Здравейте! Мога да помогна с меню, цени и информация за поръчка.",
            "bakery": "👋 Здравейте! Мога да помогна с продукти, наличности, поръчки и работно време.",
            "sweet_shop": "👋 Здравейте! Мога да помогна с торти, десерти, заявки и работно време.",
            "food_truck": "👋 Здравейте! Мога да помогна с меню, локация и работно време.",
        }.get(self.business_type, "👋 Здравейте! С какво мога да помогна?")

    def add_history(self, role, text):
        if "chat_history" not in self.context or not isinstance(self.context.get("chat_history"), list):
            self.context["chat_history"] = []

        clean_text = (text or "").strip()
        if not clean_text:
            return

        self.context["chat_history"].append({"role": role, "text": clean_text})
        self.context["chat_history"] = self.context["chat_history"][-12:]

    def make_response(self, text, buttons=None, image_url="", extra=None):
        if buttons is None:
            buttons = self.default_buttons()

        buttons = list(buttons or [])

        if buttons:
            lang_btn = "🇧🇬 Български" if self.is_en() else "🇬🇧 English"
            if lang_btn not in buttons:
                buttons.append(lang_btn)

        self.add_history("assistant", text)

        response = {
            "text": text,
            "buttons": buttons,
            "context": self.context,
        }

        if image_url:
            response["image_url"] = image_url

        if extra and isinstance(extra, dict):
            response.update(extra)

        return response

    def normalize_quick_button_text(self, text):
        t = (text or "").strip().lower()

        mapping = {
            "menu": "Меню",
            "contact": "Контакти",
            "contacts": "Контакти",
            "location": "Локация",
            "new reservation": "Нова резервация",
            "reservation": "Нова резервация",
            "show photo": "Покажи снимка",
            "more information": "Повече информация",
            "today": "Днес",
            "tomorrow": "Утре",
            "yes": "Да",
            "cancel": "Отмени",
            "salads": "Салати",
            "salad": "Салати",
            "main dishes": "Основни",
            "mains": "Основни",
            "desserts": "Десерти",
            "dessert": "Десерти",
            "drinks": "Напитки",
            "drink": "Напитки",
            "cocktails": "Коктейли",
            "beer": "Бира",
            "wine": "Вино",
            "appetizers": "Мезета",
        }

        return mapping.get(t, text)

    def translate_common_english_items(self, text):
        text = (text or "").lower()

        aliases = {
            "chicken steak": "пилешка пържола",
            "chicken fillet": "пилешка пържола",
            "pasta carbonara": "паста карбонара",
            "carbonara": "паста карбонара",
            "cheesecake": "чийзкейк",
            "homemade lemonade": "домашна лимонада",
            "lemonade": "домашна лимонада",
            "ayran": "айрян",
            "classic burger": "бургер класик",
            "pizza margherita": "пица маргарита",
            "garlic sauce": "чеснов сос",
            "french fries": "пържени картофки",
            "meat platter": "плато мезета",
            "salads": "салати",
            "salad": "салати",
            "main dishes": "основни",
            "mains": "основни",
            "main course": "основни",
            "main courses": "основни",
            "desserts": "десерти",
            "dessert": "десерти",
            "drinks": "напитки",
            "drink": "напитки",
            "beverages": "напитки",
            "soft drinks": "безалкохолни",
            "cocktails": "коктейли",
            "cocktail": "коктейли",
            "shots": "шотове",
            "beer": "бира",
            "beers": "бира",
            "draft beer": "наливна бира",
            "craft beer": "крафт бира",
            "wine": "вино",
            "wines": "вино",
            "white wine": "чаша бяло вино",
            "red wine": "чаша червено вино",
            "whiskey": "уиски",
            "vodka": "водка",
            "gin": "джин",
            "rum": "ром",
            "tequila": "текила",
            "rakia": "ракия",
            "appetizers": "мезета",
            "starter": "мезета",
            "starters": "мезета",
            "meze": "мезета",
            "snacks": "мезета",
            "fries": "картофи",
            "chips": "картофи",
            "potatoes": "картофи",
            "potato": "картофи",
            "pizza": "пици",
            "pizzas": "пици",
            "burger": "бургери",
            "burgers": "бургери",
            "pasta": "паста",
            "spaghetti": "спагети",
            "carbonara": "карбонара",
            "steak": "пържола",
            "chicken": "пиле",
            "beef": "телешко",
            "pork": "свинско",
            "bacon": "бекон",
            "meat": "месо",
            "fish": "риба",
            "greek salad": "гръцка салата",
            "caesar salad": "цезар",
            "caesar": "цезар",
            "tomato": "домати",
            "tomatoes": "домати",
            "cucumber": "краставици",
            "cucumbers": "краставици",
            "cheese": "сирене",
            "mozzarella": "моцарела",
            "parmesan": "пармезан",
            "olive": "маслини",
            "olives": "маслини",
            "cake": "торта",
            "cheesecake": "чийзкейк",
            "tiramisu": "тирамису",
            "ice cream": "сладолед",
            "coffee": "кафе",
            "espresso": "еспресо",
            "cappuccino": "капучино",
            "latte": "лате",
            "tea": "чай",
            "water": "вода",
            "juice": "сок",
            "cola": "кола",
            "coke": "кола",
            "lemonade": "лимонада",
            "ayran": "айрян",
            "mojito": "мохито",
            "aperol spritz": "aperol spritz",
            "aperol": "aperol spritz",
            "nuts": "ядки",
            "platter": "плато мезета",
            "meat platter": "плато мезета",
            "breakfast": "закуски",
            "eggs": "яйца",
            "sandwich": "сандвич",
            "sandwiches": "сандвичи",
            "soup": "супа",
            "soups": "супи",
            "grill": "скара",
            "bbq": "барбекю",
            "shopska salad": "шопска салата",
            "shopska": "шопска салата",
            "sushi": "суши",
            "ramen": "рамен",
            "tacos": "тако",
            "taco": "тако",
            "vegan": "веган",
            "vegetarian": "вегетарианско",
            "gluten free": "без глутен",
        }

        for en in sorted(aliases.keys(), key=len, reverse=True):
            text = text.replace(en, aliases[en])

        return text

    def translate_item_name(self, name, item=None):
        if not self.is_en():
            return name

        if item:
            name_en = (item.get("name_en") or "").strip()
        if name_en:
                return name_en

        return name

    def translate_category_name(self, name, category=None):
        if not self.is_en():
            return name

        if category:
            name_en = (category.get("name_en") or "").strip()
        if name_en:
            return name_en

        return name

    def translate_description(self, description, item=None):
        if not self.is_en():
            return description

        if item:
            description_en = (item.get("description_en") or "").strip()
        if description_en:
            return description_en

        return description

    def translate_address(self, address):
        if not self.is_en():
            return address

        text = address or ""

        replacements = {
            "ул.": "St.",
            "улица": "Street",
            "бул.": "Blvd.",
            "булевард": "Boulevard",
            "София": "Sofia",
            "България": "Bulgaria",
            "Центъра на града": "City center",
            "центъра на града": "City center",
            "Витоша": "Vitosha",
        }

        for bg, en in replacements.items():
            text = text.replace(bg, en)

        return text

    def translate_working_hours(self, working_hours):
        if not self.is_en():
            return working_hours

        text = working_hours or ""

        replacements = {
            "Понеделник - Неделя": "Monday - Sunday",
            "Понеделник": "Monday",
            "Вторник": "Tuesday",
            "Сряда": "Wednesday",
            "Четвъртък": "Thursday",
            "Петък": "Friday",
            "Събота": "Saturday",
            "Неделя": "Sunday",
            "понеделник": "Monday",
            "вторник": "Tuesday",
            "сряда": "Wednesday",
            "четвъртък": "Thursday",
            "петък": "Friday",
            "събота": "Saturday",
            "неделя": "Sunday",
            "Всеки ден": "Every day",
            "Почивен ден": "Closed",
            "до": "to",
        }

        for bg, en in replacements.items():
            text = text.replace(bg, en)

        return text

    def looks_like_food_question(self, text):
        text = (text or "").lower().strip()

        keywords = [
            "меню", "какво имате", "какво препоръч", "какво да ям",
            "има ли", "имате ли", "препоръчваш", "препоръчай",
            "храна", "ястие", "ястия", "напит", "напитки",
            "десерт", "десерти", "кафе", "чай", "пица", "бургер",
            "салата", "паста", "месо", "пиле", "риба", "веган",
            "вегетариан", "без глутен", "люто", "торта", "сладкиш",
            "закуска", "хляб", "кроасан", "коктейл", "бира", "вино",
            "уиски", "ракия", "леко", "вечер", "сладко", "солено",
            "нещо с", "нещо без", "а без", "какво е добро", "какво върви",
            "колко струва", "цена", "цени", "струва", "евтино",
            "евтин", "евтина", "до 10", "до 15", "до 20", "евро", "€",
            "menu", "food", "dish", "dishes", "drink", "drinks", "dessert",
            "coffee", "tea", "pizza", "burger", "salad", "pasta", "meat",
            "chicken", "fish", "vegan", "vegetarian", "gluten free",
            "spicy", "cake", "croissant", "cocktail", "beer", "wine",
            "whiskey", "cheap", "price", "prices", "how much", "recommend",
            "what do you have", "what do you recommend", "without", "something with",
            "is there anything", "do you have anything", "anything with", "anything without",
            "with potatoes", "with olives", "with cheese", "without meat", "no meat",
        ]

        return any(k in text for k in keywords)

    def looks_like_price_question(self, text):
        text = (text or "").lower().strip()
        return any(k in text for k in [
            "колко струва", "цена", "цени", "струва",
            "how much", "price", "prices", "cost"
        ])

    def looks_like_recommendation_question(self, text):
        text = (text or "").lower().strip()
        return any(k in text for k in [
            "препоръчай", "какво препоръч", "нещо евтино",
            "нещо хубаво", "нещо вкусно", "нещо леко",
            "до 10", "до 15", "до 20", "под 10", "под 12", "под 15", "под 20",
            "бюджет", "за двама", "какво да взема", "какво да поръчам",
            "има ли нещо", "имате ли нещо", "нещо с", "нещо от",
            "а без", "без ",
            "recommend", "something cheap", "something good", "something tasty",
            "something light", "under 10", "under 12", "under 15", "under 20",
            "budget", "for two", "what should i order", "what should i get",
            "do you have something", "something with", "without", "no ", "is there anything",
            "do you have anything", "do you have something", "anything with", "anything without",
            "something with", "something without", "with ", "without ", "no meat", "without meat",
            "with potatoes", "with olives", "with cheese",

        ])

    def looks_like_location_question(self, text):
        text = (text or "").lower()
        return any(k in text for k in [
            "къде сте", "локация", "адрес", "намирате", "къде се намирате",
            "where are you", "location", "address", "where are you located"
        ])

    def looks_like_more_info_request(self, text):
        text = (text or "").lower().strip()
        return any(k in text for k in [
            "повече информация", "още информация", "детайли",
            "подробности", "кажи повече", "покажи повече", "информация",
            "more info", "more information", "details", "tell me more",
            "show me more", "info"
        ])

    def looks_like_image_request(self, text):
        text = (text or "").lower().strip()

        strong_keywords = [
            "снимка", "покажи снимка", "как изглежда", "покажи ми го",
            "снимчица", "фото", "изображение",
            "photo", "image", "picture", "show photo", "show image",
            "what does it look like"
        ]

        return any(k in text for k in strong_keywords)

    def is_menu_category_message(self, text):
        text = self.translate_common_english_items(text)
        return find_menu_category_match(self.tenant_id, text) is not None

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

    def clear_reservation_context_if_needed(self, text, intent):
        if intent in ["reservation", "confirm"]:
            return

        if self.is_menu_category_message(text) or self.looks_like_food_question(text) or intent in ["menu", "contact"]:
            old_topic = self.context.get("last_topic")
            old_item = self.context.get("last_recommended_item")
            old_upsell = self.context.get("last_suggested_upsell")
            old_history = self.context.get("chat_history", [])
            old_language = self.context.get("language", "bg")
            old_category = self.context.get("last_seen_category")

            self.context = self.empty_context()
            self.context["last_topic"] = old_topic
            self.context["last_recommended_item"] = old_item
            self.context["last_suggested_upsell"] = old_upsell
            self.context["last_seen_category"] = old_category
            self.context["chat_history"] = old_history
            self.context["language"] = old_language

    def update_topic_context(self, text, intent):
        if self.looks_like_food_question(text) or intent == "menu" or self.is_menu_category_message(text):
            self.context["last_topic"] = "food"
        elif intent == "contact":
            self.context["last_topic"] = "contact"
        elif intent == "reservation":
            self.context["last_topic"] = "reservation"

    def should_use_llm(self, original_message, intent, llm_enabled):
        if llm_enabled != 1:
            return False

        if intent in ["menu", "general"]:
            return True

        if self.looks_like_food_question(original_message):
            return True

        if self.context.get("last_topic") == "food":
            return True

        return False

    def find_item_by_text(self, text):
        search_message = self.translate_common_english_items(text)
        return find_item_mentioned_in_text(self.tenant_id, search_message)

    def find_item_by_name(self, item_name):
        if not item_name:
            return None
        return self.find_item_by_text(item_name)

    def save_upsell_memory(self, upsell, base_item=None):
        if not upsell:
            return

        buttons = upsell.get("buttons") or []
        ignored_buttons = [
            "Меню", "Контакти", "Нова резервация", "Локация",
            "Menu", "Contact", "New reservation", "Location",
            "🇧🇬 Български", "🇬🇧 English"
        ]

        for button in buttons:
            if button in ignored_buttons:
                continue

            suggested_item = self.find_item_by_name(button)

            if not suggested_item:
                continue

            if base_item and suggested_item.get("id") == base_item.get("id"):
                continue

            self.context["last_suggested_upsell"] = suggested_item
            return

    def build_upsell_text(self, base_item, suggested_item):
        base_name = self.translate_item_name(base_item.get("name"), base_item) if base_item else self.tr("това", "this")
        suggested_name = self.translate_item_name(suggested_item.get("name"), suggested_item) if suggested_item else self.tr("това предложение", "this suggestion")

        if self.is_en():
            return f"{suggested_name} goes very well with “{base_name}” — would you like to make a reservation? 😊"

        return f"Към „{base_name}“ много добре върви {suggested_name} — искате ли да направим резервация? 😊"

    def ask_llm(self, original_message):
        llm_reply = get_llm_reply(
            self.tenant_id,
            original_message,
            chat_history=self.context.get("chat_history", [])
        )

        if llm_reply:
            return self.make_response(llm_reply, self.default_buttons())

        return None

    def format_item_details(self, item):
        name = self.translate_item_name(item.get("name") or self.tr("Артикул", "Item"), item)
        description = self.translate_description(item.get("description") or "", item)
        price = self.format_price_eur(item.get("price"))

        text = f"✅ {name} — {price}"

        if description:
            text += f"\n{description}"

        return text

    def handle_upsell_followup(self, original_message):
        suggested_item = self.context.get("last_suggested_upsell")
        last_item = self.context.get("last_recommended_item")

        if self.looks_like_image_request(original_message):
            target_item = self.find_item_by_text(original_message) or last_item or suggested_item

            if not target_item:
                return None

            self.context["last_recommended_item"] = target_item
            image_url = (target_item.get("image_url") or "").strip()

            if image_url:
                name = self.translate_item_name(target_item.get("name") or self.tr("Артикул", "Item"), target_item)
                return self.make_response(
                    self.tr(f"Ето как изглежда {name} 😊", f"Here is what {name} looks like 😊"),
                    [
                        self.tr("Повече информация", "More information"),
                        self.tr("Меню", "Menu"),
                        self.tr("Контакти", "Contact")
                    ],
                    image_url=image_url
                )

            return self.make_response(
                self.tr(
                    "В момента няма налична снимка за този артикул 😊\n\nИскате ли да ви дам повече информация?",
                    "There is no photo available for this item right now 😊\n\nWould you like more information?"
                ),
                [
                    self.tr("Повече информация", "More information"),
                    self.tr("Меню", "Menu"),
                    self.tr("Контакти", "Contact")
                ]
            )

        if self.looks_like_more_info_request(original_message):
            target_item = suggested_item or last_item

            if not target_item:
                return None

            text = self.format_item_details(target_item)
            image_url = (target_item.get("image_url") or "").strip()

            buttons = [self.tr("Меню", "Menu"), self.tr("Контакти", "Contact")]

            if image_url:
                buttons.insert(0, self.tr("Покажи снимка", "Show photo"))

            if self.supports_reservations():
                buttons.append(self.tr("Нова резервация", "New reservation"))

            return self.make_response(text, buttons)

        return None

    def handle_exact_item_question(self, original_message, upsell_enabled=False):
        item = self.find_item_by_text(original_message)

        if not item:
            return None

        self.context["last_recommended_item"] = item

        name = self.translate_item_name(item.get("name") or self.tr("Артикул", "Item"), item)
        description = self.translate_description(item.get("description") or "", item)
        price = self.format_price_eur(item.get("price"))
        image_url = (item.get("image_url") or "").strip()

        if self.looks_like_price_question(original_message):
            text = self.tr(f"💰 {name} струва {price}", f"💰 {name} costs {price}")
        else:
            text = self.tr(f"✅ Имаме {name} — {price}", f"✅ We have {name} — {price}")

        if description:
            text += f"\n{description}"

        if image_url:
            text += self.tr(
                "\n\nМога да ви покажа и снимка, ако желаете 😊",
                "\n\nI can also show you a photo if you want 😊"
            )

        upsell = get_smart_upsell_for_item(
            tenant_id=self.tenant_id,
            item=item,
            user_text=self.translate_common_english_items(original_message),
            business_type=self.business_type
        ) if upsell_enabled else None

        if upsell:
            self.save_upsell_memory(upsell, base_item=item)
            suggested_item = self.context.get("last_suggested_upsell")

            if suggested_item:
                text += "\n\n" + self.build_upsell_text(item, suggested_item)

        buttons = [self.tr("Меню", "Menu"), self.tr("Контакти", "Contact")]

        if image_url:
            buttons.insert(0, self.tr("Покажи снимка", "Show photo"))

        if self.supports_reservations():
            buttons.append(self.tr("Нова резервация", "New reservation"))

        return self.make_response(text, buttons)

    def handle_smart_recommendations(self, original_message, upsell_enabled=False):
        search_message = self.translate_common_english_items(original_message)

        items = get_smart_recommendations(
            tenant_id=self.tenant_id,
            user_text=search_message,
            business_type=self.business_type,
            limit=5
        )

        if not items:
            return self.make_response(
                self.tr(
                    "Не намерих точно такова нещо в менюто 😊\n\nМожете да опитате с друг въпрос, например: „нещо без месо“, „нещо с картофи“, „десерт“ или „напитки“.",
                    "I couldn't find an exact match in the menu 😊\n\nYou can try another question, for example: “something without meat”, “something with potatoes”, “dessert” or “drinks”."
                ),
                [self.tr("Меню", "Menu"), self.tr("Контакти", "Contact")]
        )

        lines = [self.tr("Ето няколко подходящи предложения 😊", "Here are a few suitable suggestions 😊")]

        for item in items:
            name = self.translate_item_name(item.get("name") or self.tr("Артикул", "Item"), item)
            description = self.translate_description(item.get("description") or "", item)
            price = self.format_price_eur(item.get("price"))

            if description:
                lines.append(f"- {name} — {price} — {description}")
            else:
                lines.append(f"- {name} — {price}")

        first_item = items[0]
        self.context["last_recommended_item"] = first_item

        if upsell_enabled:
            upsell = get_smart_upsell_for_item(
                tenant_id=self.tenant_id,
                item=first_item,
                user_text=search_message,
                business_type=self.business_type
            )

            if upsell:
                self.save_upsell_memory(upsell, base_item=first_item)
                suggested_item = self.context.get("last_suggested_upsell")

                if suggested_item:
                    lines.append("\n" + self.build_upsell_text(first_item, suggested_item))

        buttons = [self.tr("Меню", "Menu"), self.tr("Контакти", "Contact")]

        if first_item.get("image_url"):
            buttons.insert(0, self.tr("Покажи снимка", "Show photo"))

        if self.supports_reservations():
            buttons.append(self.tr("Нова резервация", "New reservation"))

        return self.make_response("\n".join(lines), buttons)

    def get_response(self, message, context=None):
        try:
            if context:
                self.context = context
            elif not self.context:
                self.context = self.empty_context()

            for key, value in self.empty_context().items():
                if key not in self.context:
                    self.context[key] = value

            original_message = (message or "").strip()
            normalized_message = self.normalize_quick_button_text(original_message)
            text = normalized_message.lower().strip()

            self.add_history("user", original_message)

            settings = get_tenant_settings(self.tenant_id) or {}
            intent = detect_intent(text)

            tenant_has_ai_chat = tenant_has_feature(self.tenant_id, "ai_chat")
            tenant_has_upsell = tenant_has_feature(self.tenant_id, "upsell")

            llm_enabled = 1 if (
                tenant_has_ai_chat and
                int(settings.get("llm_enabled", 0)) == 1
            ) else 0

            print("CHATBOT DEBUG:", {
                "message": original_message,
                "normalized": normalized_message,
                "intent": intent,
                "business_type": self.business_type,
                "language": self.get_lang(),
                "ai_chat_feature": tenant_has_ai_chat,
                "upsell_feature": tenant_has_upsell,
                "llm_enabled": llm_enabled,
            })

            if intent == "language_en":
                self.context["language"] = "en"
                return self.make_response(
                    "Sure 😊 I will continue in English.\nHow can I help — menu, reservation or contact?",
                    self.default_buttons()
                )

            if intent == "language_bg":
                self.context["language"] = "bg"
                return self.make_response(
                    "Разбира се 😊 Ще продължа на български.\nС какво да помогна — меню, резервация или контакти?",
                    self.default_buttons()
                )

            if intent == "cancel":
                old_history = self.context.get("chat_history", [])
                old_language = self.context.get("language", "bg")

                self.context = self.empty_context()
                self.context["chat_history"] = old_history
                self.context["language"] = old_language

                return self.make_response(
                    self.tr(
                        "❌ Добре, отмених текущото действие.",
                        "❌ Okay, I cancelled the current action."
                    ),
                    self.default_buttons()
                )

            followup_response = self.handle_upsell_followup(normalized_message)
            if followup_response:
                return followup_response

            if self.looks_like_image_request(normalized_message):
                item = self.find_item_by_text(normalized_message) or self.context.get("last_recommended_item")

                if item:
                    self.context["last_recommended_item"] = item
                    image_url = (item.get("image_url") or "").strip()

                    if image_url:
                        name = self.translate_item_name(item.get("name"), item)
                        return self.make_response(
                            f"📸 {name}",
                            [
                                self.tr("Повече информация", "More information"),
                                self.tr("Меню", "Menu"),
                                self.tr("Контакти", "Contact")
                            ],
                            image_url=image_url
                        )

                    return self.make_response(
                        self.tr(
                            "В момента няма налична снимка за този артикул 😊\n\nИскате ли да ви дам повече информация?",
                            "There is no photo available for this item right now 😊\n\nWould you like more information?"
                        ),
                        [
                            self.tr("Повече информация", "More information"),
                            self.tr("Меню", "Menu"),
                            self.tr("Контакти", "Contact")
                        ]
                    )

            self.clear_reservation_context_if_needed(normalized_message, intent)
            self.update_topic_context(normalized_message, intent)

            if self.business_type == "food_truck" and self.looks_like_location_question(normalized_message):
                return self.handle_contact(settings)

            if intent == "contact":
                return self.handle_contact(settings)
            
            exact_item_response = self.handle_exact_item_question(
                normalized_message,
                upsell_enabled=tenant_has_upsell
                )
            if exact_item_response:
                return exact_item_response

            if self.looks_like_recommendation_question(normalized_message):
                smart_response = self.handle_smart_recommendations(
                    normalized_message,
                    upsell_enabled=tenant_has_upsell
                )

                if smart_response:
                    return smart_response

            if self.is_menu_category_message(normalized_message):
                return self.handle_menu(
                    normalized_message,
                    upsell_enabled=tenant_has_upsell
                )

            if intent == "menu":
                return self.handle_menu(
                    normalized_message,
                    upsell_enabled=tenant_has_upsell
                )

            if intent == "reservation" and not self.supports_reservations():
                return self.make_response(
                    self.tr(
                        f"ℹ️ За този тип бизнес ({self.business_label}) няма класически резервации.\n\nМога да помогна с меню, контакти и информация.",
                        f"ℹ️ This business type ({self.business_label}) does not use classic reservations.\n\nI can help with the menu, contact details and information."
                    ),
                    self.default_buttons()
                )

            people = extract_people(normalized_message)
            date = extract_date(normalized_message)
            time = extract_time(normalized_message)
            name, phone = extract_contact(normalized_message)

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

            if self.supports_reservations() and self.is_reservation_in_progress():
                return self.handle_reservation(settings)

            if self.supports_reservations() and intent == "reservation":
                return self.handle_reservation(settings)

            if self.should_use_llm(normalized_message, intent, llm_enabled):
                llm_response = self.ask_llm(normalized_message)

                if llm_response:
                    return llm_response

            if self.looks_like_food_question(normalized_message):
                smart_response = self.handle_smart_recommendations(
                    normalized_message,
                    upsell_enabled=tenant_has_upsell
                )

                if smart_response:
                    return smart_response

            return self.make_response(
                self.welcome_fallback(),
                self.default_buttons()
            )

        except Exception as e:
            print("CHATBOT ERROR:", e)

            return {
                "text": self.tr(
                    "⚠️ Възникна грешка. Опитайте отново.",
                    "⚠️ An error occurred. Please try again."
                ),
                "buttons": self.default_buttons(),
                "context": self.context,
            }

    def handle_contact(self, settings):
        phone = settings.get("phone") or "0888 123 456"
        address = self.translate_address(settings.get("address") or "Центъра на града")
        website = settings.get("website") or ""
        email = settings.get("email") or ""
        working_hours = settings.get("working_hours") or ""
        working_hours = self.translate_working_hours(working_hours)

        extra_lines = []

        if working_hours:
            extra_lines.append(self.tr(
                f"🕒 Работно време: {working_hours}",
                f"🕒 Working hours: {working_hours}"
            ))

        if email:
            extra_lines.append(f"✉️ Email: {email}")

        if website:
            extra_lines.append(f"🌐 Website: {website}")

        extra_text = ""
        if extra_lines:
            extra_text = "\n" + "\n".join(extra_lines)

        if self.business_type == "food_truck":
            text = self.tr(
                f"📍 Локация: {address}\n📞 Телефон: {phone}{extra_text}\n\n👉 Искате ли да видите менюто?",
                f"📍 Location: {address}\n📞 Phone: {phone}{extra_text}\n\n👉 Would you like to see the menu?"
            )
            buttons = [self.tr("Меню", "Menu"), self.tr("Контакти", "Contact")]

        elif self.supports_reservations():
            text = self.tr(
                f"📞 Телефон: {phone}\n📍 Адрес: {address}{extra_text}\n\n👉 Искате ли и да направим резервация? 😊",
                f"📞 Phone: {phone}\n📍 Address: {address}{extra_text}\n\n👉 Would you like to make a reservation? 😊"
            )
            buttons = [self.tr("Нова резервация", "New reservation"), self.tr("Меню", "Menu")]

        else:
            text = self.tr(
                f"📞 Телефон: {phone}\n📍 Адрес: {address}{extra_text}\n\n👉 Искате ли да разгледате менюто?",
                f"📞 Phone: {phone}\n📍 Address: {address}{extra_text}\n\n👉 Would you like to see the menu?"
            )
            buttons = [self.tr("Меню", "Menu")]

        return self.make_response(text, buttons)

    def handle_menu(self, text, upsell_enabled=False):
        categories = get_menu_categories(self.tenant_id)

        if not categories:
            return self.make_response(
                self.tr(
                    "📋 В момента менюто не е налично.",
                    "📋 The menu is currently not available."
                ),
                self.default_buttons()
            )

        wanted_category = find_menu_category_match(
            self.tenant_id,
            self.translate_common_english_items(text)
        )

        if not wanted_category:
            category_names = [self.translate_category_name(c["name"], c) for c in categories]

            intro = self.tr(
                {
                    "restaurant": "🍽️ Разбира се 😊 Ето категориите в нашето меню.",
                    "cafe": "☕ Разбира се 😊 Ето какво можете да разгледате.",
                    "bar": "🍸 Разбира се 😊 Ето категориите с напитки и предложения.",
                    "pub": "🍺 Разбира се 😊 Ето категориите с напитки, мезета и храна.",
                    "pizzeria": "🍕 Разбира се 😊 Ето категориите в менюто.",
                    "fast_food": "🍔 Разбира се 😊 Ето какво можете да разгледате.",
                    "bakery": "🥐 Разбира се 😊 Ето нашите продукти.",
                    "sweet_shop": "🍰 Разбира се 😊 Ето десертите и предложенията.",
                    "food_truck": "🚚 Разбира се 😊 Ето менюто ни.",
                }.get(self.business_type, "📋 Разбира се 😊 Ето какво можете да разгледате."),
                "📋 Sure 😊 Here are our menu categories."
            )

            return self.make_response(
                intro + self.tr("\n\n👉 Изберете категория:", "\n\n👉 Choose a category:"),
                category_names
            )

        self.context["last_seen_category"] = wanted_category
        items = get_menu_items_by_category(self.tenant_id, wanted_category["id"])

        if not items:
            return self.make_response(
                self.tr(
                    f"📋 В категория „{wanted_category['name']}“ все още няма добавени артикули.",
                    f"📋 There are no items added in “{self.translate_category_name(wanted_category['name'])}” yet."
                ),
                [self.tr("Меню", "Menu")]
            )

        lines = [f"📋 {self.translate_category_name(wanted_category['name'], wanted_category)}:"]

        for item in items:
            item_name = self.translate_item_name(item.get("name"), item)
            description = self.translate_description(item.get("description") or "", item)
            description_text = f" — {description}" if description else ""
            has_image = " 📷" if item.get("image_url") else ""
            price = self.format_price_eur(item.get("price"))

            lines.append(f"- {item_name}{has_image} — {price}{description_text}")

        item_for_upsell = items[0] if items else None

        if item_for_upsell:
            self.context["last_recommended_item"] = item_for_upsell

        upsell = get_smart_upsell_for_item(
            self.tenant_id,
            item=item_for_upsell,
            user_text=self.translate_common_english_items(text),
            business_type=self.business_type
        ) if upsell_enabled and item_for_upsell else None

        if upsell:
            self.save_upsell_memory(upsell, base_item=item_for_upsell)
            suggested_item = self.context.get("last_suggested_upsell")

            if suggested_item:
                lines.append("\n" + self.build_upsell_text(item_for_upsell, suggested_item))
        else:
            if self.supports_reservations():
                lines.append(self.tr(
                    "\n👉 Искате ли след това да направим резервация? 😊",
                    "\n👉 Would you like to make a reservation after that? 😊"
                ))
            else:
                lines.append(self.tr(
                    "\n👉 Искате ли да видите и друга категория?",
                    "\n👉 Would you like to see another category?"
                ))

        buttons = []

        for item in items[:5]:
            if item.get("name"):
                buttons.append(self.translate_item_name(item.get("name"), item))

        buttons.append(self.tr("Меню", "Menu"))

        if self.supports_reservations():
            buttons.append(self.tr("Нова резервация", "New reservation"))

        buttons.append(self.tr("Контакти", "Contact"))

        return self.make_response("\n".join(lines), buttons)

    def handle_reservation(self, settings):
        c = self.context
        max_capacity = int(settings.get("max_capacity", 20))
        open_hour = int(settings.get("open_hour", 10))
        close_hour = int(settings.get("close_hour", 22))

        if not c.get("people"):
            c["last_question"] = "people"
            c["last_topic"] = "reservation"

            log_event(self.tenant_id, "reservation_started", {"step": "people"})

            return self.make_response(
                self.tr(
                    "С удоволствие 😊 За колко човека е резервацията?",
                    "Of course 😊 For how many people is the reservation?"
                ),
                ["2", "4", "6"]
            )

        if not is_valid_people(c["people"]):
            c["people"] = None
            c["last_question"] = "people"

            return self.make_response(
                self.tr(
                    "Моля, въведете валиден брой хора от 1 до 20 😊",
                    "Please enter a valid number of people from 1 to 20 😊"
                ),
                ["2", "4", "6"]
            )

        if not c.get("date"):
            c["last_question"] = "date"

            return self.make_response(
                self.tr(
                    f"Чудесно 😊 За {c['people']} човека — коя дата предпочитате?",
                    f"Great 😊 For {c['people']} people — which date would you prefer?"
                ),
                [self.tr("Днес", "Today"), self.tr("Утре", "Tomorrow")]
            )

        if not is_valid_future_or_today_date(c["date"]):
            c["date"] = None
            c["last_question"] = "date"

            return self.make_response(
                self.tr(
                    "Моля, въведете днешна или бъдеща дата 😊",
                    "Please enter today or a future date 😊"
                ),
                [self.tr("Днес", "Today"), self.tr("Утре", "Tomorrow")]
            )

        if not c.get("time"):
            c["last_question"] = "time"

            return self.make_response(
                self.tr(
                    f"Супер 😊 За {c['people']} човека на {c['date']} — в колко часа?",
                    f"Perfect 😊 For {c['people']} people on {c['date']} — what time?"
                ),
                ["18:00", "19:00", "20:00"]
            )

        if not is_valid_time_range(c["time"], open_hour, close_hour):
            c["time"] = None
            c["last_question"] = "time"

            return self.make_response(
                self.tr(
                    f"🕒 Работим от {open_hour}:00 до {close_hour}:00.\nМоля, изберете час в този интервал 😊",
                    f"🕒 We are open from {open_hour}:00 to {close_hour}:00.\nPlease choose a time in this range 😊"
                ),
                ["18:00", "19:00", "20:00"]
            )

        availability = self.check_availability(
            c["date"],
            c["time"],
            c["people"],
            max_capacity
        )

        if not availability["available"]:
            suggestions = self.get_suggestions(c["date"], max_capacity)
            c["last_question"] = "time"

            if suggestions:
                return self.make_response(
                    self.tr(
                        f"❌ За {c['people']} човека няма достатъчно места около {c['time']}.\n\n👉 Свободни варианти:\n{', '.join(suggestions)}",
                        f"❌ There are not enough seats for {c['people']} people around {c['time']}.\n\n👉 Available options:\n{', '.join(suggestions)}"
                    ),
                    suggestions
                )

            old_history = self.context.get("chat_history", [])
            old_language = self.context.get("language", "bg")

            self.context = self.empty_context()
            self.context["chat_history"] = old_history
            self.context["language"] = old_language

            return self.make_response(
                self.tr(
                    "❌ За тази дата няма свободни места.",
                    "❌ There are no available seats for this date."
                ),
                [self.tr("Утре", "Tomorrow"), self.tr("Меню", "Menu"), self.tr("Контакти", "Contact")]
            )

        responses = [
            self.tr(
                f"Да, има свободна маса за {c['people']} човека 😊",
                f"Yes, we have a free table for {c['people']} people 😊"
            ),
            self.tr(
                f"Разбира се! Имаме място за {c['people']} души 👍",
                f"Of course! We have space for {c['people']} people 👍"
            ),
            self.tr(
                f"Да, можем да ви настаним за {c['people']} човека 🍽️",
                f"Yes, we can seat {c['people']} people 🍽️"
            )
        ]

        if not c.get("name") or not c.get("phone"):
            c["last_question"] = "contact"

            return self.make_response(
                random.choice(responses) + self.tr(
                    f"""

📅 {c['date']}
⏰ около {c['time']}
👥 {c['people']} човека
🟢 Свободни места за този час: {availability['free_places_after']}

👉 Кажете име и телефон за резервацията 😊""",
                    f"""

📅 {c['date']}
⏰ around {c['time']}
👥 {c['people']} people
🟢 Free seats after this booking: {availability['free_places_after']}

👉 Please send a name and phone number for the reservation 😊"""
                ),
                []
            )

        if not is_valid_phone(c["phone"]):
            c["phone"] = None
            c["last_question"] = "contact"

            return self.make_response(
                self.tr(
                    "📞 Моля, изпратете валиден телефон, например 0898123456",
                    "📞 Please send a valid phone number, for example 0898123456"
                ),
                []
            )

        if not c.get("confirmed"):
            c["last_question"] = "confirm"

            return self.make_response(
                self.tr(
                    f"""📌 Моля, потвърдете резервацията:

Име: {c['name']}
Телефон: {c['phone']}
Дата: {c['date']}
Час: {c['time']}
Хора: {c['people']}

👉 Напишете 'да' за потвърждение или 'отмени'.""",
                    f"""📌 Please confirm the reservation:

Name: {c['name']}
Phone: {c['phone']}
Date: {c['date']}
Time: {c['time']}
People: {c['people']}

👉 Type 'yes' to confirm or 'cancel'."""
                ),
                [self.tr("Да", "Yes"), self.tr("Отмени", "Cancel")]
            )

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

        return {
            "available": available,
            "occupied": occupied,
            "free_places_before": max(max_capacity - occupied, 0),
            "free_places_after": max(max_capacity - (occupied + requested_people), 0)
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

        create_reservation(
            tenant_id=self.tenant_id,
            name=c["name"],
            phone=c["phone"],
            date=c["date"],
            time=c["time"],
            people=c["people"],
            source="chatbot",
            status="confirmed",
            notes=""
        )

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

        old_history = self.context.get("chat_history", [])
        old_language = self.context.get("language", "bg")

        self.context = self.empty_context()
        self.context["chat_history"] = old_history
        self.context["language"] = old_language

        return self.make_response(
            self.tr(
                f"""✅ Готово! Резервацията е записана.

📌 {data['name']}
📅 {data['date']}
⏰ {data['time']}
👥 {data['people']} човека

Очакваме ви 😊""",
                f"""✅ Done! The reservation has been saved.

📌 {data['name']}
📅 {data['date']}
⏰ {data['time']}
👥 {data['people']} people

We are expecting you 😊"""
            ),
            [
                self.tr("Меню", "Menu"),
                self.tr("Контакти", "Contact"),
                self.tr("Нова резервация", "New reservation")
            ]
        )