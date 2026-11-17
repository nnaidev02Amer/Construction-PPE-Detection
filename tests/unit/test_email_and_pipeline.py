from __future__ import annotations

import asyncio
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

import numpy as np
import pytest

from app.alerts import email_handler
from app.alerts.email_handler import EmailHandler, build_message
from app.camera.manager import CameraManager, _CameraEntry
from app.core import screenshots
from app.core.config import settings
from app.core.events import EventBus
from app.core.violation_checker import ViolationEvent
from app.core.violation_types import COMBINED, HELMET, VEST, classify, missing_items

EMAIL_KEYS = ["EMAIL_ENABLED", "EMAIL_NOTIFY_HELMET", "EMAIL_NOTIFY_VEST", "EMAIL_NOTIFY_COMBINED",
              "SENDER_EMAIL", "RECEIVER_EMAIL", "EMAIL_PASSWORD", "FRAMES_DIR"]


@pytest.fixture(autouse=True)
def restore_settings():
    saved = {k: getattr(settings, k) for k in EMAIL_KEYS}
    yield
    for k, v in saved.items():
        setattr(settings, k, v)


def event(vtype=COMBINED, frame_path=None) -> ViolationEvent:
    return ViolationEvent(camera_id=1, violation_type=vtype, confidence=0.87, track_id=4,
                          frame_path=frame_path, db_id=12, camera_name="Gate",
                          timestamp=datetime(2026, 11, 17, 10, 5, 0))


def configure_email():
    settings.EMAIL_ENABLED = True
    settings.SENDER_EMAIL, settings.RECEIVER_EMAIL = "me@example.com", "boss@example.com"
    settings.EMAIL_PASSWORD = "pw"


def test_classification_and_missing_items():
    assert classify(True, True) is None
    assert classify(False, True) == HELMET
    assert classify(True, False) == VEST
    assert classify(False, False) == COMBINED
    assert missing_items(COMBINED) == ["Hardhat", "Safety Vest"]


async def test_email_not_configured_is_silently_skipped(monkeypatch):
    settings.SENDER_EMAIL, settings.EMAIL_PASSWORD = "your_email@gmail.com", ""
    send = AsyncMock()
    monkeypatch.setattr(email_handler.aiosmtplib, "send", send)
    assert await EmailHandler().send(event()) is True
    send.assert_not_called()


async def test_email_disabled_or_type_switched_off_sends_nothing(monkeypatch):
    configure_email()
    send = AsyncMock()
    monkeypatch.setattr(email_handler.aiosmtplib, "send", send)
    settings.EMAIL_ENABLED = False
    await EmailHandler().send(event())
    settings.EMAIL_ENABLED = True
    settings.EMAIL_NOTIFY_VEST = False
    await EmailHandler().send(event(VEST))
    send.assert_not_called()


async def test_email_success_message_content(monkeypatch, tmp_path):
    configure_email()
    settings.FRAMES_DIR = str(tmp_path)
    (tmp_path / "d").mkdir()
    (tmp_path / "d" / "s.jpg").write_bytes(b"jpg")
    send, log = AsyncMock(), AsyncMock()
    monkeypatch.setattr(email_handler.aiosmtplib, "send", send)
    monkeypatch.setattr(email_handler, "log_alert", log)

    assert await EmailHandler().send(event(frame_path="d/s.jpg")) is True
    msg = send.call_args.args[0]
    assert "CRITICAL" in msg["Subject"] and "Missing helmet + vest" in msg["Subject"]
    assert "#4" in msg["Subject"] and "Gate" in msg["Subject"]
    text = msg.get_payload()[0].get_payload()
    assert "Worker ID : #4" in text and "2026-11-17 10:05:00" in text
    assert len(msg.get_payload()) == 2  # body + screenshot attachment
    log.assert_awaited_with(12, "email", True)


async def test_email_without_screenshot_still_sends():
    configure_email()
    assert len(build_message(event(frame_path="nope/missing.jpg")).get_payload()) == 1


async def test_email_failure_is_logged_not_raised(monkeypatch):
    configure_email()
    monkeypatch.setattr(email_handler.aiosmtplib, "send", AsyncMock(side_effect=OSError("down")))
    log = AsyncMock()
    monkeypatch.setattr(email_handler, "log_alert", log)
    assert await EmailHandler().send(event()) is False  # no exception
    log.assert_awaited_with(12, "email", False, "down")


def test_screenshots_organised_by_date_and_camera(tmp_path):
    settings.FRAMES_DIR = str(tmp_path)
    frame = np.zeros((48, 64, 3), dtype=np.uint8)
    rel = screenshots.save_screenshot(frame, 3, [7, None, 9])
    today = datetime.now().strftime("%Y-%m-%d")
    assert rel.startswith(f"{today}/camera_3/") and rel.endswith("_w7_w9.jpg")
    assert screenshots.absolute_path(rel) is not None
    assert screenshots.frame_url(rel) == f"/frames/{rel}"
    assert screenshots.frame_url("../../etc/passwd") is None  # no path traversal
    assert screenshots.frame_url(None) is None


