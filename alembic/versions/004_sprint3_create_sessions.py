"""sprint3 create ob_sessions

Revision ID: 004_sprint3
Revises: 003_sprint2
Create Date: 2026-03-17
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "004_sprint3"
down_revision: Union[str, None] = "003_sprint2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "ob_sessions",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("project_id", sa.Integer(), sa.ForeignKey("ob_projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("agent_code", sa.String(10), nullable=True),
        sa.Column("summary", sa.Text(), server_default=""),
        sa.Column("status", sa.String(20), server_default="running"),
        sa.Column("started_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("duration_min", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_ob_sessions_project_id", "ob_sessions", ["project_id"])
    op.create_index("ix_ob_sessions_status", "ob_sessions", ["status"])
    op.create_index("ix_ob_sessions_started_at", "ob_sessions", ["started_at"])


def downgrade() -> None:
    op.drop_table("ob_sessions")
