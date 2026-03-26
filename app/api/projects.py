from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.schemas.project import ProjectCreate, ProjectUpdate, ProjectResponse
from app.services import (
    get_projects,
    get_project_by_id,
    get_project_by_slug,
    create_project,
    update_project,
    delete_project,
)
from app.services.local_sync_service import sync_from_local

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


@router.post("/{project_id}/sync-local")
async def sync_local_agents(project_id: int, db: AsyncSession = Depends(get_db)):
    project = await get_project_by_id(db, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    if not project.local_path:
        raise HTTPException(status_code=400, detail="local_path가 설정되지 않았습니다.")
    result = await sync_from_local(db, project)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result
