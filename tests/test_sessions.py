async def test_create_session(client, project_id):
    resp = await client.post("/api/sessions", json={
        "project_id": project_id, "title": "Test Session",
    })
    assert resp.status_code == 201
    assert resp.json()["status"] == "running"


async def test_finish_session(client, project_id):
    create = await client.post("/api/sessions", json={
        "project_id": project_id, "title": "Finish Test",
    })
    sid = create.json()["id"]
    resp = await client.patch(f"/api/sessions/{sid}/finish", json={
        "summary": "- done", "status": "done",
    })
    assert resp.status_code == 200
    assert resp.json()["status"] == "done"
    assert resp.json()["finished_at"] is not None


async def test_list_sessions(client, project_id):
    resp = await client.get(f"/api/sessions/project/{project_id}")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


async def test_delete_session(client, project_id):
    create = await client.post("/api/sessions", json={
        "project_id": project_id, "title": "Del Session",
    })
    sid = create.json()["id"]
    resp = await client.delete(f"/api/sessions/{sid}")
    assert resp.status_code == 200
