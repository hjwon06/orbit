from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from datetime import datetime, timezone
from app.models import Agent, AgentRun, Project
from app.schemas.agent import AgentCreate, AgentUpdate, AgentRunCreate, AgentRunFinish, AgentSyncRequest


async def get_agents_by_project(db: AsyncSession, project_id: int):
    stmt = (
        select(Agent)
        .where(Agent.project_id == project_id, Agent.deleted_at.is_(None))
        .options(selectinload(Agent.runs))
        .order_by(Agent.agent_code)
    )
    result = await db.execute(stmt)
    agents = result.scalars().all()
    for agent in agents:
        agent.recent_runs = agent.runs[:10]  # type: ignore[attr-defined]
    return agents


async def get_agent(db: AsyncSession, agent_id: int):
    stmt = select(Agent).where(Agent.id == agent_id, Agent.deleted_at.is_(None)).options(selectinload(Agent.runs))
    result = await db.execute(stmt)
    agent = result.scalar_one_or_none()
    if agent:
        agent.recent_runs = agent.runs[:10]  # type: ignore[attr-defined]
    return agent


async def create_agent(db: AsyncSession, data: AgentCreate) -> Agent:
    agent = Agent(**data.model_dump())
    db.add(agent)
    await db.commit()
    await db.refresh(agent)
    agent.recent_runs = []  # type: ignore[attr-defined]
    return agent


async def update_agent(db: AsyncSession, agent_id: int, data: AgentUpdate) -> Agent | None:
    values = data.model_dump(exclude_unset=True)
    if not values:
        return await get_agent(db, agent_id)
    await db.execute(update(Agent).where(Agent.id == agent_id).values(**values))
    await db.commit()
    return await get_agent(db, agent_id)


async def heartbeat_agent(db: AsyncSession, agent_id: int) -> Agent | None:
    now = datetime.now(timezone.utc)
    await db.execute(
        update(Agent).where(Agent.id == agent_id).values(last_heartbeat=now)
    )
    await db.commit()
    return await get_agent(db, agent_id)


async def start_run(db: AsyncSession, data: AgentRunCreate) -> AgentRun:
    run = AgentRun(agent_id=data.agent_id, task_name=data.task_name)
    db.add(run)
    await db.execute(
        update(Agent)
        .where(Agent.id == data.agent_id)
        .values(status="running", current_task=data.task_name, last_heartbeat=datetime.now(timezone.utc))
    )
    await db.commit()
    await db.refresh(run)
    return run


async def finish_run(db: AsyncSession, run_id: int, data: AgentRunFinish) -> AgentRun | None:
    now = datetime.now(timezone.utc)
    await db.execute(
        update(AgentRun)
        .where(AgentRun.id == run_id)
        .values(status=data.status, error_log=data.error_log, duration_sec=data.duration_sec, finished_at=now)
    )
    result = await db.execute(select(AgentRun).where(AgentRun.id == run_id))
    run = result.scalar_one_or_none()
    if run:
        new_status = "error" if data.status == "error" else "idle"
        await db.execute(
            update(Agent)
            .where(Agent.id == run.agent_id)
            .values(status=new_status, current_task="")
        )
    await db.commit()
    return run


async def get_runs_by_agent(db: AsyncSession, agent_id: int, limit: int = 10):
    stmt = (
        select(AgentRun)
        .where(AgentRun.agent_id == agent_id)
        .order_by(AgentRun.started_at.desc())
        .limit(limit)
    )
    result = await db.execute(stmt)
    return result.scalars().all()


async def delete_agent(db: AsyncSession, agent_id: int) -> bool:
    result = await db.execute(
        update(Agent).where(Agent.id == agent_id).values(deleted_at=datetime.now(timezone.utc))
    )
    await db.commit()
    return result.rowcount > 0


async def sync_agents(db: AsyncSession, project_id: int, data: AgentSyncRequest) -> dict:
    # 1. 기존 에이전트 목록 조회 (deleted_at IS NULL)
    stmt = select(Agent).where(Agent.project_id == project_id, Agent.deleted_at.is_(None))
    result = await db.execute(stmt)
    existing = {a.agent_code: a for a in result.scalars().all()}

    requested_codes = {item.agent_code for item in data.agents}
    created = 0
    updated = 0
    deleted = 0

    # 2. 요청에 있는 agent_code 처리
    for item in data.agents:
        if item.agent_code in existing:
            # UPDATE
            agent = existing[item.agent_code]
            agent.agent_name = item.agent_name
            agent.model_tier = item.model_tier
            updated += 1
        else:
            # CREATE
            agent = Agent(
                project_id=project_id,
                agent_code=item.agent_code,
                agent_name=item.agent_name,
                model_tier=item.model_tier,
            )
            db.add(agent)
            created += 1

    # 3. 요청에 없는 agent_code → soft DELETE
    for code, agent in existing.items():
        if code not in requested_codes:
            agent.deleted_at = datetime.now(timezone.utc)
            deleted += 1

    await db.commit()
    return {"created": created, "updated": updated, "deleted": deleted}


async def get_agent_by_code(db: AsyncSession, project_slug: str, agent_code: str) -> Agent | None:
    stmt = (
        select(Agent)
        .join(Project)
        .where(Project.slug == project_slug, Agent.agent_code == agent_code, Agent.deleted_at.is_(None))
        .options(selectinload(Agent.runs))
    )
    result = await db.execute(stmt)
    agent = result.scalar_one_or_none()
    if agent:
        agent.recent_runs = agent.runs[:10]  # type: ignore[attr-defined]
    return agent
