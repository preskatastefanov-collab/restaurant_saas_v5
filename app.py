import os
from datetime import datetime, timedelta

from flask import Flask, request, jsonify, session, render_template, redirect, send_file
from werkzeug.utils import secure_filename

from database import init_db, seed_data, get_db
from config import SECRET_KEY
from core.chatbot import ChatBot

from services.menu import (
    get_menu_categories,
    get_full_menu,
    create_menu_category,
    create_menu_item,
    delete_menu_category,
    delete_menu_item,
    seed_default_menu_for_business_type,
    update_menu_category,
    update_menu_item,
    toggle_menu_item_status,
    bg_to_en,
)

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
    delete_tenant,
    update_tenant,
    get_tenant_plan,
    get_tenant_business_type,
    tenant_has_feature,
    normalize_plan,
    normalize_business_type,
    get_business_type_label,
    get_business_type_options,
    update_tenant_business_type,
)

from services.reservations import (
    get_reservations_by_tenant,
    update_reservation,
    delete_reservation,
)

from services.exports import export_reservations_to_excel
from services.analytics import (
    log_event,
    get_analytics_summary,
    get_recent_events,
    get_analytics_page_data,
)

from services.menu import (
    get_menu_categories,
    get_full_menu,
    create_menu_category,
    create_menu_item,
    delete_menu_category,
    delete_menu_item,
    seed_default_menu_for_business_type,
    update_menu_category,
    update_menu_item,
    toggle_menu_item_status,
)


app = Flask(__name__)
app.secret_key = SECRET_KEY

UPLOAD_FOLDER = os.path.join("static", "uploads", "menu")
ALLOWED_IMAGE_EXTENSIONS = {"png", "jpg", "jpeg", "webp", "gif"}

os.makedirs(UPLOAD_FOLDER, exist_ok=True)

init_db()
seed_data()


def allowed_image_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_IMAGE_EXTENSIONS


def save_menu_image(file):
    if not file or not file.filename:
        return ""

    if not allowed_image_file(file.filename):
        return ""

    filename = secure_filename(file.filename)
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S%f")
    filename = f"{timestamp}_{filename}"

    file_path = os.path.join(UPLOAD_FOLDER, filename)
    file.save(file_path)

    return f"/static/uploads/menu/{filename}"


def safe_int(value, default=0):
    try:
        return int(value)
    except Exception:
        return default


def safe_float(value, default=0.0):
    try:
        return float(value)
    except Exception:
        return default


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

def require_login():
    user = current_user()
    return user is not None


def can_access_premium_analytics(tenant_id):
    return is_super_admin() or (
        has_role("owner") and tenant_has_feature(tenant_id, "premium_analytics")
    )


def can_use_ai_settings(tenant_id):
    return is_super_admin() and tenant_has_feature(tenant_id, "ai_chat")


def can_use_upsell_settings(tenant_id):
    return is_super_admin() and tenant_has_feature(tenant_id, "upsell")


def can_manage_business():
    return has_role("super_admin", "owner")


def can_manage_menu():
    return has_role("super_admin", "owner", "admin")


def can_manage_users():
    return has_role("super_admin", "owner", "admin")


def can_manage_demo_requests():
    return has_role("super_admin")


def can_manage_password_requests():
    return has_role("super_admin")

def get_active_tenant_id():
    user = current_user()
    if not user:
        return None

    if user.get("role") == "super_admin":
        return session.get("active_tenant_id", user.get("tenant_id"))

    return user.get("tenant_id")


def get_active_tenant_info():
    tenant_id = get_active_tenant_id()
    if not tenant_id:
        return None

    db = get_db()
    row = db.execute("""
        SELECT id, name, slug, business_type, plan
        FROM tenants
        WHERE id = ?
        LIMIT 1
    """, (tenant_id,)).fetchone()
    db.close()

    return dict(row) if row else None


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


def clear_chat_sessions():
    keys_to_remove = [k for k in session.keys() if k.startswith("chat_data_")]
    for k in keys_to_remove:
        session.pop(k, None)
    session.modified = True


@app.route("/")
def home():
    return render_template(
        "landing.html",
        demo_success=request.args.get("demo_success") == "1",
        demo_error=request.args.get("demo_error") == "1"
    )

@app.route("/demo-request", methods=["POST"])
def demo_request():
    business_name = request.form.get("business_name", "").strip()
    contact_name = request.form.get("contact_name", "").strip()
    phone = request.form.get("phone", "").strip()
    email = request.form.get("email", "").strip()
    business_type = request.form.get("business_type", "").strip()
    message = request.form.get("message", "").strip()

    if not business_name or not phone:
        return redirect("/?demo_error=1#demo-request")

    db = get_db()
    db.execute("""
        INSERT INTO demo_requests (
            business_name,
            contact_name,
            phone,
            email,
            business_type,
            message,
            status
        )
        VALUES (?, ?, ?, ?, ?, ?, 'new')
    """, (
        business_name,
        contact_name,
        phone,
        email,
        business_type,
        message
    ))
    db.commit()
    db.close()

    return redirect("/?demo_success=1#demo-request")

@app.route("/site/<slug>")
def public_site(slug):
    tenant = get_tenant_by_slug(slug)

    if not tenant:
        return "Няма намерен бизнес.", 404

    tenant_id = tenant["id"]
    settings = get_tenant_settings(tenant_id) or {}

    tenant_plan = get_tenant_plan(tenant_id)
    business_type = normalize_business_type(tenant.get("business_type", "restaurant"))
    business_label = get_business_type_label(business_type)

    return render_template(
        "index.html",
        tenant_slug=slug,
        widget_title=settings.get("widget_title", "AI ChatBot"),
        primary_color=settings.get("primary_color", "#1e88ff"),
        widget_enabled=safe_int(settings.get("widget_enabled", 1), 1),
        welcome_message=settings.get("welcome_message", ""),
        tenant_plan=tenant_plan,
        business_type=business_type,
        business_label=business_label,
    )


