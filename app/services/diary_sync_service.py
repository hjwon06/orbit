"""옵시디언 다이어리 → ORBIT 할일 자동 동기화 서비스."""
import hashlib
import json
import logging
from datetime import date, datetime, timedelta
from pathlib import Path

from openai import AsyncOpenAI
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models import Todo, Milestone

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


def _make_diary_ref(project_slug: str, date_str: str, item_text: str) -> str:
    """중복 방지용 참조 키 생성.

    형식: "{slug}:{date}:{sha256_hash[:8]}"
    """
    h = hashlib.sha256(item_text.encode()).hexdigest()[:8]
    return f"{project_slug}:{date_str}:{h}"


async def sync_tomorrow_todos(
    db: AsyncSession,
    project_id: int,
    project_slug: str,
    diary_entries: list[dict],
) -> dict:
    """다이어리의 '내일 할 일' → Todo 생성 (중복 방지)."""
    created = 0
    skipped = 0

    # 활성 마일스톤 조회 (오늘 날짜가 start_date~end_date 범위)
    today = date.today()
    ms_result = await db.execute(
        select(Milestone).where(
            Milestone.project_id == project_id,
            Milestone.deleted_at.is_(None),
            Milestone.status != "done",
            Milestone.start_date <= today,
            Milestone.end_date >= today,
        ).limit(1)
    )
    active_milestone = ms_result.scalar_one_or_none()
    milestone_id = active_milestone.id if active_milestone else None

    for entry in diary_entries:
        date_str = entry["date"]
        for item_text in entry.get("tomorrow_items", []):
            diary_ref = _make_diary_ref(project_slug, date_str, item_text)

            # diary_ref 중복 체크
            existing_ref = await db.execute(
                select(Todo).where(Todo.diary_ref == diary_ref)
            )
            if existing_ref.scalar_one_or_none():
                skipped += 1
                continue

            # 같은 title + source="diary" + status="open" 중복 체크
            existing_title = await db.execute(
                select(Todo).where(
                    and_(
                        Todo.project_id == project_id,
                        Todo.title == item_text,
                        Todo.source == "diary",
                        Todo.status == "open",
                        Todo.deleted_at.is_(None),
                    )
                )
            )
            if existing_title.scalar_one_or_none():
                skipped += 1
                continue

            db.add(Todo(
                project_id=project_id,
                milestone_id=milestone_id,
                title=item_text,
                source="diary",
                diary_ref=diary_ref,
            ))
            created += 1

    if created > 0:
        await db.commit()

    return {"created": created, "skipped": skipped}


async def match_and_complete_todos(
    db: AsyncSession,
    project_id: int,
    done_items: list[str],
) -> dict:
    """GPT-4o로 '오늘 한 일' ↔ 열린 할일 매칭 → 완료 처리."""
    # open 할일 목록 조회
    result = await db.execute(
        select(Todo).where(
            Todo.project_id == project_id,
            Todo.status == "open",
            Todo.deleted_at.is_(None),
        )
    )
    open_todos = result.scalars().all()

    if not open_todos or not done_items:
        return {"matched": 0}

    # GPT-4o 매칭
    try:
        settings = get_settings()
        if not settings.openai_api_key:
            logger.warning("OpenAI API 키 미설정 — 매칭 스킵")
            return {"matched": 0}

        client = AsyncOpenAI(api_key=settings.openai_api_key)

        done_list = "\n".join(f"- {item}" for item in done_items)
        todo_list = "\n".join(f"- [id={t.id}] {t.title}" for t in open_todos)

        response = await client.chat.completions.create(
            model="gpt-4o",
            temperature=0,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "개발자의 오늘 한 일과 열린 할일을 비교하여 완료된 할일을 매칭하세요. "
                        "보수적으로 판단. JSON 배열 반환: "
                        '[{"todo_id": 숫자, "diary_item": "매칭된 항목"}]. '
                        "JSON만 반환."
                    ),
                },
                {
                    "role": "user",
                    "content": f"[오늘 한 일]\n{done_list}\n\n[열린 할일]\n{todo_list}",
                },
            ],
        )

        raw = response.choices[0].message.content or "[]"

        # ```json ... ``` 핸들링
        if "```" in raw:
            # ```json\n...\n``` 또는 ```\n...\n```
            parts = raw.split("```")
            for part in parts:
                stripped = part.strip()
                if stripped.startswith("json"):
                    stripped = stripped[4:].strip()
                if stripped.startswith("["):
                    raw = stripped
                    break

        matches = json.loads(raw)

        # 유효성 검증
        open_todo_ids = {t.id for t in open_todos}
        open_todo_map = {t.id: t for t in open_todos}
        matched = 0
        now = datetime.now()

        for m in matches:
            todo_id = m.get("todo_id")
            if todo_id not in open_todo_ids:
                continue
            todo = open_todo_map[todo_id]
            todo.status = "done"  # type: ignore[assignment]
            todo.completed_at = now  # type: ignore[assignment]
            matched += 1

        if matched > 0:
            await db.commit()

        logger.info(f"다이어리 매칭 완료: project={project_id}, matched={matched}")
        return {"matched": matched}

    except Exception as e:
        logger.warning(f"다이어리 매칭 실패: project={project_id}, error={e}")
        return {"matched": 0}


async def auto_sync_diary_if_needed(
    db: AsyncSession,
    project_id: int,
    project_slug: str,
) -> dict | None:
    """페이지 로드 시 호출 — 쿨다운 내면 스킵, 아니면 다이어리 동기화."""
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
        # 최근 3일 다이어리 파싱
        diary_entries = parse_recent_diaries(diary_dir, days=3)
        if not diary_entries:
            return {"sync_todos": {"created": 0, "skipped": 0}, "match": {"matched": 0}}

        # 내일 할 일 → Todo 생성
        sync_result = await sync_tomorrow_todos(db, project_id, project_slug, diary_entries)

        # 오늘 한 일 → 완료 매칭
        all_done_items: list[str] = []
        for entry in diary_entries:
            all_done_items.extend(entry.get("done_items", []))

        match_result = await match_and_complete_todos(db, project_id, all_done_items)

        logger.info(
            f"다이어리 자동 동기화 완료: project={project_id}, "
            f"sync={sync_result}, match={match_result}"
        )
        return {"sync_todos": sync_result, "match": match_result}

    except Exception as e:
        logger.warning(f"다이어리 자동 동기화 실패: project={project_id}, error={e}")
        return {"error": str(e)}
