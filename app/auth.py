"""세션 쿠키 기반 인증 — 단일 관리자."""
from fastapi import Request, HTTPException

from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired
from app.config import get_settings

COOKIE_NAME = "orbit_session"
MAX_AGE = 60 * 60 * 24 * 7  # 7일


def _get_serializer():
    settings = get_settings()
    return URLSafeTimedSerializer(settings.secret_key)


def create_session_cookie(username: str) -> str:
    s = _get_serializer()
    return s.dumps({"user": username})


def verify_session_cookie(cookie: str) -> dict | None:
    s = _get_serializer()
    try:
        return s.loads(cookie, max_age=MAX_AGE)
    except (BadSignature, SignatureExpired):
        return None


def get_current_user(request: Request) -> str | None:
    cookie = request.cookies.get(COOKIE_NAME)
    if not cookie:
        return None
    data = verify_session_cookie(cookie)
    return data.get("user") if data else None


def require_auth(request: Request) -> str:
    """페이지 라우트용 — 미인증 시 로그인으로 리다이렉트."""
    user = get_current_user(request)
    if not user:
        raise HTTPException(status_code=303, headers={"Location": "/login"})
    return user


def check_credentials(username: str, password: str) -> bool:
    settings = get_settings()
    return username == settings.admin_username and password == settings.admin_password
