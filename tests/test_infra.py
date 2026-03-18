"""Tests for infrastructure management API (Sprint 7)."""
import pytest


@pytest.mark.asyncio
async def test_list_databases(client):
    resp = await client.get("/api/infra/databases")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert len(data) >= 1
    assert "alias" in data[0]


@pytest.mark.asyncio
async def test_list_tables(client):
    dbs = (await client.get("/api/infra/databases")).json()
    alias = dbs[0]["alias"]
    resp = await client.get(f"/api/infra/databases/{alias}/tables", timeout=30)
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)


@pytest.mark.asyncio
async def test_table_detail(client):
    dbs = (await client.get("/api/infra/databases")).json()
    alias = dbs[0]["alias"]
    resp = await client.get(f"/api/infra/databases/{alias}/tables/ob_projects", timeout=30)
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "ob_projects"
    assert "columns" in data


@pytest.mark.asyncio
async def test_execute_sql_select(client):
    dbs = (await client.get("/api/infra/databases")).json()
    alias = dbs[0]["alias"]
    resp = await client.post("/api/infra/sql", json={
        "db_alias": alias,
        "query": "SELECT 1 AS ok",
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["row_count"] >= 1
    assert "ok" in data["columns"]
    assert data["error"] == ""


@pytest.mark.asyncio
async def test_sql_history(client):
    resp = await client.get("/api/infra/sql/history")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    if data:
        assert "query" in data[0]
        assert "executed_at" in data[0]


@pytest.mark.asyncio
async def test_rds_metrics(client):
    dbs = (await client.get("/api/infra/databases")).json()
    alias = dbs[0]["alias"]
    resp = await client.get(f"/api/infra/rds/{alias}/metrics")
    assert resp.status_code == 200
    data = resp.json()
    assert "active_connections" in data or "error" in data


