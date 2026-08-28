from sqlalchemy import select

from app.models.category import Category
from app.models.priority import Priority
from tests.conftest import login_client


async def _headers(client, credentials):
    tokens = await login_client(client, credentials)
    return {"Authorization": f"Bearer {tokens['access_token']}"}


async def test_authenticated_user_lists_only_active_categories_by_default(
    client,
    credentials,
):
    response = await client.get(
        "/api/v1/categories",
        headers=await _headers(client, credentials),
    )

    assert response.status_code == 200
    categories = response.json()["data"]
    assert [item["category_name"] for item in categories] == ["Phần mềm"]
    assert all(item["is_active"] for item in categories)


async def test_category_list_supports_search_and_inactive_filter(
    client,
    credentials,
):
    response = await client.get(
        "/api/v1/categories?q=ngừng&is_active=false",
        headers=await _headers(client, credentials),
    )

    assert response.status_code == 200
    assert [item["category_name"] for item in response.json()["data"]] == [
        "Danh mục ngừng dùng"
    ]


async def test_catalogs_require_authentication(client):
    for endpoint in (
        "/api/v1/categories",
        "/api/v1/priorities",
        "/api/v1/ticket-statuses",
    ):
        response = await client.get(endpoint)
        assert response.status_code == 401
        assert response.json()["code"] == "AUTH_TOKEN_MISSING"


async def test_authenticated_user_lists_active_priorities_in_level_order(
    client,
    credentials,
):
    response = await client.get(
        "/api/v1/priorities",
        headers=await _headers(client, credentials),
    )

    assert response.status_code == 200
    priorities = response.json()["data"]
    assert [item["priority_code"] for item in priorities] == ["P3"]


async def test_authenticated_user_lists_ticket_statuses(client, credentials):
    response = await client.get(
        "/api/v1/ticket-statuses",
        headers=await _headers(client, credentials),
    )

    assert response.status_code == 200
    assert response.json()["data"][0]["status_code"] == "NEW"


async def test_admin_creates_normalized_category(
    client,
    admin_credentials,
    session_factory,
):
    response = await client.post(
        "/api/v1/admin/categories",
        json={
            "category_name": "  Thiết   bị ngoại vi  ",
            "description": "  Máy in và máy quét.  ",
        },
        headers=await _headers(client, admin_credentials),
    )

    assert response.status_code == 201
    body = response.json()
    assert body["code"] == "CATEGORY_CREATED"
    assert body["data"]["category_name"] == "Thiết bị ngoại vi"
    async with session_factory() as session:
        category = (
            await session.execute(
                select(Category).where(
                    Category.category_name == "Thiết bị ngoại vi"
                )
            )
        ).scalar_one()
    assert category.description == "Máy in và máy quét."


async def test_duplicate_category_name_is_case_insensitive(
    client,
    admin_credentials,
):
    response = await client.post(
        "/api/v1/admin/categories",
        json={"category_name": "  PHẦN MỀM  "},
        headers=await _headers(client, admin_credentials),
    )

    assert response.status_code == 409
    assert response.json()["code"] == "CATEGORY_NAME_CONFLICT"


async def test_admin_updates_and_disables_category(
    client,
    admin_credentials,
    seeded_users,
):
    response = await client.patch(
        f"/api/v1/admin/categories/{seeded_users['active_category_id']}",
        json={"description": "Danh mục đã cập nhật", "is_active": False},
        headers=await _headers(client, admin_credentials),
    )

    assert response.status_code == 200
    category = response.json()["data"]
    assert category["description"] == "Danh mục đã cập nhật"
    assert category["is_active"] is False


async def test_empty_category_update_is_rejected(
    client,
    admin_credentials,
    seeded_users,
):
    response = await client.patch(
        f"/api/v1/admin/categories/{seeded_users['active_category_id']}",
        json={},
        headers=await _headers(client, admin_credentials),
    )

    assert response.status_code == 422
    assert response.json()["code"] == "VALIDATION_ERROR"


