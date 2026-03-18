async def test_create_agent(client, project_id):
    resp = await client.post("/api/agents", json={
        "project_id": project_id, "agent_code": "T0",
        "agent_name": "Test Agent", "model_tier": "sonnet",
    })
    assert resp.status_code == 201
    assert resp.json()["agent_code"] == "T0"


async def test_list_agents(client, project_id):
    await client.post("/api/agents", json={
        "project_id": project_id, "agent_code": "T1",
        "agent_name": "List Agent", "model_tier": "opus",
    })
    resp = await client.get(f"/api/agents/project/{project_id}")
    assert resp.status_code == 200
    assert len(resp.json()) >= 1


async def test_agent_heartbeat(client, project_id):
    create = await client.post("/api/agents", json={
        "project_id": project_id, "agent_code": "HB",
        "agent_name": "Heartbeat", "model_tier": "sonnet",
    })
    aid = create.json()["id"]
    resp = await client.post(f"/api/agents/{aid}/heartbeat")
    assert resp.status_code == 200
    assert resp.json()["last_heartbeat"] is not None


async def test_agent_run_lifecycle(client, project_id):
    create = await client.post("/api/agents", json={
        "project_id": project_id, "agent_code": "RN",
        "agent_name": "Runner", "model_tier": "sonnet",
    })
    aid = create.json()["id"]

    run = await client.post("/api/agents/runs", json={"agent_id": aid, "task_name": "test task"})
    assert run.status_code == 201
    run_id = run.json()["id"]

    finish = await client.patch(f"/api/agents/runs/{run_id}/finish", json={
        "status": "success", "duration_sec": 10,
    })
    assert finish.status_code == 200
    assert finish.json()["status"] == "success"
