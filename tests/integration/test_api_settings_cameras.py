from __future__ import annotations

import pytest

from app.core.config import settings
from app.db.models import Camera, Violation

SETTING_KEYS = [
    "DETECTION_CONFIDENCE", "PPE_ITEM_CONFIDENCE", "VIOLATION_PERSIST_SECONDS", "ALERT_COOLDOWN_SECONDS",
    "EMAIL_ENABLED", "EMAIL_NOTIFY_HELMET", "EMAIL_NOTIFY_VEST", "EMAIL_NOTIFY_COMBINED",
    "SMTP_HOST", "SMTP_PORT", "SENDER_EMAIL", "RECEIVER_EMAIL", "EMAIL_PASSWORD",
]


@pytest.fixture(autouse=True)
def restore_settings():
    saved = {k: getattr(settings, k) for k in SETTING_KEYS}
    yield
    for k, v in saved.items():
        setattr(settings, k, v)


async def test_settings_roundtrip_and_never_returns_password(test_client):
    r = await test_client.put("/api/v1/settings", json={
        "detection_confidence": 0.4,
        "violation_persist_seconds": 2.5,
        "alert_cooldown_seconds": 20,
        "sender_email": "a@example.com",
        "receiver_email": "b@example.com",
        "email_password": "super-secret",
    })
    assert r.status_code == 200
    body = r.json()
    assert body["detection_confidence"] == 0.4
    assert body["email_password_set"] is True
    assert "super-secret" not in r.text
    assert settings.VIOLATION_PERSIST_SECONDS == 2.5  # applied at runtime
    assert "super-secret" not in (await test_client.get("/api/v1/settings")).text


async def test_blank_password_keeps_existing(test_client):
    settings.EMAIL_PASSWORD = "keep-me"
    await test_client.put("/api/v1/settings", json={"email_password": ""})
    assert settings.EMAIL_PASSWORD == "keep-me"


async def test_settings_validation(test_client):
    assert (await test_client.put("/api/v1/settings", json={"detection_confidence": 5})).status_code == 422
    assert (await test_client.put("/api/v1/settings", json={"sender_email": "nope"})).status_code == 422


async def test_settings_persist_across_restart(test_client, db_session):
    from app.core import runtime_settings

    await test_client.put("/api/v1/settings", json={"alert_cooldown_seconds": 77})
    settings.ALERT_COOLDOWN_SECONDS = 1

    class Factory:  # reuse the in-memory session
        def __call__(self):
            return self

        async def __aenter__(self):
            return db_session

        async def __aexit__(self, *a):
            return False

    await runtime_settings.load_overrides(Factory())
    assert settings.ALERT_COOLDOWN_SECONDS == 77


async def test_test_email_not_configured(test_client):
    settings.SENDER_EMAIL, settings.EMAIL_PASSWORD = "your_email@gmail.com", ""
    r = await test_client.post("/api/v1/settings/test-email")
    assert r.status_code == 200
    assert r.json()["ok"] is False
    assert "not configured" in r.json()["message"]


async def test_test_email_delivery_failure(test_client, monkeypatch):
    settings.SENDER_EMAIL, settings.RECEIVER_EMAIL = "me@example.com", "you@example.com"
    settings.EMAIL_PASSWORD = "pw"

    async def boom(*a, **k):
        raise ConnectionRefusedError("smtp unreachable")

    monkeypatch.setattr("app.alerts.email_handler.aiosmtplib.send", boom)
    r = await test_client.post("/api/v1/settings/test-email")
    assert r.json()["ok"] is False
    assert "smtp unreachable" in r.json()["message"]


async def test_webcam_camera_needs_numeric_index(test_client):
    bad = await test_client.post("/api/v1/cameras", json={
        "name": "x", "source_type": "webcam", "source_uri": "kjkj"})
    assert bad.status_code == 422
    ok = await test_client.post("/api/v1/cameras", json={
        "name": "Laptop", "source_type": "webcam", "source_uri": "0"})
    assert ok.status_code == 201
    assert ok.json()["status"] == "stopped"
    rtsp = await test_client.post("/api/v1/cameras", json={
        "name": "IP", "source_type": "rtsp", "source_uri": "rtsp://10.0.0.5/stream"})
    assert rtsp.status_code == 201


async def test_update_camera_rejects_bad_webcam_uri(test_client, db_session):
    cam = Camera(name="L", source_type="webcam", source_uri="0")
    db_session.add(cam)
    await db_session.commit()
    assert (await test_client.put(f"/api/v1/cameras/{cam.id}", json={"source_uri": "abc"})).status_code == 422
    r = await test_client.put(f"/api/v1/cameras/{cam.id}", json={"source_uri": "1", "name": "Renamed"})
    assert r.json()["source_uri"] == "1" and r.json()["name"] == "Renamed"


async def test_start_unavailable_camera_returns_clear_error(test_client, db_session):
    cam = Camera(name="L", source_type="webcam", source_uri="9")
    db_session.add(cam)
    await db_session.commit()
    test_client._transport.app.state.camera_manager.start_camera.return_value = False
    r = await test_client.post(f"/api/v1/cameras/{cam.id}/start")
    assert r.status_code == 400
    assert "Could not start camera" in r.json()["detail"]


async def test_delete_camera_with_history_needs_confirmation(test_client, db_session):
    cam = Camera(name="L", source_type="webcam", source_uri="0")
    db_session.add(cam)
    await db_session.commit()
    db_session.add(Violation(camera_id=cam.id, violation_type="NO-Hardhat", confidence=0.9))
    await db_session.commit()
    assert (await test_client.delete(f"/api/v1/cameras/{cam.id}")).status_code == 409
    assert (await test_client.delete(f"/api/v1/cameras/{cam.id}?delete_history=true")).status_code == 204
    assert (await test_client.get("/api/v1/violations")).json()["total"] == 0
