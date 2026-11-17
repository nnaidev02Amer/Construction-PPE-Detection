"""Statistics computed from real database rows (no estimates, no sample data)."""
from __future__ import annotations

from datetime import date, datetime, time, timedelta
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.violation_types import ALL_TYPES, COMBINED, HELMET, VEST
from app.db.models import Camera, Violation, WorkerSighting

COMPLIANCE_NOTE = (
    "Compliance % = workers tracked in the period with no recorded incident / all workers "
    "tracked in the period. A 'worker' is a tracking ID within one camera session, so the same "
    "person can be counted more than once if the camera is restarted or they leave the frame."
)


def day_bounds(d: date) -> tuple[datetime, datetime]:
    start = datetime.combine(d, time.min)
    return start, start + timedelta(days=1)


def month_bounds(year: int, month: int) -> tuple[datetime, datetime]:
    start = datetime(year, month, 1)
    end = datetime(year + 1, 1, 1) if month == 12 else datetime(year, month + 1, 1)
    return start, end


def _empty_counts() -> dict:
    return {"helmet": 0, "vest": 0, "combined": 0, "total": 0}


def _bucket(vtype: str) -> Optional[str]:
    return {HELMET: "helmet", VEST: "vest", COMBINED: "combined"}.get(vtype)


async def type_counts(db: AsyncSession, start: datetime, end: datetime) -> dict:
    rows = (
        await db.execute(
            select(Violation.violation_type, func.count())
            .where(Violation.timestamp >= start, Violation.timestamp < end)
            .group_by(Violation.violation_type)
        )
    ).all()
    out = _empty_counts()
    for vtype, n in rows:
        key = _bucket(vtype)
        if key:
            out[key] += n
        out["total"] += n
    return out


async def worker_stats(db: AsyncSession, start: datetime, end: datetime) -> dict:
    """Workers tracked in the window, and how many of them had no recorded incident."""
    sighted = {
        tuple(r)
        for r in (
            await db.execute(
                select(WorkerSighting.camera_id, WorkerSighting.session_id, WorkerSighting.track_id)
                .where(WorkerSighting.first_seen >= start, WorkerSighting.first_seen < end)
            )
        ).all()
    }
    offenders = {
        tuple(r)
        for r in (
            await db.execute(
                select(Violation.camera_id, Violation.session_id, Violation.track_id)
                .where(
                    Violation.timestamp >= start,
                    Violation.timestamp < end,
                    Violation.track_id.is_not(None),
                )
                .distinct()
            )
        ).all()
    }
    with_incident = len(sighted & offenders)
    detected = len(sighted)
    compliant = detected - with_incident
    return {
        "workers_detected": detected,
        "workers_with_incidents": with_incident,
        "compliant_workers": compliant,
        # None (not 0) when nobody was tracked: the denominator would be zero
        "compliance_pct": round(compliant / detected * 100, 1) if detected else None,
    }


async def by_camera(db: AsyncSession, start: datetime, end: datetime) -> list[dict]:
    rows = (
        await db.execute(
            select(Violation.camera_id, Camera.name, Violation.violation_type, func.count())
            .join(Camera, Camera.id == Violation.camera_id, isouter=True)
            .where(Violation.timestamp >= start, Violation.timestamp < end)
            .group_by(Violation.camera_id, Camera.name, Violation.violation_type)
        )
    ).all()
    cams: dict[int, dict] = {}
    for cam_id, name, vtype, n in rows:
        c = cams.setdefault(
            cam_id, {"camera_id": cam_id, "camera_name": name or f"Camera {cam_id}", **_empty_counts()}
        )
        key = _bucket(vtype)
        if key:
            c[key] += n
        c["total"] += n
    return sorted(cams.values(), key=lambda c: -c["total"])


async def daily_series(db: AsyncSession, first_day: date, days: int) -> list[dict]:
    """Per-day counts for ``days`` days from first_day, zero-filled."""
    start = datetime.combine(first_day, time.min)
    end = start + timedelta(days=days)
    rows = (
        await db.execute(
            select(func.date(Violation.timestamp), Violation.violation_type, func.count())
            .where(Violation.timestamp >= start, Violation.timestamp < end)
            .group_by(func.date(Violation.timestamp), Violation.violation_type)
        )
    ).all()
    series = {
        (first_day + timedelta(days=i)).isoformat(): _empty_counts() for i in range(days)
    }
    for day, vtype, n in rows:
        bucket = series.get(str(day))
        if bucket is None:
            continue
        key = _bucket(vtype)
        if key:
            bucket[key] += n
        bucket["total"] += n
    return [{"date": d, **c} for d, c in series.items()]


async def daily_report(db: AsyncSession, d: date) -> dict:
    start, end = day_bounds(d)
    counts = await type_counts(db, start, end)
    hours = [0] * 24
    for (ts,) in (
        await db.execute(
            select(Violation.timestamp).where(Violation.timestamp >= start, Violation.timestamp < end)
        )
    ).all():
        hours[ts.hour] += 1
    return {
        "date": d.isoformat(),
        "helmet_violations": counts["helmet"],
        "vest_violations": counts["vest"],
        "combined_violations": counts["combined"],
        "total_incidents": counts["total"],
        **await worker_stats(db, start, end),
        "by_hour": hours,
        "by_camera": await by_camera(db, start, end),
        "note": COMPLIANCE_NOTE,
    }


async def monthly_report(db: AsyncSession, year: int, month: int) -> dict:
    start, end = month_bounds(year, month)
    counts = await type_counts(db, start, end)
    days = (end - start).days
    daily = await daily_series(db, start.date(), days)
    ranking = [(counts["helmet"], HELMET), (counts["vest"], VEST), (counts["combined"], COMBINED)]
    top_n, top_type = max(ranking)
    return {
        "month": f"{year:04d}-{month:02d}",
        "total_violations": counts["total"],
        "by_type": {HELMET: counts["helmet"], VEST: counts["vest"], COMBINED: counts["combined"]},
        "most_frequent_type": top_type if top_n > 0 else None,
        "daily": daily,
        "by_camera": await by_camera(db, start, end),
        **await worker_stats(db, start, end),
        "note": COMPLIANCE_NOTE,
    }


async def overview(db: AsyncSession, today: Optional[date] = None, trend_days: int = 7) -> dict:
    """Numbers for the Dashboard page."""
    today = today or date.today()
    report = await daily_report(db, today)
    first = today - timedelta(days=trend_days - 1)
    trend = await daily_series(db, first, trend_days)
    distribution = {
        HELMET: sum(d["helmet"] for d in trend),
        VEST: sum(d["vest"] for d in trend),
        COMBINED: sum(d["combined"] for d in trend),
    }
    return {"today": report, "trend": trend, "distribution": distribution, "trend_days": trend_days}


__all__ = [
    "ALL_TYPES", "day_bounds", "month_bounds", "type_counts", "worker_stats", "by_camera",
    "daily_series", "daily_report", "monthly_report", "overview",
]
