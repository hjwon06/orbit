import os
import asyncio
from logging.config import fileConfig
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config
from alembic import context

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# 환경변수 우선, 없으면 alembic.ini 값 사용
db_url_sync = os.environ.get(
    "ORBIT_DATABASE_URL_SYNC",
    config.get_main_option("sqlalchemy.url"),
)

from app.database import Base
from app.models import Project, Agent, AgentRun, Milestone, Session, WorkLog, CommitStat, InfraCost, Todo, SqlHistory  # noqa: F401

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    context.configure(
        url=db_url_sync,
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
    async_url = db_url_sync.replace("postgresql://", "postgresql+asyncpg://").replace("sslmode=", "ssl=")
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
        url=async_url,
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
