async def test_health(client):
    response = await client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


async def test_ready_checks_database(client):
    response = await client.get("/health/ready")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "database": "ok"}


async def test_root_identifies_service(client):
    response = await client.get("/")
    assert response.status_code == 200
    assert response.json()["service"] == "match-api"
