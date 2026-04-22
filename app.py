from flask import Flask, request, jsonify, session, render_template, redirect, send_file
from datetime import datetime
from database import init_db, seed_data, get_db
from config import SECRET_KEY
from core.chatbot import ChatBot

from services.auth import (
    authenticate_user,
    create_user,
    get_any_user_by_username,
    list_users_by_tenant,
    update_user_role,
    update_user,
    activate_user,
    deactivate_user,
    delete_user,
)
from services.tenants import (
    get_tenant_settings,
    update_tenant_settings,
    create_tenant,
    list_tenants,
    activate_tenant,
    deactivate_tenant,
)
from services.reservations import (
    get_reservations_by_tenant,
    update_reservation,
    delete_reservation,
)
from services.exports import export_reservations_to_excel
from services.analytics import log_event, get_analytics_summary
from services.menu import (
    get_menu_categories,
    get_full_menu,
    create_menu_category,
    create_menu_item,
    delete_menu_category,
    delete_menu_item,
)

app = Flask(__name__)
app.secret_key = SECRET_KEY

init_db()
seed_data()


def current_user():
    return session.get("user")


def has_role(*allowed_roles):
    user = current_user()
    if not user:
        return False
    return user.get("role") in allowed_roles


def is_super_admin():
    return has_role("super_admin")


def can_manage_premium_features():
    return has_role("super_admin")


def parse_bg_date(date_str):
    try:
        return datetime.strptime(date_str, "%d.%m.%Y").date()
    except Exception:
        return None


def get_tenant_by_slug(slug):
    db = get_db()
    row = db.execute("""
        SELECT *
        FROM tenants
        WHERE slug = ? AND is_active = 1
        LIMIT 1
    """, (slug,)).fetchone()
    db.close()
    return dict(row) if row else None


def get_default_tenant():
    db = get_db()
    row = db.execute("""
        SELECT *
        FROM tenants
        WHERE is_active = 1
        ORDER BY id ASC
        LIMIT 1
    """).fetchone()
    db.close()
    return dict(row) if row else None


@app.route("/")
def home():
    tenant = get_default_tenant()

    if not tenant:
        return "Няма активен ресторант."

    return redirect(f"/site/{tenant['slug']}")


@app.route("/site/<slug>")
def public_site(slug):
    tenant = get_tenant_by_slug(slug)

    if not tenant:
        return "Няма намерен ресторант.", 404

    tenant_id = tenant["id"]
    settings = get_tenant_settings(tenant_id) or {}

    return render_template(
        "index.html",
        tenant_slug=slug,
        widget_title=settings.get("widget_title", "AI ChatBot - Ресторант"),
        primary_color=settings.get("primary_color", "#1e88ff"),
        widget_enabled=int(settings.get("widget_enabled", 1)),
        welcome_message=settings.get("welcome_message", "👋 Здравейте! С какво мога да помогна?")
    )


@app.route("/login", methods=["GET", "POST"])
def login():
    brand_name = "Restaurant AI"
    bg_image = "/static/restaurant.jpg"

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()

        user = authenticate_user(username, password)

        if user:
            session["user"] = {
                "id": user["id"],
                "username": user["username"],
                "role": user["role"],
                "tenant_id": user["tenant_id"]
            }
            return redirect("/dashboard")

        return render_template(
            "login.html",
            error="Грешни данни",
            brand_name=brand_name,
            bg_image=bg_image
        )

    return render_template(
        "login.html",
        error=None,
        brand_name=brand_name,
        bg_image=bg_image
    )


@app.route("/logout")
def logout():
    session.pop("user", None)

    keys_to_remove = [k for k in session.keys() if k.startswith("chat_data_")]
    for k in keys_to_remove:
        session.pop(k, None)

    return redirect("/login")


@app.route("/chat/<slug>", methods=["POST"])
def chat(slug):
    tenant = get_tenant_by_slug(slug)

    if not tenant:
        return jsonify({
            "text": "Няма намерен ресторант.",
            "buttons": []
        }), 404

    tenant_id = tenant["id"]

    data = request.get_json(silent=True) or {}
    user_input = data.get("message", "").strip()

    if not user_input:
        return jsonify({
            "text": "Моля, напишете съобщение 😊",
            "buttons": []
        })

    session_key = f"chat_data_{tenant_id}"

    if session_key not in session:
        session[session_key] = {}

    bot = ChatBot(tenant_id)
    reply = bot.get_response(user_input, session.get(session_key, {}))

    session[session_key] = bot.context
    session.modified = True

    log_event(tenant_id, "chat_message", {"message": user_input})

    if isinstance(reply, str):
        return jsonify({"text": reply, "buttons": []})

    return jsonify(reply)


