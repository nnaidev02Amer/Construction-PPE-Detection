"""Saving and locating violation screenshots (stored relative to FRAMES_DIR)."""
from __future__ import annotations

import os
import time
from datetime import datetime
from typing import Optional

import cv2
import numpy as np

from app.core.config import settings


def save_screenshot(frame: np.ndarray, camera_id: int, track_ids: list[int | None]) -> str:
    """Write the frame to FRAMES_DIR/<date>/camera_<id>/ and return the relative path."""
    day = datetime.now().strftime("%Y-%m-%d")
    rel_dir = f"{day}/camera_{camera_id}"
    os.makedirs(os.path.join(settings.FRAMES_DIR, rel_dir), exist_ok=True)
    workers = "_".join(f"w{t}" for t in track_ids if t is not None)
    name = f"violation_{int(time.time() * 1000)}" + (f"_{workers}" if workers else "") + ".jpg"
    rel_path = f"{rel_dir}/{name}"
    if not cv2.imwrite(os.path.join(settings.FRAMES_DIR, rel_path), frame):
        raise OSError(f"Could not write screenshot {rel_path}")
    return rel_path


def normalize(frame_path: Optional[str]) -> Optional[str]:
    """Turn stored paths (including old Windows-style ones) into FRAMES_DIR-relative form."""
    if not frame_path:
        return None
    p = frame_path.replace("\\", "/")
    prefix = settings.FRAMES_DIR.replace("\\", "/").rstrip("/") + "/"
    if p.startswith(prefix):
        p = p[len(prefix):]
    return p


def absolute_path(frame_path: Optional[str]) -> Optional[str]:
    """Absolute file path of a stored screenshot, or None if missing/unavailable."""
    rel = normalize(frame_path)
    if not rel or ".." in rel.split("/") or os.path.isabs(rel):
        return None
    full = os.path.join(settings.FRAMES_DIR, rel)
    return full if os.path.isfile(full) else None


def frame_url(frame_path: Optional[str]) -> Optional[str]:
    """URL for the dashboard, only when the file really exists."""
    if absolute_path(frame_path) is None:
        return None
    return "/frames/" + normalize(frame_path)
