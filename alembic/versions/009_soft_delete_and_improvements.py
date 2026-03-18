"""Add deleted_at for soft delete on key tables.

Revision ID: 009_soft_delete
Revises: 008_sprint7
"""
from alembic import op
import sqlalchemy as sa

revision = "009_soft_delete"
down_revision = "008_sprint7"
branch_labels = None
depends_on = None

TABLES = ["ob_projects", "ob_agents", "ob_milestones", "ob_sessions", "ob_todos"]


def upgrade() -> None:
    for table in TABLES:
        op.add_column(table, sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    for table in TABLES:
        op.drop_column(table, "deleted_at")
