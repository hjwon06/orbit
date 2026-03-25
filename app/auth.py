"""세션 쿠키 기반 인증 — DB 사용자 + 역할(admin/member)."""
import bcrypt
from fastapi import Request, HTTPException
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings

COOKIE_NAME = "orbit_session"
MAX_AGE = 60 * 60 * 24 * 7  # 7일


def _get_serializer():
    settings = get_settings()
    return URLSafeTimedSerializer(settings.secret_key)


def create_session_cookie(username: str, role: str = "member") -> str:
    s = _get_serializer()
    return s.dumps({"user": username, "role": role})


def verify_session_cookie(cookie: str) -> dict | None:
    s = _get_serializer()
    try:
        return s.loads(cookie, max_age=MAX_AGE)
    except (BadSignature, SignatureExpired):
        return None


def get_current_user(request: Request) -> dict | None:
    """현재 로그인 사용자 정보 반환. {'user': str, 'role': str} 또는 None."""
    cookie = request.cookies.get(COOKIE_NAME)
    if not cookie:
        return None
    data = verify_session_cookie(cookie)
    if not data or "user" not in data:
        return None
    # 하위호환: 기존 쿠키에 role이 없으면 admin으로 처리
    if "role" not in data:
        data["role"] = "admin"
    return data


def is_admin(request: Request) -> bool:
    """관리자 여부 확인."""
    user = get_current_user(request)
    return user is not None and user.get("role") == "admin"


async def check_credentials(username: str, password: str, db: AsyncSession) -> dict | None:
    """DB에서 사용자 확인. 성공 시 {'username', 'role', 'display_name'} 반환."""
    from app.models import User
    result = await db.execute(select(User).where(User.username == username))
    user = result.scalar_one_or_none()
    if not user:
        return None
    if not bcrypt.checkpw(password.encode(), user.password_hash.encode()):
        return None
    return {
        "username": user.username,
        "role": user.role,
        "display_name": user.display_name,
    }


def require_auth(request: Request) -> dict:
    """페이지 라우트용 — 미인증 시 로그인으로 리다이렉트."""
    user = get_current_user(request)
    if not user:
        raise HTTPException(status_code=303, headers={"Location": "/login"})
    return user
