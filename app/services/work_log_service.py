from datetime import date, timedelta
from sqlalchemy import select, update, delete, func as sqlfunc
from sqlalchemy.ext.asyncio import AsyncSession
from app.models import WorkLog, Project, Session as SessionModel, CommitStat, Todo
from app.schemas.work_log import WorkLogCreate, WorkLogUpdate
from app.config import get_settings

try:
    import httpx
    HAS_HTTPX = True
except ImportError:
    HAS_HTTPX = False


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


async def generate_weekly_summary(db: AsyncSession, project_id: int) -> dict:
    """GPT-4o로 최근 7일 작업 요약 생성."""
    settings = get_settings()
    if not settings.openai_api_key or not HAS_HTTPX:
        return {"error": "OpenAI 키가 설정되지 않았습니다."}

    project_result = await db.execute(select(Project).where(Project.id == project_id))
    project = project_result.scalar_one_or_none()
    if not project:
        return {"error": "프로젝트를 찾을 수 없습니다."}

    week_ago = date.today() - timedelta(days=7)

    # 최근 7일 세션
    sessions_result = await db.execute(
        select(SessionModel).where(
            SessionModel.project_id == project_id,
            sqlfunc.date(SessionModel.started_at) >= week_ago,
        ).order_by(SessionModel.started_at.desc())
    )
    sessions = sessions_result.scalars().all()

    # 최근 7일 커밋
    commits_result = await db.execute(
        select(CommitStat).where(
            CommitStat.project_id == project_id,
            CommitStat.stat_date >= week_ago,
        ).order_by(CommitStat.stat_date.desc())
    )
    commits = commits_result.scalars().all()

    # 최근 7일 완료된 할일
    todos_result = await db.execute(
        select(Todo).where(
            Todo.project_id == project_id,
            Todo.status == "done",
            sqlfunc.date(Todo.completed_at) >= week_ago,
        )
    )
    done_todos = todos_result.scalars().all()

    # 최근 7일 작업 로그
    logs_result = await db.execute(
        select(WorkLog).where(
            WorkLog.project_id == project_id,
            WorkLog.log_date >= week_ago,
        ).order_by(WorkLog.log_date.desc())
    )
    work_logs = logs_result.scalars().all()

    total_commits = sum(c.commit_count for c in commits)
    total_add = sum(c.additions for c in commits)
    total_del = sum(c.deletions for c in commits)

    context = f"""프로젝트: {project.name}
기간: 최근 7일 ({week_ago} ~ {date.today()})

세션 ({len(sessions)}건):
{chr(10).join(f'- {s.title} ({s.status})' for s in sessions) or '없음'}

커밋: {total_commits}건 (+{total_add} -{total_del})

완료된 할일 ({len(done_todos)}건):
{chr(10).join(f'- {t.title}' for t in done_todos) or '없음'}

작업 로그 ({len(work_logs)}건):
{chr(10).join(f'- {w.log_date}: {(w.content or "")[:100]}' for w in work_logs) or '없음'}"""

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                "https://api.openai.com/v1/chat/completions",
                headers={"Authorization": f"Bearer {settings.openai_api_key}"},
                json={
                    "model": "gpt-4o",
                    "messages": [
                        {"role": "system", "content": "당신은 1인 개발자의 프로젝트 관제 AI입니다. 주어진 데이터를 기반으로 이번주 작업 요약을 한국어로 3~5문장으로 작성하세요. 핵심 성과와 진행 상황에 집중하세요. 마크다운 형식으로 작성하세요."},
                        {"role": "user", "content": context},
                    ],
                    "temperature": 0.5,
                    "max_tokens": 500,
                },
            )
            resp.raise_for_status()
            summary = resp.json()["choices"][0]["message"]["content"]
            return {
                "ok": True,
                "summary": summary,
                "stats": {
                    "sessions": len(sessions),
                    "commits": total_commits,
                    "additions": total_add,
                    "deletions": total_del,
                    "todos_done": len(done_todos),
                    "work_logs": len(work_logs),
                },
            }
    except Exception as e:
        return {"error": f"요약 생성 실패: {str(e)}"}
