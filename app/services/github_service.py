"""GitHub 연동 — 토큰 + repo_url 설정 시 자동 동작."""
import asyncio
import re
import logging
import time
from datetime import date, datetime, timedelta
from collections import defaultdict

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Project, CommitStat
from app.config import get_settings

logger = logging.getLogger(__name__)

# 프로젝트별 마지막 자동 동기화 시각 (메모리 캐시, 10분 쿨다운)
_last_auto_sync: dict[int, datetime] = {}
AUTO_SYNC_COOLDOWN_SEC = 600  # 10분

# 브랜치 커밋 캐시 (프로젝트 ID → (만료시각, 데이터))
_branch_commits_cache: dict[int, tuple[float, dict]] = {}
BRANCH_COMMITS_CACHE_TTL = 300  # 5분

GITHUB_API = "https://api.github.com"
GITHUB_GRAPHQL = "https://api.github.com/graphql"


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
        "repo_parsed": _parse_repo(str(project.repo_url)) is not None if project else False,
        "ready": headers is not None and project is not None and _parse_repo(str(project.repo_url)) is not None,
    }


async def _sync_commits_graphql(
    client: httpx.AsyncClient,
    owner: str,
    repo: str,
    headers: dict,
    since: str,
) -> dict[str, dict]:
    """GraphQL 단일 쿼리로 커밋 히스토리 수집 (커서 페이지네이션)."""
    query = """
    query($owner: String!, $repo: String!, $since: GitTimestamp!, $after: String) {
      repository(owner: $owner, name: $repo) {
        defaultBranchRef {
          target {
            ... on Commit {
              history(first: 100, since: $since, after: $after) {
                totalCount
                pageInfo { hasNextPage endCursor }
                nodes { oid committedDate additions deletions }
              }
            }
          }
        }
      }
    }
    """
    commits_by_date: dict[str, dict] = defaultdict(
        lambda: {"count": 0, "additions": 0, "deletions": 0},
    )
    after: str | None = None

    while True:
        variables: dict = {
            "owner": owner,
            "repo": repo,
            "since": since,
        }
        if after:
            variables["after"] = after

        resp = await client.post(
            GITHUB_GRAPHQL,
            headers=headers,
            json={"query": query, "variables": variables},
        )
        resp.raise_for_status()
        body = resp.json()

        # GraphQL 에러 체크 (HTTP 200이지만 errors 배열 포함)
        if "errors" in body:
            raise RuntimeError(f"GraphQL 에러: {body['errors']}")

        repository = body.get("data", {}).get("repository")
        if not repository:
            raise RuntimeError("리포지토리를 찾을 수 없습니다.")

        default_ref = repository.get("defaultBranchRef")
        if not default_ref:
            # 빈 리포지토리 (커밋 없음)
            logger.info(f"빈 리포지토리: {owner}/{repo}")
            break

        history = default_ref["target"]["history"]
        nodes = history.get("nodes", [])

        for node in nodes:
            commit_date = node["committedDate"][:10]
            commits_by_date[commit_date]["count"] += 1
            commits_by_date[commit_date]["additions"] += node.get("additions", 0)
            commits_by_date[commit_date]["deletions"] += node.get("deletions", 0)

        page_info = history.get("pageInfo", {})
        if page_info.get("hasNextPage"):
            after = page_info["endCursor"]
        else:
            break

    return dict(commits_by_date)


async def _sync_commits_rest(
    client: httpx.AsyncClient,
    owner: str,
    repo: str,
    headers: dict,
    since: str,
) -> dict[str, dict]:
    """REST API N+1 방식 커밋 수집 (GraphQL fallback용)."""
    commits_by_date: dict[str, dict] = defaultdict(
        lambda: {"count": 0, "additions": 0, "deletions": 0},
    )
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
            try:
                detail_resp = await client.get(
                    f"{GITHUB_API}/repos/{owner}/{repo}/commits/{sha}",
                    headers=headers,
                )
                if detail_resp.status_code == 200:
                    stats = detail_resp.json().get("stats", {})
                    commits_by_date[commit_date]["additions"] += stats.get("additions", 0)
                    commits_by_date[commit_date]["deletions"] += stats.get("deletions", 0)
            except Exception:
                logger.warning(f"커밋 상세 조회 실패: {sha}")

        if len(items) < 100:
            break
        page += 1

    return dict(commits_by_date)


async def _upsert_commit_stats(
    db: AsyncSession,
    project_id: int,
    commits_by_date: dict[str, dict],
) -> int:
    """커밋 통계 DB upsert. 동기화된 날짜 수 반환."""
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
    return synced


