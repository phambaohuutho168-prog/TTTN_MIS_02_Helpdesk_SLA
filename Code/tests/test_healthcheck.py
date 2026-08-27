async def test_liveness(client):
    response = await client.get("/api/v1/health/live")
    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["data"]["status"] == "UP"
    assert body["meta"]["request_id"]


async def test_readiness_checks_database_and_redis(client):
    response = await client.get("/api/v1/health/ready")
    assert response.status_code == 200
    dependencies = response.json()["data"]["dependencies"]
    assert {item["name"] for item in dependencies} == {"postgresql", "redis"}
    assert all(item["status"] == "UP" for item in dependencies)
