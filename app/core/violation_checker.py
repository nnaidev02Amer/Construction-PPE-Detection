from __future__ import annotations

import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from app.core.detector import Detection
from app.core.logging import get_logger
from app.core.ppe_assigner import PersonStatus
from app.core.violation_types import HELMET, classify

logger = get_logger(__name__)


@dataclass
class ViolationEvent:
    camera_id: int
    violation_type: str
    confidence: float
    frame_path: Optional[str] = None  # relative to FRAMES_DIR
    track_id: Optional[int] = None
    session_id: Optional[str] = None
    # Filled in by DatabaseHandler once the row exists
    db_id: Optional[int] = None
    camera_name: Optional[str] = None
    timestamp: Optional[datetime] = None


@dataclass
class _CameraState:
    last_hardhat_time: float = field(default_factory=time.time)
    last_alert_time: float = field(default_factory=lambda: 0.0)


@dataclass
class _TrackState:
    """What one tracked worker is currently doing wrong, and for how long."""

    current_type: Optional[str]  # None = compliant right now
    since: float  # when current_type began (reset on every change)
    last_seen: float
    last_alert: dict[str, float] = field(default_factory=dict)  # per violation type


class ViolationChecker:
    """
    Tracks per-camera state and emits ViolationEvent when a person is detected
    without a hardhat for longer than ALERT_COOLDOWN_SECONDS.

    ``check`` works on whole frames; ``check_tracks`` works per tracked worker so
    each person gets their own persistence timer and alert cooldown.
    """

    # Forget a track's state once it hasn't been seen for this long
    TRACK_STATE_TTL_SECONDS = 60.0

    def __init__(self, cooldown_seconds: int = 10, persist_seconds: int = 10) -> None:
        self.cooldown_seconds = cooldown_seconds
        self.persist_seconds = persist_seconds
        self._states: dict[int, _CameraState] = {}
        self._track_states: dict[tuple[int, int], _TrackState] = {}

    def _get_state(self, camera_id: int) -> _CameraState:
        if camera_id not in self._states:
            self._states[camera_id] = _CameraState()
        return self._states[camera_id]

    def check(
        self,
        camera_id: int,
        detections: list[Detection],
        frame_path: Optional[str] = None,
    ) -> Optional[ViolationEvent]:
        state = self._get_state(camera_id)
        now = time.time()

        hardhat_detected = any(d.class_name == "Hardhat" for d in detections)
        person_detected = any(d.class_name == "Person" for d in detections)

        if hardhat_detected:
            state.last_hardhat_time = now

        # Emit violation if: person present, no hardhat, cooldown elapsed
        if person_detected and not hardhat_detected:
            time_without_hardhat = now - state.last_hardhat_time
            time_since_last_alert = now - state.last_alert_time

            if (
                time_without_hardhat >= self.persist_seconds
                and time_since_last_alert >= self.cooldown_seconds
            ):
                state.last_alert_time = now
                person_detections = [d for d in detections if d.class_name == "Person"]
                confidence = max((d.confidence for d in person_detections), default=0.0)
                logger.info(
                    "Violation detected on camera %d: no hardhat for %.1fs",
                    camera_id,
                    time_without_hardhat,
                )
                return ViolationEvent(
                    camera_id=camera_id,
                    violation_type=HELMET,
                    confidence=confidence,
                    frame_path=frame_path,
                )

        return None

    def check_tracks(
        self,
        camera_id: int,
        persons: list[PersonStatus],
        frame_path: Optional[str] = None,
    ) -> list[ViolationEvent]:
        """
        One incident per worker when their PPE status (helmet / vest / both missing) has
        stayed the same for ``persist_seconds``. A worker missing both items yields a single
        COMBINED event. Cooldown is per (worker, type), so switching from "no helmet" to
        "no helmet + no vest" is reported after its own persistence period.
        """
        now = time.time()
        events: list[ViolationEvent] = []

        for status in persons:
            if status.track_id is None:
                continue
            vtype = classify(status.has_hardhat, status.has_vest)
            key = (camera_id, status.track_id)
            state = self._track_states.get(key)
            if state is None:
                state = self._track_states[key] = _TrackState(
                    current_type=vtype, since=now, last_seen=now
                )
            state.last_seen = now

            if vtype != state.current_type:  # status changed: restart the timer
                state.current_type = vtype
                state.since = now
            if vtype is None:
                continue

            if (
                now - state.since >= self.persist_seconds
                and now - state.last_alert.get(vtype, float("-inf")) >= self.cooldown_seconds
            ):
                state.last_alert[vtype] = now
                logger.info(
                    "Violation on camera %d: worker #%d %s for %.1fs",
                    camera_id, status.track_id, vtype, now - state.since,
                )
                events.append(
                    ViolationEvent(
                        camera_id=camera_id,
                        violation_type=vtype,
                        confidence=status.person.confidence,
                        frame_path=frame_path,
                        track_id=status.track_id,
                    )
                )

        self._prune_tracks(now)
        return events

    def _prune_tracks(self, now: float) -> None:
        stale = [
            key
            for key, state in self._track_states.items()
            if now - state.last_seen > self.TRACK_STATE_TTL_SECONDS
        ]
        for key in stale:
            del self._track_states[key]

    def reset(self, camera_id: int) -> None:
        self._states.pop(camera_id, None)
        for key in [k for k in self._track_states if k[0] == camera_id]:
            del self._track_states[key]