@app.route("/dashboard")
def dashboard():
    user = current_user()
    if not user:
        return redirect("/login")

    tenant_id = user["tenant_id"]
    reservations = get_reservations_by_tenant(tenant_id)
    settings = get_tenant_settings(tenant_id) or {}
    analytics = get_analytics_summary(tenant_id)

    today = datetime.now().date()
    today_str = today.strftime("%d.%m.%Y")
    max_capacity = int(settings.get("max_capacity", 20))

    total = len(reservations)
    today_count = 0
    upcoming = 0
    occupied_today = 0

    for r in reservations:
        res_date = parse_bg_date(r["date"])
        if not res_date:
            continue

        if r["date"] == today_str:
            today_count += 1
            try:
                occupied_today += int(r["people"])
            except Exception:
                pass

        if res_date >= today:
            upcoming += 1

    free_places_today = max(max_capacity - occupied_today, 0)

    return render_template(
        "dashboard.html",
        reservations=reservations,
        total=total,
        today_count=today_count,
        upcoming=upcoming,
        free_places_today=free_places_today,
        analytics=analytics,
        username=user["username"],
        role=user["role"],
        can_manage_premium_features=can_manage_premium_features(),
        is_super_admin=is_super_admin()
    )


@app.route("/settings", methods=["GET", "POST"])
def settings():
    user = current_user()
    if not user:
        return redirect("/login")

    if not has_role("super_admin", "owner", "admin"):
        return redirect("/dashboard")

    tenant_id = user["tenant_id"]
    can_manage_premium = can_manage_premium_features()

    if request.method == "POST":
        existing_settings = get_tenant_settings(tenant_id) or {}

        restaurant_name = request.form.get("restaurant_name", "").strip()
        phone = request.form.get("phone", "").strip()
        email = request.form.get("email", "").strip()
        address = request.form.get("address", "").strip()
        welcome_message = request.form.get("welcome_message", "").strip()
        max_capacity = int(request.form.get("max_capacity", 20))
        open_hour = int(request.form.get("open_hour", 10))
        close_hour = int(request.form.get("close_hour", 22))
        primary_color = request.form.get("primary_color", "#1e88ff").strip()
        widget_title = request.form.get("widget_title", "AI ChatBot - Ресторант").strip()
        widget_enabled = int(request.form.get("widget_enabled", 1))

        if can_manage_premium:
            llm_enabled = int(request.form.get("llm_enabled", existing_settings.get("llm_enabled", 0)))
        else:
            llm_enabled = int(existing_settings.get("llm_enabled", 0))

        update_tenant_settings(
            tenant_id=tenant_id,
            restaurant_name=restaurant_name,
            phone=phone,
            email=email,
            address=address,
            welcome_message=welcome_message,
            max_capacity=max_capacity,
            open_hour=open_hour,
            close_hour=close_hour,
            primary_color=primary_color,
            widget_title=widget_title,
            widget_enabled=widget_enabled,
            llm_enabled=llm_enabled
        )

        return redirect("/settings?saved=1")

    settings_data = get_tenant_settings(tenant_id) or {}
    saved = request.args.get("saved") == "1"

    return render_template(
        "settings.html",
        settings=settings_data,
        saved=saved,
        role=user["role"],
        can_manage_premium_features=can_manage_premium,
        is_super_admin=is_super_admin()
    )


@app.route("/restaurants")
def restaurants():
    user = current_user()
    if not user:
        return redirect("/login")

    if not has_role("super_admin"):
        return redirect("/dashboard")

    return render_template(
        "restaurants.html",
        restaurants=list_tenants()
    )


@app.route("/restaurants/deactivate", methods=["POST"])
def restaurants_deactivate():
    user = current_user()
    if not user:
        return redirect("/login")

    if not has_role("super_admin"):
        return redirect("/dashboard")

    tenant_id = int(request.form.get("tenant_id"))
    deactivate_tenant(tenant_id)
    return redirect("/restaurants")


@app.route("/restaurants/activate", methods=["POST"])
def restaurants_activate():
    user = current_user()
    if not user:
        return redirect("/login")

    if not has_role("super_admin"):
        return redirect("/dashboard")

    tenant_id = int(request.form.get("tenant_id"))
    activate_tenant(tenant_id)
    return redirect("/restaurants")


