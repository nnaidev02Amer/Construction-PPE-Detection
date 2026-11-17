from __future__ import annotations

from datetime import date, datetime

import pytest

from app.core.violation_types import COMBINED, HELMET, VEST
from app.db.models import Camera, Violation, WorkerSighting
from app.services import reports

DAY = date(2026, 11, 17)


def at(day: date, hour: int) -> datetime:
    return datetime(day.year, day.month, day.day, hour, 30)


async def seed(db):
    cam = Camera(name="Gate", source_type="webcam", source_uri="0")
    cam2 = Camera(name="Yard", source_type="file", source_uri="x.mp4")
    db.add_all([cam, cam2])
    await db.commit()
    S = "2026-11-17 09:00:00"
    # 4 workers on camera 1 today, 1 on camera 2
    for t in (1, 2, 3, 4):
        db.add(WorkerSighting(camera_id=cam.id, session_id=S, track_id=t, first_seen=at(DAY, 9)))
    db.add(WorkerSighting(camera_id=cam2.id, session_id=S, track_id=1, first_seen=at(DAY, 9)))
    rows = [
        (cam.id, 1, HELMET, at(DAY, 9)),
        (cam.id, 1, HELMET, at(DAY, 10)),  # same worker again
        (cam.id, 2, VEST, at(DAY, 10)),
        (cam.id, 3, COMBINED, at(DAY, 11)),
        (cam2.id, 1, VEST, at(date(2026, 11, 2), 8)),  # earlier in the month, other day
    ]
    for cam_id, track, vtype, ts in rows:
        db.add(Violation(camera_id=cam_id, track_id=track, violation_type=vtype,
                         confidence=0.9, timestamp=ts, session_id=S))
    await db.commit()
    return cam, cam2


async def test_daily_report_counts_real_rows(db_session):
    await seed(db_session)
    r = await reports.daily_report(db_session, DAY)
    assert r["helmet_violations"] == 2
    assert r["vest_violations"] == 1
    assert r["combined_violations"] == 1
    assert r["total_incidents"] == 4
    assert r["workers_detected"] == 5
    assert r["workers_with_incidents"] == 3  # workers 1, 2, 3 on camera 1
    assert r["compliant_workers"] == 2
    assert r["compliance_pct"] == 40.0
    assert r["by_hour"][9] == 1 and r["by_hour"][10] == 2 and r["by_hour"][11] == 1
    assert {c["camera_name"] for c in r["by_camera"]} == {"Gate"}


async def test_daily_report_empty_day_has_no_fake_compliance(db_session):
    await seed(db_session)
    r = await reports.daily_report(db_session, date(2026, 1, 1))
    assert r["total_incidents"] == 0
    assert r["workers_detected"] == 0
    assert r["compliance_pct"] is None  # zero denominator, not 0% or 100%


async def test_monthly_report(db_session):
    await seed(db_session)
    r = await reports.monthly_report(db_session, 2026, 11)
    assert r["total_violations"] == 5
    assert r["by_type"] == {HELMET: 2, VEST: 2, COMBINED: 1}
    assert r["most_frequent_type"] in (HELMET, VEST)  # tie
    assert len(r["daily"]) == 30
    by_date = {d["date"]: d for d in r["daily"]}
    assert by_date["2026-11-17"]["total"] == 4
    assert by_date["2026-11-02"]["vest"] == 1
    assert by_date["2026-11-05"]["total"] == 0  # zero-filled day
    assert {c["camera_name"]: c["total"] for c in r["by_camera"]} == {"Gate": 4, "Yard": 1}


async def test_monthly_report_empty(db_session):
    r = await reports.monthly_report(db_session, 2025, 12)
    assert r["total_violations"] == 0
    assert r["most_frequent_type"] is None
    assert len(r["daily"]) == 31


async def test_daily_api_and_csv(test_client, db_session):
    await seed(db_session)
    r = await test_client.get("/api/v1/reports/daily", params={"date": "2026-11-17"})
    assert r.status_code == 200
    assert r.json()["total_incidents"] == 4

    csv = await test_client.get("/api/v1/reports/daily/export", params={"date": "2026-11-17"})
    assert csv.status_code == 200
    assert "text/csv" in csv.headers["content-type"]
    assert "Total incidents,4" in csv.text
    assert "Missing helmet + vest" in csv.text


