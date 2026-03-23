"""EC2 SSH + RDS psql command execution service."""
import subprocess
import time
import re
from app.config import get_settings

settings = get_settings()

RDS_HOST = settings.rds_host or ""
RDS_USER = settings.rds_master_user or "giniz_master"
RDS_PASS = settings.rds_master_password or ""
RDS_DB = "postgres"

# 특수 비밀번호 (규칙에 안 맞는 유저만 등록)
_RDS_PASSWORDS_OVERRIDE = {
    RDS_USER: RDS_PASS,
}


def _get_rds_password(user: str) -> str:
    """유저별 비밀번호 자동 생성. 규칙: {Name}!2026 (예: jay → Jay!2026)"""
    if user in _RDS_PASSWORDS_OVERRIDE:
        return _RDS_PASSWORDS_OVERRIDE[user]
    return f"{user.capitalize()}!2026"

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


def _inject_pgpassword(command: str) -> str:
    """psql 명령어 감지 시 PGPASSWORD + 기본 유저 자동 주입."""
    if "psql" not in command:
        return command
    # 이미 PGPASSWORD가 있으면 스킵
    if "PGPASSWORD" in command:
        return command

    # psql 부분만 추출해서 처리 (cd ... && psql ... 대응)
    parts = command.rsplit("psql", 1)
    prefix = parts[0]  # "cd /home/ubuntu && " 또는 ""
    psql_part = "psql" + parts[1]  # "psql -h ... -d ..."

    # -U 없으면 giniz_master 자동 추가
    if not re.search(r"-U\s+\S+", psql_part):
        psql_part = psql_part.replace("psql ", f"psql -U {RDS_USER} ", 1)

    # -U 옵션에서 유저명 추출
    user_match = re.search(r"-U\s+(\S+)", psql_part)
    user = user_match.group(1) if user_match else RDS_USER
    password = _get_rds_password(user)

    return f"{prefix}PGPASSWORD='{password}' {psql_part}"


def execute_ssh_command(command: str, timeout_sec: int = 30) -> dict:
    """Execute a shell command on EC2."""
    for pattern in BLOCKED_COMMANDS:
        if pattern.search(command):
            return {"output": "", "error": f"Blocked: dangerous command ({pattern.pattern})", "duration_ms": 0, "exit_code": -1}
    command = _inject_pgpassword(command)
    return _run_ssh(command, timeout_sec)


def execute_rds_sql(sql: str, db: str = "", timeout_sec: int = 30) -> dict:
    """Execute SQL on RDS via EC2 psql."""
    target_db = db or RDS_DB
    safe_sql = sql.replace("'", "'\\''")
    remote_cmd = f"PGPASSWORD='{RDS_PASS}' psql -h {RDS_HOST} -U {RDS_USER} -d {target_db} -c '{safe_sql}'"
    return _run_ssh(remote_cmd, timeout_sec)