async def test_missing_category_returns_404(client, admin_credentials):
    response = await client.patch(
        "/api/v1/admin/categories/999999",
        json={"is_active": False},
        headers=await _headers(client, admin_credentials),
    )

    assert response.status_code == 404
    assert response.json()["code"] == "CATEGORY_NOT_FOUND"


async def test_requester_cannot_manage_catalogs(client, credentials):
    response = await client.post(
        "/api/v1/admin/categories",
        json={"category_name": "Không được tạo"},
        headers=await _headers(client, credentials),
    )

    assert response.status_code == 403
    assert response.json()["code"] == "FORBIDDEN_ACTION"


async def test_admin_creates_priority_and_normalizes_code(
    client,
    admin_credentials,
):
    response = await client.post(
        "/api/v1/admin/priorities",
        json={
            "priority_code": "p1",
            "priority_level": 1,
            "priority_name": "  Khẩn   cấp  ",
            "description": "Gián đoạn toàn hệ thống",
        },
        headers=await _headers(client, admin_credentials),
    )

    assert response.status_code == 201
    priority = response.json()["data"]
    assert priority["priority_code"] == "P1"
    assert priority["priority_level"] == 1
    assert priority["priority_name"] == "Khẩn cấp"


async def test_priority_code_conflict_is_rejected(
    client,
    admin_credentials,
):
    response = await client.post(
        "/api/v1/admin/priorities",
        json={
            "priority_code": "P3",
            "priority_level": 1,
            "priority_name": "Trùng mã",
        },
        headers=await _headers(client, admin_credentials),
    )

    assert response.status_code == 409
    assert response.json()["code"] == "PRIORITY_CODE_CONFLICT"


async def test_priority_level_conflict_is_rejected(
    client,
    admin_credentials,
):
    response = await client.post(
        "/api/v1/admin/priorities",
        json={
            "priority_code": "P2",
            "priority_level": 3,
            "priority_name": "Trùng thứ tự",
        },
        headers=await _headers(client, admin_credentials),
    )

    assert response.status_code == 409
    assert response.json()["code"] == "PRIORITY_LEVEL_CONFLICT"


async def test_invalid_priority_domain_is_rejected(
    client,
    admin_credentials,
):
    headers = await _headers(client, admin_credentials)
    invalid_payloads = [
        {"priority_code": "P5", "priority_level": 1, "priority_name": "Sai mã"},
        {"priority_code": "P1", "priority_level": 0, "priority_name": "Sai mức"},
        {"priority_code": "P1", "priority_level": 1, "priority_name": "   "},
    ]
    for payload in invalid_payloads:
        response = await client.post(
            "/api/v1/admin/priorities",
            json=payload,
            headers=headers,
        )
        assert response.status_code == 422
        assert response.json()["code"] == "VALIDATION_ERROR"


async def test_admin_updates_priority_without_changing_code_or_level(
    client,
    admin_credentials,
    seeded_users,
):
    response = await client.patch(
        f"/api/v1/admin/priorities/{seeded_users['active_priority_id']}",
        json={"priority_name": "  Bình   thường  ", "is_active": False},
        headers=await _headers(client, admin_credentials),
    )

    assert response.status_code == 200
    priority = response.json()["data"]
    assert priority["priority_code"] == "P3"
    assert priority["priority_level"] == 3
    assert priority["priority_name"] == "Bình thường"
    assert priority["is_active"] is False


async def test_priority_update_rejects_immutable_and_unknown_fields(
    client,
    admin_credentials,
    seeded_users,
):
    response = await client.patch(
        f"/api/v1/admin/priorities/{seeded_users['active_priority_id']}",
        json={"priority_code": "P1", "priority_level": 1},
        headers=await _headers(client, admin_credentials),
    )

    assert response.status_code == 422
    assert response.json()["code"] == "VALIDATION_ERROR"


async def test_missing_priority_returns_404(client, admin_credentials):
    response = await client.patch(
        "/api/v1/admin/priorities/999999",
        json={"is_active": False},
        headers=await _headers(client, admin_credentials),
    )

    assert response.status_code == 404
    assert response.json()["code"] == "PRIORITY_NOT_FOUND"
