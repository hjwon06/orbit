from sqlalchemy import select, update, delete
from sqlalchemy.ext.asyncio import AsyncSession
from app.models import CommitStat
from app.schemas.commit_stat import CommitStatCreate, CommitStatUpdate


async def get_commit_stats_by_project(db: AsyncSession, project_id: int, limit: int = 90):
    stmt = (
        select(CommitStat)
        .where(CommitStat.project_id == project_id)
        .order_by(CommitStat.stat_date.desc())
        .limit(limit)
    )
    result = await db.execute(stmt)
    return result.scalars().all()


async def get_commit_stat(db: AsyncSession, stat_id: int):
    result = await db.execute(select(CommitStat).where(CommitStat.id == stat_id))
    return result.scalar_one_or_none()


async def upsert_commit_stat(db: AsyncSession, data: CommitStatCreate) -> CommitStat:
    stmt = select(CommitStat).where(
        CommitStat.project_id == data.project_id,
        CommitStat.stat_date == data.stat_date,
    )
    result = await db.execute(stmt)
    existing = result.scalar_one_or_none()
    if existing:
        existing.commit_count = data.commit_count  # type: ignore[assignment]
        existing.additions = data.additions  # type: ignore[assignment]
        existing.deletions = data.deletions  # type: ignore[assignment]
        await db.commit()
        await db.refresh(existing)
        return existing
    stat = CommitStat(**data.model_dump())
    db.add(stat)
    await db.commit()
    await db.refresh(stat)
    return stat


async def update_commit_stat(db: AsyncSession, stat_id: int, data: CommitStatUpdate) -> CommitStat | None:
    values = data.model_dump(exclude_unset=True)
    if not values:
        return await get_commit_stat(db, stat_id)
    await db.execute(update(CommitStat).where(CommitStat.id == stat_id).values(**values))
    await db.commit()
    return await get_commit_stat(db, stat_id)


async def delete_commit_stat(db: AsyncSession, stat_id: int) -> bool:
    result = await db.execute(delete(CommitStat).where(CommitStat.id == stat_id))
    await db.commit()
    return result.rowcount > 0
