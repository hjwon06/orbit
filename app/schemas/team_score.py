from pydantic import BaseModel
from datetime import datetime
from typing import Optional


class TeamMemberCreate(BaseModel):
    project_id: int
    member_name: str
    display_name: str
    branch_pattern: str = ""
    module_path: str = ""
    is_excluded: bool = False


class TeamMemberResponse(BaseModel):
    id: int
    project_id: int
    member_name: str
    display_name: str
    branch_pattern: str
    module_path: str
    is_excluded: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class TeamScoreResponse(BaseModel):
    id: int
    project_id: int
    member_name: str
    total_score: int
    grade: str
    completeness: int
    convention: int
    quality: int
    security: int
    testing: int
    violations_json: str
    gpt_review: Optional[str]
    evaluated_at: datetime

    model_config = {"from_attributes": True}


class EvaluateRequest(BaseModel):
    member_name: Optional[str] = None  # None이면 전체 팀원
