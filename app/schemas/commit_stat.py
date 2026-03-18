from pydantic import BaseModel
from datetime import date, datetime
from typing import Optional


class CommitStatCreate(BaseModel):
    project_id: int
    stat_date: date
    commit_count: int = 0
    additions: int = 0
    deletions: int = 0


class CommitStatUpdate(BaseModel):
    commit_count: Optional[int] = None
    additions: Optional[int] = None
    deletions: Optional[int] = None


class CommitStatResponse(BaseModel):
    id: int
    project_id: int
    stat_date: date
    commit_count: int
    additions: int
    deletions: int
    source: str
    created_at: datetime

    model_config = {"from_attributes": True}