@app.route("/chat/<slug>", methods=["POST"])
def chat(slug):
    tenant = get_tenant_by_slug(slug)

    if not tenant:
        return jsonify({"text": "Няма намерен бизнес.", "buttons": []}), 404

    tenant_id = tenant["id"]
    data = request.get_json(silent=True) or {}

    user_input = data.get("message", "").strip()
    client_language = data.get("language", "bg")

    if not user_input:
        return jsonify({"text": "Моля, напишете съобщение 😊", "buttons": []})

    session_key = f"chat_data_{tenant_id}"
    chat_context = session.get(session_key, {})

    if client_language in ["bg", "en"]:
        chat_context["language"] = client_language

    bot = ChatBot(tenant_id)
    reply = bot.get_response(user_input, chat_context)

    session[session_key] = bot.context
    session.modified = True

    log_event(tenant_id, "chat_message", {"message": user_input})

    if isinstance(reply, str):
        return jsonify({"text": reply, "buttons": []})

    return jsonify(reply)


@app.route("/login", methods=["GET", "POST"])
def login():
    brand_name = "Reservy"
    bg_image = "/static/restaurant.jpg"

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()

        user = authenticate_user(username, password)

        if user:
            session.clear()

            session["user"] = {
                "id": user["id"],
                "username": user["username"],
                "role": user["role"],
                "tenant_id": user["tenant_id"]
            }

            session["active_tenant_id"] = user["tenant_id"]
            session.modified = True

            return redirect("/dashboard")

        return render_template("login.html", error="Грешни данни", brand_name=brand_name, bg_image=bg_image)

    return render_template("login.html", error=None, brand_name=brand_name, bg_image=bg_image)


@app.route("/logout")
def logout():
    session.clear()
    return redirect("/login")

@app.route("/forgot-password", methods=["GET", "POST"])
def forgot_password():
    success = None
    error = None

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        contact = request.form.get("contact", "").strip()
        message = request.form.get("message", "").strip()

        if not username or not contact:
            error = "Моля, въведете потребителско име и телефон или email."
        else:
            db = get_db()
            db.execute("""
                INSERT INTO password_reset_requests (
                    username,
                    contact,
                    message,
                    status
                )
                VALUES (?, ?, ?, 'new')
            """, (username, contact, message))
            db.commit()
            db.close()

            success = "Заявката е изпратена успешно. Администратор ще се свърже с Вас."

    return render_template(
        "forgot_password.html",
        success=success,
        error=error
    )

@app.route("/password-requests")
def password_requests():
    user = current_user()

    if not user:
        return redirect("/login")

    if not can_manage_password_requests():
        return redirect("/dashboard")

    db = get_db()
    rows = db.execute("""
        SELECT *
        FROM password_reset_requests
        ORDER BY id DESC
    """).fetchall()
    db.close()

    return render_template(
        "password_requests.html",
        requests=[dict(r) for r in rows],
        role=user["role"],
        active_business=get_active_tenant_info()
    )

@app.route("/demo-requests")
def demo_requests():
    user = current_user()

    if not user:
        return redirect("/login")

    if not can_manage_demo_requests():
        return redirect("/dashboard")

    db = get_db()
    rows = db.execute("""
        SELECT *
        FROM demo_requests
        ORDER BY id DESC
    """).fetchall()
    db.close()

    return render_template(
        "demo_requests.html",
        requests=[dict(r) for r in rows],
        role=user["role"],
        active_business=get_active_tenant_info()
    )


@app.route("/password-requests/mark-done", methods=["POST"])
def mark_password_request_done():
    user = current_user()

    if not user:
        return redirect("/login")

    if not has_role("super_admin"):
        return redirect("/dashboard")

    request_id = safe_int(request.form.get("request_id"))

    db = get_db()
    db.execute("""
        UPDATE password_reset_requests
        SET status = 'done',
            handled_by = ?,
            updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
    """, (user["username"], request_id))
    db.commit()
    db.close()

    return redirect("/password-requests")

@app.route("/password-requests/edit", methods=["POST"])
def edit_password_request():
    user = current_user()

    if not user:
        return redirect("/login")

    if not has_role("super_admin"):
        return redirect("/dashboard")

    request_id = safe_int(request.form.get("request_id"))
    username = request.form.get("username", "").strip()
    contact = request.form.get("contact", "").strip()
    message = request.form.get("message", "").strip()
    admin_note = request.form.get("admin_note", "").strip()
    status = request.form.get("status", "new").strip()

    if status not in ["new", "processing", "waiting", "done", "rejected"]:
        status = "new"

    if not request_id or not username or not contact:
        return redirect("/password-requests")

    db = get_db()
    db.execute("""
        UPDATE password_reset_requests
        SET username = ?,
            contact = ?,
            message = ?,
            admin_note = ?,
            status = ?,
            handled_by = ?,
            updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
    """, (
        username,
        contact,
        message,
        admin_note,
        status,
        user["username"],
        request_id
    ))
    db.commit()
    db.close()

    return redirect("/password-requests")

@app.route("/password-requests/delete", methods=["POST"])
def delete_password_request():
    user = current_user()

    if not user:
        return redirect("/login")

    if not has_role("super_admin"):
        return redirect("/dashboard")

    request_id = safe_int(request.form.get("request_id"))

    db = get_db()
    db.execute("""
        DELETE FROM password_reset_requests
        WHERE id = ?
    """, (request_id,))
    db.commit()
    db.close()

    return redirect("/password-requests")

@app.route("/switch-tenant/<int:tenant_id>")
def switch_tenant(tenant_id):
    user = current_user()

    if not user:
        return redirect("/login")

    if not has_role("super_admin"):
        return redirect("/dashboard")

    session["active_tenant_id"] = tenant_id
    clear_chat_sessions()

    return redirect("/dashboard")


