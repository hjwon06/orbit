from sqlalchemy import select, update, delete
from sqlalchemy.ext.asyncio import AsyncSession
from app.models import Milestone
from app.schemas.milestone import MilestoneCreate, MilestoneUpdate, MilestoneDatesUpdate


async def get_milestones_by_project(db: AsyncSession, project_id: int):
    stmt = (
        select(Milestone)
        .where(Milestone.project_id == project_id)
        .order_by(Milestone.sort_order, Milestone.start_date)
    )
    result = await db.execute(stmt)
    return result.scalars().all()


async def get_milestone(db: AsyncSession, milestone_id: int):
    result = await db.execute(select(Milestone).where(Milestone.id == milestone_id))
    return result.scalar_one_or_none()


async def create_milestone(db: AsyncSession, data: MilestoneCreate) -> Milestone:
    milestone = Milestone(**data.model_dump())
    db.add(milestone)
    await db.commit()
    await db.refresh(milestone)
    return milestone


async def update_milestone(db: AsyncSession, milestone_id: int, data: MilestoneUpdate) -> Milestone | None:
    values = data.model_dump(exclude_unset=True)
    if not values:
        return await get_milestone(db, milestone_id)
    await db.execute(update(Milestone).where(Milestone.id == milestone_id).values(**values))
    await db.commit()
    return await get_milestone(db, milestone_id)


async def update_milestone_dates(db: AsyncSession, milestone_id: int, data: MilestoneDatesUpdate) -> Milestone | None:
    await db.execute(
        update(Milestone)
        .where(Milestone.id == milestone_id)
        .values(start_date=data.start_date, end_date=data.end_date)
    )
    await db.commit()
    return await get_milestone(db, milestone_id)


async def delete_milestone(db: AsyncSession, milestone_id: int) -> bool:
    result = await db.execute(delete(Milestone).where(Milestone.id == milestone_id))
    await db.commit()
    return result.rowcount > 0
