async def test_create_milestone(client, project_id):
    resp = await client.post("/api/milestones", json={
        "project_id": project_id, "title": "Sprint 0",
        "status": "active", "start_date": "2026-03-10", "end_date": "2026-03-16",
    })
    assert resp.status_code == 201
    assert resp.json()["title"] == "Sprint 0"


async def test_list_milestones(client, project_id):
    await client.post("/api/milestones", json={
        "project_id": project_id, "title": "Sprint List",
        "status": "planned", "start_date": "2026-04-01", "end_date": "2026-04-07",
    })
    resp = await client.get(f"/api/milestones/project/{project_id}")
    assert resp.status_code == 200
    assert len(resp.json()) >= 1


async def test_update_dates(client, project_id):
    create = await client.post("/api/milestones", json={
        "project_id": project_id, "title": "Drag Test",
        "status": "planned", "start_date": "2026-05-01", "end_date": "2026-05-07",
    })
    mid = create.json()["id"]
    resp = await client.patch(f"/api/milestones/{mid}/dates", json={
        "start_date": "2026-05-03", "end_date": "2026-05-10",
    })
    assert resp.status_code == 200
    assert resp.json()["start_date"] == "2026-05-03"


async def test_delete_milestone(client, project_id):
    create = await client.post("/api/milestones", json={
        "project_id": project_id, "title": "Del MS",
        "status": "planned", "start_date": "2026-06-01", "end_date": "2026-06-07",
    })
    mid = create.json()["id"]
    resp = await client.delete(f"/api/milestones/{mid}")
    assert resp.status_code == 200
