"""sprint1 create ob_agents and ob_agent_runs

Revision ID: 002_sprint1
Revises: 001_sprint0
Create Date: 2026-03-17
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "002_sprint1"
down_revision: Union[str, None] = "001_sprint0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "ob_agents",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("project_id", sa.Integer(), sa.ForeignKey("ob_projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("agent_code", sa.String(10), nullable=False),
        sa.Column("agent_name", sa.String(100), nullable=False),
        sa.Column("model_tier", sa.String(20), server_default="sonnet"),
        sa.Column("status", sa.String(20), server_default="idle"),
        sa.Column("current_task", sa.String(200), server_default=""),
        sa.Column("last_heartbeat", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_ob_agents_project_code", "ob_agents", ["project_id", "agent_code"], unique=True)

    op.create_table(
        "ob_agent_runs",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("agent_id", sa.Integer(), sa.ForeignKey("ob_agents.id", ondelete="CASCADE"), nullable=False),
        sa.Column("task_name", sa.String(200), nullable=False),
        sa.Column("status", sa.String(20), server_default="running"),
        sa.Column("error_log", sa.Text(), server_default=""),
        sa.Column("duration_sec", sa.Integer(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_ob_agent_runs_agent_id", "ob_agent_runs", ["agent_id"])
    op.create_index("ix_ob_agent_runs_status", "ob_agent_runs", ["status"])


def downgrade() -> None:
    op.drop_table("ob_agent_runs")
    op.drop_table("ob_agents")
