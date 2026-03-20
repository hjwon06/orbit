from datetime import datetime, timezone
from sqlalchemy import select, update, func as sqlfunc
from sqlalchemy.ext.asyncio import AsyncSession
from app.models import Milestone, Todo
from app.schemas.milestone import MilestoneCreate, MilestoneUpdate, MilestoneDatesUpdate


async def get_milestones_by_project(db: AsyncSession, project_id: int):
    stmt = (
        select(Milestone)
        .where(Milestone.project_id == project_id, Milestone.deleted_at.is_(None))
        .order_by(Milestone.sort_order, Milestone.start_date)
    )
    result = await db.execute(stmt)
    milestones = result.scalars().all()

    # 마일스톤별 할일 진행률 계산
    if milestones:
        ms_ids = [m.id for m in milestones]
        total_stmt = (
            select(Todo.milestone_id, sqlfunc.count())
            .where(Todo.milestone_id.in_(ms_ids), Todo.deleted_at.is_(None))
            .group_by(Todo.milestone_id)
        )
        done_stmt = (
            select(Todo.milestone_id, sqlfunc.count())
            .where(Todo.milestone_id.in_(ms_ids), Todo.deleted_at.is_(None), Todo.status == "done")
            .group_by(Todo.milestone_id)
        )
        total_result = await db.execute(total_stmt)
        done_result = await db.execute(done_stmt)
        totals = dict(total_result.all())
        dones = dict(done_result.all())

        for m in milestones:
            m.todo_total = totals.get(m.id, 0)  # type: ignore[attr-defined]
            m.todo_done = dones.get(m.id, 0)  # type: ignore[attr-defined]
            m.todo_pct = round(m.todo_done / m.todo_total * 100) if m.todo_total > 0 else 0  # type: ignore[attr-defined]

    return milestones


async def get_milestone(db: AsyncSession, milestone_id: int):
    result = await db.execute(select(Milestone).where(Milestone.id == milestone_id, Milestone.deleted_at.is_(None)))
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
    result = await db.execute(
        update(Milestone).where(Milestone.id == milestone_id).values(deleted_at=datetime.now(timezone.utc))
    )
    await db.commit()
    return result.rowcount > 0
