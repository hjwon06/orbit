import json
import re
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone as tz

from fastapi import APIRouter, Request, Depends
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.services import get_projects
from app.services.agent_service import get_agents_by_project, create_agent
from app.services.milestone_service import get_milestones_by_project
from app.services.session_service import get_sessions_by_project
from app.services.work_log_service import get_work_logs_by_project
from app.services.commit_stat_service import get_commit_stats_by_project
from app.services.infra_cost_service import get_costs_by_project
# todo_service import 제거 (AI 할일 기능 삭제)
from app.schemas.agent import AgentCreate


def _parse_mcp_map(project_yaml: str | None) -> dict[str, list[str]]:
    """project.yaml에서 에이전트별 MCP 매핑 추출."""
    if not project_yaml:
        return {}
    mcp_map: dict[str, list[str]] = {}
    lines = project_yaml.split("\n")
    in_agents = False
    current_code = None
    for line in lines:
        stripped = line.strip()
        if stripped == "agents:":
            in_agents = True
            continue
        if in_agents:
            if stripped and not stripped.startswith("#") and not line.startswith(" ") and not line.startswith("\t"):
                break
            code_match = re.match(r"^\s{2}([A-Z][A-Z0-9]*)\s*:", line)
            if code_match:
                current_code = code_match.group(1)
                continue
            if current_code:
                mcp_match = re.match(r"\s+mcp:\s*\[(.+)\]", line)
                if mcp_match:
                    mcp_map[current_code] = [m.strip() for m in mcp_match.group(1).split(",")]
    return mcp_map


def _json_serial(obj):
    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    raise TypeError(f"Type {type(obj)} not serializable")

router = APIRouter(tags=["pages"])
templates = Jinja2Templates(directory="app/templates")

# kst 필터 등록 (main.py와 동일)
_KST = tz(timedelta(hours=9))

def _to_kst(value, fmt="%Y-%m-%d %H:%M"):
    if value is None:
        return ""
    try:
        return value.astimezone(_KST).strftime(fmt)
    except Exception:
        return str(value)

templates.env.filters["kst"] = _to_kst
templates.env.globals["is_admin_user"] = lambda request: getattr(getattr(request, "state", None), "user", {}).get("role") == "admin"
templates.env.globals["current_username"] = lambda request: getattr(getattr(request, "state", None), "user", {}).get("user", "")

DEFAULT_AGENTS = [
    ("A0", "인프라", "opus"),
    ("A1", "백엔드 API", "opus"),
    ("A2", "프론트엔드 UI", "opus"),
    ("A3", "AI/연동", "opus"),
    ("A4", "데이터 분석", "opus"),
    ("QA", "검증", "opus"),
]


def _parse_agents_from_yaml(project_yaml: str | None) -> list[tuple[str, str, str]]:
    """project_yaml에서 에이전트 목록 추출. 없으면 DEFAULT_AGENTS 반환."""
    if not project_yaml:
        return DEFAULT_AGENTS
    agents: list[tuple[str, str, str]] = []
    lines = project_yaml.split("\n")
    in_agents = False
    current_code = None
    current_name = None
    for line in lines:
        stripped = line.strip()
        if stripped == "agents:":
            in_agents = True
            continue
        if in_agents:
            if stripped and not stripped.startswith("#") and not line.startswith(" ") and not line.startswith("\t"):
                break
            code_match = re.match(r"^\s{2}([A-Z][A-Z0-9]*)\s*:", line)
            if code_match:
                if current_code and current_name:
                    agents.append((current_code, current_name, "opus"))
                current_code = code_match.group(1)
                current_name = None
                continue
            if current_code:
                name_match = re.match(r"\s+name:\s*(.+)", line)
                if name_match:
                    current_name = name_match.group(1).strip()
    if current_code and current_name:
        agents.append((current_code, current_name, "opus"))
    return agents if agents else DEFAULT_AGENTS