@app.route("/dashboard")
def dashboard():
    user = current_user()

    if not user:
        return redirect("/login")

    tenant_id = get_active_tenant_id()
    reservations = get_reservations_by_tenant(tenant_id)
    settings = get_tenant_settings(tenant_id) or {}
    analytics = get_analytics_summary(tenant_id)
    tenant_plan = get_tenant_plan(tenant_id)

    today = datetime.now().date()
    today_str = today.strftime("%d.%m.%Y")
    now_dt = datetime.now()

    max_capacity = safe_int(settings.get("max_capacity", 20), 20)

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
            occupied_today += safe_int(r.get("people", 0), 0)

        if res_date >= today:
            upcoming += 1

    free_places_today = max(max_capacity - occupied_today, 0)

    capacity_percent = 0
    if max_capacity > 0:
        capacity_percent = round((occupied_today / max_capacity) * 100)

    today_upcoming_list = []

    for r in reservations:
        if r["date"] == today_str:
            reservation_time = str(r.get("time", "")).strip()

            try:
                reservation_dt = datetime.strptime(
                    f"{today_str} {reservation_time}",
                    "%d.%m.%Y %H:%M"
                )

                diff_minutes = int((reservation_dt - now_dt).total_seconds() / 60)

                if -60 <= diff_minutes <= 15:
                    status_label = "🔵 Сега"
                    status_class = "status-now"
                elif 15 < diff_minutes <= 30:
                    status_label = f"🟠 След {diff_minutes}м"
                    status_class = "status-soon"
                elif diff_minutes > 30:
                    hours = diff_minutes // 60
                    minutes = diff_minutes % 60

                    if hours > 0:
                        status_label = f"🟢 След {hours}ч {minutes}м"
                    else:
                        status_label = f"🟢 След {minutes}м"

                    status_class = "status-later"
                else:
                    status_label = "🔴 Минала"
                    status_class = "status-late"

                today_upcoming_list.append({
                    "name": r["name"],
                    "time": reservation_time,
                    "people": r["people"],
                    "phone": r["phone"],
                    "status_label": status_label,
                    "status_class": status_class,
                    "diff_minutes": diff_minutes
                })

            except Exception:
                today_upcoming_list.append({
                    "name": r["name"],
                    "time": reservation_time,
                    "people": r["people"],
                    "phone": r["phone"],
                    "status_label": "⚪ Неизвестно",
                    "status_class": "status-unknown",
                    "diff_minutes": 9999
                })

    today_upcoming_list = sorted(
        today_upcoming_list,
        key=lambda x: x["time"]
    )[:8]

    notifications = []

    for item in today_upcoming_list:
        status_class = item.get("status_class", "")
        status_label = item.get("status_label", "")

        if status_class == "status-soon":
            notifications.append({
                "icon": "🟠",
                "title": f"Скоро резервация: {item['name']}",
                "text": f"{item['time']} · {item['people']} човека · {status_label}",
                "type": "soon"
            })

        elif status_class == "status-now":
            notifications.append({
                "icon": "🔵",
                "title": f"Текуща резервация: {item['name']}",
                "text": f"{item['time']} · {item['people']} човека · {status_label}",
                "type": "now"
            })

        elif status_class == "status-late":
            notifications.append({
                "icon": "🔴",
                "title": f"Минала резервация: {item['name']}",
                "text": f"{item['time']} · {item['people']} човека · {status_label}",
                "type": "late"
            })

    for r in reservations:
        if r["date"] == today_str and r.get("status") == "pending":
            notifications.append({
                "icon": "🟡",
                "title": f"Непотвърдена резервация: {r['name']}",
                "text": f"{r['time']} · {r['people']} човека · {r['phone']}",
                "type": "pending"
            })

        if r["date"] == today_str and r.get("status") == "cancelled":
            notifications.append({
                "icon": "⚫",
                "title": f"Отказана резервация: {r['name']}",
                "text": f"{r['time']} · {r['people']} човека · {r['phone']}",
                "type": "cancelled"
            })

    notification_count = len(notifications)

    last_7_days_chart = []

    for i in range(6, -1, -1):
        day = today - timedelta(days=i)
        day_str = day.strftime("%d.%m.%Y")

        count = 0

        for r in reservations:
            if r["date"] == day_str:
                count += 1

        last_7_days_chart.append({
            "label": day.strftime("%a"),
            "date": day_str,
            "count": count
        })

    max_chart_count = max([d["count"] for d in last_7_days_chart], default=1)

    if max_chart_count == 0:
        max_chart_count = 1

    top_hours_chart = {}

    for r in reservations:
        time_value = str(r.get("time", "")).strip()

        if not time_value:
            continue

        hour = time_value[:2]

        if not hour.isdigit():
            continue

        hour_label = f"{hour}:00"
        top_hours_chart[hour_label] = top_hours_chart.get(hour_label, 0) + 1

    top_hours_chart = [
        {
            "label": hour,
            "count": count
        }
        for hour, count in sorted(
            top_hours_chart.items(),
            key=lambda item: item[1],
            reverse=True
        )[:5]
    ]

    max_hour_count = max([h["count"] for h in top_hours_chart], default=1)

    if max_hour_count == 0:
        max_hour_count = 1

    return render_template(
        "dashboard.html",
        reservations=reservations,
        total=total,
        today_count=today_count,
        upcoming=upcoming,
        free_places_today=free_places_today,
        occupied_today=occupied_today,
        max_capacity=max_capacity,
        capacity_percent=capacity_percent,
        current_date=today_str,
        today_upcoming_list=today_upcoming_list,
        notifications=notifications,
        notification_count=notification_count,
        last_7_days_chart=last_7_days_chart,
        max_hour_count=max_hour_count,
        top_hours_chart=top_hours_chart,
        max_chart_count=max_chart_count,
        analytics=analytics,
        username=user["username"],
        role=user["role"],
        can_manage_premium_features=can_manage_premium_features(),
        is_super_admin=is_super_admin(),
        tenant_plan=tenant_plan,
        tenant_has_ai_chat=tenant_has_feature(tenant_id, "ai_chat"),
        tenant_has_premium_analytics=tenant_has_feature(tenant_id, "premium_analytics"),
        tenant_has_upsell=tenant_has_feature(tenant_id, "upsell"),
        active_business=get_active_tenant_info(),
    )

