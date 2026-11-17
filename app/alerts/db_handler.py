from __future__ import annotations

from datetime import datetime
from typing import Optional

from app.alerts.base import AlertHandler
from app.core.logging import get_logger
from app.core.violation_checker import ViolationEvent

logger = get_logger(__name__)


async def log_alert(
    violation_id: Optional[int], handler_type: str, success: bool, error: Optional[str] = None
) -> None:
    """Record the outcome of an alert channel (email, webhook...) in alert_log."""
    if violation_id is None:
        return
    try:
        from app.db.models import AlertLog
        from app.db.session import AsyncSessionLocal

        async with AsyncSessionLocal() as session:
            session.add(
                AlertLog(
                    violation_id=violation_id,
                    handler_type=handler_type,
                    success=success,
                    error_msg=error[:1000] if error else None,
                )
            )
            await session.commit()
    except Exception as exc:  # never let logging break detection
        logger.error("Could not write alert_log: %s", exc)


class DatabaseHandler(AlertHandler):
    handler_type = "db"

    async def send(self, violation: ViolationEvent) -> bool:
        try:
            from app.db.models import AlertLog, Camera, Violation
            from app.db.session import AsyncSessionLocal

            async with AsyncSessionLocal() as session:
                db_violation = Violation(
                    camera_id=violation.camera_id,
                    violation_type=violation.violation_type,
                    confidence=violation.confidence,
                    frame_path=violation.frame_path,
                    track_id=violation.track_id,
                    session_id=violation.session_id,
                    timestamp=datetime.now(),
                )
                session.add(db_violation)
                await session.flush()  # get db_violation.id

                session.add(
                    AlertLog(
                        violation_id=db_violation.id,
                        handler_type=self.handler_type,
                        success=True,
                    )
                )
                camera = await session.get(Camera, violation.camera_id)
                await session.commit()

            violation.db_id = db_violation.id
            violation.timestamp = db_violation.timestamp
            violation.camera_name = camera.name if camera else f"Camera {violation.camera_id}"
            logger.info(
                "Violation #%d saved: camera=%d worker=%s type=%s",
                db_violation.id, violation.camera_id, violation.track_id, violation.violation_type,
            )
            return True
        except Exception as exc:
            logger.error("Failed to save violation to DB: %s", exc)
            return False
