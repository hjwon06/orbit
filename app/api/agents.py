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
