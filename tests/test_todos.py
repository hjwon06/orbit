async def test_create_todo(client, project_id):
    resp = await client.post("/api/todos", json={
        "project_id": project_id, "title": "Test Todo", "priority": "high",
    })
    assert resp.status_code == 201
    assert resp.json()["status"] == "open"
    assert resp.json()["priority"] == "high"


async def test_toggle_todo_done(client, project_id):
    create = await client.post("/api/todos", json={
        "project_id": project_id, "title": "Toggle Todo",
    })
    tid = create.json()["id"]
    resp = await client.patch(f"/api/todos/{tid}", json={"status": "done"})
    assert resp.status_code == 200
    assert resp.json()["status"] == "done"
    assert resp.json()["completed_at"] is not None


async def test_toggle_todo_reopen(client, project_id):
    create = await client.post("/api/todos", json={
        "project_id": project_id, "title": "Reopen Todo",
    })
    tid = create.json()["id"]
    await client.patch(f"/api/todos/{tid}", json={"status": "done"})
    resp = await client.patch(f"/api/todos/{tid}", json={"status": "open"})
    assert resp.status_code == 200
    assert resp.json()["status"] == "open"
    assert resp.json()["completed_at"] is None


async def test_list_todos(client, project_id):
    resp = await client.get(f"/api/todos/project/{project_id}")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


async def test_delete_todo(client, project_id):
    create = await client.post("/api/todos", json={
        "project_id": project_id, "title": "Del Todo",
    })
    tid = create.json()["id"]
    resp = await client.delete(f"/api/todos/{tid}")
    assert resp.status_code == 200
