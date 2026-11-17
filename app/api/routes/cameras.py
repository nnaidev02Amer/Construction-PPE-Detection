from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_camera_manager
from app.camera.manager import CameraManager
from app.db.models import AlertLog, Camera, Violation, WorkerSighting
from app.db.session import get_db
from app.schemas.camera import CameraCreate, CameraResponse, CameraUpdate

router = APIRouter(prefix="/cameras", tags=["cameras"])


def _response(cam: Camera, manager: CameraManager) -> CameraResponse:
    return CameraResponse(
        id=cam.id,
        name=cam.name,
        source_type=cam.source_type,
        source_uri=cam.source_uri,
        is_active=cam.is_active,
        created_at=cam.created_at,
        is_running=manager.is_running(cam.id),
        status=manager.status(cam.id),
    )


@router.get("", response_model=list[CameraResponse])
async def list_cameras(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    cameras = (await db.execute(select(Camera).order_by(Camera.id))).scalars().all()
    manager: CameraManager = get_camera_manager(request)
    return [_response(cam, manager) for cam in cameras]


@router.post("", response_model=CameraResponse, status_code=201)
async def create_camera(
    body: CameraCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    cam = Camera(
        name=body.name,
        source_type=body.source_type,
        source_uri=body.source_uri,
    )
    db.add(cam)
    await db.commit()
    await db.refresh(cam)
    return CameraResponse.model_validate(cam)


@router.get("/{camera_id}", response_model=CameraResponse)
async def get_camera(
    camera_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    cam = await db.get(Camera, camera_id)
    if cam is None:
        raise HTTPException(status_code=404, detail="Camera not found")
    return _response(cam, get_camera_manager(request))


@router.put("/{camera_id}", response_model=CameraResponse)
async def update_camera(
    camera_id: int,
    body: CameraUpdate,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    cam = await db.get(Camera, camera_id)
    if cam is None:
        raise HTTPException(status_code=404, detail="Camera not found")
    manager: CameraManager = get_camera_manager(request)
    if manager.is_running(cam.id) and body.source_uri is not None:
        raise HTTPException(status_code=409, detail="Stop the camera before changing its source")
    if body.source_uri is not None:
        if cam.source_type == "webcam" and not body.source_uri.strip().isdigit():
            raise HTTPException(
                status_code=422, detail="A webcam source must be a device number such as 0 or 1"
            )
        cam.source_uri = body.source_uri.strip()
    if body.name is not None:
        cam.name = body.name
    await db.commit()
    await db.refresh(cam)
    return _response(cam, manager)


@router.delete("/{camera_id}", status_code=204)
async def delete_camera(
    camera_id: int,
    request: Request,
    delete_history: bool = Query(False, description="Also delete this camera's violations"),
    db: AsyncSession = Depends(get_db),
):
    cam = await db.get(Camera, camera_id)
    if cam is None:
        raise HTTPException(status_code=404, detail="Camera not found")
    n = (
        await db.execute(select(func.count()).select_from(Violation).where(Violation.camera_id == camera_id))
    ).scalar_one()
    if n and not delete_history:
        raise HTTPException(
            status_code=409,
            detail=f"Camera has {n} recorded violation(s). Use delete_history=true to remove them too.",
        )
    manager: CameraManager = get_camera_manager(request)
    await manager.stop_camera(camera_id)
    ids = select(Violation.id).where(Violation.camera_id == camera_id)
    await db.execute(delete(AlertLog).where(AlertLog.violation_id.in_(ids)))
    await db.execute(delete(Violation).where(Violation.camera_id == camera_id))
    await db.execute(delete(WorkerSighting).where(WorkerSighting.camera_id == camera_id))
    await db.delete(cam)
    await db.commit()


@router.post("/{camera_id}/start")
async def start_camera(
    camera_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    cam = await db.get(Camera, camera_id)
    if cam is None:
        raise HTTPException(status_code=404, detail="Camera not found")

    manager: CameraManager = get_camera_manager(request)
    ok = await manager.start_camera(camera_id, cam.source_type, cam.source_uri)
    if not ok:
        raise HTTPException(
            status_code=400,
            detail="Could not start camera. Check the source (webcam number, RTSP URL or file path) "
            "and that no other program is using the camera.",
        )

    cam.is_active = True
    await db.commit()
    return {"status": "started", "camera_id": camera_id}


@router.post("/{camera_id}/stop")
async def stop_camera(
    camera_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    cam = await db.get(Camera, camera_id)
    if cam is None:
        raise HTTPException(status_code=404, detail="Camera not found")

    manager: CameraManager = get_camera_manager(request)
    await manager.stop_camera(camera_id)
    cam.is_active = False
    await db.commit()
    return {"status": "stopped", "camera_id": camera_id}
