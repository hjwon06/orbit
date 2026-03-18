"""Test against the running server — real DB, no mocks."""
import pytest_asyncio
from httpx import AsyncClient

BASE_URL = "http://localhost:8000"


@pytest_asyncio.fixture
async def client():
    async with AsyncClient(base_url=BASE_URL) as c:
        # 로그인해서 세션 쿠키 획득
        resp = await c.post("/login", data={"username": "admin", "password": "orbit2026"}, follow_redirects=False)
        if "orbit_session" in resp.cookies:
            c.cookies.set("orbit_session", resp.cookies["orbit_session"])
        yield c


@pytest_asyncio.fixture
async def project_id(client):
    """Create a unique project for each test that needs one."""
    import uuid
    slug = f"test-{uuid.uuid4().hex[:8]}"
    resp = await client.post("/api/projects", json={
        "name": f"Test {slug}", "slug": slug,
        "description": "test project", "status": "active",
        "stack": "test", "color": "#000000",
    })
    pid = resp.json()["id"]
    yield pid
    await client.delete(f"/api/projects/{pid}")
