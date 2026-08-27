from tests.conftest import login_client


async def test_logout_revokes_session_tc_auth_05(client, credentials):
    tokens = await login_client(client, credentials)
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}

    response = await client.post(
        "/api/v1/auth/logout",
        headers=headers,
        json={"refresh_token": tokens["refresh_token"]},
    )
    assert response.status_code == 204
    assert response.content == b""

    me_response = await client.get("/api/v1/auth/me", headers=headers)
    assert me_response.status_code == 401
    assert me_response.json()["code"] == "AUTH_TOKEN_INVALID"

    refresh_response = await client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": tokens["refresh_token"]},
    )
    assert refresh_response.status_code == 401
    assert refresh_response.json()["code"] == "AUTH_REFRESH_TOKEN_INVALID"