async def sync_commits(db: AsyncSession, project_id: int, days: int = 30) -> dict:
    """GitHub 커밋 → commit_stats 동기화. GraphQL 우선, 실패 시 REST fallback."""
    headers = _get_headers()
    if not headers:
        return {"error": "ORBIT_GITHUB_TOKEN이 설정되지 않았습니다."}

    result = await db.execute(select(Project).where(Project.id == project_id))
    project = result.scalar_one_or_none()
    if not project:
        return {"error": "프로젝트를 찾을 수 없습니다."}

    parsed = _parse_repo(str(project.repo_url))
    if not parsed:
        return {"error": f"repo_url을 파싱할 수 없습니다: {project.repo_url}"}

    owner, repo = parsed
    since = (date.today() - timedelta(days=days)).isoformat() + "T00:00:00Z"

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            # GraphQL로 시도
            try:
                commits_by_date = await _sync_commits_graphql(
                    client, owner, repo, headers, since,
                )
                logger.info(f"GraphQL 커밋 동기화 성공: {owner}/{repo}")
            except Exception as e:
                # fallback: 기존 REST 방식
                logger.warning(f"GraphQL 실패, REST fallback: {owner}/{repo} — {e}")
                commits_by_date = await _sync_commits_rest(
                    client, owner, repo, headers, since,
                )

            # DB upsert
            synced = await _upsert_commit_stats(db, project_id, commits_by_date)

            return {"ok": True, "synced_days": synced, "repo": f"{owner}/{repo}"}

    except httpx.HTTPStatusError as e:
        return {"error": f"GitHub API 에러: {e.response.status_code}"}
    except Exception as e:
        return {"error": f"동기화 실패: {str(e)}"}


async def sync_issues(db: AsyncSession, project_id: int) -> dict:
    """GitHub 이슈 동기화 — Todo 기능 제거로 비활성화."""
    return {"ok": True, "created": 0, "skipped": 0, "message": "Todo 기능이 제거되어 이슈 동기화가 비활성화되었습니다."}


