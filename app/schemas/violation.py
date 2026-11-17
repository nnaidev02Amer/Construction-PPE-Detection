from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class AlertLogResponse(BaseModel):
    handler_type: str
    sent_at: datetime
    success: bool
    error_msg: Optional[str] = None

    model_config = {"from_attributes": True}


class ViolationResponse(BaseModel):
    id: int
    camera_id: int
    camera_name: Optional[str] = None
    violation_type: str
    label: Optional[str] = None  # human readable type
    missing_items: list[str] = []
    confidence: float
    timestamp: datetime
    frame_path: Optional[str]
    track_id: Optional[int] = None
    session_id: Optional[str] = None
    frame_url: Optional[str] = None  # None when the screenshot file is missing
    screenshot_available: bool = False

    model_config = {"from_attributes": True}


class ViolationDetailResponse(ViolationResponse):
    alerts: list[AlertLogResponse] = []


class ViolationListResponse(BaseModel):
    total: int
    page: int
    page_size: int
    items: list[ViolationResponse]
