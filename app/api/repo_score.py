"""레포 품질 평가 API 라우터."""
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.services.repo_score_service import evaluate_repo, get_cached_score

router = APIRouter(prefix="/api/repo-score", tags=["repo-score"])


@router.get("/{project_id}")
async def get_score(project_id: int, db: AsyncSession = Depends(get_db)):
    """캐시된 점수 반환."""
    data = await get_cached_score(db, project_id)
    if not data:
        return {"error": "평가 기록 없음", "total_score": None}
    return data


@router.post("/{project_id}/evaluate")
async def run_evaluate(project_id: int, db: AsyncSession = Depends(get_db)):
    """평가 실행."""
    result = await evaluate_repo(db, project_id)
    if not result:
        return {"error": "프로젝트를 찾을 수 없습니다"}
    return result