@router.get("/", response_class=HTMLResponse)
async def dashboard(request: Request, db: AsyncSession = Depends(get_db)):
    from datetime import date, timedelta
    from sqlalchemy import select, func as sqlfunc
    from app.models import Agent, AgentRun, Session as SessionModel, CommitStat, InfraCost, Milestone

    projects = await get_projects(db, status="active")
    project_ids = [p.id for p in projects]

    # 에이전트 실행 중
    running_result = await db.execute(
        select(sqlfunc.count()).select_from(Agent).where(Agent.deleted_at.is_(None), Agent.status == "running")
    )
    agents_running = running_result.scalar() or 0

    # 에이전트 총
    total_agents_result = await db.execute(select(sqlfunc.count()).select_from(Agent).where(Agent.deleted_at.is_(None)))
    agents_total = total_agents_result.scalar() or 0

    # 오늘 세션
    today = date.today()
    today_sessions_result = await db.execute(
        select(sqlfunc.count()).select_from(SessionModel).where(
            SessionModel.deleted_at.is_(None),
            sqlfunc.date(SessionModel.started_at) == today
        )
    )
    sessions_today = today_sessions_result.scalar() or 0

    # 이번주 커밋
    week_start = today - timedelta(days=today.weekday())
    week_commits_result = await db.execute(
        select(sqlfunc.coalesce(sqlfunc.sum(CommitStat.commit_count), 0)).where(
            CommitStat.stat_date >= week_start
        )
    )
    commits_week = week_commits_result.scalar() or 0

    # 월간 비용
    cost_result = await db.execute(
        select(
            sqlfunc.coalesce(sqlfunc.sum(InfraCost.cost_usd), 0)
        ).where(InfraCost.is_active == True, InfraCost.billing_cycle == "monthly")  # noqa: E712
    )
    monthly_cost = round(cost_result.scalar() or 0, 2)

    # yearly를 /12로 추가
    yearly_result = await db.execute(
        select(
            sqlfunc.coalesce(sqlfunc.sum(InfraCost.cost_usd), 0)
        ).where(InfraCost.is_active == True, InfraCost.billing_cycle == "yearly")  # noqa: E712
    )
    monthly_cost = round(monthly_cost + (yearly_result.scalar() or 0) / 12, 2)

    # --- 28일 트렌드 데이터 ---
    trend_start = today - timedelta(days=27)
    # 일별 세션 수
    daily_sessions_result = await db.execute(
        select(
            sqlfunc.date(SessionModel.started_at).label("d"),
            sqlfunc.count().label("cnt"),
        ).where(
            SessionModel.deleted_at.is_(None),
            sqlfunc.date(SessionModel.started_at) >= trend_start
        ).group_by(sqlfunc.date(SessionModel.started_at))
    )
    daily_sessions_map: dict = dict(daily_sessions_result.all())  # type: ignore[arg-type]

    # 일별 커밋 수
    daily_commits_result = await db.execute(
        select(
            CommitStat.stat_date,
            sqlfunc.coalesce(sqlfunc.sum(CommitStat.commit_count), 0),
        ).where(
            CommitStat.stat_date >= trend_start
        ).group_by(CommitStat.stat_date)
    )
    daily_commits_map: dict = dict(daily_commits_result.all())  # type: ignore[arg-type]

    # 28일 배열 생성
    trend_labels = []
    trend_sessions = []
    trend_commits = []
    for i in range(28):
        d = trend_start + timedelta(days=i)
        trend_labels.append(d.strftime("%m/%d"))
        trend_sessions.append(int(daily_sessions_map.get(d, 0)))
        trend_commits.append(int(daily_commits_map.get(d, 0)))

    # --- 프로젝트별 미니 통계 (GROUP BY 한 번씩) ---
    # 에이전트 수
    agents_by_proj_result = await db.execute(
        select(Agent.project_id, sqlfunc.count()).where(
            Agent.project_id.in_(project_ids),
            Agent.deleted_at.is_(None),
        ).group_by(Agent.project_id)
    )
    agents_by_proj: dict = dict(agents_by_proj_result.all())  # type: ignore[arg-type]

    # 마일스톤 수
    milestones_by_proj_result = await db.execute(
        select(Milestone.project_id, sqlfunc.count()).where(
            Milestone.project_id.in_(project_ids),
            Milestone.deleted_at.is_(None),
        ).group_by(Milestone.project_id)
    )
    milestones_by_proj: dict = dict(milestones_by_proj_result.all())  # type: ignore[arg-type]

    # 마일스톤 done 수
    milestones_done_result = await db.execute(
        select(Milestone.project_id, sqlfunc.count()).where(
            Milestone.project_id.in_(project_ids),
            Milestone.deleted_at.is_(None),
            Milestone.status == "done",
        ).group_by(Milestone.project_id)
    )
    milestones_done_by_proj: dict = dict(milestones_done_result.all())  # type: ignore[arg-type]

    # 세션 수 (최근 7일)
    week_ago = today - timedelta(days=7)
    sessions_by_proj_result = await db.execute(
        select(SessionModel.project_id, sqlfunc.count()).where(
            SessionModel.project_id.in_(project_ids),
            SessionModel.deleted_at.is_(None),
            SessionModel.started_at >= week_ago,
        ).group_by(SessionModel.project_id)
    )
    sessions_by_proj: dict = dict(sessions_by_proj_result.all())  # type: ignore[arg-type]

    # 커밋 수 (최근 7일)
    commits_by_proj_result = await db.execute(
        select(
            CommitStat.project_id,
            sqlfunc.coalesce(sqlfunc.sum(CommitStat.commit_count), 0),
        ).where(
            CommitStat.project_id.in_(project_ids),
            CommitStat.stat_date >= week_start,
        ).group_by(CommitStat.project_id)
    )
    commits_by_proj: dict = dict(commits_by_proj_result.all())  # type: ignore[arg-type]

    # --- 프로젝트별 7일 스파크라인 ---
    spark_start = today - timedelta(days=6)
    spark_sessions_result = await db.execute(
        select(
            SessionModel.project_id,
            sqlfunc.date(SessionModel.started_at).label("d"),
            sqlfunc.count().label("cnt"),
        ).where(
            SessionModel.project_id.in_(project_ids),
            SessionModel.deleted_at.is_(None),
            sqlfunc.date(SessionModel.started_at) >= spark_start,
        ).group_by(SessionModel.project_id, sqlfunc.date(SessionModel.started_at))
    )
    spark_sess_map: dict[int, dict] = defaultdict(dict)
    for pid, d, cnt in spark_sessions_result.all():
        spark_sess_map[pid][d] = cnt

    spark_commits_result = await db.execute(
        select(
            CommitStat.project_id,
            CommitStat.stat_date,
            CommitStat.commit_count,
        ).where(
            CommitStat.project_id.in_(project_ids),
            CommitStat.stat_date >= spark_start,
        )
    )
    spark_comm_map: dict[int, dict] = defaultdict(dict)
    for pid, d, cnt in spark_commits_result.all():
        spark_comm_map[pid][d] = cnt

    sparklines = {}
    for pid in project_ids:
        vals = []
        for i in range(7):
            d = spark_start + timedelta(days=i)
            s = spark_sess_map.get(pid, {}).get(d, 0)
            c = spark_comm_map.get(pid, {}).get(d, 0)
            vals.append(int(s) + int(c))
        sparklines[pid] = vals

    # --- 프로젝트별 마지막 활동 시간 ---
    last_session_result = await db.execute(
        select(SessionModel.project_id, sqlfunc.max(SessionModel.started_at)).where(
            SessionModel.project_id.in_(project_ids),
            SessionModel.deleted_at.is_(None),
        ).group_by(SessionModel.project_id)
    )
    last_session_map: dict = dict(last_session_result.all())  # type: ignore[arg-type]

    last_commit_result = await db.execute(
        select(CommitStat.project_id, sqlfunc.max(CommitStat.created_at)).where(
            CommitStat.project_id.in_(project_ids)
        ).group_by(CommitStat.project_id)
    )
    last_commit_map: dict = dict(last_commit_result.all())  # type: ignore[arg-type]

    project_stats = {
        pid: {
            "agents": agents_by_proj.get(pid, 0),
            "milestones": milestones_by_proj.get(pid, 0),
            "sessions": sessions_by_proj.get(pid, 0),
            "commits": commits_by_proj.get(pid, 0),
            "sparkline": sparklines.get(pid, [0]*7),
            "last_activity": max(filter(None, [last_session_map.get(pid), last_commit_map.get(pid)]), default=None),
            "ms_done": milestones_done_by_proj.get(pid, 0),
            "ms_total": milestones_by_proj.get(pid, 0),
            "ms_pct": round(milestones_done_by_proj.get(pid, 0) / milestones_by_proj.get(pid, 1) * 100),
        }
        for pid in project_ids
    }

    # --- 최근 활동 피드 ---
    proj_map = {p.id: (p.name, p.color) for p in projects}

    recent_activities = []

    # 세션: 최근 5건
    recent_sessions_result = await db.execute(
        select(SessionModel).where(SessionModel.deleted_at.is_(None)).order_by(SessionModel.started_at.desc()).limit(5)
    )
    for s in recent_sessions_result.scalars().all():
        pname, pcolor = proj_map.get(s.project_id, ("Unknown", "#6b7280"))
        if s.started_at:
            recent_activities.append({
                "timestamp": s.started_at,
                "type": "session",
                "action": "started",
                "project_color": pcolor,
                "project_name": pname,
                "description": f"세션 \"{s.title}\" 시작",
            })
        if s.finished_at:
            recent_activities.append({
                "timestamp": s.finished_at,
                "type": "session",
                "action": "finished",
                "project_color": pcolor,
                "project_name": pname,
                "description": f"세션 \"{s.title}\" 완료 ({s.duration_min or 0}분)",
            })

    # 에이전트 실행: 최근 5건
    recent_runs_result = await db.execute(
        select(AgentRun).join(Agent, AgentRun.agent_id == Agent.id)
        .where(Agent.deleted_at.is_(None))
        .order_by(AgentRun.started_at.desc()).limit(5)
    )
    for r in recent_runs_result.scalars().all():
        agent = await db.get(Agent, r.agent_id)
        if agent:
            pname, pcolor = proj_map.get(agent.project_id, ("Unknown", "#6b7280"))
        else:
            pname, pcolor = "Unknown", "#6b7280"
        if r.started_at:
            recent_activities.append({
                "timestamp": r.started_at,
                "type": "agent_run",
                "action": "started",
                "project_color": pcolor,
                "project_name": pname,
                "description": f"{agent.agent_code if agent else '?'} \"{r.task_name}\" 실행",
            })
        if r.finished_at:
            recent_activities.append({
                "timestamp": r.finished_at,
                "type": "agent_run",
                "action": "completed",
                "project_color": pcolor,
                "project_name": pname,
                "description": f"{agent.agent_code if agent else '?'} \"{r.task_name}\" 완료",
            })

    # 커밋 통계: 최근 5건
    recent_commits_result = await db.execute(
        select(CommitStat).order_by(CommitStat.created_at.desc()).limit(5)
    )
    for c in recent_commits_result.scalars().all():
        pname, pcolor = proj_map.get(c.project_id, ("Unknown", "#6b7280"))
        if c.created_at:
            recent_activities.append({
                "timestamp": c.created_at,
                "type": "commit",
                "action": "synced",
                "project_color": pcolor,
                "project_name": pname,
                "description": f"커밋 {c.commit_count}건 동기화 (+{c.additions}/-{c.deletions})",
            })

    # 시간순 정렬 (최신 먼저), None 방어
    recent_activities = [a for a in recent_activities if a["timestamp"] is not None]
    recent_activities.sort(key=lambda a: a["timestamp"], reverse=True)
    recent_activities = recent_activities[:10]

    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "projects": projects,
        "page_title": "ORBIT",
        "project_stats": project_stats,
        "stats": {
            "agents_running": agents_running,
            "agents_total": agents_total,
            "sessions_today": sessions_today,
            "commits_week": commits_week,
            "monthly_cost": monthly_cost,
        },
        "trend_labels_json": json.dumps(trend_labels),
        "trend_sessions_json": json.dumps(trend_sessions),
        "trend_commits_json": json.dumps(trend_commits),
        "recent_activities": recent_activities,
    })


