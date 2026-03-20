"""Add project_yaml column to ob_projects for storing project.yaml content.

Revision ID: 013_project_yaml
Revises: 012_todo_diary_ref
"""
from alembic import op
import sqlalchemy as sa

revision = "013_project_yaml"
down_revision = "012_todo_diary_ref"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("ob_projects", sa.Column("project_yaml", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("ob_projects", "project_yaml")
