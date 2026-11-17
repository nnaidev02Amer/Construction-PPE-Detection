from __future__ import annotations

import time
from unittest.mock import patch

import pytest

from app.core.detector import Detection
from app.core.ppe_assigner import PersonStatus
from app.core.violation_checker import ViolationChecker


def make_detection(class_name: str, confidence: float = 0.9) -> Detection:
    return Detection(
        class_id=0,
        class_name=class_name,
        confidence=confidence,
        x1=0, y1=0, x2=100, y2=100,
        color=(255, 0, 0),
    )


def make_status(track_id: int | None, has_hardhat: bool) -> PersonStatus:
    person = make_detection("Person")
    person.track_id = track_id
    return PersonStatus(person=person, pose=None, has_hardhat=has_hardhat, has_vest=True)


@pytest.fixture
def checker():
    return ViolationChecker(cooldown_seconds=10, persist_seconds=5)


def test_no_violation_when_hardhat_present(checker):
    detections = [make_detection("Hardhat"), make_detection("Person")]
    result = checker.check(camera_id=1, detections=detections)
    assert result is None


def test_no_violation_when_no_person(checker):
    detections = [make_detection("Hardhat")]
    result = checker.check(camera_id=1, detections=detections)
    assert result is None


def test_no_violation_before_persist_threshold(checker):
    detections = [make_detection("Person")]
    # Should not trigger immediately (persist_seconds=5)
    result = checker.check(camera_id=1, detections=detections)
    assert result is None


def test_violation_after_persist_threshold(checker):
    camera_id = 1
    detections = [make_detection("Person")]

    # Push last_hardhat_time far into the past
    with patch("time.time", return_value=1000.0):
        checker._get_state(camera_id).last_hardhat_time = 990.0  # 10s ago

    with patch("time.time", return_value=1000.0):
        result = checker.check(camera_id=camera_id, detections=detections)

    assert result is not None
    assert result.violation_type == "NO-Hardhat"
    assert result.camera_id == camera_id


def test_cooldown_prevents_duplicate_alert(checker):
    camera_id = 2
    detections = [make_detection("Person")]

    # First alert at t=1000
    with patch("time.time", return_value=1000.0):
        checker._get_state(camera_id).last_hardhat_time = 980.0
        first = checker.check(camera_id=camera_id, detections=detections)

    # Second check at t=1005 (only 5s later, cooldown=10)
    with patch("time.time", return_value=1005.0):
        second = checker.check(camera_id=camera_id, detections=detections)

    assert first is not None
    assert second is None


def test_alert_fires_again_after_cooldown(checker):
    camera_id = 3
    detections = [make_detection("Person")]

    with patch("time.time", return_value=1000.0):
        checker._get_state(camera_id).last_hardhat_time = 980.0
        first = checker.check(camera_id=camera_id, detections=detections)

    # After cooldown (10s) + a bit more
    with patch("time.time", return_value=1015.0):
        second = checker.check(camera_id=camera_id, detections=detections)

    assert first is not None
    assert second is not None


def test_per_camera_isolation(checker):
    detections_no_hardhat = [make_detection("Person")]
    detections_with_hardhat = [make_detection("Hardhat"), make_detection("Person")]

    with patch("time.time", return_value=1000.0):
        checker._get_state(1).last_hardhat_time = 980.0
        checker._get_state(2).last_hardhat_time = 980.0

    with patch("time.time", return_value=1000.0):
        result_cam1 = checker.check(1, detections_no_hardhat)
        result_cam2 = checker.check(2, detections_with_hardhat)

    assert result_cam1 is not None
    assert result_cam2 is None


def test_reset_clears_state(checker):
    camera_id = 4
    checker._get_state(camera_id)
    assert camera_id in checker._states
    checker.reset(camera_id)
    assert camera_id not in checker._states


def test_track_violation_after_persist_threshold(checker):
    with patch("time.time", return_value=1000.0):
        assert checker.check_tracks(1, [make_status(7, has_hardhat=False)]) == []

    with patch("time.time", return_value=1006.0):
        events = checker.check_tracks(1, [make_status(7, has_hardhat=False)])

    assert len(events) == 1
    assert events[0].track_id == 7
    assert events[0].violation_type == "NO-Hardhat"


def test_track_violation_only_for_offending_worker(checker):
    with patch("time.time", return_value=1000.0):
        checker.check_tracks(1, [make_status(1, True), make_status(2, False)])

    with patch("time.time", return_value=1006.0):
        events = checker.check_tracks(1, [make_status(1, True), make_status(2, False)])

    assert [e.track_id for e in events] == [2]


def test_track_cooldown_is_per_worker(checker):
    with patch("time.time", return_value=1000.0):
        checker.check_tracks(1, [make_status(1, False)])
    with patch("time.time", return_value=1006.0):
        first = checker.check_tracks(1, [make_status(1, False)])
    with patch("time.time", return_value=1007.0):
        checker.check_tracks(1, [make_status(1, False), make_status(2, False)])
    with patch("time.time", return_value=1013.0):
        second = checker.check_tracks(1, [make_status(1, False), make_status(2, False)])

    assert [e.track_id for e in first] == [1]
    # Worker 1 still in cooldown, worker 2 has now persisted long enough
    assert [e.track_id for e in second] == [2]


