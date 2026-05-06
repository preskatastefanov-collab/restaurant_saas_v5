from database import get_db


def normalize_text(value):
    return " ".join((value or "").strip().lower().split())


def safe_float(value, default=0):
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return default


def has_cyrillic(text):
    text = text or ""
    return any("а" <= ch.lower() <= "я" for ch in text)


def clean_image_url(value):
    image_url = (value or "").strip()

    if not image_url:
        return ""

    image_url = image_url.replace("\\", "/")

    if image_url.startswith("http://") or image_url.startswith("https://"):
        return image_url

    if image_url.startswith("/static/"):
        return image_url

    if image_url.startswith("static/"):
        return "/" + image_url

    if image_url.startswith("uploads/"):
        return "/static/" + image_url

    return image_url


def format_price(value):
    price = safe_float(value, 0)

    if price <= 0:
        return "без цена"

    return f"{price:.2f} €"


def bg_to_en(value):
    text = (value or "").strip()

    if not text:
        return ""

    if not has_cyrillic(text):
        return text

    try:
        from openai import OpenAI
        from config import OPENAI_API_KEY

        if not OPENAI_API_KEY:
            print("TRANSLATE DEBUG: липсва OPENAI_API_KEY")
            return text

        client = OpenAI(api_key=OPENAI_API_KEY)

        prompt = f"""
Translate this Bulgarian restaurant menu text to natural English.

Return ONLY the English translation.
No explanations.
No quotation marks.

Text:
{text}
""".strip()

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": "You are a professional restaurant menu translator from Bulgarian to English."
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            max_tokens=80,
        )

        translated = response.choices[0].message.content.strip()

        if translated and not has_cyrillic(translated):
            print("TRANSLATE OK:", text, "=>", translated)
            return translated

        print("TRANSLATE WARNING:", text, "=>", translated)
        return text

    except Exception as e:
        print("TRANSLATE ERROR:", e)
        return text


def get_en_or_translate(en_value, bg_value):
    en_value = (en_value or "").strip()
    bg_value = (bg_value or "").strip()

    if en_value and not has_cyrillic(en_value):
        return en_value

    return bg_to_en(bg_value)


def normalize_item_row(item):
    item = dict(item)
    item["image_url"] = clean_image_url(item.get("image_url"))

    item["name_en"] = item.get("name_en") or item.get("name") or ""
    item["description_en"] = item.get("description_en") or item.get("description") or ""
    item["category_name_en"] = item.get("category_name_en") or item.get("category_name") or ""
    item["upsell_drink_en"] = item.get("upsell_drink_en") or item.get("upsell_drink") or ""
    item["upsell_dessert_en"] = item.get("upsell_dessert_en") or item.get("upsell_dessert") or ""
    item["upsell_side_en"] = item.get("upsell_side_en") or item.get("upsell_side") or ""

    return item


def get_menu_categories(tenant_id):
    db = get_db()
    rows = db.execute("""
        SELECT *
        FROM menu_categories
        WHERE tenant_id = ? AND is_active = 1
        ORDER BY sort_order ASC, id ASC
    """, (tenant_id,)).fetchall()
    db.close()

    result = []

    for row in rows:
        cat = dict(row)
        cat["name_en"] = cat.get("name_en") or cat.get("name") or ""
        result.append(cat)

    return result


def get_menu_items_by_category(tenant_id, category_id, include_inactive=False):
    db = get_db()

    if include_inactive:
        rows = db.execute("""
            SELECT mi.*, mc.name AS category_name, mc.name_en AS category_name_en
            FROM menu_items mi
            LEFT JOIN menu_categories mc ON mc.id = mi.category_id
            WHERE mi.tenant_id = ? AND mi.category_id = ?
            ORDER BY mi.sort_order ASC, mi.id ASC
        """, (tenant_id, category_id)).fetchall()
    else:
        rows = db.execute("""
            SELECT mi.*, mc.name AS category_name, mc.name_en AS category_name_en
            FROM menu_items mi
            LEFT JOIN menu_categories mc ON mc.id = mi.category_id
            WHERE mi.tenant_id = ? AND mi.category_id = ? AND mi.is_active = 1
            ORDER BY mi.sort_order ASC, mi.id ASC
        """, (tenant_id, category_id)).fetchall()

    db.close()
    return [normalize_item_row(r) for r in rows]