@router.get("/projects/new", response_class=HTMLResponse)
async def new_project_form(request: Request):
    return templates.TemplateResponse("project_form.html", {
        "request": request,
        "page_title": "New project",
    })


@router.get("/projects/{slug}", response_class=HTMLResponse)
async def project_detail(request: Request, slug: str, db: AsyncSession = Depends(get_db)):
    from datetime import date as date_type, timedelta
    from sqlalchemy import select, func as sqlfunc
    from app.services import get_project_by_slug
    from app.models import Milestone, Agent, Session as SessionModel, CommitStat

    project = await get_project_by_slug(db, slug)
    if not project:
        from fastapi.exceptions import HTTPException
        raise HTTPException(status_code=404)

    pid = project.id

    # 마일스톤 진행률
    ms_total_result = await db.execute(
        select(sqlfunc.count()).select_from(Milestone).where(Milestone.project_id == pid, Milestone.deleted_at.is_(None))
    )
    ms_total = ms_total_result.scalar() or 0
    ms_done_result = await db.execute(
        select(sqlfunc.count()).select_from(Milestone).where(
            Milestone.project_id == pid, Milestone.deleted_at.is_(None), Milestone.status == "done"
        )
    )
    ms_done = ms_done_result.scalar() or 0

    # 최근 세션
    latest_session_result = await db.execute(
        select(SessionModel).where(SessionModel.project_id == pid, SessionModel.deleted_at.is_(None))
        .order_by(SessionModel.started_at.desc()).limit(1)
    )
    latest_session = latest_session_result.scalar_one_or_none()

    # 이번주 커밋
    today = date_type.today()
    week_start = today - timedelta(days=today.weekday())
    week_commits_result = await db.execute(
        select(
            sqlfunc.coalesce(sqlfunc.sum(CommitStat.commit_count), 0),
            sqlfunc.coalesce(sqlfunc.sum(CommitStat.additions), 0),
            sqlfunc.coalesce(sqlfunc.sum(CommitStat.deletions), 0),
        ).where(
            CommitStat.project_id == pid,
            CommitStat.stat_date >= week_start,
        )
    )
    week_commits, week_add, week_del = week_commits_result.one()

    # 에이전트 상태
    from app.models import InfraCost
    agents_total_result = await db.execute(
        select(sqlfunc.count()).select_from(Agent).where(Agent.project_id == pid, Agent.deleted_at.is_(None))
    )
    agents_total = agents_total_result.scalar() or 0
    agents_running_result = await db.execute(
        select(sqlfunc.count()).select_from(Agent).where(
            Agent.project_id == pid, Agent.deleted_at.is_(None), Agent.status == "running"
        )
    )
    agents_running = agents_running_result.scalar() or 0

    # 세션 총 수
    sessions_total_result = await db.execute(
        select(sqlfunc.count()).select_from(SessionModel).where(SessionModel.project_id == pid, SessionModel.deleted_at.is_(None))
    )
    sessions_total = sessions_total_result.scalar() or 0

    # 인프라 비용 서비스 수
    costs_total_result = await db.execute(
        select(sqlfunc.count()).select_from(InfraCost).where(
            InfraCost.project_id == pid, InfraCost.is_active == True  # noqa: E712
        )
    )
    costs_total = costs_total_result.scalar() or 0

    # GitHub 자동 동기화 (10분 쿨다운)
    from app.services.github_service import auto_sync_if_needed
    github_sync = await auto_sync_if_needed(db, pid)

    # 옵시디언 다이어리 자동 동기화 (1시간 쿨다운)
    from app.services.diary_sync_service import auto_sync_diary_if_needed
    diary_sync = await auto_sync_diary_if_needed(db, pid, project.slug)

    summary = {
        "ms_total": ms_total,
        "ms_done": ms_done,
        "ms_pct": round(ms_done / ms_total * 100) if ms_total > 0 else 0,
        "latest_session": latest_session,
        "week_commits": int(week_commits),
        "week_add": int(week_add),
        "week_del": int(week_del),
        "agents_total": agents_total,
        "agents_running": agents_running,
        "sessions_total": sessions_total,
        "costs_total": costs_total,
        "github_synced": github_sync is not None,
        "diary_synced": diary_sync is not None,
    }

    return templates.TemplateResponse("project_detail.html", {
        "request": request,
        "project": project,
        "summary": summary,
        "page_title": project.name,
    })


