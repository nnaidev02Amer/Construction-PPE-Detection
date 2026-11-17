from __future__ import annotations

import os
from email import encoders
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import aiosmtplib

from app.alerts.base import AlertHandler
from app.alerts.db_handler import log_alert
from app.core import screenshots
from app.core.config import settings
from app.core.logging import get_logger
from app.core.violation_checker import ViolationEvent
from app.core.violation_types import COMBINED, HELMET, LABELS, VEST

logger = get_logger(__name__)

PLACEHOLDER_SENDERS = {"your_email@gmail.com", ""}
PLACEHOLDER_RECEIVERS = {"receiver_email@example.com", "receiver@example.com", ""}
SMTP_TIMEOUT_SECONDS = 20


def is_email_configured() -> bool:
    """True when sender, password and recipient are all filled in (not the .env.example text)."""
    return (
        settings.SENDER_EMAIL not in PLACEHOLDER_SENDERS
        and bool(settings.EMAIL_PASSWORD)
        and settings.RECEIVER_EMAIL not in PLACEHOLDER_RECEIVERS
    )


def _type_enabled(violation_type: str) -> bool:
    return {
        HELMET: settings.EMAIL_NOTIFY_HELMET,
        VEST: settings.EMAIL_NOTIFY_VEST,
        COMBINED: settings.EMAIL_NOTIFY_COMBINED,
    }.get(violation_type, True)


def build_message(violation: ViolationEvent) -> MIMEMultipart:
    label = LABELS.get(violation.violation_type, violation.violation_type)
    worker = f"#{violation.track_id}" if violation.track_id is not None else "unknown"
    camera = violation.camera_name or f"Camera {violation.camera_id}"
    when = violation.timestamp.strftime("%Y-%m-%d %H:%M:%S") if violation.timestamp else "n/a"

    message = MIMEMultipart()
    message["From"] = settings.SENDER_EMAIL
    message["To"] = settings.RECEIVER_EMAIL
    prefix = "CRITICAL" if violation.violation_type == COMBINED else "Alert"
    message["Subject"] = f"[{prefix}] {label} - worker {worker} - {camera}"
    body = (
        "A PPE safety violation was recorded.\n\n"
        f"Violation : {label}\n"
        f"Worker ID : {worker} (tracking ID within this camera session, not an identity)\n"
        f"Camera    : {camera}\n"
        f"Time      : {when}\n"
        f"Confidence: {violation.confidence:.0%}\n"
        f"Incident #: {violation.db_id if violation.db_id is not None else 'n/a'}\n\n"
        "The evidence screenshot is attached when available."
    )
    message.attach(MIMEText(body, "plain"))

    path = screenshots.absolute_path(violation.frame_path)
    if path:
        with open(path, "rb") as f:
            part = MIMEBase("application", "octet-stream")
            part.set_payload(f.read())
        encoders.encode_base64(part)
        part.add_header("Content-Disposition", f"attachment; filename={os.path.basename(path)}")
        message.attach(part)
    return message


async def _deliver(message: MIMEMultipart) -> None:
    await aiosmtplib.send(
        message,
        hostname=settings.SMTP_HOST,
        port=settings.SMTP_PORT,
        username=settings.SENDER_EMAIL,
        password=settings.EMAIL_PASSWORD,
        start_tls=True,
        timeout=SMTP_TIMEOUT_SECONDS,
    )


class EmailHandler(AlertHandler):
    handler_type = "email"

    async def send(self, violation: ViolationEvent) -> bool:
        # Optional feature: silently skip when disabled / not configured / type switched off
        if not settings.EMAIL_ENABLED or not is_email_configured():
            return True
        if not _type_enabled(violation.violation_type):
            return True
        try:
            await _deliver(build_message(violation))
        except Exception as exc:  # SMTP errors must never stop detection
            logger.error("Failed to send email alert: %s", exc)
            await log_alert(violation.db_id, self.handler_type, False, str(exc))
            return False
        logger.info("Email alert sent for violation #%s", violation.db_id)
        await log_alert(violation.db_id, self.handler_type, True)
        return True


async def send_test_email() -> tuple[bool, str]:
    """Used by the Settings page. Returns (ok, human readable message)."""
    if not is_email_configured():
        return False, "Email is not configured: fill in sender, app password and recipient."
    message = MIMEMultipart()
    message["From"] = settings.SENDER_EMAIL
    message["To"] = settings.RECEIVER_EMAIL
    message["Subject"] = "PPE Safety Monitor - test email"
    message.attach(MIMEText("This is a test email from the PPE Safety Monitor.", "plain"))
    try:
        await _deliver(message)
    except Exception as exc:
        return False, f"Sending failed: {exc}"
    return True, f"Test email sent to {settings.RECEIVER_EMAIL}"
