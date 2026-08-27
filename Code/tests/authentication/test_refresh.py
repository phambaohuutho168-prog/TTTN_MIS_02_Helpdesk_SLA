from tests.conftest import login_client


async def test_refresh_rotates_token(client, credentials):
    first = await login_client(client, credentials)
    response = await client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": first["refresh_token"]},
    )
    assert response.status_code == 200
    second = response.json()["data"]
    assert second["access_token"] != first["access_token"]
    assert second["refresh_token"] != first["refresh_token"]


async def test_refresh_reuse_revokes_family(client, credentials):
    first = await login_client(client, credentials)
    rotated_response = await client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": first["refresh_token"]},
    )
    second = rotated_response.json()["data"]

    reuse_response = await client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": first["refresh_token"]},
    )
    assert reuse_response.status_code == 401
    assert reuse_response.json()["code"] == "AUTH_REFRESH_TOKEN_INVALID"

    family_response = await client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": second["refresh_token"]},
    )
    assert family_response.status_code == 401
    assert family_response.json()["code"] == "AUTH_REFRESH_TOKEN_INVALID"
