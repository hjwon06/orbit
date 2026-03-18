async def test_create_work_log(client, project_id):
    resp = await client.post("/api/work-logs", json={
        "project_id": project_id, "log_date": "2026-03-17",
        "content": "- test work log",
    })
    assert resp.status_code == 201
    assert resp.json()["log_date"] == "2026-03-17"


async def test_upsert_work_log(client, project_id):
    await client.post("/api/work-logs", json={
        "project_id": project_id, "log_date": "2026-03-18", "content": "v1",
    })
    resp = await client.post("/api/work-logs", json={
        "project_id": project_id, "log_date": "2026-03-18", "content": "v2 overwritten",
    })
    assert resp.status_code == 201
    assert resp.json()["content"] == "v2 overwritten"


async def test_list_work_logs(client, project_id):
    resp = await client.get(f"/api/work-logs/project/{project_id}")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


async def test_delete_work_log(client, project_id):
    create = await client.post("/api/work-logs", json={
        "project_id": project_id, "log_date": "2026-03-19", "content": "delete me",
    })
    lid = create.json()["id"]
    resp = await client.delete(f"/api/work-logs/{lid}")
    assert resp.status_code == 200
