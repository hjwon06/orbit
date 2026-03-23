import re
import time
from sqlalchemy import create_engine, text, inspect
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.config import get_settings

settings = get_settings()

# ── Managed databases config ─────────────────────────────

def get_managed_dbs() -> dict[str, dict]:
    """Return dict of managed database configs from settings."""
    dbs = settings.get_managed_dbs()
    return {d["alias"]: d for d in dbs}


# ── Sync engine for direct SQL ───────────────────────────

_engines: dict = {}


def get_sync_engine(db_alias: str):
    """Get or create a sync engine for the given db alias."""
    if db_alias in _engines:
        return _engines[db_alias]
    dbs = get_managed_dbs()
    if db_alias not in dbs:
        raise ValueError(f"Unknown database alias: {db_alias}")
    url = dbs[db_alias]["url"]
    engine = create_engine(url, pool_size=2, max_overflow=3)
    _engines[db_alias] = engine
    return engine


# ── Database listing ─────────────────────────────────────

def list_databases() -> list[dict]:
    """List all managed databases with table count and size."""
    dbs = get_managed_dbs()
    result = []
    for alias, info in dbs.items():
        entry = {"alias": alias, "description": info.get("description", ""), "tables": [], "size_mb": 0}
        try:
            engine = get_sync_engine(alias)
            inspector = inspect(engine)
            entry["tables"] = inspector.get_table_names()
            with engine.connect() as conn:
                row = conn.execute(text("SELECT pg_database_size(current_database())")).scalar()
                entry["size_mb"] = round(row / 1024 / 1024, 2) if row else 0
        except Exception as e:
            entry["description"] += f" (연결 실패: {str(e)[:50]})"
        result.append(entry)
    return result


# ── Table info ───────────────────────────────────────────

def get_table_info(db_alias: str, table_name: str) -> dict:
    """테이블 상세 — 컬럼, 행 수, 사이즈."""
    engine = get_sync_engine(db_alias)
    try:
        inspector = inspect(engine)
        columns = [
            {"name": c["name"], "type": str(c["type"]), "nullable": c.get("nullable", True), "default": str(c.get("default", ""))}
            for c in inspector.get_columns(table_name)
        ]
        with engine.connect() as conn:
            # 테이블명 검증 (영숫자+언더스코어만 허용)
            if not re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*$', table_name):
                return {"name": table_name, "row_count": 0, "size_kb": 0, "columns": columns, "error": "Invalid table name"}
            row_count = conn.execute(text(f'SELECT COUNT(*) FROM "{table_name}"')).scalar()  # nosec B608 # noqa: S608 - table_name validated by regex above
            size = conn.execute(text(f"SELECT pg_relation_size('{table_name}')")).scalar()  # nosec B608 # noqa: S608
        return {"name": table_name, "row_count": row_count or 0, "size_kb": round((size or 0) / 1024, 2), "columns": columns}
    except Exception as e:
        return {"name": table_name, "row_count": 0, "size_kb": 0, "columns": [], "error": str(e)}


# ── SQL execution (with injection protection) ────────────

BLOCKED_PATTERNS = [
    re.compile(r"\bDROP\s+DATABASE\b", re.IGNORECASE),
    re.compile(r"\bDROP\s+SCHEMA\b", re.IGNORECASE),
    re.compile(r"\bTRUNCATE\b", re.IGNORECASE),
]


def execute_sql(db_alias: str, query: str) -> dict:
    """Execute raw SQL with injection protection."""
    for pattern in BLOCKED_PATTERNS:
        if pattern.search(query):
            return {
                "columns": [],
                "rows": [],
                "row_count": 0,
                "duration_ms": 0,
                "error": f"Blocked: dangerous SQL pattern detected ({pattern.pattern})",
            }

    engine = get_sync_engine(db_alias)
    start = time.time()
    try:
        with engine.connect() as conn:
            result = conn.execute(text(query))
            duration_ms = int((time.time() - start) * 1000)

            if result.returns_rows:
                columns = list(result.keys())
                rows = [list(r) for r in result.fetchall()]
                row_count = len(rows)
            else:
                conn.commit()
                columns = []
                rows = []
                row_count = result.rowcount

            return {
                "columns": columns,
                "rows": rows,
                "row_count": row_count,
                "duration_ms": duration_ms,
                "error": "",
            }
    except Exception as e:
        duration_ms = int((time.time() - start) * 1000)
        return {
            "columns": [],
            "rows": [],
            "row_count": 0,
            "duration_ms": duration_ms,
            "error": str(e),
        }


# ── SQL history (async) ─────────────────────────────────

async def save_sql_history(db: AsyncSession, db_alias: str, query: str, result: dict):
    """Save executed SQL to history table."""
    try:
        from app.models import SqlHistory
        record = SqlHistory(
            db_alias=db_alias,
            query=query[:5000],
            row_count=result.get("row_count", 0),
            duration_ms=result.get("duration_ms", 0),
            status="error" if result.get("error") else "success",
            error=result.get("error", "")[:2000],
        )
        db.add(record)
        await db.commit()
    except Exception:
        await db.rollback()


async def get_sql_history(db: AsyncSession, db_alias: str | None = None, limit: int = 50) -> list:
    """Get SQL execution history."""
    try:
        from app.models import SqlHistory
        stmt = select(SqlHistory).order_by(SqlHistory.executed_at.desc()).limit(limit)
        if db_alias:
            stmt = stmt.where(SqlHistory.db_alias == db_alias)
        result = await db.execute(stmt)
        return list(result.scalars().all())
    except Exception:
        return []


# ── DB roles & permissions ───────────────────────────────

def get_db_roles(db_alias: str) -> list[dict]:
    """List database roles and their attributes."""
    engine = get_sync_engine(db_alias)
    try:
        with engine.connect() as conn:
            rows = conn.execute(text("""
                SELECT rolname, rolsuper, rolcreaterole, rolcreatedb, rolcanlogin
                FROM pg_roles
                WHERE rolname NOT LIKE 'pg_%'
                ORDER BY rolname
            """)).fetchall()
        return [
            {
                "role": r[0],
                "superuser": r[1],
                "create_role": r[2],
                "create_db": r[3],
                "can_login": r[4],
            }
            for r in rows
        ]
    except Exception as e:
        return [{"error": str(e)}]


def grant_permission(db_alias: str, role: str, permission: str, target: str) -> dict:
    """Grant a permission to a role on a target table/schema."""
    allowed_permissions = {"SELECT", "INSERT", "UPDATE", "DELETE", "ALL"}
    if permission.upper() not in allowed_permissions:
        return {"success": False, "error": f"Permission must be one of {allowed_permissions}"}

    if not re.match(r"^[a-zA-Z_][a-zA-Z0-9_]*$", role):
        return {"success": False, "error": "Invalid role name"}
    if not re.match(r"^[a-zA-Z_][a-zA-Z0-9_.]*$", target):
        return {"success": False, "error": "Invalid target name"}

    engine = get_sync_engine(db_alias)
    try:
        with engine.connect() as conn:
            conn.execute(text(f"GRANT {permission.upper()} ON {target} TO {role}"))
            conn.commit()
        return {"success": True, "message": f"Granted {permission} on {target} to {role}"}
    except Exception as e:
        return {"success": False, "error": str(e)}
