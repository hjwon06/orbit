"""EC2 SSH + RDS psql command execution service."""
import subprocess
import time
import re
from app.config import get_settings

settings = get_settings()

RDS_HOST = "giniz-db.cbyc4yk4c3iq.ap-northeast-2.rds.amazonaws.com"
RDS_USER = "giniz_master"
RDS_PASS = "Giniz0228!#$"
RDS_DB = "postgres"

BLOCKED_COMMANDS = [
    re.compile(r"\brm\s+-rf\s+/\b", re.IGNORECASE),
    re.compile(r"\bshutdown\b", re.IGNORECASE),
    re.compile(r"\breboot\b", re.IGNORECASE),
    re.compile(r"\bmkfs\b", re.IGNORECASE),
    re.compile(r"\bdd\s+if=", re.IGNORECASE),
]


def _run_ssh(remote_command: str, timeout_sec: int = 30) -> dict:
    """Execute a command on EC2 via SSH."""
    if not settings.ssh_key_path or not settings.ssh_host:
        return {"output": "", "error": "SSH not configured", "duration_ms": 0, "exit_code": -1}

    ssh_cmd = [
        "ssh",
        "-i", settings.ssh_key_path,
        "-o", "StrictHostKeyChecking=no",
        "-o", "ConnectTimeout=10",
        f"{settings.ssh_user}@{settings.ssh_host}",
        remote_command,
    ]

    start = time.time()
    try:
        result = subprocess.run(ssh_cmd, capture_output=True, text=True, timeout=timeout_sec)
        duration_ms = int((time.time() - start) * 1000)
        return {
            "output": result.stdout,
            "error": result.stderr,
            "duration_ms": duration_ms,
            "exit_code": result.returncode,
        }
    except subprocess.TimeoutExpired:
        duration_ms = int((time.time() - start) * 1000)
        return {"output": "", "error": f"Timeout after {timeout_sec}s", "duration_ms": duration_ms, "exit_code": -1}
    except Exception as e:
        duration_ms = int((time.time() - start) * 1000)
        return {"output": "", "error": str(e), "duration_ms": duration_ms, "exit_code": -1}


def execute_ssh_command(command: str, timeout_sec: int = 30) -> dict:
    """Execute a shell command on EC2."""
    for pattern in BLOCKED_COMMANDS:
        if pattern.search(command):
            return {"output": "", "error": f"Blocked: dangerous command ({pattern.pattern})", "duration_ms": 0, "exit_code": -1}
    return _run_ssh(command, timeout_sec)


def execute_rds_sql(sql: str, db: str = "", timeout_sec: int = 30) -> dict:
    """Execute SQL on RDS via EC2 psql."""
    target_db = db or RDS_DB
    safe_sql = sql.replace("'", "'\\''")
    remote_cmd = f"PGPASSWORD='{RDS_PASS}' psql -h {RDS_HOST} -U {RDS_USER} -d {target_db} -c '{safe_sql}'"
    return _run_ssh(remote_cmd, timeout_sec)
