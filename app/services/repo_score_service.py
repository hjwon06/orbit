"""Git 레포지토리 품질 평가 v2 — 코드 실행 기반 (100점 만점)."""
import asyncio
import json
import time
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models import Project, RepoScore
from app.services.github_service import _parse_repo, _get_headers
from app.services.clone_utils import (
    shallow_clone, cleanup_clone, detect_language, count_files,
    select_core_files, run_tool,
)

try:
    import httpx
    HAS_HTTPX = True
except ImportError:
    HAS_HTTPX = False

# 30분 캐시
_score_cache: dict[int, tuple[float, dict]] = {}
CACHE_TTL = 1800

# 동시 평가 제한
_eval_semaphore = asyncio.Semaphore(3)


def _get_grade(score: int) -> str:
    if score >= 90:
        return "S"
    if score >= 80:
        return "A"
    if score >= 70:
        return "B"
    if score >= 60:
        return "C"
    if score >= 50:
        return "D"
    return "F"


# ── A. 정적 분석 (35점) ─────────────────────────────

async def _score_lint(clone_path: str, language: str, file_stats: dict) -> dict:
    """린트 에러 밀도 (15점)."""
    if language != "python":
        return {"category": "정적 분석", "item": "린트 검사", "score": 0, "max_score": 15, "detail": f"{language} 미지원 (Python만)"}

    result = await run_tool(["ruff", "check", "--output-format", "json", "--quiet", "."], clone_path)
    if result["error"]:
        return {"category": "정적 분석", "item": "린트 검사", "score": 0, "max_score": 15, "detail": f"ruff 실행 실패: {result['error']}"}

    errors = result["data"] if isinstance(result["data"], list) else []
    error_count = len(errors)
    total_files = max(file_stats.get("files", 1), 1)
    density = error_count / total_files

    if density == 0:
        score = 15
    elif density < 0.5:
        score = 12
    elif density < 1.0:
        score = 9
    elif density < 3.0:
        score = 5
    else:
        score = 2

    return {"category": "정적 분석", "item": "린트 검사", "score": score, "max_score": 15, "detail": f"ruff 에러 {error_count}건 (파일당 {density:.1f})"}


async def _score_typecheck(clone_path: str, language: str, file_stats: dict) -> dict:
    """타입 체크 (10점)."""
    if language != "python":
        return {"category": "정적 분석", "item": "타입 체크", "score": 0, "max_score": 10, "detail": f"{language} 미지원"}

    result = await run_tool(["mypy", "--ignore-missing-imports", "--no-error-summary", "."], clone_path, timeout=180)
    if result["error"]:
        return {"category": "정적 분석", "item": "타입 체크", "score": 0, "max_score": 10, "detail": f"mypy 실행 실패: {result['error']}"}

    raw = result.get("raw") or ""
    error_lines = [line for line in raw.splitlines() if ": error:" in line]
    error_count = len(error_lines)

    if error_count == 0:
        score = 10
    elif error_count < 5:
        score = 7
    elif error_count < 20:
        score = 4
    else:
        score = 1

    return {"category": "정적 분석", "item": "타입 체크", "score": score, "max_score": 10, "detail": f"mypy 에러 {error_count}건"}


async def _score_complexity(clone_path: str, language: str) -> dict:
    """복잡도 (10점)."""
    if language != "python":
        return {"category": "정적 분석", "item": "복잡도", "score": 0, "max_score": 10, "detail": f"{language} 미지원"}

    result = await run_tool(["radon", "cc", "-j", "-n", "C", "."], clone_path)
    if result["error"]:
        return {"category": "정적 분석", "item": "복잡도", "score": 5, "max_score": 10, "detail": f"radon 실행 실패: {result['error']}"}

    # radon cc -j -n C: C등급 이상(복잡한) 함수만 출력
    data = result.get("data") or {}
    complex_funcs = 0
    if isinstance(data, dict):
        for file_results in data.values():
            if isinstance(file_results, list):
                complex_funcs += len(file_results)

    if complex_funcs == 0:
        score = 10
    elif complex_funcs < 3:
        score = 7
    elif complex_funcs < 10:
        score = 4
    else:
        score = 1

    return {"category": "정적 분석", "item": "복잡도", "score": score, "max_score": 10, "detail": f"복잡 함수 {complex_funcs}개 (C등급 이상)"}


