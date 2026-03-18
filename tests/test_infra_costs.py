async def test_create_infra_cost(client, project_id):
    resp = await client.post("/api/infra-costs", json={
        "project_id": project_id, "provider": "Vultr",
        "service_name": "VPS Seoul 2GB", "cost_usd": 12.0,
        "billing_cycle": "monthly",
    })
    assert resp.status_code == 201
    assert resp.json()["provider"] == "Vultr"


async def test_update_infra_cost(client, project_id):
    create = await client.post("/api/infra-costs", json={
        "project_id": project_id, "provider": "AWS",
        "service_name": "S3", "cost_usd": 3.5,
    })
    cid = create.json()["id"]
    resp = await client.patch(f"/api/infra-costs/{cid}", json={"cost_usd": 4.0})
    assert resp.status_code == 200
    assert resp.json()["cost_usd"] == 4.0


async def test_list_infra_costs(client, project_id):
    resp = await client.get(f"/api/infra-costs/project/{project_id}")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


async def test_delete_infra_cost(client, project_id):
    create = await client.post("/api/infra-costs", json={
        "project_id": project_id, "provider": "Del",
        "service_name": "DelService", "cost_usd": 1.0,
    })
    cid = create.json()["id"]
    resp = await client.delete(f"/api/infra-costs/{cid}")
    assert resp.status_code == 200
