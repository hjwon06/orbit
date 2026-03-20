from datetime import date, datetime, timedelta, timezone
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


async def ensure_weekly_milestone(db: AsyncSession, project_id: int) -> dict:
    """주간 마일스톤 자동 관리: 현재 주 생성 + 만료 완료 + 미완료 이월."""
    today = date.today()
    monday = today - timedelta(days=today.weekday())  # 이번 주 월요일
    sunday = monday + timedelta(days=6)
    iso_week = today.isocalendar()[1]
    title = f"W{iso_week} ({monday.strftime('%m/%d')}~{sunday.strftime('%m/%d')})"

    # 1. 현재 주 마일스톤 조회 or 생성
    existing = await db.execute(
        select(Milestone).where(
            Milestone.project_id == project_id,
            Milestone.deleted_at.is_(None),
            Milestone.source == "weekly",
            Milestone.start_date == monday,
        )
    )
    current_ms = existing.scalar_one_or_none()
    created_new = False

    if not current_ms:
        current_ms = Milestone(
            project_id=project_id,
            title=title,
            status="active",
            start_date=monday,
            end_date=sunday,
            source="weekly",
            sort_order=9000 + iso_week,
        )
        db.add(current_ms)
        await db.flush()  # id 확보
        created_new = True

    # 2. 만료된 weekly 마일스톤 조회 (end_date < today)
    expired_result = await db.execute(
        select(Milestone).where(
            Milestone.project_id == project_id,
            Milestone.deleted_at.is_(None),
            Milestone.source == "weekly",
            Milestone.status.in_(["active", "planned"]),
            Milestone.end_date < today,
        )
    )
    expired = expired_result.scalars().all()
    expired_ids = [m.id for m in expired]

    # 3. 만료 마일스톤의 open 할일 → 현재 주로 이월
    carried = 0
    if expired_ids:
        carry_result = await db.execute(
            update(Todo).where(
                Todo.milestone_id.in_(expired_ids),
                Todo.status == "open",
                Todo.deleted_at.is_(None),
            ).values(milestone_id=current_ms.id)
        )
        carried = carry_result.rowcount

        # 만료 마일스톤 done 처리
        await db.execute(
            update(Milestone).where(
                Milestone.id.in_(expired_ids)
            ).values(status="done")
        )

    await db.commit()

    return {
        "weekly_milestone_id": current_ms.id,
        "weekly_milestone_title": title,
        "created_new": created_new,
        "expired_count": len(expired_ids),
        "carried_count": carried,
    }
