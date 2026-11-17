from __future__ import annotations

import csv
import io
from datetime import date, datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_camera_manager
from app.core.violation_types import LABELS, missing_items
from app.db.models import Camera, Violation
from app.db.session import get_db
from app.services import reports

router = APIRouter(tags=["reports"])


def _parse_month(month: str) -> tuple[int, int]:
    try:
        d = datetime.strptime(month, "%Y-%m")
    except ValueError:
        raise HTTPException(status_code=422, detail="month must look like 2026-11")
    return d.year, d.month


def _csv_response(rows: list[list], filename: str) -> StreamingResponse:
    out = io.StringIO()
    csv.writer(out).writerows(rows)
    return StreamingResponse(
        iter([out.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@router.get("/overview")
async def overview(request: Request, db: AsyncSession = Depends(get_db)):
    """Everything the Dashboard page needs, in one call."""
    data = await reports.overview(db)
    cams = (await db.execute(select(Camera))).scalars().all()
    manager = get_camera_manager(request)
    data["cameras"] = [
        {"id": c.id, "name": c.name, "source_type": c.source_type, "status": manager.status(c.id)}
        for c in cams
    ]
    return data


@router.get("/reports/daily")
async def daily_report(
    day: Optional[date] = Query(None, alias="date"), db: AsyncSession = Depends(get_db)
):
    return await reports.daily_report(db, day or date.today())


@router.get("/reports/monthly")
async def monthly_report(
    month: Optional[str] = Query(None, description="YYYY-MM"), db: AsyncSession = Depends(get_db)
):
    year, mon = _parse_month(month) if month else (date.today().year, date.today().month)
    return await reports.monthly_report(db, year, mon)


@router.get("/reports/daily/export")
async def export_daily(
    day: Optional[date] = Query(None, alias="date"), db: AsyncSession = Depends(get_db)
):
    d = day or date.today()
    report = await reports.daily_report(db, d)
    start, end = reports.day_bounds(d)
    rows = [
        ["Daily safety report", d.isoformat()],
        ["Workers detected (tracking IDs)", report["workers_detected"]],
        ["Compliant workers", report["compliant_workers"]],
        ["Compliance %", "" if report["compliance_pct"] is None else report["compliance_pct"]],
        ["Helmet violations", report["helmet_violations"]],
        ["Vest violations", report["vest_violations"]],
        ["Combined violations", report["combined_violations"]],
        ["Total incidents", report["total_incidents"]],
        [],
        ["id", "time", "camera", "worker_id", "violation", "missing", "confidence"],
    ]
    q = (
        select(Violation, Camera.name)
        .join(Camera, Camera.id == Violation.camera_id, isouter=True)
        .where(Violation.timestamp >= start, Violation.timestamp < end)
        .order_by(Violation.timestamp)
    )
    for v, name in (await db.execute(q)).all():
        rows.append([
            v.id, v.timestamp, name or v.camera_id, v.track_id if v.track_id is not None else "",
            LABELS.get(v.violation_type, v.violation_type),
            " + ".join(missing_items(v.violation_type)), f"{v.confidence:.2f}",
        ])
    return _csv_response(rows, f"daily-report-{d.isoformat()}.csv")


@router.get("/reports/monthly/export")
async def export_monthly(
    month: Optional[str] = Query(None, description="YYYY-MM"), db: AsyncSession = Depends(get_db)
):
    year, mon = _parse_month(month) if month else (date.today().year, date.today().month)
    report = await reports.monthly_report(db, year, mon)
    rows = [
        ["Monthly safety report", report["month"]],
        ["Total violations", report["total_violations"]],
        ["Most frequent violation",
         LABELS.get(report["most_frequent_type"], "none recorded")
         if report["most_frequent_type"] else "none recorded"],
        ["Workers detected (tracking IDs)", report["workers_detected"]],
        ["Compliance %", "" if report["compliance_pct"] is None else report["compliance_pct"]],
        [],
        ["date", "helmet", "vest", "combined", "total"],
    ]
    for d in report["daily"]:
        rows.append([d["date"], d["helmet"], d["vest"], d["combined"], d["total"]])
    rows += [[], ["camera", "helmet", "vest", "combined", "total"]]
    for c in report["by_camera"]:
        rows.append([c["camera_name"], c["helmet"], c["vest"], c["combined"], c["total"]])
    return _csv_response(rows, f"monthly-report-{report['month']}.csv")