@router.get("/projects/{slug}/agents", response_class=HTMLResponse)
async def agents_page(request: Request, slug: str, db: AsyncSession = Depends(get_db)):
    from app.services import get_project_by_slug
    project = await get_project_by_slug(db, slug)
    if not project:
        from fastapi.exceptions import HTTPException
        raise HTTPException(status_code=404)
    agents = await get_agents_by_project(db, project.id)
    agents_json = json.dumps([
        {
            "id": a.id, "project_id": a.project_id,
            "agent_code": a.agent_code, "agent_name": a.agent_name,
            "model_tier": a.model_tier, "status": a.status,
            "current_task": a.current_task or "",
            "last_heartbeat": a.last_heartbeat.isoformat() if a.last_heartbeat else None,
        }
        for a in agents
    ], default=_json_serial)
    mcp_map = _parse_mcp_map(project.project_yaml)
    mcp_map_json = json.dumps(mcp_map)
    return templates.TemplateResponse("agents.html", {
        "request": request,
        "project": project,
        "agents": agents,
        "agents_json": agents_json,
        "mcp_map": mcp_map,
        "mcp_map_json": mcp_map_json,
        "project_id": project.id,
        "page_title": f"{project.name} — 에이전트",
    })


@router.get("/projects/{slug}/agents/partial", response_class=HTMLResponse)
async def agents_partial(request: Request, slug: str, db: AsyncSession = Depends(get_db)):
    from app.services import get_project_by_slug
    project = await get_project_by_slug(db, slug)
    if not project:
        from fastapi.exceptions import HTTPException
        raise HTTPException(status_code=404)
    agents = await get_agents_by_project(db, project.id)
    mcp_map = _parse_mcp_map(project.project_yaml)
    return templates.TemplateResponse("partials/agent_cards.html", {
        "request": request,
        "agents": agents,
        "mcp_map": mcp_map,
    })


