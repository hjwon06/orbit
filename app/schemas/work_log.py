from pydantic import BaseModel
from datetime import date, datetime
from typing import Optional


class WorkLogCreate(BaseModel):
    project_id: int
    log_date: date
    content: str = ""


class WorkLogUpdate(BaseModel):
    content: Optional[str] = None


class WorkLogResponse(BaseModel):
    id: int
    project_id: int
    log_date: date
    content: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
