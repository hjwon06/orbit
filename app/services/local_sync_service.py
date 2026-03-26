"""로컬 .claude/agents/*.md 파일에서 에이전트+MCP 자동 동기화."""
import re
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Agent, Project


def parse_agent_md(file_path: Path) -> dict | None:
    """에이전트 MD 파일의 frontmatter를 파싱하여 dict 반환."""
    try:
        text = file_path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None

    # frontmatter 추출 (--- ... ---)
    fm_match = re.match(r"^---\s*\n(.*?)\n---", text, re.DOTALL)
    if not fm_match:
        return None

    fm = fm_match.group(1)
    result: dict = {}

    # name
    m = re.search(r"^name:\s*(.+)", fm, re.MULTILINE)
    if m:
        result["name"] = m.group(1).strip()

    # description
    m = re.search(r"^description:\s*(.+)", fm, re.MULTILINE)
    if m:
        result["description"] = m.group(1).strip()

    # model
    m = re.search(r"^model:\s*(.+)", fm, re.MULTILINE)
    if m:
        result["model"] = m.group(1).strip()

    # mcpServers (리스트)
    mcp_servers: list[str] = []
    in_mcp = False
    for line in fm.split("\n"):
        stripped = line.strip()
        if stripped.startswith("mcpServers:"):
            # 인라인: mcpServers: [a, b]
            inline = re.search(r"\[(.+)]", stripped)
            if inline:
                mcp_servers = [s.strip() for s in inline.group(1).split(",")]
                break
            in_mcp = True
            continue
        if in_mcp:
            item = re.match(r"^\s+-\s+(.+)", line)
            if item:
                mcp_servers.append(item.group(1).strip())
            else:
                break
    result["mcp_servers"] = mcp_servers

    return result


def extract_agent_code(filename: str) -> str | None:
    """파일명에서 에이전트 코드 추출.

    a0-xxx.md → A0, qa-xxx.md → QA (기존 패턴)
    code-reviewer.md → CR, db-reviewer.md → DR (자유 형식: 단어 첫글자 조합)
    """
    stem = Path(filename).stem
    prefix = stem.split("-")[0]
    # 기존 패턴: a0~a4, qa
    if re.match(r"^a[0-9]$", prefix, re.IGNORECASE):
        return prefix.upper()
    if prefix.lower() == "qa":
        return "QA"
    # 자유 형식: 단어 첫글자 조합 (code-reviewer → CR)
    parts = stem.split("-")
    code = "".join(p[0].upper() for p in parts if p)
    return code if code else None


def scan_agents_dir(local_path: str) -> list[dict]:
    """로컬 경로에서 .claude/agents/*.md 스캔하여 에이전트 목록 반환."""
    agents_dir = Path(local_path) / ".claude" / "agents"
    if not agents_dir.is_dir():
        return []

    agents: list[dict] = []
    for md_file in sorted(agents_dir.glob("*.md")):
        agent_code = extract_agent_code(md_file.name)
        if not agent_code:
            continue
        parsed = parse_agent_md(md_file)
        if not parsed:
            continue
        agents.append({
            "agent_code": agent_code,
            "agent_name": parsed.get("description", parsed.get("name", agent_code)),
            "model_tier": parsed.get("model", "opus"),
            "mcp_servers": parsed.get("mcp_servers", []),
        })
    return agents


def generate_project_yaml(agents: list[dict]) -> str:
    """에이전트 목록으로 project_yaml 문자열 생성."""
    lines = ["agents:"]
    for a in agents:
        lines.append(f"  {a['agent_code']}:")
        lines.append(f"    name: {a['agent_name']}")
        if a.get("mcp_servers"):
            mcp_str = ", ".join(a["mcp_servers"])
            lines.append(f"    mcp: [{mcp_str}]")
    return "\n".join(lines) + "\n"


async def sync_from_local(db: AsyncSession, project: Project) -> dict:
    """로컬 .claude/agents/ 스캔 → DB 동기화 (source='local'만 대상)."""
    if not project.local_path:
        return {"error": "local_path가 설정되지 않았습니다."}

    local_path = str(project.local_path)
    scanned = scan_agents_dir(local_path)
    if not scanned:
        return {"error": f".claude/agents/ 디렉토리를 찾을 수 없거나 비어있습니다: {local_path}"}

    # 기존 source='local' 에이전트 조회
    stmt = select(Agent).where(
        Agent.project_id == project.id,
        Agent.deleted_at.is_(None),
        Agent.source == "local",
    )
    result = await db.execute(stmt)
    existing: dict[str, Agent] = {str(a.agent_code): a for a in result.scalars().all()}

    scanned_codes = {a["agent_code"] for a in scanned}
    created = 0
    updated = 0
    deleted = 0

    # 추가/수정
    for item in scanned:
        code = item["agent_code"]
        if code in existing:
            agent = existing[code]
            agent.agent_name = item["agent_name"]  # type: ignore[assignment]
            agent.model_tier = item["model_tier"]  # type: ignore[assignment]
            updated += 1
        else:
            db.add(Agent(
                project_id=project.id,
                agent_code=code,
                agent_name=item["agent_name"],
                model_tier=item["model_tier"],
                source="local",
            ))
            created += 1

    # source='local'인데 로컬 파일에 없는 에이전트 → soft delete
    from datetime import datetime, timezone
    for code, agent in existing.items():
        if code not in scanned_codes:
            agent.deleted_at = datetime.now(timezone.utc)  # type: ignore[assignment]
            deleted += 1

    # project_yaml 자동 생성
    project.project_yaml = generate_project_yaml(scanned)  # type: ignore[assignment]

    await db.commit()
    return {"created": created, "updated": updated, "deleted": deleted}
