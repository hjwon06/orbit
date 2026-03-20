"""Add diary_ref column to ob_todos for obsidian diary sync.

Revision ID: 012_todo_diary_ref
Revises: 011_todo_milestone_fk
"""
from alembic import op
import sqlalchemy as sa

revision = "012_todo_diary_ref"
down_revision = "011_todo_milestone_fk"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("ob_todos", sa.Column("diary_ref", sa.String(100), nullable=True))
    op.create_index("ix_ob_todos_diary_ref", "ob_todos", ["diary_ref"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_ob_todos_diary_ref", table_name="ob_todos")
    op.drop_column("ob_todos", "diary_ref")
