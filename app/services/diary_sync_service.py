"""옵시디언 다이어리 → ORBIT 동기화 서비스 (Todo 기능 제거됨)."""
import logging
from datetime import date, datetime, timedelta
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

# 프로젝트별 마지막 동기화 시각 (메모리 캐시, 1시간 쿨다운)
_last_diary_sync: dict[int, datetime] = {}
DIARY_SYNC_COOLDOWN_SEC = 3600  # 1시간


def parse_diary_file(file_path: Path) -> dict:
    """마크다운 다이어리 파일을 섹션별로 파싱.

    Returns:
        {"date": "2026-03-20", "done_items": [...], "tomorrow_items": [...]}
    """
    # 파일명에서 날짜 추출 (YYYY-MM-DD.md)
    date_str = file_path.stem  # "2026-03-20"

    text = file_path.read_text(encoding="utf-8")
    lines = text.splitlines()

    sections: dict[str, list[str]] = {}
    current_section = ""

    for line in lines:
        stripped = line.strip()
        # ## 헤딩으로 섹션 분리 (### 서브헤딩은 무시)
        if stripped.startswith("## ") and not stripped.startswith("### "):
            current_section = stripped[3:].strip()
            sections[current_section] = []
        elif stripped.startswith("- ") and current_section:
            sections[current_section].append(stripped[2:].strip())

    done_items = sections.get("오늘 한 일", [])
    tomorrow_items = sections.get("내일 할 일", [])

    return {
        "date": date_str,
        "done_items": done_items,
        "tomorrow_items": tomorrow_items,
    }


def parse_recent_diaries(diary_dir: Path, days: int = 3) -> list[dict]:
    """최근 N일 다이어리 파일을 파싱하여 날짜 내림차순 반환."""
    today = date.today()
    results: list[dict] = []

    for i in range(days):
        d = today - timedelta(days=i)
        file_path = diary_dir / f"{d.isoformat()}.md"
        if file_path.exists():
            try:
                entry = parse_diary_file(file_path)
                results.append(entry)
            except Exception as e:
                logger.warning(f"다이어리 파싱 실패: {file_path} — {e}")

    # 날짜 내림차순 (이미 오늘부터 역순이지만 명시적 정렬)
    results.sort(key=lambda x: x["date"], reverse=True)
    return results


async def auto_sync_diary_if_needed(
    db: AsyncSession,
    project_id: int,
    project_slug: str,
) -> dict | None:
    """페이지 로드 시 호출 — 쿨다운 내면 스킵, 아니면 다이어리 동기화."""
    from app.config import get_settings

    now = datetime.now()
    last = _last_diary_sync.get(project_id)
    if last and (now - last).total_seconds() < DIARY_SYNC_COOLDOWN_SEC:
        return None  # 쿨다운 중

    settings = get_settings()
    vault_path = settings.obsidian_vault_path
    if not vault_path:
        return None

    diary_dir = Path(vault_path) / "diary" / project_slug
    if not diary_dir.exists():
        return None

    _last_diary_sync[project_id] = now

    try:
        # 주간 마일스톤 자동 관리
        from app.services.milestone_service import ensure_weekly_milestone
        await ensure_weekly_milestone(db, project_id)

        logger.info(f"다이어리 동기화 완료: project={project_id} (Todo 동기화 비활성화)")
        return {"synced": True}

    except Exception as e:
        logger.warning(f"다이어리 자동 동기화 실패: project={project_id}, error={e}")
        return {"error": str(e)}
