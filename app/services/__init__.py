from datetime import datetime, timezone
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from app.models import Project
from app.schemas.project import ProjectCreate, ProjectUpdate


async def get_projects(db: AsyncSession, status: str | None = None):
    stmt = select(Project).where(Project.deleted_at.is_(None)).order_by(Project.created_at.desc())
    if status:
        stmt = stmt.where(Project.status == status)
    result = await db.execute(stmt)
    return result.scalars().all()


async def get_project_by_slug(db: AsyncSession, slug: str):
    result = await db.execute(select(Project).where(Project.slug == slug, Project.deleted_at.is_(None)))
    return result.scalar_one_or_none()


async def get_project_by_id(db: AsyncSession, project_id: int):
    result = await db.execute(select(Project).where(Project.id == project_id, Project.deleted_at.is_(None)))
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
    await db.execute(
        update(Project).where(Project.id == project_id).values(deleted_at=datetime.now(timezone.utc))
    )
    await db.commit()
    return True
