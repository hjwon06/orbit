from datetime import datetime, timezone
from sqlalchemy import select, update, delete
from sqlalchemy.ext.asyncio import AsyncSession
from app.models import Todo, Project, Milestone, Session as SessionModel
from app.schemas.todo import TodoCreate, TodoUpdate
from app.config import get_settings

try:
    import httpx
    HAS_HTTPX = True
except ImportError:
    HAS_HTTPX = False


async def get_todos_by_project(db: AsyncSession, project_id: int):
    stmt = (
        select(Todo)
        .where(Todo.project_id == project_id)
        .order_by(
            Todo.status.asc(),
            Todo.priority.desc(),
            Todo.created_at.desc(),
        )
    )
    result = await db.execute(stmt)
    return result.scalars().all()


async def get_todo(db: AsyncSession, todo_id: int):
    result = await db.execute(select(Todo).where(Todo.id == todo_id))
    return result.scalar_one_or_none()


async def create_todo(db: AsyncSession, data: TodoCreate) -> Todo:
    todo = Todo(**data.model_dump())
    db.add(todo)
    await db.commit()
    await db.refresh(todo)
    return todo


async def update_todo(db: AsyncSession, todo_id: int, data: TodoUpdate) -> Todo | None:
    values = data.model_dump(exclude_unset=True)
    if not values:
        return await get_todo(db, todo_id)
    if values.get("status") == "done":
        values["completed_at"] = datetime.now(timezone.utc)
    elif values.get("status") == "open":
        values["completed_at"] = None
    await db.execute(update(Todo).where(Todo.id == todo_id).values(**values))
    await db.commit()
    return await get_todo(db, todo_id)


async def delete_todo(db: AsyncSession, todo_id: int) -> bool:
    result = await db.execute(delete(Todo).where(Todo.id == todo_id))
    await db.commit()
    return result.rowcount > 0


async def ai_recommend_todos(db: AsyncSession, project_id: int) -> list[Todo]:
    """GPT-4o로 프로젝트 상태 분석 후 할일 추천."""
    settings = get_settings()
    if not settings.openai_api_key or not HAS_HTTPX:
        return await _fallback_recommendations(db, project_id)

    project_result = await db.execute(select(Project).where(Project.id == project_id))
    project = project_result.scalar_one_or_none()
    if not project:
        return []

    milestones_result = await db.execute(
        select(Milestone).where(Milestone.project_id == project_id).order_by(Milestone.sort_order)
    )
    milestones = milestones_result.scalars().all()

    sessions_result = await db.execute(
        select(SessionModel).where(SessionModel.project_id == project_id).order_by(SessionModel.started_at.desc()).limit(5)
    )
    recent_sessions = sessions_result.scalars().all()

    existing_result = await db.execute(
        select(Todo).where(Todo.project_id == project_id, Todo.status == "open")
    )
    existing_todos = existing_result.scalars().all()

    done_milestones = [m for m in milestones if m.status == "done"]
    active_milestones = [m for m in milestones if m.status != "done"]

    context = f"""프로젝트: {project.name} — {project.description}
스택: {project.stack}

[이미 완료된 마일스톤] (이 작업들은 끝났으므로 추천에서 제외하세요):
{chr(10).join(f'- ✅ {m.title}' for m in done_milestones) or '없음'}

[진행 중/계획된 마일스톤] (이 작업들을 중심으로 추천하세요):
{chr(10).join(f'- {m.title} ({m.status})' for m in active_milestones) or '없음 — 새로운 기능을 제안하세요'}

최근 세션:
{chr(10).join(f'- {s.title} ({s.status})' for s in recent_sessions)}

현재 열린 할일 (중복 추천 금지):
{chr(10).join(f'- {t.title} ({t.priority})' for t in existing_todos) or '없음'}"""

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                "https://api.openai.com/v1/chat/completions",
                headers={"Authorization": f"Bearer {settings.openai_api_key}"},
                json={
                    "model": "gpt-4o",
                    "messages": [
                        {"role": "system", "content": "당신은 1인 개발자의 프로젝트 관제 AI입니다.\n\n중요 맥락:\n- 이 프로젝트는 1인 개발자가 혼자 사용하는 로컬 관제 도구입니다.\n- 서버는 로컬 Docker로만 실행하며, 배포/클라우드 운영 안 합니다.\n- 사용자는 1명(관리자 본인)이므로 멀티유저, 피드백 시스템, 알림 시스템 등은 불필요합니다.\n- CI/CD, 성능 최적화, 보안 강화 같은 운영 관점 작업은 추천하지 마세요.\n- 개발자의 생산성을 직접 높여주는 기능이나, 대시보드를 더 유용하게 만드는 개선을 추천하세요.\n\n규칙:\n1. 이미 완료된(✅) 마일스톤 관련 작업은 절대 추천하지 마세요.\n2. 진행 중/계획된 마일스톤이 있으면 그것을 중심으로 추천하세요.\n3. 진행 중/계획된 마일스톤이 없으면 프로젝트에 의미 있는 새로운 기능이나 개선을 제안하세요.\n4. 현재 열린 할일과 중복되는 추천은 하지 마세요.\n5. 반드시 한국어로 작성하세요.\n\n다음에 해야 할 작업 3개를 JSON 배열로 반환하세요. 형식: [{\"title\": \"...\", \"description\": \"...\", \"priority\": \"high|medium|low\", \"reasoning\": \"...\"}]. JSON만 반환하세요."},
                        {"role": "user", "content": context},
                    ],
                    "temperature": 0.7,
                    "max_tokens": 1000,
                },
            )
            resp.raise_for_status()
            data = resp.json()
            content = data["choices"][0]["message"]["content"]

            import json
            content = content.strip()
            if content.startswith("```"):
                content = content.split("\n", 1)[1].rsplit("```", 1)[0]
            items = json.loads(content)

            created = []
            for item in items[:3]:
                todo = Todo(
                    project_id=project_id,
                    title=item["title"],
                    description=item.get("description", ""),
                    priority=item.get("priority", "medium"),
                    source="ai",
                    ai_reasoning=item.get("reasoning", ""),
                )
                db.add(todo)
                created.append(todo)
            await db.commit()
            for t in created:
                await db.refresh(t)
            return created

    except Exception as e:
        print(f"[ORBIT] AI recommendation error: {e}")
        return await _fallback_recommendations(db, project_id)


async def _fallback_recommendations(db: AsyncSession, project_id: int) -> list[Todo]:
    """OpenAI 키가 없을 때 기본 추천."""
    milestones_result = await db.execute(
        select(Milestone).where(
            Milestone.project_id == project_id,
            Milestone.status.in_(["planned", "active"]),
        ).order_by(Milestone.sort_order).limit(3)
    )
    milestones = milestones_result.scalars().all()

    created = []
    for m in milestones:
        todo = Todo(
            project_id=project_id,
            title=f"{m.title} 진행하기",
            description=f"마일스톤 '{m.title}'의 다음 단계를 진행합니다.",
            priority="high" if m.status == "active" else "medium",
            source="ai",
            ai_reasoning="활성/계획된 마일스톤 기반 자동 추천 (OpenAI 키 미설정)",
        )
        db.add(todo)
        created.append(todo)
    await db.commit()
    for t in created:
        await db.refresh(t)
    return created
