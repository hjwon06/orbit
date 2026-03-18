"""sprint5 create ob_infra_costs

Revision ID: 006_sprint5
Revises: 005_sprint4
Create Date: 2026-03-17
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "006_sprint5"
down_revision: Union[str, None] = "005_sprint4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "ob_infra_costs",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("project_id", sa.Integer(), sa.ForeignKey("ob_projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("provider", sa.String(50), nullable=False),
        sa.Column("service_name", sa.String(100), nullable=False),
        sa.Column("cost_usd", sa.Float(), server_default="0"),
        sa.Column("billing_cycle", sa.String(20), server_default="monthly"),
        sa.Column("is_active", sa.Boolean(), server_default="true"),
        sa.Column("notes", sa.Text(), server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_ob_infra_costs_project_id", "ob_infra_costs", ["project_id"])


def downgrade() -> None:
    op.drop_table("ob_infra_costs")
