from __future__ import annotations

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.violation_types import COMBINED, HELMET, VEST
from app.db.models import Camera, Violation, WorkerSighting
from app.db.session import get_db

router = APIRouter(prefix="/workers", tags=["workers"])


class WorkerSummary(BaseModel):
    """A tracking ID inside one camera session. NOT a real-world identity."""

    camera_id: int
    camera_name: str
    session_id: Optional[str]
    track_id: int
    total_violations: int = 0
    helmet_violations: int = 0
    vest_violations: int = 0
    combined_violations: int = 0
    first_seen: Optional[datetime] = None
    last_violation: Optional[datetime] = None


@router.get("", response_model=list[WorkerSummary])
async def list_workers(
    camera_id: Optional[int] = Query(None),
    from_dt: Optional[datetime] = Query(None, alias="from"),
    to_dt: Optional[datetime] = Query(None, alias="to"),
    only_with_violations: bool = Query(False),
    search: Optional[str] = Query(None, description="Worker ID or camera name"),
    db: AsyncSession = Depends(get_db),
):
    names = {c.id: c.name for c in (await db.execute(select(Camera))).scalars().all()}
    workers: dict[tuple, WorkerSummary] = {}

    def get(cam: int, session: Optional[str], track: int) -> WorkerSummary:
        key = (cam, session, track)
        if key not in workers:
            workers[key] = WorkerSummary(
                camera_id=cam, camera_name=names.get(cam, f"Camera {cam}"),
                session_id=session, track_id=track,
            )
        return workers[key]

    sq = select(WorkerSighting)
    if camera_id is not None:
        sq = sq.where(WorkerSighting.camera_id == camera_id)
    if from_dt:
        sq = sq.where(WorkerSighting.first_seen >= from_dt)
    if to_dt:
        sq = sq.where(WorkerSighting.first_seen <= to_dt)
    for s in (await db.execute(sq)).scalars().all():
        get(s.camera_id, s.session_id, s.track_id).first_seen = s.first_seen

    vq = select(Violation).where(Violation.track_id.is_not(None))
    if camera_id is not None:
        vq = vq.where(Violation.camera_id == camera_id)
    if from_dt:
        vq = vq.where(Violation.timestamp >= from_dt)
    if to_dt:
        vq = vq.where(Violation.timestamp <= to_dt)
    for v in (await db.execute(vq)).scalars().all():
        w = get(v.camera_id, v.session_id, v.track_id)
        w.total_violations += 1
        if v.violation_type == HELMET:
            w.helmet_violations += 1
        elif v.violation_type == VEST:
            w.vest_violations += 1
        elif v.violation_type == COMBINED:
            w.combined_violations += 1
        if w.last_violation is None or v.timestamp > w.last_violation:
            w.last_violation = v.timestamp

    result = list(workers.values())
    if only_with_violations:
        result = [w for w in result if w.total_violations]
    if search and search.strip():
        term = search.strip().lstrip("#").lower()
        result = [w for w in result if term == str(w.track_id) or term in w.camera_name.lower()]
    result.sort(key=lambda w: (w.last_violation or w.first_seen or datetime.min), reverse=True)
    return result


@router.get("/history")
async def worker_history(
    camera_id: int = Query(...),
    track_id: int = Query(...),
    session_id: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    """Violation history of one tracked worker (a tracking ID within one camera session)."""
    q = select(Violation).where(
        Violation.camera_id == camera_id, Violation.track_id == track_id
    )
    q = q.where(Violation.session_id == session_id) if session_id else q.where(
        Violation.session_id.is_(None)
    )
    rows = (await db.execute(q.order_by(Violation.timestamp.desc()))).scalars().all()
    cam = await db.get(Camera, camera_id)
    if cam is None:
        raise HTTPException(status_code=404, detail="Camera not found")
    from app.api.routes.violations import to_response

    return {
        "camera_id": camera_id,
        "camera_name": cam.name,
        "track_id": track_id,
        "session_id": session_id,
        "total_violations": len(rows),
        "helmet_violations": sum(v.violation_type == HELMET for v in rows),
        "vest_violations": sum(v.violation_type == VEST for v in rows),
        "combined_violations": sum(v.violation_type == COMBINED for v in rows),
        "violations": [to_response(v, cam.name) for v in rows],
    }
