"""sprint7 create infrastructure management tables

Revision ID: 008_sprint7
Revises: 007_sprint6
Create Date: 2026-03-17
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "008_sprint7"
down_revision: Union[str, None] = "007_sprint6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "ob_deployments",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("project_id", sa.Integer(), sa.ForeignKey("ob_projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("target", sa.String(50), nullable=False),
        sa.Column("commit_sha", sa.String(40), server_default=""),
        sa.Column("branch", sa.String(100), server_default="main"),
        sa.Column("status", sa.String(20), server_default="pending"),
        sa.Column("log", sa.Text(), server_default=""),
        sa.Column("duration_sec", sa.Integer(), nullable=True),
        sa.Column("triggered_by", sa.String(50), server_default="manual"),
        sa.Column("started_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_ob_deployments_project", "ob_deployments", ["project_id"])

    op.create_table(
        "ob_db_migrations",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("project_id", sa.Integer(), sa.ForeignKey("ob_projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("db_alias", sa.String(50), nullable=False),
        sa.Column("migration_name", sa.String(200), nullable=False),
        sa.Column("direction", sa.String(10), server_default="upgrade"),
        sa.Column("status", sa.String(20), server_default="success"),
        sa.Column("log", sa.Text(), server_default=""),
        sa.Column("executed_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "ob_sql_history",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("db_alias", sa.String(50), nullable=False),
        sa.Column("query", sa.Text(), nullable=False),
        sa.Column("row_count", sa.Integer(), server_default="0"),
        sa.Column("duration_ms", sa.Integer(), server_default="0"),
        sa.Column("status", sa.String(20), server_default="success"),
        sa.Column("error", sa.Text(), server_default=""),
        sa.Column("executed_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "ob_server_snapshots",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("server_name", sa.String(50), nullable=False),
        sa.Column("cpu_pct", sa.Numeric(5, 2), server_default="0"),
        sa.Column("memory_pct", sa.Numeric(5, 2), server_default="0"),
        sa.Column("disk_pct", sa.Numeric(5, 2), server_default="0"),
        sa.Column("memory_used_mb", sa.Integer(), server_default="0"),
        sa.Column("memory_total_mb", sa.Integer(), server_default="0"),
        sa.Column("disk_used_gb", sa.Numeric(10, 2), server_default="0"),
        sa.Column("disk_total_gb", sa.Numeric(10, 2), server_default="0"),
        sa.Column("load_avg_1m", sa.Numeric(5, 2), server_default="0"),
        sa.Column("process_count", sa.Integer(), server_default="0"),
        sa.Column("uptime_hours", sa.Integer(), server_default="0"),
        sa.Column("raw_data", sa.JSON(), server_default="{}"),
        sa.Column("collected_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_ob_server_snapshots_server", "ob_server_snapshots", ["server_name"])
    op.create_index("ix_ob_server_snapshots_time", "ob_server_snapshots", ["collected_at"])


def downgrade() -> None:
    op.drop_table("ob_server_snapshots")
    op.drop_table("ob_sql_history")
    op.drop_table("ob_db_migrations")
    op.drop_table("ob_deployments")