def get_full_menu(tenant_id, include_inactive=False):
    categories = get_menu_categories(tenant_id)
    result = []

    for category in categories:
        items = get_menu_items_by_category(
            tenant_id,
            category["id"],
            include_inactive=include_inactive
        )

        result.append({
            "category": category,
            "items": items
        })

    return result


def get_all_menu_items(tenant_id):
    db = get_db()
    rows = db.execute("""
        SELECT
            mi.*,
            mc.name AS category_name,
            mc.name_en AS category_name_en
        FROM menu_items mi
        LEFT JOIN menu_categories mc ON mc.id = mi.category_id
        WHERE mi.tenant_id = ? AND mi.is_active = 1
        ORDER BY mi.sort_order ASC, mi.id ASC
    """, (tenant_id,)).fetchall()
    db.close()

    return [normalize_item_row(r) for r in rows]


def get_search_aliases():
    return {
        "salads": "салати",
        "salad": "салати",
        "main dishes": "основни",
        "mains": "основни",
        "desserts": "десерти",
        "dessert": "десерти",
        "drinks": "напитки",
        "drink": "напитки",
        "lemonade": "лимонада",
        "ayran": "айрян",
        "chicken steak": "пилешка пържола",
        "caesar": "цезар",
        "caesar salad": "цезар",
        "greek salad": "гръцка салата",
        "pasta carbonara": "паста карбонара",
        "carbonara": "карбонара",
        "cheesecake": "чийзкейк",
    }


def expand_search_text(text):
    text_clean = normalize_text(text)
    aliases = get_search_aliases()

    variants = set()
    variants.add(text_clean)

    for en, bg in aliases.items():
        if en in text_clean:
            variants.add(normalize_text(text_clean.replace(en, bg)))
            variants.add(normalize_text(bg))

    return [v for v in variants if v]


def find_menu_category_match(tenant_id, text):
    categories = get_menu_categories(tenant_id)
    search_variants = expand_search_text(text)

    for search_text in search_variants:
        for category in categories:
            names = [
                normalize_text(category.get("name")),
                normalize_text(category.get("name_en")),
            ]

            if search_text in names:
                return category

    for search_text in search_variants:
        for category in categories:
            names = [
                normalize_text(category.get("name")),
                normalize_text(category.get("name_en")),
            ]

            if any(name and name in search_text for name in names):
                return category

    return None


def find_item_mentioned_in_text(tenant_id, text):
    search_variants = expand_search_text(text)
    items = get_all_menu_items(tenant_id)

    exact_matches = []
    partial_matches = []

    for item in items:
        item_names = [
            normalize_text(item.get("name")),
            normalize_text(item.get("name_en")),
        ]

        for search_text in search_variants:
            for item_name in item_names:
                if not item_name:
                    continue

                if search_text == item_name:
                    exact_matches.append(item)
                elif item_name in search_text:
                    partial_matches.append(item)
                elif search_text in item_name and len(search_text) >= 3:
                    partial_matches.append(item)

    if exact_matches:
        return exact_matches[0]

    if partial_matches:
        partial_matches.sort(
            key=lambda x: len(normalize_text(x.get("name"))),
            reverse=True
        )
        return partial_matches[0]

    return None


def search_menu_items(tenant_id, text, limit=6):
    search_variants = expand_search_text(text)
    items = get_all_menu_items(tenant_id)
    scored_items = []

    for item in items:
        searchable = " ".join([
            normalize_text(item.get("category_name")),
            normalize_text(item.get("category_name_en")),
            normalize_text(item.get("name")),
            normalize_text(item.get("name_en")),
            normalize_text(item.get("description")),
            normalize_text(item.get("description_en")),
        ])

        score = 0

        for search_text in search_variants:
            words = [w for w in search_text.split() if len(w) >= 3]

            if search_text in searchable:
                score += 10

            for word in words:
                if word in searchable:
                    score += 3

        if score > 0:
            scored_items.append((score, item))

    scored_items.sort(key=lambda x: x[0], reverse=True)
    return [item for score, item in scored_items[:limit]]