@app.route("/create-restaurant", methods=["GET", "POST"])
def create_restaurant():
    user = current_user()
    if not user:
        return redirect("/login")

    if not has_role("super_admin"):
        return redirect("/dashboard")

    if request.method == "POST":
        restaurant_name = request.form.get("restaurant_name", "").strip()
        slug = request.form.get("slug", "").strip()
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()
        max_capacity = int(request.form.get("max_capacity", 20))
        open_hour = int(request.form.get("open_hour", 10))
        close_hour = int(request.form.get("close_hour", 22))

        if not all([restaurant_name, slug, username, password]):
            return render_template(
                "create_restaurant.html",
                error="Моля, попълни всички полета.",
                success=None
            )

        existing_user = get_any_user_by_username(username)
        if existing_user:
            return render_template(
                "create_restaurant.html",
                error="Това потребителско име вече съществува.",
                success=None
            )

        try:
            tenant_id = create_tenant(
                name=restaurant_name,
                slug=slug,
                max_capacity=max_capacity,
                open_hour=open_hour,
                close_hour=close_hour
            )

            create_user(
                tenant_id=tenant_id,
                username=username,
                password=password,
                role="owner"
            )

            return render_template(
                "create_restaurant.html",
                error=None,
                success=f"Успешно създаде ресторант „{restaurant_name}“ с потребител „{username}“."
            )

        except Exception as e:
            print("CREATE RESTAURANT ERROR:", e)
            return render_template(
                "create_restaurant.html",
                error="Възникна грешка при създаването. Възможно е slug или потребител да съществуват вече.",
                success=None
            )

    return render_template(
        "create_restaurant.html",
        error=None,
        success=None
    )


@app.route("/users")
def users_page():
    user = current_user()
    if not user:
        return redirect("/login")

    if not has_role("owner", "admin", "super_admin"):
        return redirect("/dashboard")

    tenant_id = user["tenant_id"]

    success = request.args.get("success")
    error = request.args.get("error")

    if success == "created":
        success = "Потребителят е създаден успешно."
    elif success == "role":
        success = "Ролята е променена успешно."
    elif success == "deactivated":
        success = "Потребителят е спрян успешно."
    elif success == "activated":
        success = "Потребителят е пуснат успешно."
    elif success == "edited":
        success = "Потребителят е редактиран успешно."
    elif success == "deleted":
        success = "Потребителят е изтрит успешно."

    if error == "exists":
        error = "Това потребителско име вече съществува."
    elif error == "invalid":
        error = "Невалидни данни."
    elif error == "owner":
        error = "Този потребител не може да бъде променян оттук."
    elif error == "self":
        error = "Не можеш да редактираш или изтриеш собствения си акаунт оттук."

    return render_template(
        "users.html",
        users=list_users_by_tenant(tenant_id),
        success=success,
        error=error,
        role=user["role"],
        can_manage_premium_features=can_manage_premium_features(),
        is_super_admin=is_super_admin()
    )


@app.route("/users/create", methods=["POST"])
def users_create():
    user = current_user()
    if not user:
        return redirect("/login")

    if not has_role("owner", "admin", "super_admin"):
        return redirect("/dashboard")

    tenant_id = user["tenant_id"]
    username = request.form.get("username", "").strip()
    password = request.form.get("password", "").strip()
    role = request.form.get("role", "staff").strip()

    allowed_roles = ["admin", "staff"]
    if has_role("super_admin"):
        allowed_roles = ["owner", "admin", "staff"]

    if not username or not password or role not in allowed_roles:
        return redirect("/users?error=invalid")

    existing_user = get_any_user_by_username(username)
    if existing_user:
        return redirect("/users?error=exists")

    create_user(tenant_id, username, password, role)
    return redirect("/users?success=created")


@app.route("/users/change-role", methods=["POST"])
def users_change_role():
    user = current_user()
    if not user:
        return redirect("/login")

    if not has_role("super_admin", "owner"):
        return redirect("/dashboard")

    tenant_id = user["tenant_id"]
    user_id = int(request.form.get("user_id"))
    role = request.form.get("role", "").strip()

    allowed_roles = ["admin", "staff"]
    if has_role("super_admin"):
        allowed_roles = ["owner", "admin", "staff"]

    if role not in allowed_roles:
        return redirect("/users?error=invalid")

    users = list_users_by_tenant(tenant_id)
    target_user = next((u for u in users if u["id"] == user_id), None)

    if not target_user:
        return redirect("/users?error=invalid")

    if target_user["id"] == user["id"]:
        return redirect("/users?error=self")

    if target_user["role"] == "super_admin":
        return redirect("/users?error=owner")

    if target_user["role"] == "owner" and not has_role("super_admin"):
        return redirect("/users?error=owner")

    update_user_role(user_id, tenant_id, role)
    return redirect("/users?success=role")