@router.post("/projects/{slug}/agents/seed")
async def seed_agents(slug: str, db: AsyncSession = Depends(get_db)):
    from app.services import get_project_by_slug
    from app.services.local_sync_service import sync_from_local
    project = await get_project_by_slug(db, slug)
    if not project:
        from fastapi.exceptions import HTTPException
        raise HTTPException(status_code=404)
    # local_path가 있으면 로컬 파일에서 자동 동기화
    if project.local_path:
        await sync_from_local(db, project)
    else:
        # fallback: project_yaml 또는 기본 에이전트
        existing = await get_agents_by_project(db, project.id)
        if not existing:
            agent_list = _parse_agents_from_yaml(project.project_yaml)
            for code, name, tier in agent_list:
                await create_agent(db, AgentCreate(
                    project_id=project.id,
                    agent_code=code,
                    agent_name=name,
                    model_tier=tier,
                ))
    return RedirectResponse(url=f"/projects/{slug}/agents", status_code=303)


@router.get("/projects/{slug}/timeline", response_class=HTMLResponse)
async def timeline_page(request: Request, slug: str, db: AsyncSession = Depends(get_db)):
    from app.services import get_project_by_slug
    project = await get_project_by_slug(db, slug)
    if not project:
        from fastapi.exceptions import HTTPException
        raise HTTPException(status_code=404)
    milestones = await get_milestones_by_project(db, project.id)
    milestones_json = json.dumps([
        {
            "id": m.id, "project_id": m.project_id, "title": m.title,
            "status": m.status, "start_date": m.start_date.isoformat(),
            "end_date": m.end_date.isoformat(), "sort_order": m.sort_order,
            "color": m.color, "source": m.source,
            "todo_total": 0,
            "todo_done": 0,
            "todo_pct": 0,
        }
        for m in milestones
    ], default=_json_serial)
    return templates.TemplateResponse("timeline.html", {
        "request": request,
        "project": project,
        "milestones_json": milestones_json,
        "page_title": f"{project.name} — 타임라인",
    })