# ── B. 보안 (25점) ───────────────────────────────────

async def _score_security(clone_path: str, language: str) -> dict:
    """보안 취약점 (17점)."""
    if language != "python":
        return {"category": "보안", "item": "보안 취약점", "score": 0, "max_score": 17, "detail": f"{language} 미지원"}

    result = await run_tool(["bandit", "-r", "-f", "json", "-q", "."], clone_path)
    if result["error"]:
        return {"category": "보안", "item": "보안 취약점", "score": 0, "max_score": 17, "detail": f"bandit 실행 실패: {result['error']}"}

    data = result.get("data") or {}
    results_list = data.get("results", [])
    high = sum(1 for r in results_list if r.get("issue_severity") == "HIGH")
    medium = sum(1 for r in results_list if r.get("issue_severity") == "MEDIUM")
    low = sum(1 for r in results_list if r.get("issue_severity") == "LOW")

    if high == 0 and medium == 0:
        score = 17
    elif high == 0 and medium < 3:
        score = 13
    elif high < 3:
        score = 8
    elif high < 10:
        score = 3
    else:
        score = 0

    return {"category": "보안", "item": "보안 취약점", "score": score, "max_score": 17, "detail": f"HIGH {high}, MEDIUM {medium}, LOW {low}"}


async def _score_secrets(clone_path: str) -> dict:
    """시크릿 노출 (8점)."""
    # 간단한 패턴 매칭으로 시크릿 검출
    from pathlib import Path
    secret_patterns = ["password", "api_key", "secret_key", "access_key", "token"]
    found = 0
    skip_dirs = {".git", "node_modules", "__pycache__", "venv", ".venv"}

    for f in Path(clone_path).rglob("*"):
        if not f.is_file() or any(skip in f.parts for skip in skip_dirs):
            continue
        if f.suffix.lower() in {".md", ".txt", ".yml", ".yaml", ".toml", ".ini", ".cfg", ".json", ".example"}:
            continue
        try:
            content = f.read_text(encoding="utf-8", errors="replace")
            for line in content.splitlines():
                line_lower = line.lower().strip()
                if line_lower.startswith("#") or line_lower.startswith("//"):
                    continue
                for pat in secret_patterns:
                    if pat in line_lower and "=" in line and not line_lower.endswith('""') and not line_lower.endswith("''") and not line_lower.endswith('= ""') and not line_lower.endswith("= ''") and not line_lower.endswith("= os."):
                        # 실제 값이 있는지 체크
                        val = line.split("=", 1)[1].strip().strip('"').strip("'")
                        if len(val) > 5 and val not in {"", "None", "null", "undefined", "changeme", "xxx", "your-key-here"}:
                            found += 1
                            break
        except Exception:
            pass

    if found == 0:
        score = 8
    elif found < 3:
        score = 5
    elif found < 8:
        score = 2
    else:
        score = 0

    return {"category": "보안", "item": "시크릿 노출", "score": score, "max_score": 8, "detail": f"의심 패턴 {found}건"}


# ── C. GPT 코드 리뷰 (25점) ─────────────────────────

