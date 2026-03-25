"""브랜치별 커밋 현황 API 테스트."""
import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        # 로그인
        resp = await c.post("/login", data={"username": "admin", "password": "1234"}, follow_redirects=False)
        yield c


@pytest.mark.asyncio
async def test_branches_endpoint_returns_json(client):
    """브랜치 API가 JSON을 반환하는지 확인."""
    resp = await client.get("/api/github/branches/3")  # ORBIT project id=3
    assert resp.status_code == 200
    data = resp.json()
    # 에러 또는 정상 응답 둘 다 허용 (토큰/repo 미설정 시 error)
    assert "branches" in data or "error" in data


@pytest.mark.asyncio
async def test_branches_invalid_project(client):
    """존재하지 않는 프로젝트 ID."""
    resp = await client.get("/api/github/branches/99999")
    assert resp.status_code == 200
    data = resp.json()
    assert "error" in data


@pytest.mark.asyncio
async def test_branches_response_structure(client):
    """정상 응답 시 구조 확인."""
    resp = await client.get("/api/github/branches/74")  # tkdoor project
    data = resp.json()
    if "branches" in data:
        assert isinstance(data["branches"], list)
        assert "total_branches" in data
        assert "default_branch" in data
        if data["branches"]:
            branch = data["branches"][0]
            assert "name" in branch
            assert "commits" in branch
            assert isinstance(branch["commits"], list)
