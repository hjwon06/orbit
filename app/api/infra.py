from typing import Literal

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.schemas.infra import (
    SqlRequest, SqlResult, SqlHistoryResponse,
)
from app.services.db_admin_service import (
    list_databases, get_table_info, execute_sql, save_sql_history,
    get_sql_history, get_db_roles, grant_permission,
)
from app.services.ssh_service import execute_ssh_command, execute_rds_sql
from app.services.aws_service import (
    get_ec2_instances, get_ec2_metrics, get_rds_instances,
    get_rds_metrics, get_cloudwatch_alarms, ec2_action,
    get_cost_summary, clear_aws_cache,
)
import os
from pathlib import Path

router = APIRouter(prefix="/api/infra", tags=["infrastructure"])


# === DB 관리 ===

@router.get("/databases")
async def databases():
    return list_databases()


@router.get("/databases/{db_alias}/tables")
async def tables(db_alias: str):
    dbs = list_databases()
    db_info = next((d for d in dbs if d["alias"] == db_alias), None)
    if not db_info:
        return {"error": "Database not found"}
    return [get_table_info(db_alias, t) for t in db_info["tables"]]


@router.get("/databases/{db_alias}/tables/{table_name}")
async def table_detail(db_alias: str, table_name: str):
    return get_table_info(db_alias, table_name)


@router.post("/sql", response_model=SqlResult)
async def run_sql(req: SqlRequest, db: AsyncSession = Depends(get_db)):
    result = execute_sql(req.db_alias, req.query)
    await save_sql_history(db, req.db_alias, req.query, result)
    return result


@router.get("/sql/history", response_model=list[SqlHistoryResponse])
async def sql_history(db_alias: str | None = None, db: AsyncSession = Depends(get_db)):
    return await get_sql_history(db, db_alias)


@router.get("/databases/{db_alias}/roles")
async def db_roles(db_alias: str):
    return get_db_roles(db_alias)


@router.post("/databases/{db_alias}/grant")
async def db_grant(db_alias: str, role: str, table: str, permissions: str = "SELECT"):
    return grant_permission(db_alias, role, table, permissions)


# === RDS 모니터링 ===

@router.get("/rds/{db_alias}/metrics")
async def rds_metrics(db_alias: str):
    from app.services.db_admin_service import get_sync_engine
    from sqlalchemy import text
    engine = get_sync_engine(db_alias)
    metrics = {}
    try:
        with engine.connect() as conn:
            active = conn.execute(text("SELECT count(*) FROM pg_stat_activity WHERE state = 'active'")).scalar()
            metrics["active_connections"] = active or 0
            total = conn.execute(text("SELECT count(*) FROM pg_stat_activity")).scalar()
            metrics["total_connections"] = total or 0
            size = conn.execute(text("SELECT pg_database_size(current_database())")).scalar()
            metrics["db_size_mb"] = round((size or 0) / 1024 / 1024, 2)
            try:
                slow = conn.execute(text("""
                    SELECT query, calls, mean_exec_time, total_exec_time
                    FROM pg_stat_statements WHERE mean_exec_time > 100
                    ORDER BY mean_exec_time DESC LIMIT 10
                """))
                metrics["slow_queries"] = [
                    {"query": row[0][:200], "calls": row[1], "avg_ms": round(row[2], 2), "total_ms": round(row[3], 2)}
                    for row in slow
                ]
            except Exception:
                metrics["slow_queries"] = []
            tables = conn.execute(text("""
                SELECT relname, pg_relation_size(relid), n_live_tup
                FROM pg_stat_user_tables ORDER BY pg_relation_size(relid) DESC LIMIT 10
            """))
            metrics["table_sizes"] = [
                {"name": row[0], "size_kb": round(row[1] / 1024, 2), "rows": row[2]}
                for row in tables
            ]
    except Exception as e:
        metrics["error"] = str(e)
    return metrics


# === SSH ===

class SshRequest(BaseModel):
    command: str
    timeout: int = 120

class RdsSqlRequest(BaseModel):
    sql: str
    db: str = ""
    timeout: int = 60

@router.post("/ssh")
async def ssh_execute(req: SshRequest):
    result = execute_ssh_command(req.command, timeout_sec=min(req.timeout, 120))
    return result

@router.post("/rds/sql")
async def rds_sql_execute(req: RdsSqlRequest):
    result = execute_rds_sql(req.sql, db=req.db, timeout_sec=min(req.timeout, 60))
    return result


# === 옵시디언 다이어리 ===

DIARY_BASE = Path(os.environ.get("ORBIT_OBSIDIAN_VAULT_PATH", "/obsidian")) / "diary"


@router.get("/diary/{project_name}")
async def list_diary_entries(project_name: str):
    diary_dir = DIARY_BASE / project_name
    if not diary_dir.exists():
        return []
    files = sorted(diary_dir.glob("*.md"), reverse=True)
    return [{"date": f.stem, "size_kb": round(f.stat().st_size / 1024, 1)} for f in files[:50]]


@router.get("/diary/{project_name}/{date}")
async def get_diary_entry(project_name: str, date: str):
    file_path = DIARY_BASE / project_name / f"{date}.md"
    if not file_path.exists():
        return {"date": date, "content": "", "error": "Not found"}
    return {"date": date, "content": file_path.read_text(encoding="utf-8")}


# === AWS ===


class Ec2ActionRequest(BaseModel):
    action: Literal["start", "stop", "reboot"]
    reason: str = ""


@router.get("/aws/ec2")
async def aws_ec2_list():
    return await get_ec2_instances()


@router.get("/aws/ec2/{instance_id}/metrics")
async def aws_ec2_metrics(instance_id: str):
    return await get_ec2_metrics(instance_id)


@router.post("/aws/ec2/{instance_id}/action")
async def aws_ec2_action(instance_id: str, req: Ec2ActionRequest, request: Request):
    actor = getattr(getattr(request.state, "user", None), "username", "unknown")
    return await ec2_action(instance_id, req.action, req.reason, actor)


@router.get("/aws/rds")
async def aws_rds_list():
    return await get_rds_instances()


@router.get("/aws/rds/{db_instance_id}/metrics")
async def aws_rds_metrics(db_instance_id: str):
    return await get_rds_metrics(db_instance_id)


@router.get("/aws/alarms")
async def aws_alarms():
    return await get_cloudwatch_alarms()


@router.get("/aws/costs")
async def aws_costs():
    return await get_cost_summary()


@router.post("/aws/refresh")
async def aws_refresh():
    clear_aws_cache()
    return {"success": True, "message": "AWS 캐시 초기화 완료"}