async def _score_gpt_review(clone_path: str, language: str, file_stats: dict, lint_errors: int, type_errors: int) -> dict:
    """GPT 실제 코드 리뷰 (25점)."""
    settings = get_settings()
    if not settings.openai_api_key or not HAS_HTTPX:
        return {"category": "GPT 리뷰", "item": "코드 리뷰", "score": 0, "max_score": 25, "detail": "OpenAI 키 미설정"}

    core_files = select_core_files(clone_path, language, max_chars=12000)
    if not core_files:
        return {"category": "GPT 리뷰", "item": "코드 리뷰", "score": 0, "max_score": 25, "detail": "분석 가능한 핵심 파일 없음"}

    # 코드 블록 구성
    code_blocks = ""
    for f in core_files:
        code_blocks += f"\n### {f['path']} ({f['lines']}줄)\n```{language}\n{f['content']}\n```\n"

    prompt = (
        f"다음 {language} 레포지토리의 실제 코드를 분석하고 평가해주세요.\n\n"
        f"## 레포 통계\n"
        f"- 언어: {language}\n"
        f"- 파일 수: {file_stats.get('files', 0)}, 라인 수: {file_stats.get('lines', 0)}\n"
        f"- 린트 에러: {lint_errors}건, 타입 에러: {type_errors}건\n\n"
        f"## 핵심 코드 ({len(core_files)}개 파일)\n{code_blocks}\n\n"
        "## 평가 기준 (각 항목 0점부터 엄격하게)\n"
        "1. 아키텍처/구조 (0-9점): 디렉토리 구조, 모듈 분리, 관심사 분리, 확장성\n"
        "2. 코드 품질/패턴 (0-9점): 네이밍, DRY, 함수 크기, 일관성, 가독성\n"
        "3. 에러 처리/안정성 (0-7점): try/except, 에러 전파, 방어적 코딩, 로깅\n\n"
        'JSON 반환: {"architecture": n, "quality": n, "error_handling": n, "review": "한국어 리뷰 5줄 이내"}'
    )

    try:
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(
                "https://api.openai.com/v1/chat/completions",
                headers={"Authorization": f"Bearer {settings.openai_api_key}"},
                json={
                    "model": "gpt-4o-mini",
                    "temperature": 0.2,
                    "messages": [
                        {"role": "system", "content": "당신은 15년차 시니어 아키텍트입니다. 코드를 엄격하게 평가하세요. 점수는 후하게 주지 마세요."},
                        {"role": "user", "content": prompt},
                    ],
                },
            )
            resp.raise_for_status()
            content = resp.json()["choices"][0]["message"]["content"].strip()
            if content.startswith("```"):
                content = content.split("\n", 1)[1].rsplit("```", 1)[0]
            result = json.loads(content)

            arch = min(9, max(0, int(result.get("architecture", 0))))
            quality = min(9, max(0, int(result.get("quality", 0))))
            err = min(7, max(0, int(result.get("error_handling", 0))))
            total = arch + quality + err
            review = result.get("review", "")

            return {"category": "GPT 리뷰", "item": "코드 리뷰", "score": total, "max_score": 25,
                    "detail": review,
                    "sub_scores": {"아키텍처": f"{arch}/9", "코드 품질": f"{quality}/9", "에러 처리": f"{err}/7"}}
    except Exception as e:
        return {"category": "GPT 리뷰", "item": "코드 리뷰", "score": 0, "max_score": 25, "detail": f"GPT 호출 실패: {e}"}


# ── D. 기본 관리 (15점) ──────────────────────────────

async def _score_basic_management(owner: str, repo: str, headers: dict) -> list[dict]:
    """GitHub API로 기본 관리 항목 체크 (15점)."""
    results = []

    try:
        async with httpx.AsyncClient(timeout=20) as client:
            # README
            resp = await client.get(f"https://api.github.com/repos/{owner}/{repo}/readme", headers=headers)
            has_readme = resp.status_code == 200
            results.append({"category": "기본 관리", "item": "README", "score": 5 if has_readme else 0, "max_score": 5, "detail": "존재" if has_readme else "없음"})

            # 트리에서 테스트+의존성 파일 확인
            resp = await client.get(f"https://api.github.com/repos/{owner}/{repo}/git/trees/HEAD", headers=headers, params={"recursive": "false"})
            tree_items = []
            if resp.status_code == 200:
                tree_items = resp.json().get("tree", [])

            paths = [t.get("path", "") for t in tree_items]

            has_tests = any(p.startswith("tests") or p.startswith("test") or p == "pytest.ini" or p == "jest.config.js" for p in paths)
            results.append({"category": "기본 관리", "item": "테스트", "score": 5 if has_tests else 0, "max_score": 5, "detail": "존재" if has_tests else "없음"})

            dep_files = ["requirements.txt", "pyproject.toml", "package.json", "go.mod", "Cargo.toml", "Gemfile"]
            found_deps = [p for p in paths if p in dep_files]
            has_deps = len(found_deps) > 0
            results.append({"category": "기본 관리", "item": "의존성 관리", "score": 5 if has_deps else 0, "max_score": 5, "detail": ", ".join(found_deps) if found_deps else "없음"})

    except Exception as e:
        results = [
            {"category": "기본 관리", "item": "README", "score": 0, "max_score": 5, "detail": f"API 오류: {e}"},
            {"category": "기본 관리", "item": "테스트", "score": 0, "max_score": 5, "detail": ""},
            {"category": "기본 관리", "item": "의존성 관리", "score": 0, "max_score": 5, "detail": ""},
        ]

    return results


# ── 오케스트레이터 ───────────────────────────────────

