import smtplib

from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

from config import (
    SMTP_HOST,
    SMTP_PORT,
    SMTP_EMAIL,
    SMTP_PASSWORD
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

        settings = get_tenant_settings(tenant_id)

        if not settings:
            return False

        business_email = settings.get("email", "").strip()

        if not business_email:
            return False

        message = MIMEMultipart()

        message["From"] = SMTP_EMAIL
        message["To"] = business_email
        message["Subject"] = "Нова резервация - Reservy"

        body = f"""
Нова резервация:

Име: {name}
Телефон: {phone}
Дата: {date}
Час: {time}
Хора: {people}

Източник: AI Chatbot
"""

        message.attach(
            MIMEText(body, "plain", "utf-8")
        )

        server = smtplib.SMTP(
            SMTP_HOST,
            SMTP_PORT
        )

        server.starttls()

        server.login(
            SMTP_EMAIL,
            SMTP_PASSWORD
        )

        server.send_message(message)

        server.quit()

        return True

    except Exception as e:
        print("EMAIL ERROR:", e)
        return False