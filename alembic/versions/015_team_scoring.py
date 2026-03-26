"""ob_team_members + ob_team_scores 테이블 생성

Revision ID: 015
"""
from alembic import op
import sqlalchemy as sa

revision = "015"
down_revision = "014"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "ob_team_members",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("project_id", sa.Integer, sa.ForeignKey("ob_projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("member_name", sa.String(50), nullable=False),
        sa.Column("display_name", sa.String(100), nullable=False),
        sa.Column("branch_pattern", sa.String(200), default=""),
        sa.Column("module_path", sa.String(500), default=""),
        sa.Column("is_excluded", sa.Boolean, server_default="false"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("project_id", "member_name", name="uq_team_member"),
    )

    op.create_table(
        "ob_team_scores",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("project_id", sa.Integer, sa.ForeignKey("ob_projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("member_name", sa.String(50), nullable=False),
        sa.Column("total_score", sa.Integer, default=100),
        sa.Column("grade", sa.String(2), default="S"),
        sa.Column("completeness", sa.Integer, default=35),
        sa.Column("convention", sa.Integer, default=25),
        sa.Column("quality", sa.Integer, default=20),
        sa.Column("security", sa.Integer, default=10),
        sa.Column("testing", sa.Integer, default=10),
        sa.Column("violations_json", sa.Text, default="[]"),
        sa.Column("gpt_review", sa.Text, nullable=True),
        sa.Column("evaluated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )


def downgrade():
    op.drop_table("ob_team_scores")
    op.drop_table("ob_team_members")