async def evaluate_repo(db: AsyncSession, project_id: int) -> dict | None:
    """레포 품질 평가 v2 실행."""
    async with _eval_semaphore:
        project = await db.get(Project, project_id)
        if not project:
            return None

        settings = get_settings()
        headers = _get_headers()
        if not headers or not settings.github_token:
            return {"error": "GitHub 토큰 미설정"}

        parsed = _parse_repo(str(project.repo_url))
        if not parsed:
            return {"error": f"repo_url 파싱 실패: {project.repo_url}"}

        owner, repo = parsed
        clone_path = None

        try:
            # 1. Clone
            clone_path = await shallow_clone(owner, repo, settings.github_token)

            # 2. 언어 감지 + 통계
            language = detect_language(clone_path)
            file_stats = count_files(clone_path, language)

            # 3. 정적 분석 (병렬)
            lint_task = _score_lint(clone_path, language, file_stats)
            type_task = _score_typecheck(clone_path, language, file_stats)
            complexity_task = _score_complexity(clone_path, language)
            security_task = _score_security(clone_path, language)
            secrets_task = _score_secrets(clone_path)

            lint_r, type_r, complexity_r, security_r, secrets_r = await asyncio.gather(
                lint_task, type_task, complexity_task, security_task, secrets_task
            )

            # 4. GPT 코드 리뷰
            lint_errors = int(lint_r["detail"].split("에러 ")[1].split("건")[0]) if "에러 " in lint_r["detail"] else 0
            type_errors = int(type_r["detail"].split("에러 ")[1].split("건")[0]) if "에러 " in type_r["detail"] else 0
            gpt_r = await _score_gpt_review(clone_path, language, file_stats, lint_errors, type_errors)

            # 5. 기본 관리 (GitHub API)
            basic_results = await _score_basic_management(owner, repo, headers)

        except (TimeoutError, ValueError) as e:
            return {"error": str(e)}
        except Exception as e:
            return {"error": f"평가 실패: {e}"}
        finally:
            if clone_path:
                cleanup_clone(clone_path)

        # 6. 합산
        categories = [lint_r, type_r, complexity_r, security_r, secrets_r, gpt_r] + basic_results
        total = sum(c["score"] for c in categories)
        grade = _get_grade(total)
        gpt_review = gpt_r.get("detail", "")

        # 7. DB upsert
        result = await db.execute(select(RepoScore).where(RepoScore.project_id == project_id))
        existing = result.scalar_one_or_none()
        if existing:
            existing.total_score = total  # type: ignore[assignment]
            existing.grade = grade  # type: ignore[assignment]
            existing.categories_json = json.dumps(categories, ensure_ascii=False)  # type: ignore[assignment]
            existing.gpt_review = gpt_review  # type: ignore[assignment]
            existing.evaluated_at = datetime.now(timezone.utc)  # type: ignore[assignment]
        else:
            score_obj = RepoScore(
                project_id=project_id,
                total_score=total,
                grade=grade,
                categories_json=json.dumps(categories, ensure_ascii=False),
                gpt_review=gpt_review,
            )
            db.add(score_obj)
        await db.commit()

        result_data = {
            "project_id": project_id,
            "total_score": total,
            "grade": grade,
            "language": language,
            "file_stats": file_stats,
            "categories": categories,
            "gpt_review": gpt_review,
            "evaluated_at": datetime.now(timezone.utc).isoformat(),
        }
        _score_cache[project_id] = (time.time() + CACHE_TTL, result_data)
        return result_data


async def get_cached_score(db: AsyncSession, project_id: int) -> dict | None:
    """캐시 또는 DB에서 점수 조회."""
    if project_id in _score_cache:
        expire_ts, data = _score_cache[project_id]
        if time.time() < expire_ts:
            return data
        del _score_cache[project_id]

    result = await db.execute(select(RepoScore).where(RepoScore.project_id == project_id))
    score = result.scalar_one_or_none()
    if not score:
        return None

    data = {
        "project_id": score.project_id,
        "total_score": score.total_score,
        "grade": score.grade,
        "categories": json.loads(str(score.categories_json)) if score.categories_json else [],
        "gpt_review": score.gpt_review or "",
        "evaluated_at": score.evaluated_at.isoformat() if score.evaluated_at else "",
    }
    _score_cache[project_id] = (time.time() + CACHE_TTL, data)
    return data
