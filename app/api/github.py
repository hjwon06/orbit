from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.services.github_service import check_github_ready, sync_commits, sync_issues, get_branch_commits

router = APIRouter(prefix="/api/github", tags=["github"])


@router.get("/status/{project_id}")
async def github_status(project_id: int, db: AsyncSession = Depends(get_db)):
    return await check_github_ready(db, project_id)


@router.post("/sync-commits/{project_id}")
async def github_sync_commits(project_id: int, days: int = 30, db: AsyncSession = Depends(get_db)):
    return await sync_commits(db, project_id, days)


@router.post("/sync-issues/{project_id}")
async def github_sync_issues(project_id: int, db: AsyncSession = Depends(get_db)):
    return await sync_issues(db, project_id)


@router.get("/branches/{project_id}")
async def github_branches(project_id: int, db: AsyncSession = Depends(get_db)):
    return await get_branch_commits(db, project_id)
