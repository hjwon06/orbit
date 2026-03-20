"""Add milestone_id FK to ob_todos for progress tracking.

Revision ID: 011_todo_milestone_fk
Revises: 010_model_tier_opus
"""
from alembic import op
import sqlalchemy as sa

revision = "011_todo_milestone_fk"
down_revision = "010_model_tier_opus"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("ob_todos", sa.Column("milestone_id", sa.Integer(), nullable=True))
    op.create_foreign_key(
        "fk_todos_milestone_id",
        "ob_todos",
        "ob_milestones",
        ["milestone_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint("fk_todos_milestone_id", "ob_todos", type_="foreignkey")
    op.drop_column("ob_todos", "milestone_id")