def get_items_by_category_keywords(tenant_id, keywords):
    items = get_all_menu_items(tenant_id)
    result = []

    normalized_keywords = []
    for keyword in keywords:
        normalized_keywords += expand_search_text(keyword)

    normalized_keywords = list(set([k for k in normalized_keywords if k]))

    for item in items:
        combined = " ".join([
            normalize_text(item.get("category_name")),
            normalize_text(item.get("category_name_en")),
            normalize_text(item.get("name")),
            normalize_text(item.get("name_en")),
            normalize_text(item.get("description")),
            normalize_text(item.get("description_en")),
        ])

        if any(k in combined for k in normalized_keywords):
            result.append(item)

    return result


def get_items_by_price_range(tenant_id, max_price=None, min_price=None, limit=8):
    items = get_all_menu_items(tenant_id)
    result = []

    for item in items:
        price = safe_float(item.get("price"))

        if price <= 0:
            continue

        if max_price is not None and price > max_price:
            continue

        if min_price is not None and price < min_price:
            continue

        result.append(item)

    result.sort(key=lambda x: safe_float(x.get("price")))
    return result[:limit]


def get_popular_menu_items(tenant_id, business_type="restaurant", limit=6):
    return get_all_menu_items(tenant_id)[:limit]


def get_best_drink(tenant_id, business_type="restaurant"):
    drinks = get_items_by_category_keywords(
        tenant_id,
        ["напит", "лимонада", "айрян", "бира", "вино", "кафе", "lemonade", "ayran", "beer", "wine", "coffee"]
    )
    return drinks[0] if drinks else None


def get_best_dessert(tenant_id, business_type="restaurant"):
    desserts = get_items_by_category_keywords(
        tenant_id,
        ["десерт", "чийзкейк", "торта", "тирамису", "dessert", "cheesecake", "cake", "tiramisu"]
    )
    return desserts[0] if desserts else None


def get_best_side(tenant_id, business_type="restaurant"):
    sides = get_items_by_category_keywords(
        tenant_id,
        ["картофи", "сос", "мезе", "плато", "fries", "sauce", "appetizer", "platter"]
    )
    return sides[0] if sides else None


def extract_price_limit(text):
    text = normalize_text(text)

    numbers = []
    current = ""

    for char in text:
        if char.isdigit():
            current += char
        else:
            if current:
                numbers.append(int(current))
                current = ""

    if current:
        numbers.append(int(current))

    if not numbers:
        return None

    return max(numbers)


def unique_items(items):
    result = []
    seen = set()

    for item in items:
        name = normalize_text(item.get("name"))

        if name in seen:
            continue

        seen.add(name)
        result.append(item)

    return result


def item_search_text(item):
    return normalize_text(" ".join([
        item.get("category_name") or "",
        item.get("category_name_en") or "",
        item.get("name") or "",
        item.get("name_en") or "",
        item.get("description") or "",
        item.get("description_en") or "",
    ]))


def detect_food_filters(user_text):
    text = normalize_text(user_text)

    filters = {
        "without": [],
        "with": [],
        "category": [],
    }

    groups = {
        "meat": [
            "месо", "пиле", "пилешко", "телешко", "свинско", "бекон", "шунка",
            "кюфте", "кебапче", "пържола", "агне", "риба", "сьомга",
            "meat", "chicken", "beef", "pork", "bacon", "ham", "steak", "lamb", "fish"
        ],
        "potatoes": [
            "картоф", "картофи", "картофки", "пържени картофи",
            "potato", "potatoes", "fries", "french fries"
        ],
        "cheese": [
            "сирене", "кашкавал", "моцарела", "пармезан",
            "cheese", "mozzarella", "parmesan"
        ],
        "spicy": [
            "люто", "пикантно", "чили",
            "spicy", "hot", "chili"
        ],
        "dessert": [
            "десерт", "торта", "сладкиш", "чийзкейк", "тирамису",
            "dessert", "cake", "cheesecake", "tiramisu"
        ],
        "drink": [
            "напитка", "напитки", "лимонада", "бира", "вино", "кафе", "айрян",
            "drink", "drinks", "lemonade", "beer", "wine", "coffee", "ayran"
        ],
        "vegetarian": [
            "вегетариан", "без месо", "vegetarian", "without meat", "no meat"
        ],
    }

    negative_words = ["без", "няма", "without", "no "]
    positive_words = ["с ", "със ", "има ли", "имате ли", "нещо с", "with", "something with"]

    for group_name, keywords in groups.items():
        if any(k in text for k in keywords):
            if any(w in text for w in negative_words):
                filters["without"].extend(keywords)
            elif group_name == "vegetarian":
                filters["without"].extend(groups["meat"])
            else:
                filters["with"].extend(keywords)

    return filters


