import requests

from services.tenants import tenant_has_feature
from config import (
    RESEND_API_KEY,
    FROM_EMAIL
)

from services.tenants import get_tenant_settings


def send_reservation_email(
    tenant_id,
    name,
    phone,
    date,
    time,
    people
):
    try:


        if not tenant_has_feature(
                tenant_id,
                "email_notifications"
            ):
            print(
            "EMAIL DISABLED FOR PLAN"
        )
            return False

        settings = get_tenant_settings(tenant_id)

        if not settings:
            return False

        business_email = settings.get(
            "email",
            ""
        ).strip()

        if not business_email:
            return False
        
        print(
            "BUSINESS EMAIL:",
            business_email
)

        payload = {
            "from": FROM_EMAIL,
            "to": [business_email],
            "subject": "Нова резервация - Reservy",
            "html": f"""
            <h2>📅 Нова резервация</h2>

            <p><strong>Име:</strong> {name}</p>

            <p><strong>Телефон:</strong> {phone}</p>

            <p><strong>Дата:</strong> {date}</p>

            <p><strong>Час:</strong> {time}</p>

            <p><strong>Хора:</strong> {people}</p>

            <hr>

            <p>Източник: AI Chatbot</p>
            """
        }

        response = requests.post(
            "https://api.resend.com/emails",
            headers={
                "Authorization": f"Bearer {RESEND_API_KEY}",
                "Content-Type": "application/json"
            },
            json=payload,
            timeout=30
        )

        print(
            "RESEND STATUS:",
            response.status_code
        )

        print(
            "RESEND RESPONSE:",
            response.text
        )

        return response.status_code in [200, 201]

    except Exception as e:
        print(
            "EMAIL ERROR:",
            e
        )

        return False