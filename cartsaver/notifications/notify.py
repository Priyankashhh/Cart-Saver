"""
CartSaver — Multi-Channel Notification Dispatcher
Sends messages via Email (SendGrid), SMS (Twilio), and WhatsApp (Twilio).
Falls back to logging when credentials are not configured.
"""

import logging
from pathlib import Path
from datetime import datetime

from cartsaver.config import (
    SENDGRID_API_KEY, SENDGRID_FROM_EMAIL,
    TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN,
    TWILIO_SMS_FROM, TWILIO_WHATSAPP_FROM,
    LOG_DIR,
)

logger = logging.getLogger(__name__)

# Ensure log directory exists
_log_dir = Path(LOG_DIR)
_log_dir.mkdir(parents=True, exist_ok=True)
_NOTIFICATION_LOG = _log_dir / "notifications_sent.log"


def _log_notification(channel: str, recipient: str, message: str):
    """Append a notification record to the local log file."""
    ts = datetime.now().isoformat()
    with open(_NOTIFICATION_LOG, "a", encoding="utf-8") as f:
        f.write(f"[{ts}] [{channel.upper()}] To: {recipient}\n{message}\n{'─'*60}\n")


# ---------------------------------------------------------------------------
# Email via SendGrid
# ---------------------------------------------------------------------------

def send_email(to_email: str, subject: str, body: str) -> bool:
    """Send an email via SendGrid. Returns True on success."""
    if not SENDGRID_API_KEY:
        logger.info("[EMAIL-MOCK] → %s | %s", to_email, subject)
        _log_notification("email", to_email, body)
        return True

    try:
        from sendgrid import SendGridAPIClient
        from sendgrid.helpers.mail import Mail

        message = Mail(
            from_email=SENDGRID_FROM_EMAIL,
            to_emails=to_email,
            subject=subject,
            plain_text_content=body,
        )
        sg = SendGridAPIClient(SENDGRID_API_KEY)
        response = sg.send(message)
        logger.info("[EMAIL] Sent to %s — status %s", to_email, response.status_code)
        _log_notification("email", to_email, body)
        return True
    except Exception as exc:
        logger.error("[EMAIL] Failed for %s: %s", to_email, exc)
        _log_notification("email-FAILED", to_email, f"{body}\nERROR: {exc}")
        return False


# ---------------------------------------------------------------------------
# SMS via Twilio
# ---------------------------------------------------------------------------

def send_sms(to_phone: str, body: str) -> bool:
    """Send an SMS via Twilio. Returns True on success."""
    if not TWILIO_ACCOUNT_SID or not TWILIO_AUTH_TOKEN:
        logger.info("[SMS-MOCK] → %s", to_phone)
        _log_notification("sms", to_phone, body)
        return True

    try:
        from twilio.rest import Client

        client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
        msg = client.messages.create(
            body=body,
            from_=TWILIO_SMS_FROM,
            to=to_phone,
        )
        logger.info("[SMS] Sent to %s — SID %s", to_phone, msg.sid)
        _log_notification("sms", to_phone, body)
        return True
    except Exception as exc:
        logger.error("[SMS] Failed for %s: %s", to_phone, exc)
        _log_notification("sms-FAILED", to_phone, f"{body}\nERROR: {exc}")
        return False


# ---------------------------------------------------------------------------
# WhatsApp via Twilio
# ---------------------------------------------------------------------------

def send_whatsapp(to_phone: str, body: str) -> bool:
    """Send a WhatsApp message via Twilio sandbox. Returns True on success."""
    if not TWILIO_ACCOUNT_SID or not TWILIO_AUTH_TOKEN:
        logger.info("[WHATSAPP-MOCK] → %s", to_phone)
        _log_notification("whatsapp", to_phone, body)
        return True

    try:
        from twilio.rest import Client

        wa_to = to_phone if to_phone.startswith("whatsapp:") else f"whatsapp:{to_phone}"
        client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
        msg = client.messages.create(
            body=body,
            from_=TWILIO_WHATSAPP_FROM,
            to=wa_to,
        )
        logger.info("[WHATSAPP] Sent to %s — SID %s", to_phone, msg.sid)
        _log_notification("whatsapp", to_phone, body)
        return True
    except Exception as exc:
        logger.error("[WHATSAPP] Failed for %s: %s", to_phone, exc)
        _log_notification("whatsapp-FAILED", to_phone, f"{body}\nERROR: {exc}")
        return False


# ---------------------------------------------------------------------------
# Convenience: send on all 3 channels
# ---------------------------------------------------------------------------

def notify_user(row: dict) -> dict:
    """
    Send the generated message to a user via email, SMS, and WhatsApp.

    Parameters
    ----------
    row : dict
        Must include keys: email, phone, name, product_name, generated_message,
        message_type, final_discount_pct.

    Returns
    -------
    dict with keys: email_ok, sms_ok, whatsapp_ok
    """
    msg = row.get("generated_message", "")
    name = row.get("name", "Customer")
    product = row.get("product_name", "product")
    subject = f"🛒 {name}, your {product} is waiting!"

    email_ok = send_email(row.get("email", ""), subject, msg)
    sms_ok = send_sms(row.get("phone", ""), msg)
    whatsapp_ok = send_whatsapp(row.get("phone", ""), msg)

    return {"email_ok": email_ok, "sms_ok": sms_ok, "whatsapp_ok": whatsapp_ok}


def notify_all(offers: list[dict]) -> list[dict]:
    """Send notifications for all offer rows.  Adds ``notification_status``."""
    for row in offers:
        row["notification_status"] = notify_user(row)
    logger.info("Notifications dispatched for %d users.", len(offers))
    return offers