@router.get("/projects/{slug}/sessions", response_class=HTMLResponse)
async def sessions_page(request: Request, slug: str, db: AsyncSession = Depends(get_db)):
    from app.services import get_project_by_slug
    project = await get_project_by_slug(db, slug)
    if not project:
        from fastapi.exceptions import HTTPException
        raise HTTPException(status_code=404)
    sessions = await get_sessions_by_project(db, project.id)
    sessions_json = json.dumps([
        {
            "id": s.id, "project_id": s.project_id, "title": s.title,
            "agent_code": s.agent_code, "summary": s.summary or "",
            "status": s.status, "started_at": s.started_at.isoformat() if s.started_at else None,
            "finished_at": s.finished_at.isoformat() if s.finished_at else None,
            "duration_min": s.duration_min,
        }
        for s in sessions
    ], default=_json_serial)
    agents = await get_agents_by_project(db, project.id)
    agents_json = json.dumps([
        {"agent_code": a.agent_code, "agent_name": a.agent_name}
        for a in agents
    ], default=_json_serial)
    return templates.TemplateResponse("sessions.html", {
        "request": request,
        "project": project,
        "sessions_json": sessions_json,
        "agents_json": agents_json,
        "page_title": f"{project.name} — 세션 로그",
    })


@router.get("/projects/{slug}/logs", response_class=HTMLResponse)
async def logs_page(request: Request, slug: str, db: AsyncSession = Depends(get_db)):
    from app.services import get_project_by_slug
    project = await get_project_by_slug(db, slug)
    if not project:
        from fastapi.exceptions import HTTPException
        raise HTTPException(status_code=404)
    # GitHub 자동 동기화 (10분 쿨다운)
    from app.services.github_service import auto_sync_if_needed
    await auto_sync_if_needed(db, project.id)

    work_logs = await get_work_logs_by_project(db, project.id)
    commit_stats = await get_commit_stats_by_project(db, project.id)
    work_logs_json = json.dumps([
        {"id": w.id, "project_id": w.project_id, "log_date": w.log_date.isoformat(), "content": w.content or ""}
        for w in work_logs
    ], default=_json_serial)
    commit_stats_json = json.dumps([
        {
            "id": s.id, "project_id": s.project_id, "stat_date": s.stat_date.isoformat(),
            "commit_count": s.commit_count, "additions": s.additions, "deletions": s.deletions,
            "source": s.source,
        }
        for s in commit_stats
    ], default=_json_serial)
    return templates.TemplateResponse("logs.html", {
        "request": request,
        "project": project,
        "work_logs_json": work_logs_json,
        "commit_stats_json": commit_stats_json,
        "page_title": f"{project.name} — 작업 로그",
    })


