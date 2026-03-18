"""Seed initial projects, agents, and milestones into ORBIT."""
import asyncio
from datetime import date
from app.database import async_session, engine, Base
from app.models import Project, Agent, Milestone
from sqlalchemy import select


SEED_PROJECTS = [
    {
        "name": "Giniz",
        "slug": "giniz",
        "description": "부동산 중개 SaaS 플랫폼",
        "status": "active",
        "repo_url": "",
        "stack": "Spring Boot + Flutter + MSSQL",
        "color": "#185FA5",
    },
    {
        "name": "DAESIN",
        "slug": "daesin",
        "description": "법인 부동산 CRM — 시화반월/남동 산업단지",
        "status": "active",
        "repo_url": "",
        "stack": "FastAPI + Flutter + PostgreSQL + pgvector",
        "color": "#0F6E56",
    },
    {
        "name": "ORBIT",
        "slug": "orbit",
        "description": "1인 개발자 프로젝트 관제 허브",
        "status": "active",
        "repo_url": "",
        "stack": "FastAPI + Jinja2 + HTMX + Tailwind + PostgreSQL",
        "color": "#534AB7",
    },
]

SEED_AGENTS = {
    "daesin": [
        ("A0", "Infrastructure", "opus"),
        ("A1", "Public Data", "sonnet"),
        ("A2", "Corporate CRM", "sonnet"),
        ("A3", "AI-RAG", "opus"),
        ("A4", "Properties/Transactions", "sonnet"),
    ],
    "orbit": [
        ("A0", "Infrastructure", "opus"),
        ("A1", "Backend API", "sonnet"),
        ("A2", "Frontend UI", "sonnet"),
        ("A3", "AI & Integration", "opus"),
        ("A4", "Data & Analytics", "sonnet"),
        ("QA", "QA Verification", "opus"),
    ],
}


SEED_MILESTONES = {
    "orbit": [
        ("Sprint 0 — 프로젝트 뼈대", "done", "2026-03-10", "2026-03-16", 0),
        ("Sprint 1 — 에이전트 모니터", "done", "2026-03-17", "2026-03-17", 1),
        ("Sprint 2 — 타임라인", "active", "2026-03-17", "2026-03-23", 2),
        ("Sprint 3 — 세션 로그", "planned", "2026-03-24", "2026-03-30", 3),
    ],
    "daesin": [
        ("Phase 1 — MVP 설계", "done", "2026-03-01", "2026-03-14", 0),
        ("Phase 2 — 공공데이터 수집", "active", "2026-03-15", "2026-03-28", 1),
        ("Phase 3 — CRM 코어", "planned", "2026-03-29", "2026-04-11", 2),
    ],
}


async def seed():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with async_session() as db:
        for data in SEED_PROJECTS:
            exists = await db.execute(
                select(Project).where(Project.slug == data["slug"])
            )
            if not exists.scalar_one_or_none():
                db.add(Project(**data))
                print(f"  + Project: {data['name']}")
            else:
                print(f"  ~ Project: {data['name']} (exists)")
        await db.commit()

        for slug, agents in SEED_AGENTS.items():
            result = await db.execute(select(Project).where(Project.slug == slug))
            project = result.scalar_one_or_none()
            if not project:
                continue
            for code, name, tier in agents:
                exists = await db.execute(
                    select(Agent).where(Agent.project_id == project.id, Agent.agent_code == code)
                )
                if not exists.scalar_one_or_none():
                    db.add(Agent(project_id=project.id, agent_code=code, agent_name=name, model_tier=tier))
                    print(f"  + Agent: {slug}/{code} {name}")
                else:
                    print(f"  ~ Agent: {slug}/{code} (exists)")
        await db.commit()

        for slug, milestones in SEED_MILESTONES.items():
            result = await db.execute(select(Project).where(Project.slug == slug))
            project = result.scalar_one_or_none()
            if not project:
                continue
            for title, status, start, end, sort in milestones:
                exists = await db.execute(
                    select(Milestone).where(
                        Milestone.project_id == project.id,
                        Milestone.title == title,
                    )
                )
                if not exists.scalar_one_or_none():
                    db.add(Milestone(
                        project_id=project.id, title=title, status=status,
                        start_date=date.fromisoformat(start),
                        end_date=date.fromisoformat(end),
                        sort_order=sort,
                    ))
                    print(f"  + Milestone: {slug}/{title}")
                else:
                    print(f"  ~ Milestone: {slug}/{title} (exists)")
        await db.commit()

    print("\nSeed complete.")


if __name__ == "__main__":
    asyncio.run(seed())
