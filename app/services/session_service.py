from pathlib import Path
from datetime import datetime, timezone
from sqlalchemy import select, update, delete
from sqlalchemy.ext.asyncio import AsyncSession
from app.models import Session, Project
from app.schemas.session import SessionCreate, SessionUpdate, SessionFinish
from app.config import get_settings

WEEKDAYS_KO = ["월", "화", "수", "목", "금", "토", "일"]


async def get_sessions_by_project(db: AsyncSession, project_id: int, limit: int = 50, offset: int = 0):
    stmt = (
        select(Session)
        .where(Session.project_id == project_id)
        .order_by(Session.started_at.desc())
        .limit(limit)
        .offset(offset)
    )
    result = await db.execute(stmt)
    return result.scalars().all()


async def get_session(db: AsyncSession, session_id: int):
    result = await db.execute(select(Session).where(Session.id == session_id))
    return result.scalar_one_or_none()


async def create_session(db: AsyncSession, data: SessionCreate) -> Session:
    session = Session(
        project_id=data.project_id,
        title=data.title,
        agent_code=data.agent_code,
    )
    db.add(session)
    await db.commit()
    await db.refresh(session)
    return session


async def update_session(db: AsyncSession, session_id: int, data: SessionUpdate) -> Session | None:
    values = data.model_dump(exclude_unset=True)
    if not values:
        return await get_session(db, session_id)
    await db.execute(update(Session).where(Session.id == session_id).values(**values))
    await db.commit()
    return await get_session(db, session_id)


async def finish_session(db: AsyncSession, session_id: int, data: SessionFinish) -> Session | None:
    now = datetime.now(timezone.utc)
    session = await get_session(db, session_id)
    if not session:
        return None

    duration = None
    if session.started_at:
        started = session.started_at
        if started.tzinfo is None:
            started = started.replace(tzinfo=timezone.utc)
        delta = now - started
        duration = int(delta.total_seconds() / 60)

    await db.execute(
        update(Session)
        .where(Session.id == session_id)
        .values(
            summary=data.summary,
            status=data.status,
            finished_at=now,
            duration_min=duration,
        )
    )
    await db.commit()
    session = await get_session(db, session_id)

    if session and data.status == "done":
        await _write_obsidian_diary(db, session)

    return session


async def delete_session(db: AsyncSession, session_id: int) -> bool:
    result = await db.execute(delete(Session).where(Session.id == session_id))
    await db.commit()
    return result.rowcount > 0


async def _write_obsidian_diary(db: AsyncSession, session: Session):
    """세션 종료 시 옵시디언 다이어리 자동 생성/이어쓰기."""
    try:
        settings = get_settings()
        vault_path = settings.obsidian_vault_path
        if not vault_path:
            return

        result = await db.execute(select(Project).where(Project.id == session.project_id))
        project = result.scalar_one_or_none()
        if not project:
            return

        now = session.finished_at or datetime.now(timezone.utc)
        date_str = now.strftime("%Y-%m-%d")
        weekday = WEEKDAYS_KO[now.weekday()]

        diary_dir = Path(vault_path) / "diary" / project.slug
        diary_dir.mkdir(parents=True, exist_ok=True)
        diary_path = diary_dir / f"{date_str}.md"

        time_range = ""
        if session.started_at:
            start_t = session.started_at.strftime("%H:%M")
            end_t = now.strftime("%H:%M")
            dur = f" ({session.duration_min}분)" if session.duration_min else ""
            time_range = f"{start_t}~{end_t}{dur}"

        agent_str = f" {session.agent_code}" if session.agent_code else ""

        entry = f"\n### {time_range}{agent_str} — {session.title}\n"
        if session.summary:
            entry += f"\n{session.summary}\n"

        if diary_path.exists():
            with open(diary_path, "a", encoding="utf-8") as f:
                f.write(f"\n---\n{entry}")
        else:
            header = f"# {date_str} ({weekday}) — {project.name}\n"
            with open(diary_path, "w", encoding="utf-8") as f:
                f.write(header + entry)

    except Exception as e:
        print(f"[ORBIT] Obsidian diary write error: {e}")