@router.get("/projects/{slug}/costs", response_class=HTMLResponse)
async def costs_page(request: Request, slug: str, db: AsyncSession = Depends(get_db)):
    from app.services import get_project_by_slug
    project = await get_project_by_slug(db, slug)
    if not project:
        from fastapi.exceptions import HTTPException
        raise HTTPException(status_code=404)
    costs = await get_costs_by_project(db, project.id)
    costs_json = json.dumps([
        {
            "id": c.id, "project_id": c.project_id, "provider": c.provider,
            "service_name": c.service_name, "cost_usd": c.cost_usd,
            "billing_cycle": c.billing_cycle, "is_active": c.is_active,
            "notes": c.notes or "",
        }
        for c in costs
    ], default=_json_serial)
    return templates.TemplateResponse("costs.html", {
        "request": request,
        "project": project,
        "costs_json": costs_json,
        "page_title": f"{project.name} — 인프라 비용",
    })


# AI 할일 라우트 삭제됨


@router.get("/projects/{slug}/repo-score", response_class=HTMLResponse)
async def repo_score_page(request: Request, slug: str, db: AsyncSession = Depends(get_db)):
    from app.services import get_project_by_slug
    from app.services.github_service import check_github_ready
    project = await get_project_by_slug(db, slug)
    if not project:
        from fastapi.exceptions import HTTPException
        raise HTTPException(status_code=404)
    github_status = await check_github_ready(db, project.id)
    return templates.TemplateResponse("repo_score.html", {
        "request": request,
        "project": project,
        "github_ready": "true" if github_status.get("ready") else "false",
        "page_title": f"{project.name} — 레포 품질",
    })