@app.route("/users/edit", methods=["POST"])
def users_edit():
    user = current_user()
    if not user:
        return redirect("/login")

    if not has_role("super_admin", "owner"):
        return redirect("/dashboard")

    tenant_id = user["tenant_id"]
    user_id = int(request.form.get("user_id"))
    username = request.form.get("username", "").strip()
    password = request.form.get("password", "").strip()
    role = request.form.get("role", "").strip()

    users = list_users_by_tenant(tenant_id)
    target_user = next((u for u in users if u["id"] == user_id), None)

    if not target_user:
        return redirect("/users?error=invalid")

    if target_user["id"] == user["id"]:
        return redirect("/users?error=self")

    if target_user["role"] == "super_admin":
        return redirect("/users?error=owner")

    if target_user["role"] == "owner" and not has_role("super_admin"):
        return redirect("/users?error=owner")

    allowed_roles = ["admin", "staff"]
    if has_role("super_admin"):
        allowed_roles = ["owner", "admin", "staff"]

    if not username or role not in allowed_roles:
        return redirect("/users?error=invalid")

    existing_user = get_any_user_by_username(username)
    if existing_user and existing_user["id"] != user_id:
        return redirect("/users?error=exists")

    if password:
        update_user(user_id, tenant_id, username, password=password, role=role)
    else:
        update_user(user_id, tenant_id, username, role=role)

    return redirect("/users?success=edited")


@app.route("/users/deactivate", methods=["POST"])
def users_deactivate():
    user = current_user()
    if not user:
        return redirect("/login")

    if not has_role("super_admin", "owner"):
        return redirect("/dashboard")

    tenant_id = user["tenant_id"]
    user_id = int(request.form.get("user_id"))

    users = list_users_by_tenant(tenant_id)
    target_user = next((u for u in users if u["id"] == user_id), None)

    if not target_user:
        return redirect("/users?error=invalid")

    if target_user["id"] == user["id"]:
        return redirect("/users?error=self")

    if target_user["role"] == "super_admin":
        return redirect("/users?error=owner")

    if target_user["role"] == "owner" and not has_role("super_admin"):
        return redirect("/users?error=owner")

    deactivate_user(user_id, tenant_id)
    return redirect("/users?success=deactivated")


@app.route("/users/activate", methods=["POST"])
def users_activate():
    user = current_user()
    if not user:
        return redirect("/login")

    if not has_role("super_admin", "owner"):
        return redirect("/dashboard")

    tenant_id = user["tenant_id"]
    user_id = int(request.form.get("user_id"))

    users = list_users_by_tenant(tenant_id)
    target_user = next((u for u in users if u["id"] == user_id), None)

    if not target_user:
        return redirect("/users?error=invalid")

    if target_user["role"] == "super_admin":
        return redirect("/users?error=owner")

    if target_user["role"] == "owner" and not has_role("super_admin"):
        return redirect("/users?error=owner")

    activate_user(user_id, tenant_id)
    return redirect("/users?success=activated")


@app.route("/users/delete", methods=["POST"])
def users_delete():
    user = current_user()
    if not user:
        return redirect("/login")

    if not has_role("super_admin", "owner"):
        return redirect("/dashboard")

    tenant_id = user["tenant_id"]
    user_id = int(request.form.get("user_id"))

    users = list_users_by_tenant(tenant_id)
    target_user = next((u for u in users if u["id"] == user_id), None)

    if not target_user:
        return redirect("/users?error=invalid")

    if target_user["id"] == user["id"]:
        return redirect("/users?error=self")

    if target_user["role"] == "super_admin":
        return redirect("/users?error=owner")

    if target_user["role"] == "owner" and not has_role("super_admin"):
        return redirect("/users?error=owner")

    delete_user(user_id, tenant_id)
    return redirect("/users?success=deleted")


