from __future__ import annotations

import csv
import io
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import String, cast, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import screenshots
from app.core.violation_types import LABELS, missing_items
from app.db.models import AlertLog, Camera, Violation
from app.db.session import get_db
from app.schemas.violation import (
    ViolationDetailResponse,
    ViolationListResponse,
    ViolationResponse,
)

router = APIRouter(prefix="/violations", tags=["violations"])


def to_response(v: Violation, camera_name: Optional[str] = None) -> ViolationResponse:
    url = screenshots.frame_url(v.frame_path)  # None if the file is gone
    return ViolationResponse(
        id=v.id,
        camera_id=v.camera_id,
        camera_name=camera_name,
        violation_type=v.violation_type,
        label=LABELS.get(v.violation_type, v.violation_type),
        missing_items=missing_items(v.violation_type),
        confidence=v.confidence,
        timestamp=v.timestamp,
        frame_path=v.frame_path,
        track_id=v.track_id,
        session_id=v.session_id,
        frame_url=url,
        screenshot_available=url is not None,
    )


def _filtered(
    camera_id: Optional[int],
    violation_type: Optional[str],
    worker_id: Optional[int],
    session_id: Optional[str],
    search: Optional[str],
    from_dt: Optional[datetime],
    to_dt: Optional[datetime],
):
    q = (
        select(Violation, Camera.name)
        .join(Camera, Camera.id == Violation.camera_id, isouter=True)
        .order_by(Violation.timestamp.desc(), Violation.id.desc())
    )
    if camera_id is not None:
        q = q.where(Violation.camera_id == camera_id)
    if violation_type:
        q = q.where(Violation.violation_type == violation_type)
    if worker_id is not None:
        q = q.where(Violation.track_id == worker_id)
    if session_id:
        q = q.where(Violation.session_id == session_id)
    if from_dt is not None:
        q = q.where(Violation.timestamp >= from_dt)
    if to_dt is not None:
        q = q.where(Violation.timestamp <= to_dt)
    if search and search.strip():
        term = search.strip().lstrip("#")
        conds = [
            Camera.name.ilike(f"%{term}%"),
            Violation.violation_type.ilike(f"%{term}%"),
            cast(Violation.timestamp, String).like(f"%{term}%"),
        ]
        if term.isdigit():
            conds += [Violation.id == int(term), Violation.track_id == int(term)]
        q = q.where(or_(*conds))
    return q


@router.get("", response_model=ViolationListResponse)
async def list_violations(
    camera_id: Optional[int] = Query(None),
    violation_type: Optional[str] = Query(None),
    worker_id: Optional[int] = Query(None, description="Tracking ID of the worker"),
    session_id: Optional[str] = Query(None),
    search: Optional[str] = Query(None, description="Matches ID, worker, camera name, type, date"),
    from_dt: Optional[datetime] = Query(None, alias="from"),
    to_dt: Optional[datetime] = Query(None, alias="to"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
):
    q = _filtered(camera_id, violation_type, worker_id, session_id, search, from_dt, to_dt)
    total = (await db.execute(select(func.count()).select_from(q.order_by(None).subquery()))).scalar_one()
    rows = (await db.execute(q.offset((page - 1) * page_size).limit(page_size))).all()
    return ViolationListResponse(
        total=total,
        page=page,
        page_size=page_size,
        items=[to_response(v, name) for v, name in rows],
    )


@router.get("/export")
async def export_violations(
    camera_id: Optional[int] = Query(None),
    violation_type: Optional[str] = Query(None),
    worker_id: Optional[int] = Query(None),
    search: Optional[str] = Query(None),
    from_dt: Optional[datetime] = Query(None, alias="from"),
    to_dt: Optional[datetime] = Query(None, alias="to"),
    db: AsyncSession = Depends(get_db),
):
    q = _filtered(camera_id, violation_type, worker_id, None, search, from_dt, to_dt)
    rows = (await db.execute(q)).all()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(
        ["id", "camera_id", "track_id", "violation_type", "confidence", "timestamp", "frame_path",
         "camera_name", "missing_items", "session_id"]
    )
    for v, name in rows:
        writer.writerow(
            [v.id, v.camera_id, v.track_id, v.violation_type, v.confidence, v.timestamp,
             v.frame_path, name or "", " + ".join(missing_items(v.violation_type)), v.session_id or ""]
        )

    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=violations.csv"},
    )


@router.get("/{violation_id}", response_model=ViolationDetailResponse)
async def get_violation(
    violation_id: int,
    db: AsyncSession = Depends(get_db),
):
    v = await db.get(Violation, violation_id)
    if v is None:
        raise HTTPException(status_code=404, detail="Violation not found")
    cam = await db.get(Camera, v.camera_id)
    logs = (
        await db.execute(
            select(AlertLog).where(AlertLog.violation_id == v.id).order_by(AlertLog.id)
        )
    ).scalars().all()
    base = to_response(v, cam.name if cam else None)
    return ViolationDetailResponse(**base.model_dump(), alerts=logs)
