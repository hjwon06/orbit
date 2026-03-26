"""팀원 코드 채점 서비스 — 100점 감점 방식.

카테고리별 배점:
  기능 완성도 35점 | 컨벤션 준수 25점 | 코드 품질 20점 | 보안/안정성 10점 | 테스트 10점
"""
import asyncio
import json
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models import Project, TeamMember, TeamScore

try:
    import httpx
    HAS_HTTPX = True
except ImportError:
    HAS_HTTPX = False

_eval_semaphore = asyncio.Semaphore(2)


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


# ── 1. 컨벤션 자동 검사 (25점) ──────────────────────────

CONVENTION_RULES = [
    {
        "id": "#5",
        "name": "도메인 하드코딩",
        "pattern": r"door_width|door_height|finish_material|opt_mid_key",
        "penalty": 2,
    },
    {
        "id": "#6",
        "name": "v3 잔재 컬럼명",
        "pattern": r"condition_value|action_value|target_attribute",
        "penalty": 1,
    },
    {
        "id": "#8",
        "name": "float 사용",
        "pattern": r"float\(",
        "penalty": 2,
    },
    {
        "id": "#9",
        "name": "서비스에서 commit",
        "pattern": r"\.commit\(\)",
        "penalty": 2,
        "search_path": "services/",
    },
]


def _check_conventions(local_path: str, module_path: str) -> tuple[int, list[dict]]:
    """grep 기반 컨벤션 자동 검사. (점수, 위반목록) 반환."""
    score = 25
    violations: list[dict] = []
    search_dir = Path(local_path) / module_path.strip("/")

    if not search_dir.is_dir():
        return score, violations

    for rule in CONVENTION_RULES:
        search_path = search_dir
        if rule.get("search_path"):
            search_path = search_dir / rule["search_path"]
            if not search_path.is_dir():
                continue

        pattern = re.compile(rule["pattern"])
        found = 0
        for py_file in search_path.rglob("*.py"):
            try:
                lines = py_file.read_text(encoding="utf-8").split("\n")
                for i, line in enumerate(lines, 1):
                    if pattern.search(line):
                        found += 1
                        if found <= 10:
                            rel = py_file.relative_to(Path(local_path))
                            penalty = rule["penalty"]
                            score = max(0, score - penalty)
                            violations.append({
                                "rule": rule["id"],
                                "name": rule["name"],
                                "location": f"{rel}:{i}: {line.strip()[:100]}",
                                "penalty": penalty,
                                "category": "convention",
                            })
            except (OSError, UnicodeDecodeError):
                continue

    return max(0, score), violations


# ── 2. 모듈 월권 검사 (컨벤션 추가 감점) ──────────────────

def _check_module_boundary(local_path: str, member_name: str, module_path: str) -> list[dict]:
    """git log에서 팀원이 다른 모듈 파일을 수정했는지 확인."""
    violations: list[dict] = []
    if not module_path:
        return violations
    try:
        result = subprocess.run(
            ["git", "log", "--author", member_name, "--name-only", "--pretty=format:", "-20"],
            capture_output=True, text=True, timeout=10, cwd=local_path,
        )
        if not result or not result.stdout or not result.stdout.strip():
            return violations

        files = set(result.stdout.strip().split("\n"))
        my_module = module_path.strip("/")
        for f in files:
            f = f.strip()
            if not f or not f.startswith("app/modules/"):
                continue
            if not f.startswith(my_module):
                violations.append({
                    "rule": "#7",
                    "name": "모듈 월권",
                    "location": f,
                    "penalty": 3,
                    "category": "convention",
                })
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        pass
    return violations


# ── 3. 테스트 검사 (10점) ──────────────────────────────

def _check_tests(local_path: str, module_path: str) -> tuple[int, list[dict]]:
    """pytest 실행 결과 기반 테스트 점수."""
    score = 10
    violations: list[dict] = []

    # 모듈 관련 테스트 파일 존재 여부
    test_dir = Path(local_path) / "tests"
    module_name = module_path.strip("/").split("/")[-1] if module_path else ""

    if not test_dir.is_dir():
        violations.append({
            "rule": "TEST",
            "name": "tests/ 디렉토리 없음",
            "location": "tests/",
            "penalty": 10,
            "category": "testing",
        })
        return 0, violations

    # 모듈 관련 테스트 파일 검색
    test_files = list(test_dir.glob(f"*{module_name}*")) if module_name else []
    if not test_files and module_name:
        violations.append({
            "rule": "TEST",
            "name": f"{module_name} 모듈 테스트 파일 없음",
            "location": f"tests/*{module_name}*",
            "penalty": 5,
            "category": "testing",
        })
        score -= 5

    return max(0, score), violations