def get_smart_recommendations(tenant_id, user_text="", business_type="restaurant", limit=5):
    user_text_clean = normalize_text(user_text)

    items = get_all_menu_items(tenant_id)

    if not items:
        return []

    if not user_text_clean:
        return get_popular_menu_items(tenant_id, business_type, limit=limit)

    cheap_words = ["евтино", "бюджет", "най-евтин", "най евтин", "по-евтино", "достъпно", "cheap", "budget"]
    price_words = ["до", "под", "€", "евро", "under", "up to"]

    max_price = extract_price_limit(user_text_clean)

    if max_price and any(w in user_text_clean for w in price_words + cheap_words):
        return get_items_by_price_range(tenant_id, max_price=max_price, limit=limit)

    if any(w in user_text_clean for w in cheap_words):
        return get_items_by_price_range(tenant_id, max_price=10, limit=limit)

    filters = detect_food_filters(user_text_clean)

    if filters["without"]:
        blocked = [normalize_text(x) for x in filters["without"] if x]

    extra_meat_words = [
        "месо",
        "пиле",
        "пилешко",
        "телешко",
        "свинско",
        "бекон",
        "шунка",
        "риба",
        "сьомга",
        "бургер",
        "кюфте",
        "кебапче",
        "пържола",
        "meat",
        "chicken",
        "beef",
        "pork",
        "bacon",
        "ham",
        "fish",
        "salmon",
        "burger",
        "steak",
    ]

    if any(x in blocked for x in ["месо", "meat"]):
        blocked.extend(extra_meat_words)

    result = []

    for item in items:
        combined = item_search_text(item)

        if any(word in combined for word in blocked):
            continue

        result.append(item)

        return unique_items(result)[:limit]
        result = []

        for item in items:
            combined = item_search_text(item)

            if not any(word in combined for word in blocked):
                result.append(item)

        return unique_items(result)[:limit]

    if filters["with"]:
        wanted = [normalize_text(x) for x in filters["with"] if x]
        result = []

        for item in items:
            combined = item_search_text(item)

            if any(word in combined for word in wanted):
                result.append(item)

        return unique_items(result)[:limit]

    searched = search_menu_items(tenant_id, user_text, limit=limit)

    if searched:
        return unique_items(searched)[:limit]

    return []


def menu_item_to_text(item):
    name = item.get("name", "Артикул")
    name_en = item.get("name_en") or bg_to_en(name)
    description = item.get("description") or ""
    description_en = item.get("description_en") or bg_to_en(description)
    price = format_price(item.get("price"))
    category = item.get("category_name") or ""
    category_en = item.get("category_name_en") or bg_to_en(category)
    image_note = "има снимка" if item.get("image_url") else "няма снимка"

    parts = [f"{name} / {name_en}"]

    if category:
        parts.append(f"категория: {category} / {category_en}")

    if description:
        parts.append(f"{description} / {description_en}")

    parts.append(f"цена: {price}")
    parts.append(image_note)

    return " — ".join(parts)


def get_menu_summary_for_ai(tenant_id, max_items=80):
    full_menu = get_full_menu(tenant_id)
    lines = []

    for block in full_menu:
        category = block.get("category", {})
        items = block.get("items", [])

        category_name = category.get("name", "Категория")
        category_name_en = category.get("name_en") or bg_to_en(category_name)

        lines.append(f"\nКатегория: {category_name} / {category_name_en}")

        for item in items[:max_items]:
            name = item.get("name", "Артикул")
            name_en = item.get("name_en") or bg_to_en(name)
            description = item.get("description") or ""
            description_en = item.get("description_en") or bg_to_en(description)
            price = format_price(item.get("price"))
            image_note = " | има снимка" if item.get("image_url") else ""

            if description:
                lines.append(f"- {name} / {name_en}: {description} / {description_en} ({price}){image_note}")
            else:
                lines.append(f"- {name} / {name_en} ({price}){image_note}")

    result = "\n".join(lines).strip()
    return result if result else "Няма въведено меню."


