from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.schemas.team_score import TeamMemberResponse, TeamScoreResponse, EvaluateRequest
from app.services.team_score_service import evaluate_all, get_latest_scores, get_member_history
from app.services import get_project_by_id

router = APIRouter(prefix="/api/team-scores", tags=["team-scores"])


@router.get("/{project_id}", response_model=list[dict])
async def list_scores(project_id: int, db: AsyncSession = Depends(get_db)):
    results = await get_latest_scores(db, project_id)
    out = []
    for r in results:
        member = r["member"]
        score = r["score"]
        out.append({
            "member": TeamMemberResponse.model_validate(member).model_dump(),
            "score": TeamScoreResponse.model_validate(score).model_dump() if score else None,
        })
    return out


@router.post("/{project_id}/evaluate")
async def run_evaluate(project_id: int, db: AsyncSession = Depends(get_db)):
    project = await get_project_by_id(db, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    scores = await evaluate_all(db, project_id)
    return [TeamScoreResponse.model_validate(s).model_dump() for s in scores]


@router.get("/{project_id}/{member_name}/history")
async def member_history(project_id: int, member_name: str, db: AsyncSession = Depends(get_db)):
    history = await get_member_history(db, project_id, member_name)
    return [TeamScoreResponse.model_validate(s).model_dump() for s in history]