# ── 4. GPT 리뷰 (코드 품질 20점 + 보안 10점) ──────────────

async def _gpt_review(local_path: str, module_path: str, member_name: str) -> tuple[int, int, list[dict], str]:
    """GPT 정밀 리뷰. (quality_score, security_score, violations, review_text) 반환."""
    quality = 20
    security = 10
    violations: list[dict] = []
    review_text = ""

    if not HAS_HTTPX:
        return quality, security, violations, "httpx 미설치"

    settings = get_settings()
    api_key = settings.openai_api_key
    if not api_key:
        return quality, security, violations, "OpenAI API 키 미설정"

    # 모듈 파일 수집 (최대 12000자)
    search_dir = Path(local_path) / module_path.strip("/")
    if not search_dir.is_dir():
        return quality, security, violations, "모듈 경로 없음"

    code_text = ""
    for py_file in sorted(search_dir.rglob("*.py"))[:15]:
        try:
            content = py_file.read_text(encoding="utf-8")
            rel = py_file.relative_to(Path(local_path))
            code_text += f"\n### {rel}\n```python\n{content[:2000]}\n```\n"
            if len(code_text) > 12000:
                break
        except (OSError, UnicodeDecodeError):
            continue

    if not code_text:
        return quality, security, violations, "코드 파일 없음"

    prompt = f"""당신은 시니어 코드 리뷰어입니다. 다음은 '{member_name}' 팀원의 코드입니다.

아래 기준으로 검수하세요:
1. 터지는 곳 (보안/안정성 문제): path traversal, SQL injection, 블로킹 I/O, 세션 미정리
2. 고치면 좋은 곳 (코드 품질): 아키텍처, 에러 처리, 가독성, 중복 코드

반드시 다음 JSON 형식으로만 응답하세요:
{{
  "critical": [{{"file": "...", "line": 0, "reason": "..."}}],
  "improvement": [{{"file": "...", "line": 0, "reason": "..."}}],
  "summary": "한국어 3줄 요약"
}}

{code_text}"""

    try:
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(
                "https://api.openai.com/v1/chat/completions",
                headers={"Authorization": f"Bearer {api_key}"},
                json={
                    "model": "gpt-4o-mini",
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.2,
                },
            )
            data = resp.json()
            content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
            review_text = content

            # JSON 파싱
            json_match = re.search(r"\{[\s\S]*\}", content)
            if json_match:
                parsed = json.loads(json_match.group())

                # 터지는 곳 → 보안 감점 (건당 -3)
                for item in parsed.get("critical", []):
                    penalty = 3
                    security = max(0, security - penalty)
                    violations.append({
                        "rule": "SEC",
                        "name": item.get("reason", "보안 이슈")[:100],
                        "location": f"{item.get('file', '?')}:{item.get('line', '?')}",
                        "penalty": penalty,
                        "category": "security",
                    })

                # 고치면 좋은 곳 → 품질 감점 (건당 -1)
                for item in parsed.get("improvement", []):
                    penalty = 1
                    quality = max(0, quality - penalty)
                    violations.append({
                        "rule": "QUAL",
                        "name": item.get("reason", "품질 개선")[:100],
                        "location": f"{item.get('file', '?')}:{item.get('line', '?')}",
                        "penalty": penalty,
                        "category": "quality",
                    })

    except Exception:
        review_text = "GPT 리뷰 실패 (API 오류)"

    return max(0, quality), max(0, security), violations, review_text


# ── 5. 기능 완성도 (35점) — 파일 존재 기반 ──────────────────

