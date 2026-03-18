from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional


class SessionCreate(BaseModel):
    project_id: int
    title: str = Field(..., max_length=200)
    agent_code: Optional[str] = None


class SessionUpdate(BaseModel):
    title: Optional[str] = None
    summary: Optional[str] = None
    status: Optional[str] = None
    agent_code: Optional[str] = None


class SessionFinish(BaseModel):
    summary: str = ""
    status: str = "done"


class SessionResponse(BaseModel):
    id: int
    project_id: int
    title: str
    agent_code: Optional[str]
    summary: str
    status: str
    started_at: datetime
    finished_at: Optional[datetime]
    duration_min: Optional[int]
    created_at: datetime

    model_config = {"from_attributes": True}
