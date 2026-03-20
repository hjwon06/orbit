# ORBIT — 1인 개발자 프로젝트 관제 허브 (Sprint 0+1 전체 스펙)

> Claude Code에서 이 파일을 읽고 전체 프로젝트를 생성해주세요.
> 모든 파일을 아래 명시된 경로에 정확히 생성하면 됩니다.

---

## 프로젝트 개요

- **이름**: ORBIT
- **목적**: 멀티 프로젝트 운영하는 솔로 개발자를 위한 통합 관제 대시보드
- **스택**: Python 3.12 + FastAPI + Jinja2 + HTMX + Tailwind CSS + PostgreSQL 16 + pgvector
- **배포**: Docker Compose → Coolify + Vultr Seoul VPS
- **디자인**: Pretendard 폰트, warm off-white(#FAFAF7), accent purple(#534AB7), shadow-sm max, rounded-lg max

## 디렉토리 구조

```
orbit/
├── .env.example
├── .gitignore
├── Dockerfile
├── README.md
├── alembic.ini
├── docker-compose.yml
├── requirements.txt
├── seed.py
├── alembic/
│   ├── env.py

│   ├── script.py.mako
│   └── versions/
│       ├── 001_sprint0_create_ob_projects.py
│       └── 002_sprint1_create_agents.py
└── app/
    ├── __init__.py          (빈 파일)
    ├── config.py
    ├── database.py
    ├── main.py
    ├── api/
    │   ├── __init__.py
    │   ├── projects.py
    │   └── agents.py
    ├── models/
    │   └── __init__.py
    ├── pages/
    │   └── __init__.py
    ├── schemas/
    │   ├── __init__.py
    │   ├── project.py
    │   └── agent.py
    ├── services/
    │   ├── __init__.py      (project 서비스)
    │   └── agent_service.py
    ├── static/
    │   ├── css/             (빈 디렉토리, 향후 사용)
    │   └── js/              (빈 디렉토리, 향후 사용)
    └── templates/
        ├── base.html
        ├── dashboard.html
        ├── project_form.html
        ├── project_detail.html
        ├── agents.html
        └── partials/
            └── agent_cards.html
```

---

## 파일 내용

### `requirements.txt`

```
fastapi==0.115.6
uvicorn[standard]==0.34.0
sqlalchemy[asyncio]==2.0.36
asyncpg==0.30.0
psycopg2-binary==2.9.10
pydantic==2.10.3
pydantic-settings==2.7.0
jinja2==3.1.4
python-multipart==0.0.18
alembic==1.14.0
pgvector==0.3.6
httpx==0.28.1
```

### `.env.example`

```
ORBIT_DATABASE_URL=postgresql+asyncpg://orbit:orbit@localhost:5432/orbit
ORBIT_DATABASE_URL_SYNC=postgresql://orbit:orbit@localhost:5432/orbit
ORBIT_DEBUG=true

# GitHub (Sprint 6)
ORBIT_GITHUB_TOKEN=
ORBIT_GITHUB_WEBHOOK_SECRET=

# AWS (Sprint 5)
ORBIT_AWS_ACCESS_KEY_ID=
ORBIT_AWS_SECRET_ACCESS_KEY=
ORBIT_AWS_REGION=ap-northeast-2

# Vultr (Sprint 5)
ORBIT_VULTR_API_KEY=

# OpenAI (Sprint 6 - AI recommendations)
ORBIT_OPENAI_API_KEY=

# Obsidian (Sprint 4)
ORBIT_OBSIDIAN_VAULT_PATH=C:\Users\win11\Desktop\ObsidianVault
```

### `.gitignore`

```
__pycache__/
*.pyc
.env
*.egg-info/
dist/
build/
.venv/
venv/
*.db
.idea/
.vscode/
```

### `Dockerfile`

```dockerfile
FROM python:3.12-slim

WORKDIR /app

RUN pip install --no-cache-dir --upgrade pip

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### `docker-compose.yml`

```yaml
services:
  db:
    image: pgvector/pgvector:pg16
    container_name: orbit-db
    environment:
      POSTGRES_DB: orbit
      POSTGRES_USER: orbit
      POSTGRES_PASSWORD: orbit
    ports:
      - "5432:5432"
    volumes:
      - orbit_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U orbit"]
      interval: 5s
      timeout: 5s
      retries: 5

  app:
    build: .
    container_name: orbit-app
    ports:
      - "8000:8000"
    environment:
      ORBIT_DATABASE_URL: postgresql+asyncpg://orbit:orbit@db:5432/orbit
      ORBIT_DATABASE_URL_SYNC: postgresql://orbit:orbit@db:5432/orbit
      ORBIT_DEBUG: "true"
    volumes:
      - ./app:/app/app
    depends_on:
      db:
        condition: service_healthy
    command: uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

volumes:
  orbit_data:
```

### `alembic.ini`

```ini
[alembic]
script_location = alembic
prepend_sys_path = .
sqlalchemy.url = postgresql://orbit:orbit@localhost:5432/orbit

[loggers]
keys = root,sqlalchemy,alembic

[handlers]
keys = console

[formatters]
keys = generic

[logger_root]
level = WARN
handlers = console

[logger_sqlalchemy]
level = WARN
handlers =
qualname = sqlalchemy.engine

[logger_alembic]
level = INFO
handlers =
qualname = alembic

[handler_console]
class = StreamHandler
args = (sys.stderr,)
level = NOTSET
formatter = generic

[formatter_generic]
format = %(levelname)-5.5s [%(name)s] %(message)s
datefmt = %H:%M:%S
```

### `alembic/env.py`

```python
from logging.config import fileConfig
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config
from alembic import context
import asyncio

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

from app.database import Base
from app.models import Project, Agent, AgentRun  # noqa: F401

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
        url=config.get_main_option("sqlalchemy.url").replace(
            "postgresql://", "postgresql+asyncpg://"
        ),
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


def run_migrations_online() -> None:
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
```

### `alembic/script.py.mako`

```mako
"""${message}

Revision ID: ${up_revision}
Revises: ${down_revision | comma,n}
Create Date: ${create_date}
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
${imports if imports else ""}

revision: str = ${repr(up_revision)}
down_revision: Union[str, None] = ${repr(down_revision)}
branch_labels: Union[str, Sequence[str], None] = ${repr(branch_labels)}
depends_on: Union[str, Sequence[str], None] = ${repr(depends_on)}


def upgrade() -> None:
    ${upgrades if upgrades else "pass"}


def downgrade() -> None:
    ${downgrades if downgrades else "pass"}
```

### `alembic/versions/001_sprint0_create_ob_projects.py`

```python
"""sprint0 create ob_projects

Revision ID: 001_sprint0
Revises:
Create Date: 2026-03-17
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "001_sprint0"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.create_table(
        "ob_projects",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("slug", sa.String(50), unique=True, nullable=False, index=True),
        sa.Column("description", sa.Text(), server_default=""),
        sa.Column("status", sa.String(20), server_default="active"),
        sa.Column("repo_url", sa.String(500), server_default=""),
        sa.Column("stack", sa.String(200), server_default=""),
        sa.Column("color", sa.String(7), server_default="#534AB7"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("ob_projects")
```

### `alembic/versions/002_sprint1_create_agents.py`

```python
"""sprint1 create ob_agents and ob_agent_runs

Revision ID: 002_sprint1
Revises: 001_sprint0
Create Date: 2026-03-17
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "002_sprint1"
down_revision: Union[str, None] = "001_sprint0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "ob_agents",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("project_id", sa.Integer(), sa.ForeignKey("ob_projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("agent_code", sa.String(10), nullable=False),
        sa.Column("agent_name", sa.String(100), nullable=False),
        sa.Column("model_tier", sa.String(20), server_default="sonnet"),
        sa.Column("status", sa.String(20), server_default="idle"),
        sa.Column("current_task", sa.String(200), server_default=""),
        sa.Column("last_heartbeat", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_ob_agents_project_code", "ob_agents", ["project_id", "agent_code"], unique=True)

    op.create_table(
        "ob_agent_runs",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("agent_id", sa.Integer(), sa.ForeignKey("ob_agents.id", ondelete="CASCADE"), nullable=False),
        sa.Column("task_name", sa.String(200), nullable=False),
        sa.Column("status", sa.String(20), server_default="running"),
        sa.Column("error_log", sa.Text(), server_default=""),
        sa.Column("duration_sec", sa.Integer(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_ob_agent_runs_agent_id", "ob_agent_runs", ["agent_id"])
    op.create_index("ix_ob_agent_runs_status", "ob_agent_runs", ["status"])


def downgrade() -> None:
    op.drop_table("ob_agent_runs")
    op.drop_table("ob_agents")
```

---

### `app/__init__.py`

```python
# 빈 파일
```

### `app/config.py`

```python
from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    app_name: str = "ORBIT"
    app_version: str = "0.1.0"
    debug: bool = True

    database_url: str = "postgresql+asyncpg://orbit:orbit@localhost:5432/orbit"
    database_url_sync: str = "postgresql://orbit:orbit@localhost:5432/orbit"

    github_token: str = ""
    github_webhook_secret: str = ""

    aws_access_key_id: str = ""
    aws_secret_access_key: str = ""
    aws_region: str = "ap-northeast-2"

    vultr_api_key: str = ""

    openai_api_key: str = ""

    obsidian_vault_path: str = r"C:\Users\win11\Desktop\ObsidianVault"

    class Config:
        env_file = ".env"
        env_prefix = "ORBIT_"


@lru_cache
def get_settings() -> Settings:
    return Settings()
```

### `app/database.py`

```python
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import DeclarativeBase
from app.config import get_settings

settings = get_settings()

engine = create_async_engine(
    settings.database_url,
    echo=settings.debug,
    pool_size=5,
    max_overflow=10,
)

async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


async def get_db():
    async with async_session() as session:
        try:
            yield session
        finally:
            await session.close()
```

### `app/main.py`

```python
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from contextlib import asynccontextmanager
from app.config import get_settings
from app.database import engine, Base
from app.api import api_router
from app.pages import router as pages_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    await engine.dispose()


settings = get_settings()

app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    lifespan=lifespan,
)

app.mount("/static", StaticFiles(directory="app/static"), name="static")
app.include_router(api_router)
app.include_router(pages_router)
```

### `app/models/__init__.py`

```python
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, func
from sqlalchemy.orm import relationship
from app.database import Base


class Project(Base):
    __tablename__ = "ob_projects"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), nullable=False)
    slug = Column(String(50), unique=True, nullable=False, index=True)
    description = Column(Text, default="")
    status = Column(String(20), default="active")
    repo_url = Column(String(500), default="")
    stack = Column(String(200), default="")
    color = Column(String(7), default="#534AB7")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    agents = relationship("Agent", back_populates="project", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Project {self.slug}>"


class Agent(Base):
    __tablename__ = "ob_agents"

    id = Column(Integer, primary_key=True, autoincrement=True)
    project_id = Column(Integer, ForeignKey("ob_projects.id", ondelete="CASCADE"), nullable=False)
    agent_code = Column(String(10), nullable=False)
    agent_name = Column(String(100), nullable=False)
    model_tier = Column(String(20), default="sonnet")
    status = Column(String(20), default="idle")
    current_task = Column(String(200), default="")
    last_heartbeat = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    project = relationship("Project", back_populates="agents")
    runs = relationship("AgentRun", back_populates="agent", cascade="all, delete-orphan", order_by="AgentRun.started_at.desc()")

    def __repr__(self):
        return f"<Agent {self.agent_code}:{self.agent_name}>"


class AgentRun(Base):
    __tablename__ = "ob_agent_runs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    agent_id = Column(Integer, ForeignKey("ob_agents.id", ondelete="CASCADE"), nullable=False)
    task_name = Column(String(200), nullable=False)
    status = Column(String(20), default="running")
    error_log = Column(Text, default="")
    duration_sec = Column(Integer, nullable=True)
    started_at = Column(DateTime(timezone=True), server_default=func.now())
    finished_at = Column(DateTime(timezone=True), nullable=True)

    agent = relationship("Agent", back_populates="runs")

    def __repr__(self):
        return f"<AgentRun {self.task_name}:{self.status}>"
```

### `app/schemas/__init__.py`

```python
from app.schemas.project import ProjectCreate, ProjectUpdate, ProjectResponse
from app.schemas.agent import AgentCreate, AgentUpdate, AgentRunCreate, AgentRunFinish, AgentResponse, AgentRunResponse

__all__ = [
    "ProjectCreate", "ProjectUpdate", "ProjectResponse",
    "AgentCreate", "AgentUpdate", "AgentRunCreate", "AgentRunFinish",
    "AgentResponse", "AgentRunResponse",
]
```

### `app/schemas/project.py`

```python
from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional


class ProjectCreate(BaseModel):
    name: str = Field(..., max_length=100)
    slug: str = Field(..., max_length=50, pattern=r"^[a-z0-9\-]+$")
    description: str = ""
    repo_url: str = ""
    stack: str = ""
    color: str = "#534AB7"


class ProjectUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None
    repo_url: Optional[str] = None
    stack: Optional[str] = None
    color: Optional[str] = None


class ProjectResponse(BaseModel):
    id: int
    name: str
    slug: str
    description: str
    status: str
    repo_url: str
    stack: str
    color: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
```

### `app/schemas/agent.py`

```python
from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional


class AgentCreate(BaseModel):
    project_id: int
    agent_code: str = Field(..., max_length=10)
    agent_name: str = Field(..., max_length=100)
    model_tier: str = "sonnet"


class AgentUpdate(BaseModel):
    status: Optional[str] = None
    current_task: Optional[str] = None
    last_heartbeat: Optional[datetime] = None


class AgentRunCreate(BaseModel):
    agent_id: int
    task_name: str = Field(..., max_length=200)


class AgentRunFinish(BaseModel):
    status: str  # success, error, cancelled
    error_log: str = ""
    duration_sec: Optional[int] = None


class AgentRunResponse(BaseModel):
    id: int
    agent_id: int
    task_name: str
    status: str
    error_log: str
    duration_sec: Optional[int]
    started_at: datetime
    finished_at: Optional[datetime]

    model_config = {"from_attributes": True}


class AgentResponse(BaseModel):
    id: int
    project_id: int
    agent_code: str
    agent_name: str
    model_tier: str
    status: str
    current_task: str
    last_heartbeat: Optional[datetime]
    created_at: datetime
    recent_runs: list[AgentRunResponse] = []

    model_config = {"from_attributes": True}
```

### `app/services/__init__.py`

```python
from sqlalchemy import select, update, delete
from sqlalchemy.ext.asyncio import AsyncSession
from app.models import Project
from app.schemas.project import ProjectCreate, ProjectUpdate


async def get_projects(db: AsyncSession, status: str | None = None):
    stmt = select(Project).order_by(Project.created_at.desc())
    if status:
        stmt = stmt.where(Project.status == status)
    result = await db.execute(stmt)
    return result.scalars().all()


async def get_project_by_slug(db: AsyncSession, slug: str):
    result = await db.execute(select(Project).where(Project.slug == slug))
    return result.scalar_one_or_none()


async def get_project_by_id(db: AsyncSession, project_id: int):
    result = await db.execute(select(Project).where(Project.id == project_id))
    return result.scalar_one_or_none()


async def create_project(db: AsyncSession, data: ProjectCreate) -> Project:
    project = Project(**data.model_dump())
    db.add(project)
    await db.commit()
    await db.refresh(project)
    return project


async def update_project(db: AsyncSession, project_id: int, data: ProjectUpdate) -> Project | None:
    values = data.model_dump(exclude_unset=True)
    if not values:
        return await get_project_by_id(db, project_id)
    await db.execute(update(Project).where(Project.id == project_id).values(**values))
    await db.commit()
    return await get_project_by_id(db, project_id)


async def delete_project(db: AsyncSession, project_id: int) -> bool:
    result = await db.execute(delete(Project).where(Project.id == project_id))
    await db.commit()
    return result.rowcount > 0
```

### `app/services/agent_service.py`

```python
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from datetime import datetime, timezone
from app.models import Agent, AgentRun
from app.schemas.agent import AgentCreate, AgentUpdate, AgentRunCreate, AgentRunFinish


async def get_agents_by_project(db: AsyncSession, project_id: int):
    stmt = (
        select(Agent)
        .where(Agent.project_id == project_id)
        .options(selectinload(Agent.runs))
        .order_by(Agent.agent_code)
    )
    result = await db.execute(stmt)
    agents = result.scalars().all()
    for agent in agents:
        agent.recent_runs = agent.runs[:10]
    return agents


async def get_agent(db: AsyncSession, agent_id: int):
    stmt = select(Agent).where(Agent.id == agent_id).options(selectinload(Agent.runs))
    result = await db.execute(stmt)
    agent = result.scalar_one_or_none()
    if agent:
        agent.recent_runs = agent.runs[:10]
    return agent


async def create_agent(db: AsyncSession, data: AgentCreate) -> Agent:
    agent = Agent(**data.model_dump())
    db.add(agent)
    await db.commit()
    await db.refresh(agent)
    agent.recent_runs = []
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
```

### `app/api/__init__.py`

```python
from fastapi import APIRouter
from app.api.projects import router as projects_router
from app.api.agents import router as agents_router

api_router = APIRouter()
api_router.include_router(projects_router)
api_router.include_router(agents_router)
```

### `app/api/projects.py`

```python
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.schemas.project import ProjectCreate, ProjectUpdate, ProjectResponse
from app.services import (
    get_projects,
    get_project_by_slug,
    get_project_by_id,
    create_project,
    update_project,
    delete_project,
)

router = APIRouter(prefix="/api/projects", tags=["projects"])


@router.get("", response_model=list[ProjectResponse])
async def list_projects(status: str | None = None, db: AsyncSession = Depends(get_db)):
    return await get_projects(db, status)


@router.get("/{slug}", response_model=ProjectResponse)
async def read_project(slug: str, db: AsyncSession = Depends(get_db)):
    project = await get_project_by_slug(db, slug)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


@router.post("", response_model=ProjectResponse, status_code=201)
async def new_project(data: ProjectCreate, db: AsyncSession = Depends(get_db)):
    existing = await get_project_by_slug(db, data.slug)
    if existing:
        raise HTTPException(status_code=409, detail="Slug already exists")
    return await create_project(db, data)


@router.patch("/{project_id}", response_model=ProjectResponse)
async def edit_project(project_id: int, data: ProjectUpdate, db: AsyncSession = Depends(get_db)):
    project = await update_project(db, project_id, data)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


@router.delete("/{project_id}", status_code=204)
async def remove_project(project_id: int, db: AsyncSession = Depends(get_db)):
    deleted = await delete_project(db, project_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Project not found")
```

### `app/api/agents.py`

```python
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.schemas.agent import (
    AgentCreate, AgentUpdate, AgentResponse,
    AgentRunCreate, AgentRunFinish, AgentRunResponse,
)
from app.services.agent_service import (
    get_agents_by_project, get_agent, create_agent, update_agent,
    heartbeat_agent, start_run, finish_run, get_runs_by_agent,
)

router = APIRouter(prefix="/api/agents", tags=["agents"])


@router.get("/project/{project_id}", response_model=list[AgentResponse])
async def list_agents(project_id: int, db: AsyncSession = Depends(get_db)):
    return await get_agents_by_project(db, project_id)


@router.get("/{agent_id}", response_model=AgentResponse)
async def read_agent(agent_id: int, db: AsyncSession = Depends(get_db)):
    agent = await get_agent(db, agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    return agent


@router.post("", response_model=AgentResponse, status_code=201)
async def new_agent(data: AgentCreate, db: AsyncSession = Depends(get_db)):
    return await create_agent(db, data)


@router.patch("/{agent_id}", response_model=AgentResponse)
async def edit_agent(agent_id: int, data: AgentUpdate, db: AsyncSession = Depends(get_db)):
    agent = await update_agent(db, agent_id, data)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    return agent


@router.post("/{agent_id}/heartbeat", response_model=AgentResponse)
async def agent_heartbeat(agent_id: int, db: AsyncSession = Depends(get_db)):
    agent = await heartbeat_agent(db, agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    return agent


@router.post("/runs", response_model=AgentRunResponse, status_code=201)
async def new_run(data: AgentRunCreate, db: AsyncSession = Depends(get_db)):
    return await start_run(db, data)


@router.patch("/runs/{run_id}/finish", response_model=AgentRunResponse)
async def end_run(run_id: int, data: AgentRunFinish, db: AsyncSession = Depends(get_db)):
    run = await finish_run(db, run_id, data)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    return run


@router.get("/{agent_id}/runs", response_model=list[AgentRunResponse])
async def list_runs(agent_id: int, limit: int = 10, db: AsyncSession = Depends(get_db)):
    return await get_runs_by_agent(db, agent_id, limit)
```

### `app/pages/__init__.py`

```python
from fastapi import APIRouter, Request, Depends
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.services import get_projects
from app.services.agent_service import get_agents_by_project, create_agent
from app.schemas.agent import AgentCreate

router = APIRouter(tags=["pages"])
templates = Jinja2Templates(directory="app/templates")

DAESIN_AGENTS = [
    ("A0", "Infrastructure", "opus"),
    ("A1", "Public Data", "sonnet"),
    ("A2", "Corporate CRM", "sonnet"),
    ("A3", "AI-RAG", "opus"),
    ("A4", "Properties/Transactions", "sonnet"),
]


@router.get("/", response_class=HTMLResponse)
async def dashboard(request: Request, db: AsyncSession = Depends(get_db)):
    projects = await get_projects(db, status="active")
    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "projects": projects,
        "page_title": "ORBIT",
    })


@router.get("/projects/new", response_class=HTMLResponse)
async def new_project_form(request: Request):
    return templates.TemplateResponse("project_form.html", {
        "request": request,
        "page_title": "New project",
    })


@router.get("/projects/{slug}", response_class=HTMLResponse)
async def project_detail(request: Request, slug: str, db: AsyncSession = Depends(get_db)):
    from app.services import get_project_by_slug
    project = await get_project_by_slug(db, slug)
    if not project:
        return HTMLResponse(content="Not found", status_code=404)
    return templates.TemplateResponse("project_detail.html", {
        "request": request,
        "project": project,
        "page_title": project.name,
    })


@router.get("/projects/{slug}/agents", response_class=HTMLResponse)
async def agents_page(request: Request, slug: str, db: AsyncSession = Depends(get_db)):
    from app.services import get_project_by_slug
    project = await get_project_by_slug(db, slug)
    if not project:
        return HTMLResponse(content="Not found", status_code=404)
    agents = await get_agents_by_project(db, project.id)
    return templates.TemplateResponse("agents.html", {
        "request": request,
        "project": project,
        "agents": agents,
        "page_title": f"{project.name} — 에이전트",
    })


@router.get("/projects/{slug}/agents/partial", response_class=HTMLResponse)
async def agents_partial(request: Request, slug: str, db: AsyncSession = Depends(get_db)):
    from app.services import get_project_by_slug
    project = await get_project_by_slug(db, slug)
    if not project:
        return HTMLResponse(content="", status_code=404)
    agents = await get_agents_by_project(db, project.id)
    return templates.TemplateResponse("partials/agent_cards.html", {
        "request": request,
        "agents": agents,
    })


@router.post("/projects/{slug}/agents/seed")
async def seed_agents(slug: str, db: AsyncSession = Depends(get_db)):
    from app.services import get_project_by_slug
    project = await get_project_by_slug(db, slug)
    if not project:
        return HTMLResponse(content="Not found", status_code=404)
    existing = await get_agents_by_project(db, project.id)
    if not existing:
        for code, name, tier in DAESIN_AGENTS:
            await create_agent(db, AgentCreate(
                project_id=project.id,
                agent_code=code,
                agent_name=name,
                model_tier=tier,
            ))
    return RedirectResponse(url=f"/projects/{slug}/agents", status_code=303)
```

---

## 템플릿 파일

### `app/templates/base.html`

```html
<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{{ page_title }} — ORBIT</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <script src="https://unpkg.com/htmx.org@2.0.4"></script>
    <link rel="preconnect" href="https://cdn.jsdelivr.net">
    <link href="https://cdn.jsdelivr.net/gh/orioncactus/pretendard@v1.3.9/dist/web/variable/pretendardvariable-dynamic-subset.min.css" rel="stylesheet">
    <script>
        tailwind.config = {
            theme: {
                extend: {
                    fontFamily: {
                        sans: ['Pretendard Variable', 'Pretendard', 'system-ui', 'sans-serif'],
                    },
                    colors: {
                        surface: '#FAFAF7',
                        card: '#FFFFFF',
                        border: '#E8E6E1',
                        muted: '#8C8A84',
                        accent: '#534AB7',
                        'accent-light': '#EEEDFE',
                        'accent-dark': '#3C3489',
                        success: '#0F6E56',
                        'success-light': '#E1F5EE',
                        warning: '#854F0B',
                        'warning-light': '#FAEEDA',
                        danger: '#A32D2D',
                        'danger-light': '#FCEBEB',
                    }
                }
            }
        }
    </script>
    <style>
        :root { --font-sans: 'Pretendard Variable', sans-serif; }
        body { font-family: var(--font-sans); background: #FAFAF7; color: #2C2C2A; }
        .htmx-indicator { opacity: 0; transition: opacity 200ms ease-in; }
        .htmx-request .htmx-indicator { opacity: 1; }
        .htmx-request.htmx-indicator { opacity: 1; }
    </style>
    {% block head %}{% endblock %}
</head>
<body class="min-h-screen bg-surface text-gray-900 antialiased">
    <div class="flex min-h-screen">
        <!-- Sidebar -->
        <aside class="w-56 border-r border-border bg-card flex flex-col py-6 px-4 shrink-0">
            <div class="mb-8">
                <h1 class="text-lg font-semibold tracking-tight text-accent-dark">ORBIT</h1>
                <p class="text-xs text-muted mt-0.5">관제 허브 v0.1</p>
            </div>

            <nav class="flex flex-col gap-1 text-sm">
                <a href="/" class="flex items-center gap-2 px-3 py-2 rounded-lg hover:bg-surface transition-colors {% if page_title == 'ORBIT' %}bg-accent-light text-accent-dark font-medium{% else %}text-gray-600{% endif %}">
                    <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-4 0a1 1 0 01-1-1v-4a1 1 0 011-1h2a1 1 0 011 1v4a1 1 0 01-1 1"/></svg>
                    대시보드
                </a>
                <a href="#" class="flex items-center gap-2 px-3 py-2 rounded-lg hover:bg-surface transition-colors {% if 'agents' in (page_title|default('')) or '에이전트' in (page_title|default('')) %}bg-accent-light text-accent-dark font-medium{% else %}text-gray-600{% endif %}"
                   onclick="if(window.__currentSlug){location.href='/projects/'+window.__currentSlug+'/agents'}else{alert('프로젝트를 먼저 선택하세요')}; return false;">
                    <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M9 3v2m6-2v2M9 19v2m6-2v2M5 9H3m2 6H3m18-6h-2m2 6h-2M7 19h10a2 2 0 002-2V7a2 2 0 00-2-2H7a2 2 0 00-2 2v10a2 2 0 002 2z"/></svg>
                    에이전트
                </a>
                <a href="#" class="flex items-center gap-2 px-3 py-2 rounded-lg hover:bg-surface transition-colors text-gray-400 cursor-not-allowed">
                    <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z"/></svg>
                    타임라인
                    <span class="ml-auto text-[10px] bg-surface text-muted px-1.5 py-0.5 rounded">S2</span>
                </a>
                <a href="#" class="flex items-center gap-2 px-3 py-2 rounded-lg hover:bg-surface transition-colors text-gray-400 cursor-not-allowed">
                    <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"/></svg>
                    세션 로그
                    <span class="ml-auto text-[10px] bg-surface text-muted px-1.5 py-0.5 rounded">S3</span>
                </a>
            </nav>

            <div class="mt-auto pt-4 border-t border-border">
                <p class="text-[11px] text-muted">Sprint 1 — 에이전트 모니터</p>
            </div>
        </aside>

        <!-- Main content -->
        <main class="flex-1 p-8 overflow-auto">
            {% block content %}{% endblock %}
        </main>
    </div>

    {% block scripts %}{% endblock %}
</body>
</html>
```

### `app/templates/dashboard.html`

```html
{% extends "base.html" %}

{% block content %}
<div class="max-w-5xl">
    <div class="flex items-center justify-between mb-8">
        <div>
            <h2 class="text-xl font-semibold tracking-tight">프로젝트 관제</h2>
            <p class="text-sm text-muted mt-1">등록된 프로젝트를 한눈에 관리합니다</p>
        </div>
        <a href="/projects/new"
           class="inline-flex items-center gap-1.5 px-4 py-2 text-sm font-medium text-white bg-accent rounded-lg hover:bg-accent-dark transition-colors shadow-sm">
            <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4v16m8-8H4"/></svg>
            새 프로젝트
        </a>
    </div>

    <div class="grid grid-cols-3 gap-4 mb-8">
        <div class="bg-card border border-border rounded-lg p-4">
            <p class="text-xs text-muted mb-1">전체 프로젝트</p>
            <p class="text-2xl font-semibold">{{ projects | length }}</p>
        </div>
        <div class="bg-card border border-border rounded-lg p-4">
            <p class="text-xs text-muted mb-1">활성 프로젝트</p>
            <p class="text-2xl font-semibold text-success">{{ projects | selectattr("status", "equalto", "active") | list | length }}</p>
        </div>
        <div class="bg-card border border-border rounded-lg p-4">
            <p class="text-xs text-muted mb-1">현재 스프린트</p>
            <p class="text-2xl font-semibold text-accent">S0</p>
        </div>
    </div>

    <div id="project-list" class="grid grid-cols-1 md:grid-cols-2 gap-4">
        {% if projects %}
            {% for project in projects %}
            <a href="/projects/{{ project.slug }}" class="group bg-card border border-border rounded-lg p-5 hover:border-accent/30 hover:shadow-sm transition-all">
                <div class="flex items-start gap-3">
                    <div class="w-3 h-3 rounded-full mt-1.5 shrink-0" style="background-color: {{ project.color }}"></div>
                    <div class="flex-1 min-w-0">
                        <h3 class="font-medium text-sm group-hover:text-accent-dark transition-colors">{{ project.name }}</h3>
                        <p class="text-xs text-muted mt-1 truncate">{{ project.description or '설명 없음' }}</p>
                        <div class="flex items-center gap-3 mt-3">
                            <span class="inline-flex items-center text-[11px] px-2 py-0.5 rounded-full
                                {% if project.status == 'active' %}bg-success-light text-success
                                {% elif project.status == 'paused' %}bg-warning-light text-warning
                                {% else %}bg-surface text-muted{% endif %}">
                                {{ project.status }}
                            </span>
                            {% if project.stack %}
                            <span class="text-[11px] text-muted">{{ project.stack }}</span>
                            {% endif %}
                        </div>
                    </div>
                </div>
            </a>
            {% endfor %}
        {% else %}
            <div class="col-span-2 text-center py-16 bg-card border border-dashed border-border rounded-lg">
                <svg class="w-12 h-12 mx-auto text-gray-300 mb-3" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="1" d="M20 7l-8-4-8 4m16 0l-8 4m8-4v10l-8 4m0-10L4 7m8 4v10M4 7v10l8 4"/></svg>
                <p class="text-sm text-muted mb-3">아직 등록된 프로젝트가 없습니다</p>
                <a href="/projects/new" class="text-sm text-accent hover:text-accent-dark font-medium">첫 프로젝트 추가하기 →</a>
            </div>
        {% endif %}
    </div>
</div>
{% endblock %}
```

### `app/templates/project_form.html`

```html
{% extends "base.html" %}

{% block content %}
<div class="max-w-lg">
    <div class="mb-6">
        <a href="/" class="text-sm text-muted hover:text-accent transition-colors">← 대시보드</a>
    </div>

    <h2 class="text-xl font-semibold tracking-tight mb-6">새 프로젝트</h2>

    <form id="project-form" class="space-y-5 bg-card border border-border rounded-lg p-6">
        <div>
            <label for="name" class="block text-sm font-medium mb-1.5">프로젝트명</label>
            <input type="text" id="name" name="name" required
                   class="w-full px-3 py-2 text-sm border border-border rounded-lg bg-surface focus:outline-none focus:ring-2 focus:ring-accent/20 focus:border-accent transition-colors"
                   placeholder="예: ORBIT">
        </div>

        <div>
            <label for="slug" class="block text-sm font-medium mb-1.5">슬러그</label>
            <input type="text" id="slug" name="slug" required pattern="[a-z0-9\-]+"
                   class="w-full px-3 py-2 text-sm border border-border rounded-lg bg-surface focus:outline-none focus:ring-2 focus:ring-accent/20 focus:border-accent transition-colors"
                   placeholder="예: orbit (영문 소문자, 숫자, 하이픈만)">
        </div>

        <div>
            <label for="description" class="block text-sm font-medium mb-1.5">설명</label>
            <textarea id="description" name="description" rows="2"
                      class="w-full px-3 py-2 text-sm border border-border rounded-lg bg-surface focus:outline-none focus:ring-2 focus:ring-accent/20 focus:border-accent transition-colors resize-none"
                      placeholder="프로젝트에 대한 간단한 설명"></textarea>
        </div>

        <div>
            <label for="repo_url" class="block text-sm font-medium mb-1.5">GitHub 저장소 URL</label>
            <input type="url" id="repo_url" name="repo_url"
                   class="w-full px-3 py-2 text-sm border border-border rounded-lg bg-surface focus:outline-none focus:ring-2 focus:ring-accent/20 focus:border-accent transition-colors"
                   placeholder="https://github.com/...">
        </div>

        <div>
            <label for="stack" class="block text-sm font-medium mb-1.5">기술 스택</label>
            <input type="text" id="stack" name="stack"
                   class="w-full px-3 py-2 text-sm border border-border rounded-lg bg-surface focus:outline-none focus:ring-2 focus:ring-accent/20 focus:border-accent transition-colors"
                   placeholder="예: FastAPI + PostgreSQL + HTMX">
        </div>

        <div>
            <label for="color" class="block text-sm font-medium mb-1.5">프로젝트 컬러</label>
            <div class="flex gap-2">
                {% for c in ['#534AB7', '#0F6E56', '#D85A30', '#185FA5', '#993556', '#854F0B'] %}
                <label class="cursor-pointer">
                    <input type="radio" name="color" value="{{ c }}" class="sr-only peer" {% if loop.first %}checked{% endif %}>
                    <div class="w-8 h-8 rounded-lg border-2 border-transparent peer-checked:border-gray-900 peer-checked:shadow-sm transition-all" style="background-color: {{ c }}"></div>
                </label>
                {% endfor %}
            </div>
        </div>

        <div class="pt-2 flex gap-3">
            <button type="submit"
                    class="px-5 py-2 text-sm font-medium text-white bg-accent rounded-lg hover:bg-accent-dark transition-colors shadow-sm">
                프로젝트 생성
            </button>
            <a href="/" class="px-5 py-2 text-sm text-muted hover:text-gray-700 transition-colors">취소</a>
        </div>

        <div id="form-error" class="hidden text-sm text-danger mt-2"></div>
    </form>
</div>
{% endblock %}

{% block scripts %}
<script>
document.getElementById('name').addEventListener('input', function(e) {
    const slug = e.target.value
        .toLowerCase()
        .replace(/[^a-z0-9가-힣\s-]/g, '')
        .replace(/\s+/g, '-')
        .replace(/[가-힣]/g, '');
    document.getElementById('slug').value = slug;
});

document.getElementById('project-form').addEventListener('submit', async function(e) {
    e.preventDefault();
    const form = e.target;
    const errorEl = document.getElementById('form-error');
    errorEl.classList.add('hidden');

    const data = {
        name: form.name.value,
        slug: form.slug.value,
        description: form.description.value,
        repo_url: form.repo_url.value,
        stack: form.stack.value,
        color: form.querySelector('input[name="color"]:checked').value,
    };

    try {
        const res = await fetch('/api/projects', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data),
        });
        if (res.ok) {
            window.location.href = '/';
        } else {
            const err = await res.json();
            errorEl.textContent = err.detail || '오류가 발생했습니다';
            errorEl.classList.remove('hidden');
        }
    } catch (err) {
        errorEl.textContent = '서버 연결에 실패했습니다';
        errorEl.classList.remove('hidden');
    }
});
</script>
{% endblock %}
```

### `app/templates/project_detail.html`

```html
{% extends "base.html" %}

{% block content %}
<div class="max-w-5xl">
    <div class="mb-6">
        <a href="/" class="text-sm text-muted hover:text-accent transition-colors">← 대시보드</a>
    </div>

    <div class="flex items-start gap-4 mb-8">
        <div class="w-4 h-4 rounded-full mt-1 shrink-0" style="background-color: {{ project.color }}"></div>
        <div class="flex-1">
            <div class="flex items-center gap-3">
                <h2 class="text-xl font-semibold tracking-tight">{{ project.name }}</h2>
                <span class="inline-flex items-center text-[11px] px-2 py-0.5 rounded-full
                    {% if project.status == 'active' %}bg-success-light text-success
                    {% elif project.status == 'paused' %}bg-warning-light text-warning
                    {% else %}bg-surface text-muted{% endif %}">
                    {{ project.status }}
                </span>
            </div>
            <p class="text-sm text-muted mt-1">{{ project.description or '설명 없음' }}</p>
            {% if project.stack %}
            <p class="text-xs text-muted mt-2">{{ project.stack }}</p>
            {% endif %}
        </div>
    </div>

    <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
        <a href="/projects/{{ project.slug }}/agents" class="bg-card border border-border rounded-lg p-6 text-center hover:border-accent/30 hover:shadow-sm transition-all group">
            <p class="text-sm font-medium group-hover:text-accent-dark transition-colors">에이전트 모니터</p>
            <p class="text-[11px] text-accent mt-1">Sprint 1 — 바로가기 →</p>
        </a>
        <div class="bg-card border border-dashed border-border rounded-lg p-6 text-center">
            <p class="text-sm text-muted mb-1">타임라인</p>
            <p class="text-[11px] text-gray-400">Sprint 2에서 추가됩니다</p>
        </div>
        <div class="bg-card border border-dashed border-border rounded-lg p-6 text-center">
            <p class="text-sm text-muted mb-1">세션 로그</p>
            <p class="text-[11px] text-gray-400">Sprint 3에서 추가됩니다</p>
        </div>
        <div class="bg-card border border-dashed border-border rounded-lg p-6 text-center">
            <p class="text-sm text-muted mb-1">작업 로그</p>
            <p class="text-[11px] text-gray-400">Sprint 4에서 추가됩니다</p>
        </div>
    </div>
</div>
{% endblock %}

{% block scripts %}
<script>window.__currentSlug = '{{ project.slug }}';</script>
{% endblock %}
```

### `app/templates/agents.html`

```html
{% extends "base.html" %}

{% block content %}
<div class="max-w-5xl">
    <div class="flex items-center justify-between mb-6">
        <div class="flex items-center gap-3">
            <a href="/projects/{{ project.slug }}" class="text-sm text-muted hover:text-accent transition-colors">← {{ project.name }}</a>
            <span class="text-gray-300">/</span>
            <h2 class="text-lg font-semibold tracking-tight">에이전트 모니터</h2>
        </div>
        <div class="flex items-center gap-3">
            <span class="text-[11px] text-muted">3초마다 자동 갱신</span>
            <div class="w-2 h-2 rounded-full bg-emerald-500 animate-pulse"></div>
        </div>
    </div>

    <div class="grid grid-cols-4 gap-3 mb-6">
        <div class="bg-card border border-border rounded-lg p-3">
            <p class="text-[11px] text-muted">전체</p>
            <p class="text-xl font-semibold">{{ agents | length }}</p>
        </div>
        <div class="bg-card border border-border rounded-lg p-3">
            <p class="text-[11px] text-accent">실행 중</p>
            <p class="text-xl font-semibold text-accent">{{ agents | selectattr("status", "equalto", "running") | list | length }}</p>
        </div>
        <div class="bg-card border border-border rounded-lg p-3">
            <p class="text-[11px] text-success">대기</p>
            <p class="text-xl font-semibold text-success">{{ agents | selectattr("status", "equalto", "idle") | list | length }}</p>
        </div>
        <div class="bg-card border border-border rounded-lg p-3">
            <p class="text-[11px] text-danger">에러</p>
            <p class="text-xl font-semibold text-danger">{{ agents | selectattr("status", "equalto", "error") | list | length }}</p>
        </div>
    </div>

    {% set error_agents = agents | selectattr("status", "equalto", "error") | list %}
    {% if error_agents %}
    <div class="bg-danger-light border border-red-200 rounded-lg px-4 py-3 mb-6 flex items-center gap-3">
        <svg class="w-5 h-5 text-danger shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4c-.77-.833-1.964-.833-2.732 0L4.082 16.5c-.77.833.192 2.5 1.732 2.5z"/></svg>
        <div>
            <p class="text-sm font-medium text-danger">에러 발생</p>
            <p class="text-xs text-red-600 mt-0.5">
                {% for a in error_agents %}{{ a.agent_code }} {{ a.agent_name }}{% if not loop.last %}, {% endif %}{% endfor %}
            </p>
        </div>
    </div>
    {% endif %}

    <div id="agent-grid"
         class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4"
         hx-get="/projects/{{ project.slug }}/agents/partial"
         hx-trigger="every 3s"
         hx-swap="innerHTML">
        {% include "partials/agent_cards.html" %}
    </div>

    <form id="seed-agents-form" method="post" action="/projects/{{ project.slug }}/agents/seed" class="hidden"></form>
</div>
{% endblock %}
```

### `app/templates/partials/agent_cards.html`

```html
{% for agent in agents %}
<div class="bg-card border border-border rounded-lg p-4 relative overflow-hidden">
    <div class="absolute top-0 left-0 right-0 h-1
        {% if agent.status == 'running' %}bg-accent
        {% elif agent.status == 'error' %}bg-red-500
        {% elif agent.status == 'done' %}bg-emerald-500
        {% else %}bg-gray-200{% endif %}">
        {% if agent.status == 'running' %}
        <div class="h-full bg-accent/60 animate-pulse"></div>
        {% endif %}
    </div>

    <div class="flex items-start justify-between mt-1">
        <div class="flex items-center gap-2.5">
            <span class="inline-flex items-center justify-center w-9 h-9 rounded-lg text-xs font-semibold
                {% if agent.model_tier == 'opus' %}bg-accent-light text-accent-dark
                {% else %}bg-surface text-muted{% endif %}">
                {{ agent.agent_code }}
            </span>
            <div>
                <p class="text-sm font-medium">{{ agent.agent_name }}</p>
                <p class="text-[11px] text-muted">{{ agent.model_tier }}</p>
            </div>
        </div>

        <span class="inline-flex items-center gap-1 text-[11px] px-2 py-0.5 rounded-full
            {% if agent.status == 'running' %}bg-accent-light text-accent-dark
            {% elif agent.status == 'error' %}bg-danger-light text-danger
            {% elif agent.status == 'done' %}bg-success-light text-success
            {% else %}bg-surface text-muted{% endif %}">
            <span class="w-1.5 h-1.5 rounded-full
                {% if agent.status == 'running' %}bg-accent animate-pulse
                {% elif agent.status == 'error' %}bg-danger
                {% elif agent.status == 'done' %}bg-success
                {% else %}bg-gray-400{% endif %}"></span>
            {{ agent.status }}
        </span>
    </div>

    {% if agent.current_task %}
    <div class="mt-3 px-2.5 py-1.5 bg-surface rounded text-xs text-gray-600 truncate">
        {{ agent.current_task }}
    </div>
    {% endif %}

    {% if agent.last_heartbeat %}
    <p class="mt-2 text-[10px] text-gray-400">
        마지막 활동: {{ agent.last_heartbeat.strftime('%H:%M:%S') }}
    </p>
    {% endif %}

    {% if agent.recent_runs %}
    <div class="mt-3 border-t border-border pt-2">
        <p class="text-[10px] text-muted mb-1.5 uppercase tracking-wider">최근 실행</p>
        {% for run in agent.recent_runs[:3] %}
        <div class="flex items-center gap-2 py-1 text-[11px]">
            <span class="w-1.5 h-1.5 rounded-full shrink-0
                {% if run.status == 'success' %}bg-emerald-500
                {% elif run.status == 'error' %}bg-red-500
                {% elif run.status == 'running' %}bg-accent animate-pulse
                {% else %}bg-gray-300{% endif %}"></span>
            <span class="truncate flex-1 text-gray-600">{{ run.task_name }}</span>
            {% if run.duration_sec %}
            <span class="text-gray-400 shrink-0">{{ run.duration_sec }}s</span>
            {% endif %}
        </div>
        {% endfor %}
    </div>
    {% endif %}
</div>
{% endfor %}

{% if not agents %}
<div class="col-span-full text-center py-12 bg-card border border-dashed border-border rounded-lg">
    <p class="text-sm text-muted mb-2">등록된 에이전트가 없습니다</p>
    <button onclick="document.getElementById('seed-agents-form').submit()"
            class="text-sm text-accent hover:text-accent-dark font-medium">
        기본 에이전트 세팅하기 →
    </button>
</div>
{% endif %}
```

---

### `seed.py`

```python
"""Seed initial projects and agents into ORBIT."""
import asyncio
from app.database import async_session, engine, Base
from app.models import Project, Agent
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
        ("A0", "Core Setup", "sonnet"),
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

    print("\nSeed complete.")


if __name__ == "__main__":
    asyncio.run(seed())
```

---

## 실행 방법

```bash
cp .env.example .env
docker compose up -d
docker compose exec app python seed.py
# http://localhost:8000
```

## 테스트 체크리스트

1. `http://localhost:8000` — 대시보드에 Giniz/DAESIN/ORBIT 카드 3개
2. "새 프로젝트" 버튼 → 폼 입력 → 생성 → 대시보드에 추가됨
3. DAESIN 카드 클릭 → 프로젝트 상세 → "에이전트 모니터" 클릭
4. 에이전트 페이지에서 A0~A4 카드 5개 표시
5. 브라우저 DevTools Network 탭에서 3초마다 `/agents/partial` 요청 확인
6. API 테스트: `curl http://localhost:8000/api/projects` → JSON 응답