async def test_monthly_api_and_csv(test_client, db_session):
    await seed(db_session)
    r = await test_client.get("/api/v1/reports/monthly", params={"month": "2026-11"})
    assert r.status_code == 200
    assert r.json()["total_violations"] == 5
    csv = await test_client.get("/api/v1/reports/monthly/export", params={"month": "2026-11"})
    assert "2026-11-17,2,1,1,4" in csv.text
    bad = await test_client.get("/api/v1/reports/monthly", params={"month": "nonsense"})
    assert bad.status_code == 422


async def test_overview_api(test_client, db_session):
    r = await test_client.get("/api/v1/overview")
    assert r.status_code == 200
    data = r.json()
    assert len(data["trend"]) == 7
    assert set(data["distribution"]) == {HELMET, VEST, COMBINED}
    assert data["cameras"] == []


async def test_workers_list_and_history(test_client, db_session):
    cam, _ = await seed(db_session)
    r = await test_client.get("/api/v1/workers", params={"camera_id": cam.id})
    assert r.status_code == 200
    workers = {w["track_id"]: w for w in r.json()}
    assert workers[1]["total_violations"] == 2 and workers[1]["helmet_violations"] == 2
    assert workers[2]["vest_violations"] == 1
    assert workers[3]["combined_violations"] == 1
    assert workers[4]["total_violations"] == 0  # tracked, never violated

    only = await test_client.get("/api/v1/workers", params={"only_with_violations": True,
                                                            "camera_id": cam.id})
    assert {w["track_id"] for w in only.json()} == {1, 2, 3}

    h = await test_client.get("/api/v1/workers/history", params={
        "camera_id": cam.id, "track_id": 1, "session_id": "2026-11-17 09:00:00"})
    assert h.status_code == 200
    assert h.json()["total_violations"] == 2
    assert len(h.json()["violations"]) == 2


async def test_violation_filters(test_client, db_session):
    cam, _ = await seed(db_session)
    r = await test_client.get("/api/v1/violations", params={"violation_type": VEST})
    assert r.json()["total"] == 2
    r = await test_client.get("/api/v1/violations", params={"worker_id": 3})
    assert r.json()["items"][0]["violation_type"] == COMBINED
    assert r.json()["items"][0]["camera_name"] == "Gate"
    r = await test_client.get("/api/v1/violations", params={"from": "2026-11-17T00:00:00",
                                                            "to": "2026-11-17T23:59:59"})
    assert r.json()["total"] == 4
    r = await test_client.get("/api/v1/violations", params={"search": "yard"})
    assert r.json()["total"] == 1


async def test_screenshot_unavailable_is_handled(test_client, db_session, tmp_path, monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "FRAMES_DIR", str(tmp_path))
    cam = Camera(name="C", source_type="webcam", source_uri="0")
    db_session.add(cam)
    await db_session.commit()
    (tmp_path / "2026-11-17" / "camera_1").mkdir(parents=True)
    (tmp_path / "2026-11-17" / "camera_1" / "ok.jpg").write_bytes(b"\xff\xd8jpeg")
    for path in ("2026-11-17/camera_1/ok.jpg", "2026-11-17/camera_1/missing.jpg", None,
                 "violation_frames\\camera_1\\legacy.jpg"):
        db_session.add(Violation(camera_id=cam.id, violation_type=HELMET, confidence=0.5,
                                 frame_path=path, timestamp=at(DAY, 9)))
    await db_session.commit()

    items = (await test_client.get("/api/v1/violations")).json()["items"]
    by_path = {i["frame_path"]: i for i in items}
    assert by_path["2026-11-17/camera_1/ok.jpg"]["screenshot_available"] is True
    assert by_path["2026-11-17/camera_1/ok.jpg"]["frame_url"] == "/frames/2026-11-17/camera_1/ok.jpg"
    for p in ("2026-11-17/camera_1/missing.jpg", None, "violation_frames\\camera_1\\legacy.jpg"):
        assert by_path[p]["screenshot_available"] is False
        assert by_path[p]["frame_url"] is None


async def test_violation_detail_includes_alert_log(test_client, db_session):
    from app.db.models import AlertLog

    cam, _ = await seed(db_session)
    v = (await test_client.get("/api/v1/violations")).json()["items"][0]
    db_session.add(AlertLog(violation_id=v["id"], handler_type="email", success=False,
                            error_msg="SMTP down"))
    await db_session.commit()
    d = (await test_client.get(f"/api/v1/violations/{v['id']}")).json()
    assert d["alerts"][0]["handler_type"] == "email"
    assert d["alerts"][0]["error_msg"] == "SMTP down"
    assert d["missing_items"]
