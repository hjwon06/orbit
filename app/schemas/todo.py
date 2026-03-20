from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional


class TodoCreate(BaseModel):
    project_id: int
    milestone_id: Optional[int] = None
    title: str = Field(..., max_length=300)
    description: str = ""
    priority: str = "medium"
    source: str = "manual"


class TodoUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    priority: Optional[str] = None
    status: Optional[str] = None
    milestone_id: Optional[int] = None
    ai_reasoning: Optional[str] = None
    source: Optional[str] = None


class TodoResponse(BaseModel):
    id: int
    project_id: int
    milestone_id: Optional[int]
    title: str
    description: str
    priority: str
    status: str
    source: str
    github_issue_url: Optional[str]
    ai_reasoning: str
    created_at: datetime
    completed_at: Optional[datetime]

    model_config = {"from_attributes": True}
