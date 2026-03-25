"""add ob_users table

Revision ID: 05962730bed7
Revises: 013_project_yaml
Create Date: 2026-03-25 05:56:43.557178
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


revision: str = '05962730bed7'
down_revision: Union[str, None] = '013_project_yaml'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ob_users 테이블이 이미 존재하는 경우를 대비한 조건부 생성
    conn = op.get_bind()
    result = conn.execute(sa.text(
        "SELECT 1 FROM information_schema.tables WHERE table_name='ob_users'"
    ))
    if result.fetchone() is None:
        op.create_table(
            'ob_users',
            sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
            sa.Column('username', sa.String(length=50), nullable=False),
            sa.Column('password_hash', sa.String(length=200), nullable=False),
            sa.Column('display_name', sa.String(length=100), nullable=False),
            sa.Column('role', sa.String(length=20), nullable=False, server_default='member'),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.PrimaryKeyConstraint('id'),
            sa.UniqueConstraint('username'),
        )

    # 초기 사용자 seed (10명: admin 3 + member 7)
    seed_users = [
        ("mia", "$2b$12$w3x8DFQHsL6LHAcALl8gTOPSev75mfX8gzYo5okK5ZYrmzSUyr5OS", "미아", "admin"),
        ("yangyang", "$2b$12$4UkASobgSgoN4QdvEIbxoumcLu4joiQWJauN8rSrWHoDjs6SxdsJq", "양양", "admin"),
        ("jay", "$2b$12$BN1auS3dNSQQ8ooStvjwpeGX88dUoDtTqVjyoMPrR8K51sxsYpd82", "제이", "admin"),
        ("sunny", "$2b$12$12V3UVSYegZ78O0ZPpKE9Oc2lBNwARkj.xApkxZM2xcNCSpGhT5gm", "써니", "member"),
        ("jimmy", "$2b$12$FGKjIeDMmUt56HWE3c1fWuuIPajuSA50699rXdhPSFsTcV3tz7aEq", "지미", "member"),
        ("chloe", "$2b$12$lyKrhFJ6JQb.GwJEUziKHe6JuRvyewFQeleilY.u14fw2p4FJFcEu", "클로이", "member"),
        ("joy", "$2b$12$bJNgz927UOhuvRREiVxp7.p.37vhclYf/r8tvEke6UA68kMY/tNUu", "조이", "member"),
        ("jaesoon", "$2b$12$KrlZEYyvBJRrsiPCpdZoCeWR9tmA8HUMkHxbyKAG.MID72Xone02u", "재순", "member"),
        ("yanghi", "$2b$12$9zleAsEpLrFcgmHT5GyCLeAI56pjJgQYVo6Lny5xz5KiZQeJvekbq", "양희", "member"),
        ("joey", "$2b$12$yUJeWBW2q/eUJYtTCk0i5uNUcLHqNc96t38IIxWAKnnWLVQa9urge", "조이2", "member"),
    ]

    for username, pw_hash, display_name, role in seed_users:
        # 이미 존재하는 사용자는 건너뛰기
        exists = conn.execute(sa.text(
            "SELECT 1 FROM ob_users WHERE username = :u"
        ), {"u": username}).fetchone()
        if exists is None:
            conn.execute(sa.text(
                "INSERT INTO ob_users (username, password_hash, display_name, role) "
                "VALUES (:u, :p, :d, :r)"
            ), {"u": username, "p": pw_hash, "d": display_name, "r": role})


def downgrade() -> None:
    op.drop_table('ob_users')
