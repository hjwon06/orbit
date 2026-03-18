"""GitHub 연동 — 토큰 + repo_url 설정 시 자동 동작."""
import re
from datetime import date, timedelta
from collections import defaultdict

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Project, CommitStat, Todo
from app.config import get_settings

GITHUB_API = "https://api.github.com"


def _parse_repo(repo_url: str) -> tuple[str, str] | None:
    """repo_url에서 owner/repo 추출. 다양한 형식 지원."""
    if not repo_url:
        return None
    # https://github.com/owner/repo(.git)
    m = re.match(r"https?://github\.com/([^/]+)/([^/.]+)", repo_url)
    if m:
        return m.group(1), m.group(2)
    # git@github.com:owner/repo.git
    m = re.match(r"git@github\.com:([^/]+)/([^/.]+)", repo_url)
    if m:
        return m.group(1), m.group(2)
    # owner/repo (직접 입력)
    m = re.match(r"^([^/]+)/([^/]+)$", repo_url)
    if m:
        return m.group(1), m.group(2)
    return None


def _get_headers() -> dict | None:
    """GitHub 토큰 헤더. 토큰 미설정 시 None 반환."""
    settings = get_settings()
    if not settings.github_token:
        return None
    return {
        "Authorization": f"Bearer {settings.github_token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }


async def check_github_ready(db: AsyncSession, project_id: int) -> dict:
    """GitHub 연동 가능 여부 체크."""
    headers = _get_headers()
    result = await db.execute(select(Project).where(Project.id == project_id))
    project = result.scalar_one_or_none()

    return {
        "token_set": headers is not None,
        "repo_url": project.repo_url if project else "",
        "repo_parsed": _parse_repo(project.repo_url) is not None if project else False,
        "ready": headers is not None and project is not None and _parse_repo(project.repo_url) is not None,
    }


async def sync_commits(db: AsyncSession, project_id: int, days: int = 30) -> dict:
    """GitHub 커밋 → commit_stats 동기화."""
    headers = _get_headers()
    if not headers:
        return {"error": "ORBIT_GITHUB_TOKEN이 설정되지 않았습니다."}

    result = await db.execute(select(Project).where(Project.id == project_id))
    project = result.scalar_one_or_none()
    if not project:
        return {"error": "프로젝트를 찾을 수 없습니다."}

    parsed = _parse_repo(project.repo_url)
    if not parsed:
        return {"error": f"repo_url을 파싱할 수 없습니다: {project.repo_url}"}

    owner, repo = parsed
    since = (date.today() - timedelta(days=days)).isoformat() + "T00:00:00Z"

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            commits_by_date: dict[str, dict] = defaultdict(lambda: {"count": 0, "additions": 0, "deletions": 0})
            page = 1

            while True:
                resp = await client.get(
                    f"{GITHUB_API}/repos/{owner}/{repo}/commits",
                    headers=headers,
                    params={"since": since, "per_page": 100, "page": page},
                )
                resp.raise_for_status()
                items = resp.json()
                if not items:
                    break

                for commit in items:
                    commit_date = commit["commit"]["author"]["date"][:10]
                    commits_by_date[commit_date]["count"] += 1

                    # 개별 커밋 상세에서 additions/deletions 가져오기 (rate limit 주의)
                    sha = commit["sha"]
                    detail_resp = await client.get(
                        f"{GITHUB_API}/repos/{owner}/{repo}/commits/{sha}",
                        headers=headers,
                    )
                    if detail_resp.status_code == 200:
                        stats = detail_resp.json().get("stats", {})
                        commits_by_date[commit_date]["additions"] += stats.get("additions", 0)
                        commits_by_date[commit_date]["deletions"] += stats.get("deletions", 0)

                if len(items) < 100:
                    break
                page += 1

            # DB upsert
            synced = 0
            for date_str, data in commits_by_date.items():
                d = date.fromisoformat(date_str)
                existing = await db.execute(
                    select(CommitStat).where(
                        CommitStat.project_id == project_id,
                        CommitStat.stat_date == d,
                    )
                )
                stat = existing.scalar_one_or_none()
                if stat:
                    stat.commit_count = data["count"]  # type: ignore[assignment]
                    stat.additions = data["additions"]  # type: ignore[assignment]
                    stat.deletions = data["deletions"]  # type: ignore[assignment]
                    stat.source = "github"  # type: ignore[assignment]
                else:
                    db.add(CommitStat(
                        project_id=project_id, stat_date=d,
                        commit_count=data["count"], additions=data["additions"],
                        deletions=data["deletions"], source="github",
                    ))
                synced += 1
            await db.commit()

            return {"ok": True, "synced_days": synced, "repo": f"{owner}/{repo}"}

    except httpx.HTTPStatusError as e:
        return {"error": f"GitHub API 에러: {e.response.status_code}"}
    except Exception as e:
        return {"error": f"동기화 실패: {str(e)}"}


async def sync_issues(db: AsyncSession, project_id: int) -> dict:
    """GitHub 이슈 → todos 동기화."""
    headers = _get_headers()
    if not headers:
        return {"error": "ORBIT_GITHUB_TOKEN이 설정되지 않았습니다."}

    result = await db.execute(select(Project).where(Project.id == project_id))
    project = result.scalar_one_or_none()
    if not project:
        return {"error": "프로젝트를 찾을 수 없습니다."}

    parsed = _parse_repo(project.repo_url)
    if not parsed:
        return {"error": f"repo_url을 파싱할 수 없습니다: {project.repo_url}"}

    owner, repo = parsed

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(
                f"{GITHUB_API}/repos/{owner}/{repo}/issues",
                headers=headers,
                params={"state": "open", "per_page": 50},
            )
            resp.raise_for_status()
            issues = resp.json()

            created = 0
            skipped = 0
            for issue in issues:
                if issue.get("pull_request"):
                    continue

                issue_url = issue["html_url"]
                existing = await db.execute(
                    select(Todo).where(
                        Todo.project_id == project_id,
                        Todo.github_issue_url == issue_url,
                    )
                )
                if existing.scalar_one_or_none():
                    skipped += 1
                    continue

                labels = [lb["name"] for lb in issue.get("labels", [])]
                priority = "high" if "bug" in labels or "urgent" in labels else "medium"

                db.add(Todo(
                    project_id=project_id,
                    title=f"#{issue['number']} {issue['title']}",
                    description=issue.get("body", "")[:500] or "",
                    priority=priority,
                    source="github",
                    github_issue_url=issue_url,
                ))
                created += 1

            await db.commit()
            return {"ok": True, "created": created, "skipped": skipped, "repo": f"{owner}/{repo}"}

    except httpx.HTTPStatusError as e:
        return {"error": f"GitHub API 에러: {e.response.status_code}"}
    except Exception as e:
        return {"error": f"동기화 실패: {str(e)}"}