@app.route("/api/notifications")
def api_notifications():
    user = current_user()

    if not user:
        return jsonify({
            "status": "error",
            "message": "Неоторизиран достъп",
            "notifications": [],
            "count": 0
        }), 401

    tenant_id = get_active_tenant_id()
    reservations = get_reservations_by_tenant(tenant_id)

    now_dt = datetime.now()
    today_str = now_dt.strftime("%d.%m.%Y")

    notifications = []

    for r in reservations:
        if r["date"] != today_str:
            continue

        reservation_time = str(r.get("time", "")).strip()

        try:
            reservation_dt = datetime.strptime(
                f"{today_str} {reservation_time}",
                "%d.%m.%Y %H:%M"
            )

            diff_minutes = int((reservation_dt - now_dt).total_seconds() / 60)

            if 0 <= diff_minutes <= 30:
                notifications.append({
                    "icon": "⏰",
                    "title": "Резервация скоро",
                    "text": f"{r['name']} — {reservation_time}, {r['people']} човека",
                    "type": "soon"
                })

            elif -60 <= diff_minutes < 0:
                notifications.append({
                    "icon": "🔵",
                    "title": "Текуща резервация",
                    "text": f"{r['name']} — {reservation_time}, {r['people']} човека",
                    "type": "now"
                })

            elif diff_minutes < -60 and r.get("status", "confirmed") == "pending":
                notifications.append({
                    "icon": "⚠️",
                    "title": "Минала непотвърдена",
                    "text": f"{r['name']} — {reservation_time}",
                    "type": "late"
                })

        except Exception:
            continue

    pending_count = 0

    for r in reservations:
        if r.get("status") == "pending":
            pending_count += 1

    if pending_count > 0:
        notifications.append({
            "icon": "🟠",
            "title": "Непотвърдени резервации",
            "text": f"Има {pending_count} резервации със статус „Непотвърдена“.",
            "type": "pending"
        })

    notifications = notifications[:8]

    return jsonify({
        "status": "success",
        "count": len(notifications),
        "notifications": notifications
    })

@app.route("/notifications")
def notifications_page():
    user = current_user()

    if not user:
        return redirect("/login")

    tenant_id = get_active_tenant_id()
    reservations = get_reservations_by_tenant(tenant_id)

    now_dt = datetime.now()
    today = now_dt.date()
    today_str = today.strftime("%d.%m.%Y")

    all_notifications = []

    for r in reservations:
        res_date = parse_bg_date(r["date"])
        if not res_date:
            continue

        reservation_time = str(r.get("time", "")).strip()
        status = r.get("status", "confirmed")

        try:
            reservation_dt = datetime.strptime(
                f"{r['date']} {reservation_time}",
                "%d.%m.%Y %H:%M"
            )

            diff_minutes = int((reservation_dt - now_dt).total_seconds() / 60)

            if res_date < today:
                type_label = "Минала"
                icon = "🔴"
                type_class = "notification-late"
            elif res_date == today and diff_minutes < -60:
                type_label = "Минала днес"
                icon = "🔴"
                type_class = "notification-late"
            elif res_date == today and -60 <= diff_minutes <= 15:
                type_label = "Сега"
                icon = "🔵"
                type_class = "notification-now"
            elif res_date == today and 15 < diff_minutes <= 30:
                type_label = "Скоро"
                icon = "🟠"
                type_class = "notification-soon"
            elif res_date >= today:
                type_label = "Предстояща"
                icon = "🟢"
                type_class = "notification-upcoming"
            else:
                type_label = "Известие"
                icon = "🔔"
                type_class = "notification-default"

            if status == "pending":
                type_label = "Непотвърдена"
                icon = "🟡"
                type_class = "notification-pending"

            if status == "cancelled":
                type_label = "Отказана"
                icon = "⚫"
                type_class = "notification-cancelled"

            all_notifications.append({
                "icon": icon,
                "title": f"{type_label} резервация: {r['name']}",
                "text": f"{r['date']} · {reservation_time} · {r['people']} човека · {r['phone']}",
                "type_label": type_label,
                "type_class": type_class,
                "date": r["date"],
                "time": reservation_time
            })

        except Exception:
            continue

    all_notifications = sorted(
        all_notifications,
        key=lambda x: (x["date"], x["time"]),
        reverse=True
    )

    return render_template(
        "notifications.html",
        notifications=all_notifications,
        role=user["role"],
        active_business=get_active_tenant_info()
    )

@app.route("/analytics/chats")
def analytics_chats():
    user = current_user()

    if not user:
        return redirect("/login")

    tenant_id = get_active_tenant_id()

    if not can_access_premium_analytics(tenant_id):
        return redirect("/dashboard")

    return render_template(
        "analytics_chats.html",
        role=user["role"],
        active_business=get_active_tenant_info(),
        data=get_analytics_page_data(tenant_id),
        events=get_recent_events(tenant_id, event_type="chat_message", limit=100),
    )


@app.route("/analytics/reservations")
def analytics_reservations():
    user = current_user()

    if not user:
        return redirect("/login")

    tenant_id = get_active_tenant_id()

    if not can_access_premium_analytics(tenant_id):
        return redirect("/dashboard")

    return render_template(
        "analytics_reservations.html",
        role=user["role"],
        active_business=get_active_tenant_info(),
        data=get_analytics_page_data(tenant_id),
        started_events=get_recent_events(tenant_id, event_type="reservation_started", limit=100),
        created_events=get_recent_events(tenant_id, event_type="reservation_created", limit=100),
    )