@router.get("/projects/{slug}/team-scores", response_class=HTMLResponse)
async def team_scores_page(request: Request, slug: str, db: AsyncSession = Depends(get_db)):
    from app.services import get_project_by_slug
    from app.services.team_score_service import get_latest_scores
    project = await get_project_by_slug(db, slug)
    if not project:
        from fastapi.exceptions import HTTPException
        raise HTTPException(status_code=404)
    scores_data = await get_latest_scores(db, project.id)
    return templates.TemplateResponse("team_scores.html", {
        "request": request,
        "project": project,
        "scores_data": scores_data,
        "page_title": f"{project.name} — 팀원 채점",
    })


@router.get("/terminal", response_class=HTMLResponse)
async def terminal_page(request: Request, db: AsyncSession = Depends(get_db)):
    projects = await get_projects(db, status="active")
    return templates.TemplateResponse("terminal.html", {
        "request": request,
        "projects": projects,
        "page_title": "터미널",
        "initial_slug": "",
        "initial_name": "",
    })


@router.get("/projects/{slug}/terminal", response_class=HTMLResponse)
async def project_terminal_page(request: Request, slug: str, db: AsyncSession = Depends(get_db)):
    from app.services import get_project_by_slug
    project = await get_project_by_slug(db, slug)
    if not project:
        from fastapi.exceptions import HTTPException
        raise HTTPException(status_code=404)
    projects = await get_projects(db, status="active")
    return templates.TemplateResponse("terminal.html", {
        "request": request,
        "projects": projects,
        "project": project,
        "page_title": f"{project.name} — 터미널",
        "initial_slug": project.slug,
        "initial_name": project.name,
    })


@router.get("/server-costs", response_class=HTMLResponse)
async def server_costs_page(request: Request, db: AsyncSession = Depends(get_db)):
    from sqlalchemy import select, func as sqlfunc
    from app.models import InfraCost

    # 수동 등록 비용 전체 합산 (monthly + yearly/12)
    monthly_result = await db.execute(
        select(sqlfunc.coalesce(sqlfunc.sum(InfraCost.cost_usd), 0)).where(
            InfraCost.is_active == True, InfraCost.billing_cycle == "monthly"  # noqa: E712
        )
    )
    monthly = monthly_result.scalar() or 0

    yearly_result = await db.execute(
        select(sqlfunc.coalesce(sqlfunc.sum(InfraCost.cost_usd), 0)).where(
            InfraCost.is_active == True, InfraCost.billing_cycle == "yearly"  # noqa: E712
        )
    )
    yearly = yearly_result.scalar() or 0

    manual_total = round(monthly + yearly / 12, 2)

    return templates.TemplateResponse("server_costs.html", {
        "request": request,
        "page_title": "서버 비용",
        "manual_total": manual_total,
    })


@router.get("/infra", response_class=HTMLResponse)
async def infra_page(request: Request):
    return templates.TemplateResponse("infra.html", {
        "request": request,
        "page_title": "인프라 관리",
    })