def _check_completeness(local_path: str, module_path: str) -> tuple[int, list[dict]]:
    """모듈 내 서비스/라우터/모델 파일 존재 여부로 완성도 추정."""
    score = 35
    violations: list[dict] = []
    search_dir = Path(local_path) / module_path.strip("/")

    if not search_dir.is_dir():
        return 0, [{"rule": "COMP", "name": "모듈 디렉토리 없음", "location": module_path, "penalty": 35, "category": "completeness"}]

    # 필수 구조 체크
    expected = {
        "routers/": "라우터",
        "services/": "서비스",
    }
    for subdir, label in expected.items():
        subpath = search_dir / subdir
        if not subpath.is_dir() or not list(subpath.glob("*.py")):
            penalty = 10
            score -= penalty
            violations.append({
                "rule": "COMP",
                "name": f"{label} 레이어 없음",
                "location": f"{module_path}{subdir}",
                "penalty": penalty,
                "category": "completeness",
            })

    # 빈 파일 / TODO 잔재
    for py_file in search_dir.rglob("*.py"):
        try:
            content = py_file.read_text(encoding="utf-8")
            if len(content.strip()) < 50:
                score -= 2
                violations.append({
                    "rule": "COMP",
                    "name": "빈 파일 또는 스텁",
                    "location": str(py_file.relative_to(Path(local_path))),
                    "penalty": 2,
                    "category": "completeness",
                })
            todo_count = content.lower().count("todo")
            if todo_count >= 3:
                score -= 1
                violations.append({
                    "rule": "COMP",
                    "name": f"TODO {todo_count}건 잔재",
                    "location": str(py_file.relative_to(Path(local_path))),
                    "penalty": 1,
                    "category": "completeness",
                })
        except (OSError, UnicodeDecodeError):
            continue

    return max(0, score), violations


# ── 메인 평가 함수 ──────────────────────────────────

async def evaluate_member(
    db: AsyncSession, project: Project, member: TeamMember
) -> TeamScore:
    """팀원 1명 채점."""
    async with _eval_semaphore:
        local_path = str(project.local_path or "")
        module_path = member.module_path or ""

        # 1. 컨벤션 (25점)
        conv_score, conv_violations = _check_conventions(local_path, module_path)

        # 모듈 월권 추가 감점
        boundary_violations = _check_module_boundary(local_path, str(member.member_name), module_path)
        for v in boundary_violations:
            conv_score = max(0, conv_score - v["penalty"])
        conv_violations.extend(boundary_violations)

        # 2. 테스트 (10점)
        test_score, test_violations = _check_tests(local_path, module_path)

        # 3. GPT 리뷰 (품질 20점 + 보안 10점)
        qual_score, sec_score, gpt_violations, review_text = await _gpt_review(
            local_path, module_path, str(member.display_name)
        )

        # 4. 기능 완성도 (35점)
        comp_score, comp_violations = _check_completeness(local_path, module_path)

        # 총점
        total = comp_score + conv_score + qual_score + sec_score + test_score
        total = max(0, min(100, total))

        all_violations = conv_violations + test_violations + gpt_violations + comp_violations

        # DB 저장
        score = TeamScore(
            project_id=project.id,
            member_name=str(member.member_name),
            total_score=total,
            grade=_get_grade(total),
            completeness=comp_score,
            convention=conv_score,
            quality=qual_score,
            security=sec_score,
            testing=test_score,
            violations_json=json.dumps(all_violations, ensure_ascii=False),
            gpt_review=review_text,
        )
        db.add(score)
        await db.commit()
        await db.refresh(score)
        return score


async def evaluate_all(db: AsyncSession, project_id: int) -> list[TeamScore]:
    """전체 팀원 채점."""
    project = (await db.execute(
        select(Project).where(Project.id == project_id)
    )).scalar_one_or_none()
    if not project:
        return []

    members = (await db.execute(
        select(TeamMember).where(
            TeamMember.project_id == project_id,
            TeamMember.is_excluded.is_(False),
        )
    )).scalars().all()

    results: list[TeamScore] = []
    for member in members:
        score = await evaluate_member(db, project, member)
        results.append(score)
    return results


async def get_latest_scores(db: AsyncSession, project_id: int) -> list[dict]:
    """팀원별 최신 채점 결과 조회."""
    members = (await db.execute(
        select(TeamMember).where(
            TeamMember.project_id == project_id,
            TeamMember.is_excluded.is_(False),
        )
    )).scalars().all()

    results: list[dict] = []
    for member in members:
        score = (await db.execute(
            select(TeamScore).where(
                TeamScore.project_id == project_id,
                TeamScore.member_name == member.member_name,
            ).order_by(TeamScore.evaluated_at.desc()).limit(1)
        )).scalar_one_or_none()

        results.append({
            "member": member,
            "score": score,
        })
    return results


async def get_member_history(db: AsyncSession, project_id: int, member_name: str, limit: int = 10) -> list[TeamScore]:
    """팀원 점수 이력."""
    result = await db.execute(
        select(TeamScore).where(
            TeamScore.project_id == project_id,
            TeamScore.member_name == member_name,
        ).order_by(TeamScore.evaluated_at.desc()).limit(limit)
    )
    return list(result.scalars().all())
