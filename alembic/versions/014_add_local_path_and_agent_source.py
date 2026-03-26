"""ob_projects.local_path + ob_agents.source 컬럼 추가

Revision ID: 014
"""
from alembic import op
import sqlalchemy as sa

revision = "014"
down_revision = "013"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("ob_projects", sa.Column("local_path", sa.String(500), nullable=True))
    op.add_column("ob_agents", sa.Column("source", sa.String(20), server_default="manual", nullable=False))


def downgrade():
    op.drop_column("ob_agents", "source")
    op.drop_column("ob_projects", "local_path")
