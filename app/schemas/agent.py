from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional


class AgentCreate(BaseModel):
    project_id: int
    agent_code: str = Field(..., max_length=10)
    agent_name: str = Field(..., max_length=100)
    model_tier: str = "opus"


class AgentUpdate(BaseModel):
    status: Optional[str] = None
    current_task: Optional[str] = None
    last_heartbeat: Optional[datetime] = None
    agent_name: Optional[str] = None
    model_tier: Optional[str] = None


class AgentRunCreate(BaseModel):
    agent_id: int
    task_name: str = Field(..., max_length=200)


class AgentRunFinish(BaseModel):
    status: str  # success, error, cancelled
    error_log: str = ""
    duration_sec: Optional[int] = None


class AgentRunResponse(BaseModel):
    id: int
    agent_id: int
    task_name: str
    status: str
    error_log: str
    duration_sec: Optional[int]
    started_at: datetime
    finished_at: Optional[datetime]

    model_config = {"from_attributes": True}


class AgentSyncItem(BaseModel):
    agent_code: str
    agent_name: str
    model_tier: str = "opus"


class AgentSyncRequest(BaseModel):
    agents: list[AgentSyncItem]


class AgentSyncResponse(BaseModel):
    created: int
    updated: int
    deleted: int


class AgentResponse(BaseModel):
    id: int
    project_id: int
    agent_code: str
    agent_name: str
    model_tier: str
    status: str
    current_task: str
    source: str = "manual"
    last_heartbeat: Optional[datetime]
    created_at: datetime
    recent_runs: list[AgentRunResponse] = []

    model_config = {"from_attributes": True}
