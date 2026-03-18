from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.schemas.work_log import WorkLogCreate, WorkLogUpdate, WorkLogResponse
from app.services.work_log_service import (
    get_work_logs_by_project, upsert_work_log, update_work_log, delete_work_log,
)

router = APIRouter(prefix="/api/work-logs", tags=["work-logs"])


@router.get("/project/{project_id}", response_model=list[WorkLogResponse])
async def list_logs(project_id: int, limit: int = 60, db: AsyncSession = Depends(get_db)):
    return await get_work_logs_by_project(db, project_id, limit)


@router.post("", response_model=WorkLogResponse, status_code=201)
async def create_or_update_log(data: WorkLogCreate, db: AsyncSession = Depends(get_db)):
    return await upsert_work_log(db, data)


@router.patch("/{log_id}", response_model=WorkLogResponse)
async def edit_log(log_id: int, data: WorkLogUpdate, db: AsyncSession = Depends(get_db)):
    log = await update_work_log(db, log_id, data)
    if not log:
        raise HTTPException(status_code=404, detail="Work log not found")
    return log


@router.delete("/{log_id}")
async def remove_log(log_id: int, db: AsyncSession = Depends(get_db)):
    if not await delete_work_log(db, log_id):
        raise HTTPException(status_code=404, detail="Work log not found")
    return {"ok": True}
