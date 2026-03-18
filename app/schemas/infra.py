from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional, Any


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


# ── Migration ─────────────────────────────────────────────

class MigrationRequest(BaseModel):
    project_id: int
    db_alias: str
    direction: str = "upgrade"


class MigrationResponse(BaseModel):
    id: int
    project_id: int
    db_alias: str
    migration_name: str
    direction: str
    status: str
    log: str
    executed_at: datetime

    model_config = {"from_attributes": True}


# ── Deployment ────────────────────────────────────────────

class DeployRequest(BaseModel):
    project_id: int
    target: str = "production"
    branch: str = "main"
    triggered_by: str = "manual"


class DeploymentResponse(BaseModel):
    id: int
    project_id: int
    target: str
    commit_sha: str
    branch: str
    status: str
    log: str
    duration_sec: Optional[int] = None
    triggered_by: str
    started_at: datetime
    finished_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


# ── Server Monitor ────────────────────────────────────────

class ServerStatus(BaseModel):
    server_name: str
    cpu_pct: float = 0
    memory_pct: float = 0
    disk_pct: float = 0
    memory_used_mb: int = 0
    memory_total_mb: int = 0
    disk_used_gb: float = 0
    disk_total_gb: float = 0
    load_avg_1m: float = 0
    process_count: int = 0
    uptime_hours: int = 0
    collected_at: Optional[datetime] = None


class ServerSnapshotResponse(BaseModel):
    id: int
    server_name: str
    cpu_pct: float
    memory_pct: float
    disk_pct: float
    memory_used_mb: int
    memory_total_mb: int
    disk_used_gb: float
    disk_total_gb: float
    load_avg_1m: float
    process_count: int
    uptime_hours: int
    raw_data: dict[str, Any] = {}
    collected_at: datetime

    model_config = {"from_attributes": True}
