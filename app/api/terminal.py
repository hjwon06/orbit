"""터미널 세션 REST API."""
from fastapi import APIRouter
from pydantic import BaseModel
from app.services.terminal_service import terminal_manager

router = APIRouter(prefix="/api/terminal", tags=["terminal"])


class TerminalCreateRequest(BaseModel):
    project_id: int | None = None
    project_slug: str = ""
    shell: str = "auto"
    cwd: str = ""
    cols: int = 120
    rows: int = 30


@router.post("/sessions")
async def create_session(req: TerminalCreateRequest):
    try:
        session = await terminal_manager.create_session(
            project_id=req.project_id,
            project_slug=req.project_slug,
            shell=req.shell,
            cwd=req.cwd,
            cols=req.cols,
            rows=req.rows,
        )
        return {
            "session_id": session.session_id,
            "project_id": session.project_id,
            "project_slug": session.project_slug,
            "shell": session.shell,
            "cwd": session.cwd,
            "status": "running",
        }
    except RuntimeError as e:
        return {"error": str(e)}


@router.get("/sessions")
async def list_sessions():
    return terminal_manager.list_sessions()


@router.delete("/sessions/{session_id}")
async def delete_session(session_id: str):
    killed = await terminal_manager.kill_session(session_id)
    return {"killed": killed}
