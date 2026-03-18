from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.schemas.session import (
    SessionCreate, SessionUpdate, SessionFinish, SessionResponse,
)
from app.services.session_service import (
    get_sessions_by_project, get_session,
    create_session, update_session, finish_session, delete_session,
)

router = APIRouter(prefix="/api/sessions", tags=["sessions"])


@router.get("/project/{project_id}", response_model=list[SessionResponse])
async def list_sessions(
    project_id: int, limit: int = 50, offset: int = 0,
    db: AsyncSession = Depends(get_db),
):
    return await get_sessions_by_project(db, project_id, limit, offset)


@router.post("", response_model=SessionResponse, status_code=201)
async def new_session(data: SessionCreate, db: AsyncSession = Depends(get_db)):
    return await create_session(db, data)


@router.get("/{session_id}", response_model=SessionResponse)
async def read_session(session_id: int, db: AsyncSession = Depends(get_db)):
    session = await get_session(db, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return session


@router.patch("/{session_id}", response_model=SessionResponse)
async def edit_session(session_id: int, data: SessionUpdate, db: AsyncSession = Depends(get_db)):
    session = await update_session(db, session_id, data)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return session


@router.patch("/{session_id}/finish", response_model=SessionResponse)
async def end_session(session_id: int, data: SessionFinish, db: AsyncSession = Depends(get_db)):
    session = await finish_session(db, session_id, data)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return session


@router.delete("/{session_id}")
async def remove_session(session_id: int, db: AsyncSession = Depends(get_db)):
    if not await delete_session(db, session_id):
        raise HTTPException(status_code=404, detail="Session not found")
    return {"ok": True}