def test_putting_on_hardhat_resets_track_timer(checker):
    with patch("time.time", return_value=1000.0):
        checker.check_tracks(1, [make_status(1, False)])
    with patch("time.time", return_value=1004.0):
        checker.check_tracks(1, [make_status(1, True)])
    with patch("time.time", return_value=1008.0):
        events = checker.check_tracks(1, [make_status(1, False)])

    assert events == []


def test_untracked_people_ignored(checker):
    with patch("time.time", return_value=1000.0):
        assert checker.check_tracks(1, [make_status(None, False)]) == []
    assert checker._track_states == {}


def test_stale_track_state_pruned(checker):
    with patch("time.time", return_value=1000.0):
        checker.check_tracks(1, [make_status(1, False)])
    with patch("time.time", return_value=1000.0 + checker.TRACK_STATE_TTL_SECONDS + 1):
        checker.check_tracks(1, [])
    assert checker._track_states == {}


def test_reset_clears_track_state(checker):
    with patch("time.time", return_value=1000.0):
        checker.check_tracks(1, [make_status(1, False)])
        checker.check_tracks(2, [make_status(1, False)])
    checker.reset(1)
    assert list(checker._track_states) == [(2, 1)]


# ── Violation categories: helmet / vest / combined ───────────────────────────

from app.core.violation_types import COMBINED, HELMET, VEST  # noqa: E402


def make_ppe_status(track_id: int, hardhat: bool, vest: bool) -> PersonStatus:
    person = make_detection("Person")
    person.track_id = track_id
    return PersonStatus(person=person, pose=None, has_hardhat=hardhat, has_vest=vest)


def run(checker, steps):
    """steps: list of (time, [PersonStatus]) -> list of (time, events)"""
    out = []
    for t, persons in steps:
        with patch("time.time", return_value=t):
            out.append((t, checker.check_tracks(1, persons)))
    return out


def test_default_persist_time_is_three_seconds():
    from app.core.config import Settings

    assert Settings(_env_file=None).VIOLATION_PERSIST_SECONDS == 3


def test_helmet_only_violation(checker):
    res = run(checker, [(1000, [make_ppe_status(1, False, True)]),
                        (1006, [make_ppe_status(1, False, True)])])
    assert [e.violation_type for e in res[1][1]] == [HELMET]


def test_vest_only_violation(checker):
    res = run(checker, [(1000, [make_ppe_status(1, True, False)]),
                        (1006, [make_ppe_status(1, True, False)])])
    assert [e.violation_type for e in res[1][1]] == [VEST]
    assert res[1][1][0].track_id == 1


def test_missing_both_is_one_combined_incident_not_two(checker):
    res = run(checker, [(1000, [make_ppe_status(1, False, False)]),
                        (1006, [make_ppe_status(1, False, False)])])
    events = res[1][1]
    assert len(events) == 1
    assert events[0].violation_type == COMBINED


def test_compliant_worker_never_triggers(checker):
    res = run(checker, [(1000, [make_ppe_status(1, True, True)]),
                        (1060, [make_ppe_status(1, True, True)])])
    assert all(events == [] for _, events in res)


def test_no_event_before_persistence_period(checker):
    res = run(checker, [(1000, [make_ppe_status(1, True, False)]),
                        (1004, [make_ppe_status(1, True, False)])])
    assert res[1][1] == []


def test_one_record_per_episode_until_cooldown(checker):
    """Every frame in between must not create a record."""
    steps = [(1000 + i, [make_ppe_status(1, False, True)]) for i in range(0, 10)]
    total = sum(len(ev) for _, ev in run(checker, steps))
    assert total == 1  # persist=5s, cooldown=10s: only the t=1005 incident


def test_repeat_after_cooldown(checker):
    steps = [(1000 + i, [make_ppe_status(1, False, True)]) for i in range(0, 17)]
    times = [t for t, ev in run(checker, steps) if ev]
    assert times == [1005, 1015]


def test_change_from_helmet_to_combined_is_recorded_as_new_type(checker):
    steps = [
        (1000, [make_ppe_status(1, False, True)]),
        (1006, [make_ppe_status(1, False, True)]),   # HELMET recorded
        (1007, [make_ppe_status(1, False, False)]),  # now also missing vest -> timer restarts
        (1010, [make_ppe_status(1, False, False)]),  # not persisted yet
        (1013, [make_ppe_status(1, False, False)]),  # persisted: COMBINED, despite helmet cooldown
    ]
    res = run(checker, steps)
    assert [e.violation_type for e in res[1][1]] == [HELMET]
    assert res[3][1] == []
    assert [e.violation_type for e in res[4][1]] == [COMBINED]


def test_change_from_vest_to_helmet_resets_timer(checker):
    steps = [
        (1000, [make_ppe_status(1, True, False)]),
        (1004, [make_ppe_status(1, False, True)]),  # swapped problem: timer restarts
        (1008, [make_ppe_status(1, False, True)]),  # only 4s of "no helmet"
        (1010, [make_ppe_status(1, False, True)]),
    ]
    res = run(checker, steps)
    assert res[2][1] == []
    assert [e.violation_type for e in res[3][1]] == [HELMET]


def test_multiple_workers_get_independent_incidents(checker):
    both = [make_ppe_status(1, False, True), make_ppe_status(2, True, False),
            make_ppe_status(3, False, False), make_ppe_status(4, True, True)]
    res = run(checker, [(1000, both), (1006, both)])
    got = {e.track_id: e.violation_type for e in res[1][1]}
    assert got == {1: HELMET, 2: VEST, 3: COMBINED}
