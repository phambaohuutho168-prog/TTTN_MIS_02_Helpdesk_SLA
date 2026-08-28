from app.models.user_role import UserRole
from tests.conftest import login_client


async def _headers(client, credentials):
    tokens = await login_client(client, credentials)
    return {"Authorization": f"Bearer {tokens['access_token']}"}


async def test_admin_lists_roles_and_departments(
    client,
    admin_credentials,
    seeded_users,
):
    headers = await _headers(client, admin_credentials)

    roles_response = await client.get("/api/v1/admin/roles", headers=headers)
    assert roles_response.status_code == 200
    roles = roles_response.json()["data"]
    assert {item["role_code"] for item in roles} == {
        "REQUESTER",
        "PROCESSOR",
        "ADMIN",
    }

    departments_response = await client.get(
        "/api/v1/admin/departments",
        headers=headers,
    )
    assert departments_response.status_code == 200
    departments = departments_response.json()["data"]
    assert departments[0]["department_id"] == seeded_users["department_id"]


async def test_requester_cannot_list_roles(client, credentials):
    response = await client.get(
        "/api/v1/admin/roles",
        headers=await _headers(client, credentials),
    )

    assert response.status_code == 403
    assert response.json()["code"] == "FORBIDDEN_ACTION"


async def test_admin_assigns_role_and_records_actor(
    client,
    admin_credentials,
    seeded_users,
    session_factory,
):
    response = await client.put(
        "/api/v1/admin/users/"
        f"{seeded_users['active_user_id']}/roles/{seeded_users['processor_role_id']}",
        headers=await _headers(client, admin_credentials),
    )

    assert response.status_code == 200
    role_codes = {item["role_code"] for item in response.json()["data"]["roles"]}
    assert role_codes == {"REQUESTER", "PROCESSOR"}

    async with session_factory() as session:
        assignment = await session.get(
            UserRole,
            (
                seeded_users["active_user_id"],
                seeded_users["processor_role_id"],
            ),
        )
        assert assignment is not None
        assert assignment.assigned_by == seeded_users["admin_user_id"]


async def test_duplicate_role_assignment_is_rejected(
    client,
    admin_credentials,
    seeded_users,
):
    response = await client.put(
        "/api/v1/admin/users/"
        f"{seeded_users['active_user_id']}/roles/{seeded_users['requester_role_id']}",
        headers=await _headers(client, admin_credentials),
    )

    assert response.status_code == 409
    assert response.json()["code"] == "ROLE_ALREADY_ASSIGNED"


async def test_admin_removes_role_and_missing_assignment_returns_404(
    client,
    admin_credentials,
    seeded_users,
):
    headers = await _headers(client, admin_credentials)
    endpoint = (
        "/api/v1/admin/users/"
        f"{seeded_users['active_user_id']}/roles/{seeded_users['processor_role_id']}"
    )

    assigned = await client.put(endpoint, headers=headers)
    assert assigned.status_code == 200

    removed = await client.delete(endpoint, headers=headers)
    assert removed.status_code == 204
    assert removed.content == b""

    missing = await client.delete(endpoint, headers=headers)
    assert missing.status_code == 404
    assert missing.json()["code"] == "ROLE_ASSIGNMENT_NOT_FOUND"


async def test_last_admin_role_cannot_be_removed(
    client,
    admin_credentials,
    seeded_users,
):
    response = await client.delete(
        "/api/v1/admin/users/"
        f"{seeded_users['admin_user_id']}/roles/{seeded_users['admin_role_id']}",
        headers=await _headers(client, admin_credentials),
    )

    assert response.status_code == 409
    assert response.json()["code"] == "LAST_ADMIN_ROLE_FORBIDDEN"


async def test_role_change_affects_existing_access_token_immediately(
    client,
    credentials,
    admin_credentials,
    seeded_users,
):
    requester_headers = await _headers(client, credentials)
    admin_headers = await _headers(client, admin_credentials)
    endpoint = (
        "/api/v1/admin/users/"
        f"{seeded_users['active_user_id']}/roles/{seeded_users['admin_role_id']}"
    )

    before = await client.get("/api/v1/admin/roles", headers=requester_headers)
    assert before.status_code == 403

    assigned = await client.put(endpoint, headers=admin_headers)
    assert assigned.status_code == 200

    after_assignment = await client.get(
        "/api/v1/admin/roles",
        headers=requester_headers,
    )
    assert after_assignment.status_code == 200

    removed = await client.delete(endpoint, headers=admin_headers)
    assert removed.status_code == 204

    after_removal = await client.get(
        "/api/v1/admin/roles",
        headers=requester_headers,
    )
    assert after_removal.status_code == 403
    assert after_removal.json()["code"] == "FORBIDDEN_ACTION"
