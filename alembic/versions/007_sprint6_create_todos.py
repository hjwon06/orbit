"""sprint6 create ob_todos

Revision ID: 007_sprint6
Revises: 006_sprint5
Create Date: 2026-03-17
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "007_sprint6"
down_revision: Union[str, None] = "006_sprint5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "ob_todos",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("project_id", sa.Integer(), sa.ForeignKey("ob_projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.String(300), nullable=False),
        sa.Column("description", sa.Text(), server_default=""),
        sa.Column("priority", sa.String(10), server_default="medium"),
        sa.Column("status", sa.String(20), server_default="open"),
        sa.Column("source", sa.String(20), server_default="manual"),
        sa.Column("github_issue_url", sa.String(500), nullable=True),
        sa.Column("ai_reasoning", sa.Text(), server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_ob_todos_project_id", "ob_todos", ["project_id"])
    op.create_index("ix_ob_todos_status", "ob_todos", ["status"])


def downgrade() -> None:
    op.drop_table("ob_todos")
