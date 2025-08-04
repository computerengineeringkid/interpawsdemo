"""Utility functions for sending appointment reminders via email and SMS."""

import os
from typing import Optional


def send_email_reminder(to_email: str, subject: str, body: str) -> None:
    """Send an email reminder using SendGrid.

    Requires the ``SENDGRID_API_KEY`` environment variable. If the
    ``sendgrid`` package or API key is missing, the function will log to stdout
    instead of raising an exception.
    """
    api_key = os.getenv("SENDGRID_API_KEY")
    if not api_key:
        print("SENDGRID_API_KEY not set; skipping email")
        return
    try:
        from sendgrid import SendGridAPIClient
        from sendgrid.helpers.mail import Mail
    except Exception as exc:  # ImportError or other issues
        print(f"SendGrid not available: {exc}")
        return
    message = Mail(
        from_email=os.getenv("REMINDER_EMAIL", "noreply@example.com"),
        to_emails=to_email,
        subject=subject,
        plain_text_content=body,
    )
    try:
        sg = SendGridAPIClient(api_key)
        sg.send(message)
    except Exception as exc:  # pragma: no cover - network call
        print(f"Error sending email: {exc}")


def send_sms_reminder(to_phone: str, body: str) -> None:
    """Send an SMS reminder using Twilio.

    Requires ``TWILIO_SID``, ``TWILIO_AUTH_TOKEN``, and ``TWILIO_PHONE_NUMBER``
    environment variables. Missing configuration results in a log message.
    """
    sid = os.getenv("TWILIO_SID")
    token = os.getenv("TWILIO_AUTH_TOKEN")
    from_phone = os.getenv("TWILIO_PHONE_NUMBER")
    if not all([sid, token, from_phone]):
        print("Twilio credentials not set; skipping SMS")
        return
    try:
        from twilio.rest import Client as TwilioClient
    except Exception as exc:
        print(f"Twilio not available: {exc}")
        return
    try:  # pragma: no cover - network call
        client = TwilioClient(sid, token)
        client.messages.create(body=body, from_=from_phone, to=to_phone)
    except Exception as exc:
        print(f"Error sending SMS: {exc}")


__all__ = ["send_email_reminder", "send_sms_reminder"]
