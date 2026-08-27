from tests.conftest import login_client


async def test_me_requires_token_tc_auth_04(client):
    response = await client.get("/api/v1/auth/me")
    assert response.status_code == 401
    assert response.json()["code"] == "AUTH_TOKEN_MISSING"


async def test_me_returns_current_user(client, credentials):
    tokens = await login_client(client, credentials)
    response = await client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {tokens['access_token']}"},
    )
    assert response.status_code == 200
    user = response.json()["data"]
    assert user["email"] == credentials["email"]
    assert user["roles"][0]["role_code"] == "REQUESTER"


async def test_update_own_profile_auth_05(client, credentials):
    tokens = await login_client(client, credentials)
    response = await client.patch(
        "/api/v1/users/me",
        headers={"Authorization": f"Bearer {tokens['access_token']}"},
        json={"full_name": "Requester Updated", "phone": "+84901234567"},
    )
    assert response.status_code == 200
    user = response.json()["data"]
    assert user["full_name"] == "Requester Updated"
    assert user["phone"] == "+84901234567"
