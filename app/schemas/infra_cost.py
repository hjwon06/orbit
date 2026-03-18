from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional


class InfraCostCreate(BaseModel):
    project_id: int
    provider: str = Field(..., max_length=50)
    service_name: str = Field(..., max_length=100)
    cost_usd: float = 0
    billing_cycle: str = "monthly"
    is_active: bool = True
    notes: str = ""


class InfraCostUpdate(BaseModel):
    provider: Optional[str] = None
    service_name: Optional[str] = None
    cost_usd: Optional[float] = None
    billing_cycle: Optional[str] = None
    is_active: Optional[bool] = None
    notes: Optional[str] = None


class InfraCostResponse(BaseModel):
    id: int
    project_id: int
    provider: str
    service_name: str
    cost_usd: float
    billing_cycle: str
    is_active: bool
    notes: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
