from pydantic import BaseModel, Field
from datetime import date, datetime
from typing import Optional


class MilestoneCreate(BaseModel):
    project_id: int
    title: str = Field(..., max_length=200)
    status: str = "planned"
    start_date: date
    end_date: date
    color: Optional[str] = None
    sort_order: int = 0


class MilestoneUpdate(BaseModel):
    title: Optional[str] = None
    status: Optional[str] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    color: Optional[str] = None
    sort_order: Optional[int] = None


class MilestoneDatesUpdate(BaseModel):
    start_date: date
    end_date: date


class MilestoneResponse(BaseModel):
    id: int
    project_id: int
    title: str
    status: str
    start_date: date
    end_date: date
    color: Optional[str]
    sort_order: int
    github_issue_url: Optional[str]
    github_issue_number: Optional[int]
    source: str
    created_at: datetime
    updated_at: datetime
    todo_total: int = 0
    todo_done: int = 0
    todo_pct: int = 0

    model_config = {"from_attributes": True}
