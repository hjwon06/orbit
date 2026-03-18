from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.schemas.commit_stat import CommitStatCreate, CommitStatUpdate, CommitStatResponse
from app.services.commit_stat_service import (
    get_commit_stats_by_project, upsert_commit_stat, update_commit_stat, delete_commit_stat,
)

router = APIRouter(prefix="/api/commit-stats", tags=["commit-stats"])


@router.get("/project/{project_id}", response_model=list[CommitStatResponse])
async def list_stats(project_id: int, limit: int = 90, db: AsyncSession = Depends(get_db)):
    return await get_commit_stats_by_project(db, project_id, limit)


@router.post("", response_model=CommitStatResponse, status_code=201)
async def create_or_update_stat(data: CommitStatCreate, db: AsyncSession = Depends(get_db)):
    return await upsert_commit_stat(db, data)


@router.patch("/{stat_id}", response_model=CommitStatResponse)
async def edit_stat(stat_id: int, data: CommitStatUpdate, db: AsyncSession = Depends(get_db)):
    stat = await update_commit_stat(db, stat_id, data)
    if not stat:
        raise HTTPException(status_code=404, detail="Commit stat not found")
    return stat


@router.delete("/{stat_id}")
async def remove_stat(stat_id: int, db: AsyncSession = Depends(get_db)):
    if not await delete_commit_stat(db, stat_id):
        raise HTTPException(status_code=404, detail="Commit stat not found")
    return {"ok": True}