async def test_event_bus_delivers_and_drops_for_slow_consumers():
    bus = EventBus()
    q = bus.subscribe()
    bus.publish({"id": 1})
    assert await q.get() == {"id": 1}
    for i in range(200):  # more than the queue holds: must not raise or block
        bus.publish({"id": i})
    bus.unsubscribe(q)
    assert bus.subscriber_count == 0


class FakeSource:
    def __init__(self):
        self.connects = 0

    async def connect(self):
        self.connects += 1
        return True

    async def read_frame(self):
        return None  # camera unplugged

    async def release(self):
        pass


async def test_camera_disconnect_reports_no_signal_and_keeps_running(monkeypatch):
    monkeypatch.setattr("app.camera.manager.NO_SIGNAL_SECONDS", 0.05)
    monkeypatch.setattr("app.camera.manager.RECONNECT_INTERVAL_SECONDS", 0.1)
    manager = CameraManager(MagicMock())
    source = FakeSource()
    entry = _CameraEntry(camera_id=1, source=source)
    manager._entries[1] = entry
    entry.task = asyncio.create_task(manager._process_loop(entry))
    await asyncio.sleep(0.4)
    assert manager.status(1) == "no_signal"  # reported, process loop still alive
    assert source.connects >= 1  # tries to reconnect
    assert entry.latest_counts["signal"] is False
    await manager.stop_camera(1)
    assert manager.status(1) == "stopped"


async def test_record_violations_one_screenshot_shared_and_event_published(tmp_path):
    """Combined + helmet incidents of one frame: one image, all rows point at it."""
    settings.FRAMES_DIR = str(tmp_path)
    manager = CameraManager(MagicMock())
    q = manager.events.subscribe()
    entry = _CameraEntry(camera_id=2, source=FakeSource(), session_id="S1")

    class FakeDb:
        n = 0

        async def send(self, v):
            FakeDb.n += 1
            v.db_id, v.camera_name = FakeDb.n, "Gate"
            v.timestamp = datetime(2026, 11, 17, 10, 0, 0)
            return True

    dispatcher = MagicMock()
    dispatcher.dispatch = AsyncMock()
    evs = [ViolationEvent(2, COMBINED, 0.9, track_id=1), ViolationEvent(2, VEST, 0.8, track_id=2)]
    frame = np.zeros((120, 160, 3), dtype=np.uint8)
    await manager._record_violations(entry, evs, frame, [], 0, 0, 2, None, FakeDb(), dispatcher)
    await asyncio.sleep(0)  # let the background alert task run

    assert evs[0].frame_path == evs[1].frame_path
    assert screenshots.absolute_path(evs[0].frame_path)
    assert len(list(tmp_path.rglob("*.jpg"))) == 1
    first = q.get_nowait()
    assert first["id"] == 1 and first["violation_type"] == COMBINED
    assert first["screenshot_available"] is True and first["camera_name"] == "Gate"
    assert q.get_nowait()["track_id"] == 2
    assert dispatcher.dispatch.await_count == 2
    assert evs[0].session_id == "S1"


def test_detector_uses_lower_threshold_for_helmet_and_vest_only():
    from app.core.detector import PPEDetector

    class_names = {0: "Hardhat", 5: "Person", 7: "Safety Vest", 4: "NO-Safety Vest"}

    class Box:
        def __init__(self, cls, conf):
            self.cls, self.conf = [cls], [conf]
            self.xyxy = [[0, 0, 10, 10]]

    class Result:
        boxes = [Box(0, 0.35), Box(5, 0.35), Box(7, 0.31), Box(7, 0.2), Box(5, 0.9), Box(4, 0.4)]

    seen = {}

    class FakeModel:
        names = class_names

        def __call__(self, frame, conf, verbose):
            seen["conf"] = conf
            return [Result()]

    det = PPEDetector.__new__(PPEDetector)
    det.model, det.confidence, det.ppe_confidence = FakeModel(), 0.5, 0.3
    out = [(d.class_name, round(d.confidence, 2)) for d in det.detect(None)]
    assert seen["conf"] == 0.3  # model is asked for the lowest bar, then filtered per class
    assert ("Hardhat", 0.35) in out and ("Safety Vest", 0.31) in out  # kept at 0.3
    assert ("Person", 0.35) not in out and ("Person", 0.9) in out  # person still needs 0.5
    assert ("NO-Safety Vest", 0.4) not in out
    assert ("Safety Vest", 0.2) not in out
