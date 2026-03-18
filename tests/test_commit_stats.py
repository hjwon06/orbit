async def test_create_commit_stat(client, project_id):
    resp = await client.post("/api/commit-stats", json={
        "project_id": project_id, "stat_date": "2026-03-17",
        "commit_count": 5, "additions": 200, "deletions": 50,
    })
    assert resp.status_code == 201
    assert resp.json()["commit_count"] == 5


async def test_upsert_commit_stat(client, project_id):
    await client.post("/api/commit-stats", json={
        "project_id": project_id, "stat_date": "2026-03-18",
        "commit_count": 3, "additions": 100, "deletions": 20,
    })
    resp = await client.post("/api/commit-stats", json={
        "project_id": project_id, "stat_date": "2026-03-18",
        "commit_count": 8, "additions": 300, "deletions": 80,
    })
    assert resp.status_code == 201
    assert resp.json()["commit_count"] == 8


async def test_list_commit_stats(client, project_id):
    resp = await client.get(f"/api/commit-stats/project/{project_id}")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)
