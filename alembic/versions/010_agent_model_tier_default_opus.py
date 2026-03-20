"""Change ob_agents.model_tier server_default from sonnet to opus.

Revision ID: 010_model_tier_opus
Revises: 009_soft_delete
"""
from alembic import op

revision = "010_model_tier_opus"
down_revision = "009_soft_delete"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column(
        "ob_agents",
        "model_tier",
        server_default="opus",
    )


def downgrade() -> None:
    op.alter_column(
        "ob_agents",
        "model_tier",
        server_default="sonnet",
    )
