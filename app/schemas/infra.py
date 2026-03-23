from pydantic import BaseModel, Field
from datetime import datetime
from typing import Any


# ── DB Admin ──────────────────────────────────────────────

class DbInfo(BaseModel):
    alias: str
    host: str
    port: int = 5432
    database: str
    status: str = "unknown"


class TableInfo(BaseModel):
    table_name: str
    row_estimate: int = 0
    total_size: str = ""
    columns: list[dict[str, Any]] = []


class SqlRequest(BaseModel):
    db_alias: str
    query: str = Field(..., min_length=1, max_length=10000)


class SqlResult(BaseModel):
    columns: list[str] = []
    rows: list[list[Any]] = []
    row_count: int = 0
    duration_ms: int = 0
    error: str = ""


class SqlHistoryResponse(BaseModel):
    id: int
    db_alias: str
    query: str
    row_count: int
    duration_ms: int
    status: str
    error: str
    executed_at: datetime

    model_config = {"from_attributes": True}


