"""Email notifications. If SMTP isn't configured the message is only logged."""
import logging
from email.message import EmailMessage

import aiosmtplib

from app.core.config import settings

log = logging.getLogger(__name__)


async def send_email(to: str | list[str], subject: str, body: str) -> bool:
    recipients = [to] if isinstance(to, str) else [r for r in to if r]
    if not recipients:
        return False
    if not settings.SMTP_HOST:
        log.info("[email disabled] To=%s Subject=%s", recipients, subject)
        return False
    msg = EmailMessage()
    msg["From"] = settings.SMTP_FROM
    msg["To"] = ", ".join(recipients)
    msg["Subject"] = subject
    msg.set_content(body)
    try:
        await aiosmtplib.send(
            msg, hostname=settings.SMTP_HOST, port=settings.SMTP_PORT,
            username=settings.SMTP_USER or None, password=settings.SMTP_PASSWORD or None,
            start_tls=settings.SMTP_TLS, timeout=20,
        )
        return True
    except Exception as exc:  # never break the request because email failed
        log.error("Email send failed: %s", exc)
        return False
