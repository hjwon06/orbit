from fastapi import FastAPI, Request, Form
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse, HTMLResponse
from fastapi.templating import Jinja2Templates
from starlette.middleware.base import BaseHTTPMiddleware
from contextlib import asynccontextmanager
from app.config import get_settings
from app.database import engine, Base
from app.api import api_router
from app.pages import router as pages_router
from app.auth import (
    get_current_user, check_credentials, create_session_cookie, COOKIE_NAME, MAX_AGE,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    await engine.dispose()


settings = get_settings()

app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    lifespan=lifespan,
)

templates = Jinja2Templates(directory="app/templates")

# KST 시간 표시 필터
from datetime import timedelta, timezone as tz
KST = tz(timedelta(hours=9))


def _to_kst(value, fmt="%Y-%m-%d %H:%M"):
    if value is None:
        return ""
    try:
        return value.astimezone(KST).strftime(fmt)
    except Exception:
        return str(value)


templates.env.filters["kst"] = _to_kst

# 인증 불필요 경로
PUBLIC_PATHS = {"/login", "/api/docs", "/openapi.json", "/docs", "/redoc"}
PUBLIC_PREFIXES = ("/static/",)


class AuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        path = request.url.path

        # 공개 경로는 통과
        if path in PUBLIC_PATHS or any(path.startswith(p) for p in PUBLIC_PREFIXES):
            return await call_next(request)

        # 로컬 에이전트 API 면제 (Claude Code 연동용)
        AGENT_API_EXEMPT = ("/api/agents/runs", "/api/agents/lookup")
        if any(path.startswith(p) for p in AGENT_API_EXEMPT):
            client_ip = request.client.host if request.client else ""
            if client_ip in {"127.0.0.1", "::1"} or client_ip.startswith("172."):
                return await call_next(request)

        # API는 쿠키 인증 (미인증 시 401)
        if path.startswith("/api/"):
            user = get_current_user(request)
            if not user:
                from fastapi.responses import JSONResponse
                return JSONResponse(status_code=401, content={"detail": "Not authenticated"})
            return await call_next(request)

        # 페이지는 미인증 시 로그인으로 리다이렉트
        user = get_current_user(request)
        if not user:
            return RedirectResponse(url="/login", status_code=303)
        return await call_next(request)


app.add_middleware(AuthMiddleware)

app.mount("/static", StaticFiles(directory="app/static"), name="static")
app.include_router(api_router)
app.include_router(pages_router)


@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    if get_current_user(request):
        return RedirectResponse(url="/", status_code=303)
    return templates.TemplateResponse("login.html", {"request": request, "error": None})


# Rate Limit (메모리 기반)
from datetime import datetime as dt
from collections import defaultdict

_login_attempts: dict[str, list] = defaultdict(list)
RATE_LIMIT_MAX = 5
RATE_LIMIT_WINDOW = 900  # 15분


def _is_rate_limited(key: str) -> bool:
    now = dt.now()
    _login_attempts[key] = [t for t in _login_attempts[key] if (now - t).total_seconds() < RATE_LIMIT_WINDOW]
    return len(_login_attempts[key]) >= RATE_LIMIT_MAX


def _record_attempt(key: str):
    _login_attempts[key].append(dt.now())


@app.post("/login")
async def login_submit(request: Request, username: str = Form(...), password: str = Form(...)):
    ip = request.client.host if request.client else "unknown"
    # 로컬/컨테이너 내부 요청은 rate limit 면제 (테스트 호환)
    exempt_ips = {"127.0.0.1", "::1", "localhost"}
    if ip not in exempt_ips and (_is_rate_limited(f"ip:{ip}") or _is_rate_limited(f"user:{username}")):
        return templates.TemplateResponse("login.html", {
            "request": request,
            "error": "로그인 시도가 너무 많습니다. 15분 후 다시 시도하세요.",
        })
    if check_credentials(username, password):
        _login_attempts.pop(f"ip:{ip}", None)
        _login_attempts.pop(f"user:{username}", None)
        response = RedirectResponse(url="/", status_code=303)
        cookie = create_session_cookie(username)
        response.set_cookie(
            key=COOKIE_NAME, value=cookie, max_age=MAX_AGE,
            httponly=True, samesite="lax",
        )
        return response
    _record_attempt(f"ip:{ip}")
    _record_attempt(f"user:{username}")
    return templates.TemplateResponse("login.html", {
        "request": request,
        "error": "아이디 또는 비밀번호가 잘못되었습니다.",
    })


@app.get("/logout")
async def logout():
    response = RedirectResponse(url="/login", status_code=303)
    response.delete_cookie(key=COOKIE_NAME)
    return response


# --- 에러 핸들러 ---
from starlette.exceptions import HTTPException as StarletteHTTPException


@app.exception_handler(404)
async def not_found_handler(request: Request, exc: StarletteHTTPException):
    if request.url.path.startswith("/api/"):
        from fastapi.responses import JSONResponse
        return JSONResponse(status_code=404, content={"detail": "Not found"})
    return templates.TemplateResponse("error.html", {
        "request": request,
        "page_title": "404",
        "error_code": 404,
        "error_title": "페이지를 찾을 수 없습니다",
        "error_message": "요청하신 페이지가 존재하지 않거나 삭제되었습니다.",
    }, status_code=404)


@app.exception_handler(500)
async def server_error_handler(request: Request, exc: StarletteHTTPException):
    if request.url.path.startswith("/api/"):
        from fastapi.responses import JSONResponse
        return JSONResponse(status_code=500, content={"detail": "Internal server error"})
    return templates.TemplateResponse("error.html", {
        "request": request,
        "page_title": "500",
        "error_code": 500,
        "error_title": "서버 오류가 발생했습니다",
        "error_message": "잠시 후 다시 시도해주세요.",
    }, status_code=500)
