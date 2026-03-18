from sqlalchemy import select, update, delete
from sqlalchemy.ext.asyncio import AsyncSession
from app.models import WorkLog
from app.schemas.work_log import WorkLogCreate, WorkLogUpdate


async def get_work_logs_by_project(db: AsyncSession, project_id: int, limit: int = 60):
    stmt = (
        select(WorkLog)
        .where(WorkLog.project_id == project_id)
        .order_by(WorkLog.log_date.desc())
        .limit(limit)
    )
    result = await db.execute(stmt)
    return result.scalars().all()


async def get_work_log(db: AsyncSession, log_id: int):
    result = await db.execute(select(WorkLog).where(WorkLog.id == log_id))
    return result.scalar_one_or_none()


async def get_work_log_by_date(db: AsyncSession, project_id: int, log_date):
    stmt = select(WorkLog).where(WorkLog.project_id == project_id, WorkLog.log_date == log_date)
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def upsert_work_log(db: AsyncSession, data: WorkLogCreate) -> WorkLog:
    existing = await get_work_log_by_date(db, data.project_id, data.log_date)
    if existing:
        existing.content = data.content
        await db.commit()
        await db.refresh(existing)
        return existing
    log = WorkLog(**data.model_dump())
    db.add(log)
    await db.commit()
    await db.refresh(log)
    return log


async def update_work_log(db: AsyncSession, log_id: int, data: WorkLogUpdate) -> WorkLog | None:
    values = data.model_dump(exclude_unset=True)
    if not values:
        return await get_work_log(db, log_id)
    await db.execute(update(WorkLog).where(WorkLog.id == log_id).values(**values))
    await db.commit()
    return await get_work_log(db, log_id)


async def delete_work_log(db: AsyncSession, log_id: int) -> bool:
    result = await db.execute(delete(WorkLog).where(WorkLog.id == log_id))
    await db.commit()
    return result.rowcount > 0