@app.route("/menu-manager")
def menu_manager():
    user = current_user()
    if not user:
        return redirect("/login")

    if not has_role("super_admin", "owner", "admin"):
        return redirect("/dashboard")

    tenant_id = user["tenant_id"]
    categories = get_menu_categories(tenant_id)
    menu_data = get_full_menu(tenant_id)
    saved = request.args.get("saved") == "1"

    return render_template(
        "menu_manager.html",
        categories=categories,
        menu_data=menu_data,
        saved=saved,
        role=user["role"],
        can_manage_premium_features=can_manage_premium_features(),
        is_super_admin=is_super_admin()
    )


@app.route("/menu-manager/add-category", methods=["POST"])
def add_menu_category_route():
    user = current_user()
    if not user:
        return redirect("/login")

    if not has_role("super_admin", "owner", "admin"):
        return redirect("/dashboard")

    tenant_id = user["tenant_id"]
    name = request.form.get("name", "").strip()
    sort_order = int(request.form.get("sort_order", 0))

    if name:
        create_menu_category(tenant_id, name, sort_order)

    return redirect("/menu-manager?saved=1")


@app.route("/menu-manager/add-item", methods=["POST"])
def add_menu_item_route():
    user = current_user()
    if not user:
        return redirect("/login")

    if not has_role("super_admin", "owner", "admin"):
        return redirect("/dashboard")

    tenant_id = user["tenant_id"]
    category_id = int(request.form.get("category_id"))
    name = request.form.get("name", "").strip()
    description = request.form.get("description", "").strip()
    price = float(request.form.get("price", 0))
    sort_order = int(request.form.get("sort_order", 0))

    if name:
        create_menu_item(tenant_id, category_id, name, description, price, sort_order)

    return redirect("/menu-manager?saved=1")


@app.route("/menu-manager/delete-category", methods=["POST"])
def delete_menu_category_route():
    user = current_user()
    if not user:
        return redirect("/login")

    if not has_role("super_admin", "owner", "admin"):
        return redirect("/dashboard")

    tenant_id = user["tenant_id"]
    category_id = int(request.form.get("category_id"))
    delete_menu_category(category_id, tenant_id)

    return redirect("/menu-manager?saved=1")


@app.route("/menu-manager/delete-item", methods=["POST"])
def delete_menu_item_route():
    user = current_user()
    if not user:
        return redirect("/login")

    if not has_role("super_admin", "owner", "admin"):
        return redirect("/dashboard")

    tenant_id = user["tenant_id"]
    item_id = int(request.form.get("item_id"))
    delete_menu_item(item_id, tenant_id)

    return redirect("/menu-manager?saved=1")


@app.route("/delete_reservation", methods=["POST"])
def delete_reservation_route():
    user = current_user()
    if not user:
        return jsonify({"status": "error", "message": "Неоторизиран достъп"})

    if not has_role("owner", "admin", "staff", "super_admin"):
        return jsonify({"status": "error", "message": "Нямате права"})

    data = request.get_json(silent=True) or {}
    reservation_id = data.get("id")

    if not reservation_id:
        return jsonify({"status": "error", "message": "Липсва ID"})

    delete_reservation(reservation_id, user["tenant_id"])
    return jsonify({"status": "success"})


@app.route("/edit_reservation", methods=["POST"])
def edit_reservation_route():
    user = current_user()
    if not user:
        return jsonify({"status": "error", "message": "Неоторизиран достъп"})

    if not has_role("owner", "admin", "staff", "super_admin"):
        return jsonify({"status": "error", "message": "Нямате права"})

    data = request.get_json(silent=True) or {}

    reservation_id = data.get("id")
    name = data.get("name", "").strip()
    phone = data.get("phone", "").strip()
    date = data.get("date", "").strip()
    time = data.get("time", "").strip()
    people = data.get("people", "").strip()

    if not all([reservation_id, name, phone, date, time, people]):
        return jsonify({"status": "error", "message": "Липсват данни"})

    update_reservation(
        reservation_id=reservation_id,
        tenant_id=user["tenant_id"],
        name=name,
        phone=phone,
        date=date,
        time=time,
        people=people,
        status="confirmed",
        notes=""
    )

    return jsonify({"status": "success"})


@app.route("/export")
def export():
    user = current_user()
    if not user:
        return redirect("/login")

    if not has_role("owner", "admin", "staff", "super_admin"):
        return redirect("/dashboard")

    file_path = export_reservations_to_excel(user["tenant_id"], output_dir="data")

    if not file_path:
        return "Няма данни за export"

    return send_file(file_path, as_attachment=True)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000, debug=True)