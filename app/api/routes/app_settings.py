from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.alerts.email_handler import is_email_configured, send_test_email
from app.core import runtime_settings
from app.core.config import settings
from app.db.session import get_db

router = APIRouter(prefix="/settings", tags=["settings"])


class SettingsUpdate(BaseModel):
    detection_confidence: Optional[float] = Field(None, ge=0.05, le=0.95)
    ppe_item_confidence: Optional[float] = Field(None, ge=0.05, le=0.95)
    violation_persist_seconds: Optional[float] = Field(None, ge=0, le=60)
    alert_cooldown_seconds: Optional[int] = Field(None, ge=0, le=3600)
    email_enabled: Optional[bool] = None
    email_notify_helmet: Optional[bool] = None
    email_notify_vest: Optional[bool] = None
    email_notify_combined: Optional[bool] = None
    smtp_host: Optional[str] = Field(None, max_length=200)
    smtp_port: Optional[int] = Field(None, ge=1, le=65535)
    sender_email: Optional[str] = Field(None, max_length=200)
    receiver_email: Optional[str] = Field(None, max_length=200)
    email_password: Optional[str] = Field(None, max_length=200)  # write-only


def _current() -> dict:
    return {
        "detection_confidence": settings.DETECTION_CONFIDENCE,
        "ppe_item_confidence": settings.PPE_ITEM_CONFIDENCE,
        "violation_persist_seconds": settings.VIOLATION_PERSIST_SECONDS,
        "alert_cooldown_seconds": settings.ALERT_COOLDOWN_SECONDS,
        "email_enabled": settings.EMAIL_ENABLED,
        "email_notify_helmet": settings.EMAIL_NOTIFY_HELMET,
        "email_notify_vest": settings.EMAIL_NOTIFY_VEST,
        "email_notify_combined": settings.EMAIL_NOTIFY_COMBINED,
        "smtp_host": settings.SMTP_HOST,
        "smtp_port": settings.SMTP_PORT,
        "sender_email": settings.SENDER_EMAIL,
        "receiver_email": settings.RECEIVER_EMAIL,
        # The password itself is never sent back to the browser
        "email_password_set": bool(settings.EMAIL_PASSWORD),
        "email_configured": is_email_configured(),
    }


@router.get("")
async def get_settings():
    return _current()


@router.put("")
async def update_settings(
    body: SettingsUpdate, request: Request, db: AsyncSession = Depends(get_db)
):
    values = body.model_dump(exclude_none=True)
    if not values.get("email_password"):
        values.pop("email_password", None)  # blank = keep the existing password
    for key in ("sender_email", "receiver_email"):
        if values.get(key) and "@" not in values[key]:
            raise HTTPException(status_code=422, detail=f"{key} must be an email address")
    await runtime_settings.save_overrides({k.upper(): v for k, v in values.items()}, db)
    runtime_settings.apply_to_runtime(request.app)
    return _current()


@router.post("/test-email")
async def test_email():
    ok, message = await send_test_email()
    return {"ok": ok, "message": message}
