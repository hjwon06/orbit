import uuid


async def test_create_project(client):
    slug = f"proj-{uuid.uuid4().hex[:8]}"
    resp = await client.post("/api/projects", json={
        "name": "TestProj", "slug": slug,
        "description": "test", "status": "active",
        "stack": "Python", "color": "#000000",
    })
    assert resp.status_code == 201
    assert resp.json()["slug"] == slug


async def test_list_projects(client):
    resp = await client.get("/api/projects")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


async def test_get_project_by_slug(client):
    slug = f"slug-{uuid.uuid4().hex[:8]}"
    await client.post("/api/projects", json={
        "name": "SlugTest", "slug": slug,
        "description": "", "status": "active",
        "stack": "", "color": "#111111",
    })
    resp = await client.get(f"/api/projects/{slug}")
    assert resp.status_code == 200
    assert resp.json()["name"] == "SlugTest"


async def test_update_project(client):
    slug = f"upd-{uuid.uuid4().hex[:8]}"
    create = await client.post("/api/projects", json={
        "name": "UpdProj", "slug": slug,
        "description": "", "status": "active",
        "stack": "", "color": "#222222",
    })
    pid = create.json()["id"]
    resp = await client.patch(f"/api/projects/{pid}", json={"description": "updated"})
    assert resp.status_code == 200
    assert resp.json()["description"] == "updated"


async def test_delete_project(client):
    slug = f"del-{uuid.uuid4().hex[:8]}"
    create = await client.post("/api/projects", json={
        "name": "DelProj", "slug": slug,
        "description": "", "status": "active",
        "stack": "", "color": "#333333",
    })
    pid = create.json()["id"]
    resp = await client.delete(f"/api/projects/{pid}")
    assert resp.status_code in (200, 204)
