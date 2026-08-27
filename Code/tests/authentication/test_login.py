async def test_login_success_tc_auth_01(client, credentials):
    response = await client.post("/api/v1/auth/login", json=credentials)
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["access_token"]
    assert data["refresh_token"]
    assert data["token_type"] == "bearer"
    assert data["expires_in"] == 900
    assert data["user"]["roles"][0]["role_code"] == "REQUESTER"


async def test_login_wrong_password_tc_auth_02(client, credentials):
    credentials["password"] = "WrongPassword123!"
    response = await client.post("/api/v1/auth/login", json=credentials)
    assert response.status_code == 401
    body = response.json()
    assert body["code"] == "AUTH_INVALID_CREDENTIALS"
    assert "tồn tại" not in body["message"].lower()


async def test_login_inactive_account_tc_auth_03(client, seeded_users):
    response = await client.post(
        "/api/v1/auth/login",
        json={
            "email": seeded_users["inactive_email"],
            "password": seeded_users["password"],
        },
    )
    assert response.status_code == 403
    assert response.json()["code"] == "AUTH_ACCOUNT_INACTIVE"


async def test_login_rate_limit(client, credentials):
    invalid = {**credentials, "password": "WrongPassword123!"}
    for _ in range(5):
        response = await client.post("/api/v1/auth/login", json=invalid)
        assert response.status_code == 401
    response = await client.post("/api/v1/auth/login", json=invalid)
    assert response.status_code == 429
    assert response.json()["code"] == "RATE_LIMIT_EXCEEDED"
    assert response.headers["Retry-After"] == "300"
