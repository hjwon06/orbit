from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.schemas.milestone import (
    MilestoneCreate, MilestoneUpdate, MilestoneDatesUpdate, MilestoneResponse,
)
from app.services.milestone_service import (
    get_milestones_by_project, create_milestone, update_milestone, update_milestone_dates, delete_milestone,
)

router = APIRouter(prefix="/api/milestones", tags=["milestones"])


@router.get("/project/{project_id}", response_model=list[MilestoneResponse])
async def list_milestones(project_id: int, db: AsyncSession = Depends(get_db)):
    return await get_milestones_by_project(db, project_id)


@router.post("", response_model=MilestoneResponse, status_code=201)
async def new_milestone(data: MilestoneCreate, db: AsyncSession = Depends(get_db)):
    return await create_milestone(db, data)


@router.patch("/{milestone_id}", response_model=MilestoneResponse)
async def edit_milestone(milestone_id: int, data: MilestoneUpdate, db: AsyncSession = Depends(get_db)):
    milestone = await update_milestone(db, milestone_id, data)
    if not milestone:
        raise HTTPException(status_code=404, detail="Milestone not found")
    return milestone


@router.patch("/{milestone_id}/dates", response_model=MilestoneResponse)
async def edit_dates(milestone_id: int, data: MilestoneDatesUpdate, db: AsyncSession = Depends(get_db)):
    milestone = await update_milestone_dates(db, milestone_id, data)
    if not milestone:
        raise HTTPException(status_code=404, detail="Milestone not found")
    return milestone


@router.delete("/{milestone_id}")
async def remove_milestone(milestone_id: int, db: AsyncSession = Depends(get_db)):
    if not await delete_milestone(db, milestone_id):
        raise HTTPException(status_code=404, detail="Milestone not found")
    return {"ok": True}
