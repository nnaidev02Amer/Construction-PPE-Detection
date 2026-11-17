"""Settings editable from the dashboard. Saved in the app_settings table, override .env."""
from __future__ import annotations

from typing import Any

from sqlalchemy import select

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)

# name -> python type. Everything else (model path, database URL...) stays .env-only.
EDITABLE: dict[str, type] = {
    "DETECTION_CONFIDENCE": float,
    "PPE_ITEM_CONFIDENCE": float,
    "VIOLATION_PERSIST_SECONDS": float,
    "ALERT_COOLDOWN_SECONDS": int,
    "EMAIL_ENABLED": bool,
    "EMAIL_NOTIFY_HELMET": bool,
    "EMAIL_NOTIFY_VEST": bool,
    "EMAIL_NOTIFY_COMBINED": bool,
    "SMTP_HOST": str,
    "SMTP_PORT": int,
    "SENDER_EMAIL": str,
    "RECEIVER_EMAIL": str,
    "EMAIL_PASSWORD": str,  # write-only: never returned by the API
}


def _cast(kind: type, raw: str) -> Any:
    if kind is bool:
        return raw.lower() in {"1", "true", "yes", "on"}
    return kind(raw)


async def load_overrides(session_factory=None) -> None:
    from app.db.models import AppSetting
    from app.db.session import AsyncSessionLocal

    factory = session_factory or AsyncSessionLocal
    async with factory() as session:
        rows = (await session.execute(select(AppSetting))).scalars().all()
    for row in rows:
        kind = EDITABLE.get(row.key)
        if kind is None:
            continue
        try:
            setattr(settings, row.key, _cast(kind, row.value))
        except ValueError:
            logger.warning("Ignoring invalid saved setting %s=%r", row.key, row.value)


async def save_overrides(values: dict[str, Any], session) -> None:
    from app.db.models import AppSetting

    for key, value in values.items():
        if key not in EDITABLE:
            continue
        setattr(settings, key, value)
        raw = str(value).lower() if isinstance(value, bool) else str(value)
        existing = await session.get(AppSetting, key)
        if existing is None:
            session.add(AppSetting(key=key, value=raw))
        else:
            existing.value = raw
    await session.commit()


def apply_to_runtime(app) -> None:
    """Push changed values into the live detector and violation checker."""
    detector = getattr(app.state, "detector", None)
    if detector is not None:
        detector.confidence = settings.DETECTION_CONFIDENCE
        detector.ppe_confidence = settings.PPE_ITEM_CONFIDENCE
    manager = getattr(app.state, "camera_manager", None)
    if manager is not None and hasattr(manager, "apply_settings"):
        manager.apply_settings()
