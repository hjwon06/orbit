from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional


class ProjectCreate(BaseModel):
    name: str = Field(..., max_length=100)
    slug: str = Field(..., max_length=50, pattern=r"^[a-z0-9\-]+$")
    description: str = ""
    repo_url: str = ""
    stack: str = ""
    color: str = "#534AB7"


class ProjectUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None
    repo_url: Optional[str] = None
    stack: Optional[str] = None
    color: Optional[str] = None
    project_yaml: Optional[str] = None


class ProjectResponse(BaseModel):
    id: int
    name: str
    slug: str
    description: str
    status: str
    repo_url: str
    stack: str
    color: str
    project_yaml: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