@app.route("/analytics/conversion")
def analytics_conversion():
    user = current_user()

    if not user:
        return redirect("/login")

    tenant_id = get_active_tenant_id()

    if not can_access_premium_analytics(tenant_id):
        return redirect("/dashboard")

    return render_template(
        "analytics_conversion.html",
        role=user["role"],
        active_business=get_active_tenant_info(),
        data=get_analytics_page_data(tenant_id),
    )

@app.route("/settings", methods=["GET", "POST"])
def settings():
    user = current_user()

    if not user:
        return redirect("/login")

    if not has_role("super_admin", "owner", "admin"):
        return redirect("/dashboard")

    tenant_id = get_active_tenant_id()

    can_manage_premium = can_manage_premium_features()
    tenant_plan = get_tenant_plan(tenant_id)
    tenant_has_ai_chat = tenant_has_feature(tenant_id, "ai_chat")
    tenant_has_premium_analytics = tenant_has_feature(tenant_id, "premium_analytics")
    tenant_has_upsell = tenant_has_feature(tenant_id, "upsell")

    if request.method == "POST":
        existing_settings = get_tenant_settings(tenant_id) or {}

        restaurant_name = request.form.get(
            "restaurant_name",
            existing_settings.get("restaurant_name", "")
        ).strip()

        phone = request.form.get(
            "phone",
            existing_settings.get("phone", "")
        ).strip()

        email = request.form.get(
            "email",
            existing_settings.get("email", "")
        ).strip()

        address = request.form.get(
            "address",
            existing_settings.get("address", "")
        ).strip()

        welcome_message = request.form.get(
            "welcome_message",
            existing_settings.get("welcome_message", "")
        ).strip()

        primary_color = request.form.get(
            "primary_color",
            existing_settings.get("primary_color", "#1e88ff")
        ).strip()

        widget_title = request.form.get(
            "widget_title",
            existing_settings.get("widget_title", "AI ChatBot")
        ).strip()

        widget_enabled = safe_int(
            request.form.get(
                "widget_enabled",
                existing_settings.get("widget_enabled", 1)
            ),
            1
        )

        if has_role("super_admin", "owner"):
            business_type = normalize_business_type(
                request.form.get(
                    "business_type",
                    get_tenant_business_type(tenant_id)
                )
            )
            update_tenant_business_type(tenant_id, business_type)

            max_capacity = safe_int(
                request.form.get(
                    "max_capacity",
                    existing_settings.get("max_capacity", 20)
                ),
                20
            )

            open_hour = safe_int(
                request.form.get(
                    "open_hour",
                    existing_settings.get("open_hour", 10)
                ),
                10
            )

            close_hour = safe_int(
                request.form.get(
                    "close_hour",
                    existing_settings.get("close_hour", 22)
                ),
                22
            )
        else:
            max_capacity = safe_int(existing_settings.get("max_capacity", 20), 20)
            open_hour = safe_int(existing_settings.get("open_hour", 10), 10)
            close_hour = safe_int(existing_settings.get("close_hour", 22), 22)

        if can_use_ai_settings(tenant_id):
            llm_enabled = safe_int(
                request.form.get(
                    "llm_enabled",
                    existing_settings.get("llm_enabled", 0)
                ),
                0
            )
        else:
            llm_enabled = safe_int(existing_settings.get("llm_enabled", 0), 0)

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

    return render_template(
        "settings.html",
        settings=get_tenant_settings(tenant_id) or {},
        saved=request.args.get("saved") == "1",
        role=user["role"],
        can_manage_premium_features=can_manage_premium,
        is_super_admin=is_super_admin(),
        tenant_plan=tenant_plan,
        tenant_has_ai_chat=tenant_has_ai_chat,
        tenant_has_premium_analytics=tenant_has_premium_analytics,
        tenant_has_upsell=tenant_has_upsell,
        business_type_options=get_business_type_options(),
        current_business_type=get_tenant_business_type(tenant_id),
        active_business=get_active_tenant_info(),
    )


