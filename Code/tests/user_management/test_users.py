from tests.conftest import login_client


async def _headers(client, credentials):
    tokens = await login_client(client, credentials)
    return {"Authorization": f"Bearer {tokens['access_token']}"}


async def test_requester_cannot_list_admin_users(client, credentials):
    response = await client.get(
        "/api/v1/admin/users",
        headers=await _headers(client, credentials),
    )

    assert response.status_code == 403
    assert response.json()["code"] == "FORBIDDEN_ACTION"


async def test_admin_lists_and_filters_users(client, admin_credentials):
    headers = await _headers(client, admin_credentials)

    response = await client.get("/api/v1/admin/users", headers=headers)
    assert response.status_code == 200
    page = response.json()["data"]
    assert page["total"] == 4
    assert page["page"] == 1
    assert len(page["items"]) == 4

    filtered = await client.get(
        "/api/v1/admin/users",
        params={"role_code": "PROCESSOR", "is_active": True},
        headers=headers,
    )
    assert filtered.status_code == 200
    data = filtered.json()["data"]
    assert data["total"] == 1
    assert data["items"][0]["email"] == "processor@example.com"


async def test_admin_creates_account_with_role(
    client,
    admin_credentials,
    seeded_users,
):
    headers = await _headers(client, admin_credentials)
    payload = {
        "email": "new.processor@example.com",
        "full_name": "  New   Processor  ",
        "password": "NewPassword123!",
        "phone": "0901 234 567",
        "department_id": seeded_users["department_id"],
        "role_ids": [seeded_users["processor_role_id"]],
    }

    response = await client.post(
        "/api/v1/admin/users",
        json=payload,
        headers=headers,
    )

    assert response.status_code == 201
    user = response.json()["data"]
    assert user["email"] == "new.processor@example.com"
    assert user["full_name"] == "New Processor"
    assert user["phone"] == "0901234567"
    assert user["roles"][0]["role_code"] == "PROCESSOR"
    assert "password" not in user
    assert "password_hash" not in user

    login_response = await client.post(
        "/api/v1/auth/login",
        json={
            "email": payload["email"],
            "password": payload["password"],
        },
    )
    assert login_response.status_code == 200


async def test_admin_cannot_create_duplicate_email(
    client,
    admin_credentials,
    seeded_users,
):
    response = await client.post(
        "/api/v1/admin/users",
        headers=await _headers(client, admin_credentials),
        json={
            "email": seeded_users["active_email"].upper(),
            "full_name": "Duplicate User",
            "password": "NewPassword123!",
            "role_ids": [seeded_users["requester_role_id"]],
        },
    )

    assert response.status_code == 409
    assert response.json()["code"] == "USER_EMAIL_CONFLICT"


async def test_admin_gets_and_deactivates_user(
    client,
    admin_credentials,
    seeded_users,
):
    headers = await _headers(client, admin_credentials)
    user_id = seeded_users["processor_user_id"]

    detail = await client.get(f"/api/v1/admin/users/{user_id}", headers=headers)
    assert detail.status_code == 200
    assert detail.json()["data"]["email"] == seeded_users["processor_email"]

    updated = await client.patch(
        f"/api/v1/admin/users/{user_id}",
        headers=headers,
        json={"full_name": "Processor Updated", "is_active": False},
    )
    assert updated.status_code == 200
    assert updated.json()["data"]["full_name"] == "Processor Updated"
    assert updated.json()["data"]["is_active"] is False

    login_response = await client.post(
        "/api/v1/auth/login",
        json={
            "email": seeded_users["processor_email"],
            "password": seeded_users["password"],
        },
    )
    assert login_response.status_code == 403
    assert login_response.json()["code"] == "AUTH_ACCOUNT_INACTIVE"


async def test_admin_update_rejects_unknown_department(
    client,
    admin_credentials,
    seeded_users,
):
    response = await client.patch(
        f"/api/v1/admin/users/{seeded_users['processor_user_id']}",
        headers=await _headers(client, admin_credentials),
        json={"department_id": 999999},
    )

    assert response.status_code == 404
    assert response.json()["code"] == "DEPARTMENT_NOT_FOUND"


async def test_admin_user_not_found(client, admin_credentials):
    response = await client.get(
        "/api/v1/admin/users/999999",
        headers=await _headers(client, admin_credentials),
    )

    assert response.status_code == 404
    assert response.json()["code"] == "USER_NOT_FOUND"


async def test_last_active_admin_cannot_be_deactivated(
    client,
    admin_credentials,
    seeded_users,
):
    response = await client.patch(
        f"/api/v1/admin/users/{seeded_users['admin_user_id']}",
        headers=await _headers(client, admin_credentials),
        json={"is_active": False},
    )

    assert response.status_code == 409
    assert response.json()["code"] == "LAST_ADMIN_ROLE_FORBIDDEN"