def get_menu_context_for_chatbot(tenant_id, business_type="restaurant", user_text="", limit=6):
    recommendations = get_smart_recommendations(
        tenant_id=tenant_id,
        user_text=user_text,
        business_type=business_type,
        limit=limit
    )

    if not recommendations:
        return {
            "recommendations": [],
            "recommendations_text": "Няма намерени подходящи предложения.",
            "full_menu_text": get_menu_summary_for_ai(tenant_id)
        }

    recommendations_text = "\n".join([
        f"- {menu_item_to_text(item)}"
        for item in recommendations
    ])

    return {
        "recommendations": recommendations,
        "recommendations_text": recommendations_text,
        "full_menu_text": get_menu_summary_for_ai(tenant_id)
    }


def get_smart_upsell_for_item(tenant_id, item=None, user_text="", business_type="restaurant"):
    if not item:
        return None

    drink = get_best_drink(tenant_id, business_type)
    dessert = get_best_dessert(tenant_id, business_type)
    side = get_best_side(tenant_id, business_type)

    def not_same(candidate):
        if not candidate:
            return False
        return candidate.get("id") != item.get("id")

    for candidate in [drink, dessert, side]:
        if candidate and not_same(candidate):
            return {
                "text": f"Към „{item.get('name')}“ много добре върви {candidate.get('name')} — искате ли да направим резервация? 😊",
                "buttons": [candidate.get("name"), "Меню", "Нова резервация", "Контакти"]
            }

    return None


def create_menu_category(tenant_id, name, sort_order=0, name_en=""):
    if not name_en:
        name_en = bg_to_en(name)

    db = get_db()
    cursor = db.cursor()

    cursor.execute("""
        INSERT INTO menu_categories (tenant_id, name, name_en, sort_order, is_active)
        VALUES (?, ?, ?, ?, 1)
    """, (tenant_id, name, name_en, sort_order))

    category_id = cursor.lastrowid

    db.commit()
    db.close()

    return category_id


def create_menu_item(
    tenant_id,
    category_id,
    name,
    description="",
    price=0,
    sort_order=0,
    upsell_drink="",
    upsell_dessert="",
    image_url="",
    upsell_side="",
    name_en="",
    description_en="",
    upsell_drink_en="",
    upsell_dessert_en="",
    upsell_side_en=""
):
    image_url = clean_image_url(image_url)

    name_en = get_en_or_translate(name_en, name)
    description_en = get_en_or_translate(description_en, description)
    upsell_drink_en = get_en_or_translate(upsell_drink_en, upsell_drink)
    upsell_dessert_en = get_en_or_translate(upsell_dessert_en, upsell_dessert)
    upsell_side_en = get_en_or_translate(upsell_side_en, upsell_side)

    db = get_db()

    db.execute("""
        INSERT INTO menu_items (
            tenant_id, category_id, name, name_en, description, description_en, price,
            image_url, upsell_drink, upsell_drink_en, upsell_dessert, upsell_dessert_en,
            upsell_side, upsell_side_en, is_active, sort_order
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?)
    """, (
        tenant_id, category_id, name, name_en, description, description_en, price,
        image_url, upsell_drink, upsell_drink_en, upsell_dessert, upsell_dessert_en,
        upsell_side, upsell_side_en, sort_order
    ))

    db.commit()
    db.close()


def delete_menu_category(category_id, tenant_id):
    db = get_db()
    db.execute("DELETE FROM menu_items WHERE category_id = ? AND tenant_id = ?", (category_id, tenant_id))
    db.execute("DELETE FROM menu_categories WHERE id = ? AND tenant_id = ?", (category_id, tenant_id))
    db.commit()
    db.close()


def delete_menu_item(item_id, tenant_id):
    db = get_db()
    db.execute("DELETE FROM menu_items WHERE id = ? AND tenant_id = ?", (item_id, tenant_id))
    db.commit()
    db.close()


def get_menu_item_by_id(item_id, tenant_id):
    db = get_db()
    row = db.execute("""
        SELECT *
        FROM menu_items
        WHERE id = ? AND tenant_id = ?
        LIMIT 1
    """, (item_id, tenant_id)).fetchone()
    db.close()
    return normalize_item_row(row) if row else None


def update_menu_category(category_id, tenant_id, name, sort_order=0, name_en=""):
    name_en = get_en_or_translate(name_en, name)

    db = get_db()

    db.execute("""
        UPDATE menu_categories
        SET name = ?, name_en = ?, sort_order = ?
        WHERE id = ? AND tenant_id = ?
    """, (name, name_en, sort_order, category_id, tenant_id))

    db.commit()
    db.close()