@app.route("/restaurants")
def restaurants():
    user = current_user()

    if not user:
        return redirect("/login")

    if not has_role("super_admin"):
        return redirect("/dashboard")

    all_restaurants = list_tenants()

    page = safe_int(request.args.get("page", 1), 1)
    per_page = 3

    total_items = len(all_restaurants)
    total_pages = max((total_items + per_page - 1) // per_page, 1)

    if page < 1:
        page = 1

    if page > total_pages:
        page = total_pages

    start = (page - 1) * per_page
    end = start + per_page

    restaurants_page = all_restaurants[start:end]

    return render_template(
        "restaurants.html",
        restaurants=restaurants_page,
        business_type_options=get_business_type_options(),
        current_page=page,
        total_pages=total_pages,
        total_items=total_items,
        per_page=per_page,
        start_item=start + 1 if total_items > 0 else 0,
        end_item=min(end, total_items),
    )


@app.route("/restaurants/deactivate", methods=["POST"])
def restaurants_deactivate():
    if not current_user():
        return redirect("/login")

    if not has_role("super_admin"):
        return redirect("/dashboard")

    tenant_id = safe_int(request.form.get("tenant_id"))
    deactivate_tenant(tenant_id)

    return redirect("/restaurants")


@app.route("/restaurants/activate", methods=["POST"])
def restaurants_activate():
    if not current_user():
        return redirect("/login")

    if not has_role("super_admin"):
        return redirect("/dashboard")

    tenant_id = safe_int(request.form.get("tenant_id"))
    activate_tenant(tenant_id)

    return redirect("/restaurants")


@app.route("/restaurants/edit", methods=["POST"])
def restaurants_edit():
    user = current_user()

    if not user:
        return redirect("/login")

    if not has_role("super_admin"):
        return redirect("/dashboard")

    tenant_id = safe_int(request.form.get("tenant_id"))
    name = request.form.get("name", "").strip()
    slug = request.form.get("slug", "").strip()
    plan = normalize_plan(request.form.get("plan", "basic"))
    business_type = normalize_business_type(request.form.get("business_type", "restaurant"))

    if not name or not slug:
        return redirect("/restaurants?error=invalid")

    try:
        update_tenant(
            tenant_id=tenant_id,
            name=name,
            slug=slug,
            plan=plan,
            business_type=business_type
        )

        clear_chat_sessions()
        return redirect("/restaurants?success=edited")

    except Exception as e:
        print("EDIT TENANT ERROR:", e)
        return redirect("/restaurants?error=edit")


@app.route("/restaurants/delete", methods=["POST"])
def restaurants_delete():
    user = current_user()

    if not user:
        return redirect("/login")

    if not has_role("super_admin"):
        return redirect("/dashboard")

    tenant_id = safe_int(request.form.get("tenant_id"))

    if tenant_id == user["tenant_id"]:
        return redirect("/restaurants?error=self_delete")

    try:
        delete_tenant(tenant_id)
        clear_chat_sessions()
        return redirect("/restaurants?success=deleted")

    except Exception as e:
        print("DELETE TENANT ERROR:", e)
        return redirect("/restaurants?error=delete")


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

        max_capacity = safe_int(request.form.get("max_capacity", 20), 20)
        open_hour = safe_int(request.form.get("open_hour", 10), 10)
        close_hour = safe_int(request.form.get("close_hour", 22), 22)

        plan = normalize_plan(request.form.get("plan", "basic"))
        business_type = normalize_business_type(request.form.get("business_type", "restaurant"))
        auto_menu = safe_int(request.form.get("auto_menu", 1), 1)

        if not all([restaurant_name, slug, username, password]):
            return render_template("create_restaurant.html", error="Моля, попълни всички полета.", success=None)

        existing_user = get_any_user_by_username(username)

        if existing_user:
            return render_template("create_restaurant.html", error="Това потребителско име вече съществува.", success=None)

        try:
            tenant_id = create_tenant(
                name=restaurant_name,
                slug=slug,
                max_capacity=max_capacity,
                open_hour=open_hour,
                close_hour=close_hour,
                plan=plan,
                business_type=business_type
            )

            create_user(tenant_id=tenant_id, username=username, password=password, role="owner")

            if auto_menu == 1:
                seed_default_menu_for_business_type(tenant_id, business_type)

            clear_chat_sessions()

            return render_template(
                "create_restaurant.html",
                error=None,
                success=f"Успешно създаде бизнес „{restaurant_name}“ с потребител „{username}“."
            )

        except Exception as e:
            print("CREATE RESTAURANT ERROR:", e)
            return render_template(
                "create_restaurant.html",
                error="Възникна грешка при създаването. Възможно е slug или потребител да съществуват вече.",
                success=None
            )

    return render_template("create_restaurant.html", error=None, success=None)


@app.route("/users")
def users_page():
    user = current_user()

    if not user:
        return redirect("/login")

    if not has_role("owner", "admin", "super_admin"):
        return redirect("/dashboard")

    tenant_id = get_active_tenant_id()

    users = list_users_by_tenant(tenant_id)

    for u in users:
        if "email" not in u or not u.get("email"):
            u["email"] = f"{u['username']}@example.com"

        if "last_login" not in u or not u.get("last_login"):
            u["last_login"] = "20.04.2026 17:40"

    success = request.args.get("success")
    error = request.args.get("error")

    success_map = {
        "created": "Потребителят е създаден успешно.",
        "role": "Ролята е променена успешно.",
        "deactivated": "Потребителят е спрян успешно.",
        "activated": "Потребителят е пуснат успешно.",
        "edited": "Потребителят е редактиран успешно.",
        "deleted": "Потребителят е изтрит успешно.",
    }

    error_map = {
        "exists": "Това потребителско име вече съществува.",
        "invalid": "Невалидни данни.",
        "owner": "Този потребител не може да бъде променян оттук.",
        "self": "Не можеш да редактираш или изтриеш собствения си акаунт оттук.",
    }

    return render_template(
        "users.html",
        users=users,
        success=success_map.get(success),
        error=error_map.get(error),
        role=user["role"],
        can_manage_premium_features=can_manage_premium_features(),
        is_super_admin=is_super_admin(),
        active_business=get_active_tenant_info(),
    )


@app.route("/users/create", methods=["POST"])
def users_create():
    user = current_user()

    if not user:
        return redirect("/login")

    if not has_role("owner", "admin", "super_admin"):
        return redirect("/dashboard")

    tenant_id = get_active_tenant_id()
    username = request.form.get("username", "").strip()
    password = request.form.get("password", "").strip()
    role = request.form.get("role", "").strip()

    if has_role("super_admin"):
        allowed_roles = ["owner", "admin", "staff"]
    elif has_role("owner"):
        allowed_roles = ["admin", "staff"]
    else:
        allowed_roles = ["staff"]

    if not username or not password or role not in allowed_roles:
        return redirect("/users?error=invalid")

    if get_any_user_by_username(username):
        return redirect("/users?error=exists")

    create_user(tenant_id, username, password, role)

    return redirect("/users?success=created")


@app.route("/users/change-role", methods=["POST"])
def users_change_role():
    user = current_user()

    if not user:
        return redirect("/login")

    if not has_role("owner", "admin", "super_admin"):
        return redirect("/dashboard")

    tenant_id = get_active_tenant_id()
    user_id = safe_int(request.form.get("user_id"))
    role = request.form.get("role", "").strip()

    users = list_users_by_tenant(tenant_id)
    target_user = next((u for u in users if u["id"] == user_id), None)

    if not target_user:
        return redirect("/users?error=invalid")

    if target_user["id"] == user["id"]:
        return redirect("/users?error=self")

    if target_user["role"] == "super_admin":
        return redirect("/users?error=owner")

    if has_role("super_admin"):
        allowed_roles = ["owner", "admin", "staff"]
    elif has_role("owner"):
        if target_user["role"] == "owner":
            return redirect("/users?error=owner")
        allowed_roles = ["admin", "staff"]
    else:
        if target_user["role"] != "staff":
            return redirect("/users?error=owner")
        allowed_roles = ["staff"]

    if role not in allowed_roles:
        return redirect("/users?error=invalid")

    update_user_role(user_id, tenant_id, role)

    return redirect("/users?success=role")


@app.route("/users/edit", methods=["POST"])
def users_edit():
    user = current_user()

    if not user:
        return redirect("/login")

    if not has_role("owner", "admin", "super_admin"):
        return redirect("/dashboard")

    tenant_id = get_active_tenant_id()
    user_id = safe_int(request.form.get("user_id"))

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

    if has_role("super_admin"):
        allowed_roles = ["owner", "admin", "staff"]
    elif has_role("owner"):
        if target_user["role"] == "owner":
            return redirect("/users?error=owner")
        allowed_roles = ["admin", "staff"]
    else:
        if target_user["role"] != "staff":
            return redirect("/users?error=owner")
        allowed_roles = ["staff"]

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

    if not has_role("owner", "admin", "super_admin"):
        return redirect("/dashboard")

    tenant_id = get_active_tenant_id()
    user_id = safe_int(request.form.get("user_id"))

    users = list_users_by_tenant(tenant_id)
    target_user = next((u for u in users if u["id"] == user_id), None)

    if not target_user:
        return redirect("/users?error=invalid")

    if target_user["id"] == user["id"]:
        return redirect("/users?error=self")

    if target_user["role"] == "super_admin":
        return redirect("/users?error=owner")

    if has_role("admin") and target_user["role"] != "staff":
        return redirect("/users?error=owner")

    if has_role("owner") and target_user["role"] == "owner":
        return redirect("/users?error=owner")

    deactivate_user(user_id, tenant_id)

    return redirect("/users?success=deactivated")


@app.route("/users/activate", methods=["POST"])
def users_activate():
    user = current_user()

    if not user:
        return redirect("/login")

    if not has_role("owner", "admin", "super_admin"):
        return redirect("/dashboard")

    tenant_id = get_active_tenant_id()
    user_id = safe_int(request.form.get("user_id"))

    users = list_users_by_tenant(tenant_id)
    target_user = next((u for u in users if u["id"] == user_id), None)

    if not target_user:
        return redirect("/users?error=invalid")

    if target_user["id"] == user["id"]:
        return redirect("/users?error=self")

    if target_user["role"] == "super_admin":
        return redirect("/users?error=owner")

    if has_role("admin") and target_user["role"] != "staff":
        return redirect("/users?error=owner")

    if has_role("owner") and target_user["role"] == "owner":
        return redirect("/users?error=owner")

    activate_user(user_id, tenant_id)

    return redirect("/users?success=activated")


@app.route("/users/delete", methods=["POST"])
def users_delete():
    user = current_user()

    if not user:
        return redirect("/login")

    if not has_role("owner", "admin", "super_admin"):
        return redirect("/dashboard")

    tenant_id = get_active_tenant_id()
    user_id = safe_int(request.form.get("user_id"))

    users = list_users_by_tenant(tenant_id)
    target_user = next((u for u in users if u["id"] == user_id), None)

    if not target_user:
        return redirect("/users?error=invalid")

    if target_user["id"] == user["id"]:
        return redirect("/users?error=self")

    if target_user["role"] == "super_admin":
        return redirect("/users?error=owner")

    if has_role("admin") and target_user["role"] != "staff":
        return redirect("/users?error=owner")

    if has_role("owner") and target_user["role"] == "owner":
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

    tenant_id = get_active_tenant_id()

    return render_template(
    "menu_manager.html",
    categories=get_menu_categories(tenant_id),
    menu_data=get_full_menu(tenant_id, include_inactive=True),
    saved=request.args.get("saved") == "1",
    role=user["role"],
    can_manage_premium_features=can_manage_premium_features(),
    is_super_admin=is_super_admin(),
    tenant_plan=get_tenant_plan(tenant_id),
    tenant_has_product_images=tenant_has_feature(tenant_id, "product_images"),
    tenant_has_upsell=tenant_has_feature(tenant_id, "upsell"),
    active_business=get_active_tenant_info(),
)


@app.route("/menu-manager/add-category", methods=["POST"])
def add_menu_category_route():
    if not current_user():
        return redirect("/login")

    if not has_role("super_admin", "owner", "admin"):
        return redirect("/dashboard")

    tenant_id = get_active_tenant_id()
    name = request.form.get("name", "").strip()
    sort_order = safe_int(request.form.get("sort_order", 0), 0)

    if name:
        name_en = bg_to_en(name)

        create_menu_category(
            tenant_id=tenant_id,
            name=name,
            sort_order=sort_order,
            name_en=name_en
        )

    clear_chat_sessions()
    return redirect("/menu-manager?saved=1")


@app.route("/menu-manager/add-item", methods=["POST"])
def add_menu_item_route():
    if not current_user():
        return redirect("/login")

    if not has_role("super_admin", "owner", "admin"):
        return redirect("/dashboard")

    tenant_id = get_active_tenant_id()

    category_id = safe_int(request.form.get("category_id"))
    name = request.form.get("name", "").strip()
    description = request.form.get("description", "").strip()
    price = safe_float(request.form.get("price", 0), 0.0)
    upsell_drink = request.form.get("upsell_drink", "").strip()
    upsell_dessert = request.form.get("upsell_dessert", "").strip()
    upsell_side = request.form.get("upsell_side", "").strip()
    can_use_upsell = tenant_has_feature(tenant_id, "upsell")
    can_use_product_images = tenant_has_feature(tenant_id, "product_images")

    if not can_use_upsell:
        upsell_drink = ""
        upsell_dessert = ""
        upsell_side = ""
        sort_order = safe_int(request.form.get("sort_order", 0), 0)

        image_url = ""

    if can_use_product_images:
        image_url = request.form.get("image_url", "").strip()
        uploaded_image = save_menu_image(request.files.get("image_file"))

    if uploaded_image:
        image_url = uploaded_image

    if name:
        create_menu_item(
            tenant_id=tenant_id,
            category_id=category_id,
            name=name,
            name_en=bg_to_en(name),
            description=description,
            description_en=bg_to_en(description),
            price=price,
            sort_order=sort_order,
            upsell_drink=upsell_drink,
            upsell_drink_en=bg_to_en(upsell_drink),
            upsell_dessert=upsell_dessert,
            upsell_dessert_en=bg_to_en(upsell_dessert),
            upsell_side=upsell_side,
            upsell_side_en=bg_to_en(upsell_side),
            image_url=image_url
        )

    clear_chat_sessions()
    return redirect("/menu-manager?saved=1")


@app.route("/menu-manager/edit-category", methods=["POST"])
def edit_menu_category_route():
    if not current_user():
        return redirect("/login")

    if not has_role("super_admin", "owner", "admin"):
        return redirect("/dashboard")

    tenant_id = get_active_tenant_id()
    category_id = safe_int(request.form.get("category_id"))
    name = request.form.get("name", "").strip()
    sort_order = safe_int(request.form.get("sort_order", 0), 0)

    if name:
        update_menu_category(
            category_id=category_id,
            tenant_id=tenant_id,
            name=name,
            sort_order=sort_order,
            name_en=bg_to_en(name)
        )

    clear_chat_sessions()
    return redirect("/menu-manager?saved=1")


@app.route("/menu-manager/edit-item", methods=["POST"])
def edit_menu_item_route():
    if not current_user():
        return redirect("/login")

    if not has_role("super_admin", "owner", "admin"):
        return redirect("/dashboard")

    tenant_id = get_active_tenant_id()

    item_id = safe_int(request.form.get("item_id"))
    category_id = safe_int(request.form.get("category_id"))
    name = request.form.get("name", "").strip()
    description = request.form.get("description", "").strip()
    price = safe_float(request.form.get("price", 0), 0.0)
    sort_order = safe_int(request.form.get("sort_order", 0), 0)
    upsell_drink = request.form.get("upsell_drink", "").strip()
    upsell_dessert = request.form.get("upsell_dessert", "").strip()
    upsell_side = request.form.get("upsell_side", "").strip()
    can_use_upsell = tenant_has_feature(tenant_id, "upsell")
    can_use_product_images = tenant_has_feature(tenant_id, "product_images")

    if not can_use_upsell:
        upsell_drink = ""
        upsell_dessert = ""
        upsell_side = ""

        image_url = ""

    if can_use_product_images:
        image_url = request.form.get("image_url", "").strip()
        uploaded_image = save_menu_image(request.files.get("image_file"))

    if uploaded_image:
        image_url = uploaded_image

    if name:
        update_menu_item(
            item_id=item_id,
            tenant_id=tenant_id,
            category_id=category_id,
            name=name,
            name_en=bg_to_en(name),
            description=description,
            description_en=bg_to_en(description),
            price=price,
            sort_order=sort_order,
            upsell_drink=upsell_drink,
            upsell_drink_en=bg_to_en(upsell_drink),
            upsell_dessert=upsell_dessert,
            upsell_dessert_en=bg_to_en(upsell_dessert),
            upsell_side=upsell_side,
            upsell_side_en=bg_to_en(upsell_side),
            image_url=image_url
        )

    clear_chat_sessions()
    return redirect("/menu-manager?saved=1")


@app.route("/menu-manager/delete-category", methods=["POST"])
def delete_menu_category_route():
    if not current_user():
        return redirect("/login")

    if not has_role("super_admin", "owner", "admin"):
        return redirect("/dashboard")

    tenant_id = get_active_tenant_id()
    category_id = safe_int(request.form.get("category_id"))

    delete_menu_category(category_id, tenant_id)
    clear_chat_sessions()

    return redirect("/menu-manager?saved=1")


@app.route("/menu-manager/delete-item", methods=["POST"])
def delete_menu_item_route():
    if not current_user():
        return redirect("/login")

    if not has_role("super_admin", "owner", "admin"):
        return redirect("/dashboard")

    tenant_id = get_active_tenant_id()
    item_id = safe_int(request.form.get("item_id"))

    delete_menu_item(item_id, tenant_id)
    clear_chat_sessions()

    return redirect("/menu-manager?saved=1")


@app.route("/menu-manager/toggle-item", methods=["POST"])
def toggle_menu_item_route():
    if not current_user():
        return redirect("/login")

    if not has_role("super_admin", "owner", "admin"):
        return redirect("/dashboard")

    tenant_id = get_active_tenant_id()
    item_id = safe_int(request.form.get("item_id"))

    toggle_menu_item_status(item_id, tenant_id)
    clear_chat_sessions()

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

    delete_reservation(reservation_id, get_active_tenant_id())

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
    status = data.get("status", "confirmed").strip()

    if not all([reservation_id, name, phone, date, time, people]):
        return jsonify({"status": "error", "message": "Липсват данни"})

    update_reservation(
        reservation_id=reservation_id,
        tenant_id=get_active_tenant_id(),
        name=name,
        phone=phone,
        date=date,
        time=time,
        people=people,
        status=status,
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

    file_path = export_reservations_to_excel(get_active_tenant_id(), output_dir="data")

    if not file_path:
        return "Няма данни за export"

    return send_file(file_path, as_attachment=True)


if __name__ == "__main__":
    import os

    port = int(os.environ.get("PORT", 10000))

    app.run(
        host="0.0.0.0",
        port=port,
        debug=False
    )