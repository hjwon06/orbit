"""Seed initial projects, agents, and milestones into ORBIT."""
import asyncio
from datetime import date
from app.database import async_session, engine, Base
from app.models import Project, Agent, Milestone
from sqlalchemy import select


ORBIT_PROJECT_YAML = """\
agents:
  A0:
    name: 인프라
    mcp: [postgres]
  A1:
    name: 백엔드 API
    mcp: [context7, postgres]
  A2:
    name: 프론트엔드 UI
    mcp: [context7, playwright]
  A3:
    name: AI/연동
    mcp: [github, context7]
  A4:
    name: 데이터 분석
    mcp: [github]
  QA:
    name: 검증
    mcp: [playwright, sequential-thinking]
"""

SEED_PROJECTS = [
    {
        "name": "ORBIT",
        "slug": "orbit",
        "description": "1인 개발자 프로젝트 관제 허브",
        "status": "active",
        "repo_url": "",
        "stack": "FastAPI + Jinja2 + HTMX + Tailwind + PostgreSQL",
        "color": "#534AB7",
        "project_yaml": ORBIT_PROJECT_YAML,
        "local_path": r"C:\Users\win11\Desktop\Project\orbit",
    },
]

SEED_AGENTS = {
    "orbit": [
        ("A0", "인프라", "opus"),
        ("A1", "백엔드 API", "opus"),
        ("A2", "프론트엔드 UI", "opus"),
        ("A3", "AI/연동", "opus"),
        ("A4", "데이터 분석", "opus"),
        ("QA", "검증", "opus"),
    ],
}


SEED_MILESTONES = {
    "orbit": [
        ("S0 — 프로젝트 뼈대", "done", "2026-03-10", "2026-03-16", 0),
        ("S1 — 에이전트 모니터", "done", "2026-03-17", "2026-03-17", 1),
        ("S2 — 타임라인/간트", "done", "2026-03-17", "2026-03-17", 2),
        ("S3 — 세션 로그", "done", "2026-03-17", "2026-03-17", 3),
        ("S4 — 작업 로그/커밋", "done", "2026-03-17", "2026-03-17", 4),
        ("S5 — 인프라 비용", "done", "2026-03-17", "2026-03-17", 5),
        ("S6 — AI 할일", "done", "2026-03-17", "2026-03-18", 6),
        ("S7 — 인프라 관리", "done", "2026-03-17", "2026-03-18", 7),
        ("S8 — 대시보드 트렌드", "done", "2026-03-18", "2026-03-18", 8),
        ("S9 — UI 보강", "done", "2026-03-18", "2026-03-18", 9),
        ("S10 — 오케스트레이터", "done", "2026-03-18", "2026-03-18", 10),
        ("S11 — Glass 디자인", "done", "2026-03-18", "2026-03-18", 11),
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
                    db.add(Agent(project_id=project.id, agent_code=code, agent_name=name, model_tier=tier, source="local"))
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
