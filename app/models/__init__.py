from sqlalchemy import Column, Integer, String, Text, DateTime, Date, Float, Boolean, Numeric, ForeignKey, func
from sqlalchemy.dialects.postgresql import JSON
from sqlalchemy.orm import relationship
from app.database import Base


class Project(Base):
    __tablename__ = "ob_projects"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), nullable=False)
    slug = Column(String(50), unique=True, nullable=False, index=True)
    description = Column(Text, default="")
    status = Column(String(20), default="active")
    repo_url = Column(String(500), default="")
    stack = Column(String(200), default="")
    color = Column(String(7), default="#534AB7")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    deleted_at = Column(DateTime(timezone=True), nullable=True)

    agents = relationship("Agent", back_populates="project", cascade="all, delete-orphan")
    milestones = relationship("Milestone", back_populates="project", cascade="all, delete-orphan")
    sessions = relationship("Session", back_populates="project", cascade="all, delete-orphan")
    work_logs = relationship("WorkLog", back_populates="project", cascade="all, delete-orphan")
    commit_stats = relationship("CommitStat", back_populates="project", cascade="all, delete-orphan")
    infra_costs = relationship("InfraCost", back_populates="project", cascade="all, delete-orphan")
    todos = relationship("Todo", back_populates="project", cascade="all, delete-orphan")
    def __repr__(self):
        return f"<Project {self.slug}>"


class Agent(Base):
    __tablename__ = "ob_agents"

    id = Column(Integer, primary_key=True, autoincrement=True)
    project_id = Column(Integer, ForeignKey("ob_projects.id", ondelete="CASCADE"), nullable=False)
    agent_code = Column(String(10), nullable=False)
    agent_name = Column(String(100), nullable=False)
    model_tier = Column(String(20), default="opus")
    status = Column(String(20), default="idle")
    current_task = Column(String(200), default="")
    last_heartbeat = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    deleted_at = Column(DateTime(timezone=True), nullable=True)

    project = relationship("Project", back_populates="agents")
    runs = relationship("AgentRun", back_populates="agent", cascade="all, delete-orphan", order_by="AgentRun.started_at.desc()")

    def __repr__(self):
        return f"<Agent {self.agent_code}:{self.agent_name}>"


class AgentRun(Base):
    __tablename__ = "ob_agent_runs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    agent_id = Column(Integer, ForeignKey("ob_agents.id", ondelete="CASCADE"), nullable=False)
    task_name = Column(String(200), nullable=False)
    status = Column(String(20), default="running")
    error_log = Column(Text, default="")
    duration_sec = Column(Integer, nullable=True)
    started_at = Column(DateTime(timezone=True), server_default=func.now())
    finished_at = Column(DateTime(timezone=True), nullable=True)

    agent = relationship("Agent", back_populates="runs")

    def __repr__(self):
        return f"<AgentRun {self.task_name}:{self.status}>"


class Milestone(Base):
    __tablename__ = "ob_milestones"

    id = Column(Integer, primary_key=True, autoincrement=True)
    project_id = Column(Integer, ForeignKey("ob_projects.id", ondelete="CASCADE"), nullable=False)
    title = Column(String(200), nullable=False)
    status = Column(String(20), default="planned")
    start_date = Column(Date, nullable=False)
    end_date = Column(Date, nullable=False)
    color = Column(String(7), nullable=True)
    sort_order = Column(Integer, default=0)
    github_issue_url = Column(String(500), nullable=True)
    github_issue_number = Column(Integer, nullable=True)
    source = Column(String(20), default="manual")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    deleted_at = Column(DateTime(timezone=True), nullable=True)

    project = relationship("Project", back_populates="milestones")

    def __repr__(self):
        return f"<Milestone {self.title}>"


class Session(Base):
    __tablename__ = "ob_sessions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    project_id = Column(Integer, ForeignKey("ob_projects.id", ondelete="CASCADE"), nullable=False)
    title = Column(String(200), nullable=False)
    agent_code = Column(String(10), nullable=True)
    summary = Column(Text, default="")
    status = Column(String(20), default="running")
    started_at = Column(DateTime(timezone=True), server_default=func.now())
    finished_at = Column(DateTime(timezone=True), nullable=True)
    duration_min = Column(Integer, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    deleted_at = Column(DateTime(timezone=True), nullable=True)

    project = relationship("Project", back_populates="sessions")

    def __repr__(self):
        return f"<Session {self.title}:{self.status}>"


class WorkLog(Base):
    __tablename__ = "ob_work_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    project_id = Column(Integer, ForeignKey("ob_projects.id", ondelete="CASCADE"), nullable=False)
    log_date = Column(Date, nullable=False)
    content = Column(Text, default="")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    project = relationship("Project", back_populates="work_logs")

    def __repr__(self):
        return f"<WorkLog {self.log_date}>"


class CommitStat(Base):
    __tablename__ = "ob_commit_stats"

    id = Column(Integer, primary_key=True, autoincrement=True)
    project_id = Column(Integer, ForeignKey("ob_projects.id", ondelete="CASCADE"), nullable=False)
    stat_date = Column(Date, nullable=False)
    commit_count = Column(Integer, default=0)
    additions = Column(Integer, default=0)
    deletions = Column(Integer, default=0)
    source = Column(String(20), default="manual")
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    project = relationship("Project", back_populates="commit_stats")

    def __repr__(self):
        return f"<CommitStat {self.stat_date}:{self.commit_count}>"


class InfraCost(Base):
    __tablename__ = "ob_infra_costs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    project_id = Column(Integer, ForeignKey("ob_projects.id", ondelete="CASCADE"), nullable=False)
    provider = Column(String(50), nullable=False)
    service_name = Column(String(100), nullable=False)
    cost_usd = Column(Float, default=0)
    billing_cycle = Column(String(20), default="monthly")
    is_active = Column(Boolean, default=True)
    notes = Column(Text, default="")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    project = relationship("Project", back_populates="infra_costs")

    def __repr__(self):
        return f"<InfraCost {self.provider}:{self.service_name}>"


class Todo(Base):
    __tablename__ = "ob_todos"

    id = Column(Integer, primary_key=True, autoincrement=True)
    project_id = Column(Integer, ForeignKey("ob_projects.id", ondelete="CASCADE"), nullable=False)
    title = Column(String(300), nullable=False)
    description = Column(Text, default="")
    priority = Column(String(10), default="medium")
    status = Column(String(20), default="open")
    source = Column(String(20), default="manual")
    github_issue_url = Column(String(500), nullable=True)
    ai_reasoning = Column(Text, default="")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    completed_at = Column(DateTime(timezone=True), nullable=True)
    deleted_at = Column(DateTime(timezone=True), nullable=True)

    project = relationship("Project", back_populates="todos")

    def __repr__(self):
        return f"<Todo {self.title}:{self.status}>"



class SqlHistory(Base):
    __tablename__ = "ob_sql_history"

    id = Column(Integer, primary_key=True, autoincrement=True)
    db_alias = Column(String(50), nullable=False)
    query = Column(Text, nullable=False)
    row_count = Column(Integer, default=0)
    duration_ms = Column(Integer, default=0)
    status = Column(String(20), default="success")
    error = Column(Text, default="")
    executed_at = Column(DateTime(timezone=True), server_default=func.now())