def update_menu_item(
    item_id,
    tenant_id,
    category_id,
    name,
    description="",
    price=0,
    sort_order=0,
    upsell_drink="",
    upsell_dessert="",
    image_url="",
    upsell_side="",
    name_en="",
    description_en="",
    upsell_drink_en="",
    upsell_dessert_en="",
    upsell_side_en=""
):
    image_url = clean_image_url(image_url)

    name_en = get_en_or_translate(name_en, name)
    description_en = get_en_or_translate(description_en, description)
    upsell_drink_en = get_en_or_translate(upsell_drink_en, upsell_drink)
    upsell_dessert_en = get_en_or_translate(upsell_dessert_en, upsell_dessert)
    upsell_side_en = get_en_or_translate(upsell_side_en, upsell_side)

    db = get_db()

    db.execute("""
        UPDATE menu_items
        SET category_id = ?,
            name = ?,
            name_en = ?,
            description = ?,
            description_en = ?,
            price = ?,
            sort_order = ?,
            image_url = ?,
            upsell_drink = ?,
            upsell_drink_en = ?,
            upsell_dessert = ?,
            upsell_dessert_en = ?,
            upsell_side = ?,
            upsell_side_en = ?
        WHERE id = ? AND tenant_id = ?
    """, (
        category_id, name, name_en, description, description_en, price, sort_order,
        image_url, upsell_drink, upsell_drink_en, upsell_dessert,
        upsell_dessert_en, upsell_side, upsell_side_en, item_id, tenant_id
    ))

    db.commit()
    db.close()


def toggle_menu_item_status(item_id, tenant_id):
    db = get_db()

    db.execute("""
        UPDATE menu_items
        SET is_active = CASE
            WHEN is_active = 1 THEN 0
            ELSE 1
        END
        WHERE id = ? AND tenant_id = ?
    """, (item_id, tenant_id))

    db.commit()
    db.close()


DEFAULT_MENU_DATA = {
    "restaurant": {
        "Салати": [
            ("Цезар", "Класическа салата с пиле, крутони и дресинг", 12.90, "Лимонада", "Чийзкейк", "Пържени картофки"),
            ("Гръцка салата", "Домати, краставици, сирене и маслини", 10.50, "Айрян", "Домашен десерт", "Чеснов сос"),
        ],
        "Основни": [
            ("Пилешка пържола", "Пилешко филе с гарнитура", 16.90, "Лимонада", "Чийзкейк", "Пържени картофки"),
            ("Паста Карбонара", "Паста със сметанов сос, бекон и пармезан", 14.90, "Чаша бяло вино", "Тирамису", "Чесново хлебче"),
        ],
        "Десерти": [
            ("Чийзкейк", "Домашен чийзкейк", 7.50, "Кафе", "", ""),
        ],
        "Напитки": [
            ("Лимонада", "Домашна лимонада", 4.90, "", "Чийзкейк", ""),
            ("Айрян", "Студен айрян", 3.50, "", "", ""),
        ],
    }
}


def seed_default_menu_for_business_type(tenant_id, business_type="restaurant"):
    existing_categories = get_menu_categories(tenant_id)

    if existing_categories:
        return

    business_type = normalize_text(business_type) or "restaurant"
    menu_data = DEFAULT_MENU_DATA.get(business_type, DEFAULT_MENU_DATA["restaurant"])

    for category_index, (category_name, items) in enumerate(menu_data.items(), start=1):
        category_id = create_menu_category(
            tenant_id=tenant_id,
            name=category_name,
            name_en=bg_to_en(category_name),
            sort_order=category_index
        )

        for item_index, item in enumerate(items, start=1):
            name, description, price, upsell_drink, upsell_dessert, upsell_side = item

            create_menu_item(
                tenant_id=tenant_id,
                category_id=category_id,
                name=name,
                name_en=bg_to_en(name),
                description=description,
                description_en=bg_to_en(description),
                price=price,
                sort_order=item_index,
                upsell_drink=upsell_drink,
                upsell_drink_en=bg_to_en(upsell_drink),
                upsell_dessert=upsell_dessert,
                upsell_dessert_en=bg_to_en(upsell_dessert),
                upsell_side=upsell_side,
                upsell_side_en=bg_to_en(upsell_side)
            )