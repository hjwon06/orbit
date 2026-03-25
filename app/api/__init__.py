from fastapi import APIRouter
from app.api.projects import router as projects_router
from app.api.agents import router as agents_router
from app.api.milestones import router as milestones_router
from app.api.sessions import router as sessions_router
from app.api.work_logs import router as work_logs_router
from app.api.commit_stats import router as commit_stats_router
from app.api.infra_costs import router as infra_costs_router
# todos 라우터 삭제 (AI 할일 기능 제거)
from app.api.github import router as github_router
from app.api.infra import router as infra_router
from app.api.cloud_costs import router as cloud_costs_router
from app.api.repo_score import router as repo_score_router

api_router = APIRouter()
api_router.include_router(projects_router)
api_router.include_router(agents_router)
api_router.include_router(milestones_router)
api_router.include_router(sessions_router)
api_router.include_router(work_logs_router)
api_router.include_router(commit_stats_router)
api_router.include_router(infra_costs_router)
# todos_router 제거됨
api_router.include_router(github_router)
api_router.include_router(infra_router)
api_router.include_router(cloud_costs_router)
api_router.include_router(repo_score_router)