async def get_branch_commits(
    db: AsyncSession,
    project_id: int,
    max_branches: int = 20,
    commits_per_branch: int = 5,
) -> dict:
    """브랜치 목록 + 각 브랜치 최근 커밋 조회. 5분 메모리 캐시."""
    # ── 캐시 히트 ──
    if project_id in _branch_commits_cache:
        expire_ts, cached = _branch_commits_cache[project_id]
        if time.time() < expire_ts:
            return cached
        del _branch_commits_cache[project_id]

    # ── 사전 검증 ──
    headers = _get_headers()
    if not headers:
        return {"error": "ORBIT_GITHUB_TOKEN이 설정되지 않았습니다."}

    result = await db.execute(select(Project).where(Project.id == project_id))
    project = result.scalar_one_or_none()
    if not project:
        return {"error": "프로젝트를 찾을 수 없습니다."}

    parsed = _parse_repo(str(project.repo_url))
    if not parsed:
        return {"error": f"repo_url을 파싱할 수 없습니다: {project.repo_url}"}

    owner, repo = parsed

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            # 1) 레포 기본 정보 (default branch)
            repo_resp = await client.get(
                f"{GITHUB_API}/repos/{owner}/{repo}",
                headers=headers,
            )
            repo_resp.raise_for_status()
            default_branch = repo_resp.json().get("default_branch", "main")

            # 2) 브랜치 목록 조회
            branches_resp = await client.get(
                f"{GITHUB_API}/repos/{owner}/{repo}/branches",
                headers=headers,
                params={"per_page": 100},
            )
            branches_resp.raise_for_status()
            all_branches = branches_resp.json()

            # max_branches 제한 (default 브랜치 포함 보장)
            branch_names = [b["name"] for b in all_branches]
            if default_branch in branch_names:
                branch_names.remove(default_branch)
                branch_names = [default_branch] + branch_names[:max_branches - 1]
            else:
                branch_names = branch_names[:max_branches]

            branch_protected_map = {
                b["name"]: b.get("protected", False) for b in all_branches
            }

            # 3-0) 머지된 브랜치의 PR 커밋 조회 헬퍼 (모든 PR 합산)
            async def _fetch_pr_commits(
                client: httpx.AsyncClient, owner: str, repo: str,
                branch_name: str, headers: dict, limit: int,
            ) -> list:
                """머지된 PR 전체에서 해당 브랜치의 고유 커밋을 조회."""
                try:
                    pr_resp = await client.get(
                        f"{GITHUB_API}/repos/{owner}/{repo}/pulls",
                        headers=headers,
                        params={
                            "state": "closed",
                            "head": f"{owner}:{branch_name}",
                            "sort": "updated",
                            "direction": "desc",
                            "per_page": 10,
                        },
                    )
                    pr_resp.raise_for_status()
                    prs = [p for p in pr_resp.json() if p.get("merged_at")]
                    if not prs:
                        return []

                    # 모든 머지된 PR의 커밋을 병렬 수집
                    async def _get_pr(pr_number: int) -> list:
                        try:
                            resp = await client.get(
                                f"{GITHUB_API}/repos/{owner}/{repo}/pulls/{pr_number}/commits",
                                headers=headers,
                                params={"per_page": 30},
                            )
                            resp.raise_for_status()
                            return resp.json()
                        except Exception:
                            return []

                    all_results = await asyncio.gather(
                        *[_get_pr(p["number"]) for p in prs]
                    )

                    # 중복 제거 (sha 기준) + 최신순 정렬
                    seen = set()
                    all_commits = []
                    for pr_commits in all_results:
                        for c in pr_commits:
                            if c["sha"] not in seen:
                                seen.add(c["sha"])
                                all_commits.append(c)
                    all_commits.sort(
                        key=lambda c: c["commit"]["author"]["date"], reverse=True,
                    )
                    return all_commits[:limit]
                except Exception:
                    return []

            # 3) 각 브랜치 고유 커밋 병렬 조회 (Compare API)
            async def _fetch_branch_commits(branch_name: str) -> dict | None:
                try:
                    ahead = 0
                    behind = 0
                    merged = False

                    if branch_name == default_branch:
                        # default 브랜치: 일반 commits API
                        resp = await client.get(
                            f"{GITHUB_API}/repos/{owner}/{repo}/commits",
                            headers=headers,
                            params={"sha": branch_name, "per_page": commits_per_branch},
                        )
                        resp.raise_for_status()
                        raw_commits = resp.json()
                    else:
                        # Compare: default...branch → 고유 커밋 + ahead/behind
                        resp = await client.get(
                            f"{GITHUB_API}/repos/{owner}/{repo}/compare/{default_branch}...{branch_name}",
                            headers=headers,
                        )
                        resp.raise_for_status()
                        compare_data = resp.json()
                        ahead = compare_data.get("ahead_by", 0)
                        behind = compare_data.get("behind_by", 0)
                        unique_commits = list(reversed(compare_data.get("commits", [])))[:commits_per_branch]

                        if unique_commits:
                            # 고유 커밋이 있으면 그것만 표시
                            raw_commits = unique_commits
                        else:
                            # 머지 완료: PR 커밋 히스토리 조회
                            merged = True
                            raw_commits = await _fetch_pr_commits(
                                client, owner, repo, branch_name,
                                headers, commits_per_branch,
                            )

                    commits = []
                    for c in raw_commits:
                        commits.append({
                            "sha": c["sha"][:7],
                            "message": c["commit"]["message"].split("\n")[0][:120],
                            "author": (
                                c.get("author", {}) or {}
                            ).get("login", c["commit"]["author"]["name"]),
                            "author_avatar": (
                                c.get("author", {}) or {}
                            ).get("avatar_url", ""),
                            "date": c["commit"]["author"]["date"],
                        })

                    last_commit_date = commits[0]["date"] if commits else ""

                    return {
                        "name": branch_name,
                        "protected": branch_protected_map.get(branch_name, False),
                        "last_commit_date": last_commit_date,
                        "commits": commits,
                        "ahead": ahead,
                        "behind": behind,
                        "merged": merged,
                    }
                except Exception as e:
                    logger.warning(
                        f"브랜치 커밋 조회 실패: {owner}/{repo}/{branch_name} — {e}"
                    )
                    return None  # 개별 실패 시 해당 브랜치 스킵

            tasks = [_fetch_branch_commits(name) for name in branch_names]
            results = await asyncio.gather(*tasks)

            # None(실패) 제거
            branches = [b for b in results if b is not None]

            # 정렬: default 브랜치 최상단 고정, 나머지는 최근 커밋 순
            default_list = [b for b in branches if b["name"] == default_branch]
            other_list = [b for b in branches if b["name"] != default_branch]
            other_list.sort(key=lambda b: b.get("last_commit_date", ""), reverse=True)

            sorted_branches = default_list + other_list

            data = {
                "branches": sorted_branches,
                "total_branches": len(all_branches),
                "default_branch": default_branch,
            }

            # 캐시 저장
            _branch_commits_cache[project_id] = (
                time.time() + BRANCH_COMMITS_CACHE_TTL,
                data,
            )
            return data

    except httpx.HTTPStatusError as e:
        return {"error": f"GitHub API 에러: {e.response.status_code}"}
    except Exception as e:
        return {"error": f"브랜치 커밋 조회 실패: {str(e)}"}


async def auto_sync_if_needed(db: AsyncSession, project_id: int) -> dict | None:
    """페이지 로드 시 호출 — 쿨다운 내면 스킵, 아니면 커밋+이슈 동기화."""
    now = datetime.now()
    last = _last_auto_sync.get(project_id)
    if last and (now - last).total_seconds() < AUTO_SYNC_COOLDOWN_SEC:
        return None  # 쿨다운 중

    # GitHub 연동 가능 여부 체크
    ready = await check_github_ready(db, project_id)
    if not ready.get("ready"):
        return None

    _last_auto_sync[project_id] = now

    try:
        commits_result = await sync_commits(db, project_id, days=7)
        issues_result = await sync_issues(db, project_id)
        logger.info(f"GitHub 자동 동기화 완료: project={project_id}, commits={commits_result}, issues={issues_result}")
        return {"commits": commits_result, "issues": issues_result}
    except Exception as e:
        logger.warning(f"GitHub 자동 동기화 실패: project={project_id}, error={e}")
        return {"error": str(e)}
