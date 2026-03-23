"""레포 clone + 정적 분석 유틸리티."""
import asyncio
import json
import shutil
import tempfile
import uuid
from collections import Counter
from pathlib import Path
from typing import Any

CLONE_BASE = str(Path(tempfile.gettempdir()) / "orbit-clone")  # noqa: S108
MAX_REPO_SIZE = 100 * 1024 * 1024  # 100MB
SKIP_DIRS = {".git", "node_modules", "__pycache__", "venv", ".venv", "env", ".env", "dist", "build", ".next"}
SENSITIVE_PATTERNS = {".env", "credentials", "secret", "token", ".pem", ".key", "id_rsa"}


async def shallow_clone(owner: str, repo: str, github_token: str) -> str:
    """shallow clone (depth=1). 반환: clone 경로."""
    clone_id = uuid.uuid4().hex[:8]
    clone_path = f"{CLONE_BASE}-{clone_id}/{owner}-{repo}"
    parent = Path(clone_path).parent
    parent.mkdir(parents=True, exist_ok=True)

    clone_url = f"https://x-access-token:{github_token}@github.com/{owner}/{repo}.git"

    proc = await asyncio.create_subprocess_exec(
        "git", "clone", "--depth", "1", "--single-branch", clone_url, clone_path,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        await asyncio.wait_for(proc.communicate(), timeout=60)
    except asyncio.TimeoutError:
        cleanup_clone(str(parent))
        raise TimeoutError("clone 60초 초과")

    # 크기 체크
    total_size = sum(f.stat().st_size for f in Path(clone_path).rglob("*") if f.is_file())
    if total_size > MAX_REPO_SIZE:
        cleanup_clone(str(parent))
        raise ValueError(f"레포 크기 {total_size // 1024 // 1024}MB — 100MB 초과")

    return clone_path


def cleanup_clone(path: str) -> None:
    """clone 디렉토리 안전 삭제."""
    if path and CLONE_BASE in path:
        shutil.rmtree(path, ignore_errors=True)
        parent = str(Path(path).parent)
        if CLONE_BASE in parent:
            shutil.rmtree(parent, ignore_errors=True)


def detect_language(clone_path: str) -> str:
    """파일 확장자 통계로 주 언어 감지."""
    ext_count: Counter[str] = Counter()
    for f in Path(clone_path).rglob("*"):
        if f.is_file() and not any(skip in f.parts for skip in SKIP_DIRS):
            ext_count[f.suffix.lower()] += 1

    lang_map = {
        ".py": "python", ".js": "javascript", ".ts": "typescript",
        ".go": "go", ".rs": "rust", ".java": "java",
        ".jsx": "javascript", ".tsx": "typescript",
    }
    for ext, _ in ext_count.most_common(5):
        if ext in lang_map:
            return lang_map[ext]
    return "unknown"


def count_files(clone_path: str, language: str) -> dict:
    """파일 수 + 라인 수 통계."""
    ext_map = {
        "python": {".py"}, "javascript": {".js", ".jsx"}, "typescript": {".ts", ".tsx"},
        "go": {".go"}, "rust": {".rs"}, "java": {".java"},
    }
    exts = ext_map.get(language, set())
    total_files = 0
    total_lines = 0
    for f in Path(clone_path).rglob("*"):
        if f.is_file() and f.suffix.lower() in exts and not any(skip in f.parts for skip in SKIP_DIRS):
            total_files += 1
            try:
                total_lines += len(f.read_text(encoding="utf-8", errors="replace").splitlines())
            except Exception:
                pass
    return {"files": total_files, "lines": total_lines}


def select_core_files(clone_path: str, language: str, max_chars: int = 12000) -> list[dict]:
    """GPT용 핵심 파일 선별 (max_chars 이내)."""
    ext_map = {
        "python": {".py"}, "javascript": {".js", ".jsx"}, "typescript": {".ts", ".tsx"},
        "go": {".go"}, "rust": {".rs"}, "java": {".java"},
    }
    priority_names = {
        "python": ["main.py", "app.py", "config.py", "models.py", "settings.py", "database.py"],
        "javascript": ["index.js", "app.js", "server.js", "config.js"],
        "typescript": ["index.ts", "app.ts", "main.ts", "server.ts"],
        "go": ["main.go", "server.go", "config.go"],
    }

    exts = ext_map.get(language, set())
    priorities = priority_names.get(language, [])

    candidates: list[dict[str, Any]] = []
    for f in Path(clone_path).rglob("*"):
        if not f.is_file() or f.suffix.lower() not in exts:
            continue
        if any(skip in f.parts for skip in SKIP_DIRS):
            continue
        # 민감 파일 제외
        if any(pat in f.name.lower() for pat in SENSITIVE_PATTERNS):
            continue
        # 테스트 파일 제외 (코드 품질 평가 대상 아님)
        if "test" in f.name.lower() and f.name.lower() != "conftest.py":
            continue

        try:
            content = f.read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue

        lines = content.splitlines()
        if len(lines) < 5:
            continue

        # 500줄 초과면 앞 300줄만
        if len(lines) > 500:
            content = "\n".join(lines[:300])

        rel_path = str(f.relative_to(clone_path))
        # 우선순위 점수
        score = 0
        if f.name in priorities:
            score += 100
        if any(d in f.parts for d in ["src", "app", "lib", "core", "services"]):
            score += 50
        score += min(len(lines), 200)  # 적당한 크기가 좋음

        candidates.append({"path": rel_path, "content": content, "score": score, "lines": len(lines)})

    # 점수 높은 순
    candidates.sort(key=lambda x: int(x["score"]), reverse=True)  # type: ignore[arg-type]

    selected = []
    char_count = 0
    for c in candidates:
        if char_count + len(c["content"]) > max_chars:
            # 남은 공간에 맞게 잘라서 넣기
            remaining = max_chars - char_count
            if remaining > 500:
                c["content"] = c["content"][:remaining]
                selected.append(c)
            break
        selected.append(c)
        char_count += len(c["content"])

    return selected


async def run_tool(cmd: list[str], cwd: str, timeout: int = 120) -> dict:
    """정적 분석 도구 비동기 실행."""
    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd, cwd=cwd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        output = stdout.decode("utf-8", errors="replace")

        try:
            return {"data": json.loads(output), "raw": None, "exit_code": proc.returncode, "error": None}
        except (json.JSONDecodeError, ValueError):
            return {"data": None, "raw": output, "exit_code": proc.returncode, "error": None}
    except asyncio.TimeoutError:
        return {"data": None, "raw": None, "exit_code": -1, "error": f"Timeout {timeout}s"}
    except Exception as e:
        return {"data": None, "raw": None, "exit_code": -1, "error": str(e)}
