"""CV050 - Security Test cho RBAC, UI gate và attachment access control."""

from pathlib import Path

import pytest
from sqlalchemy import func, select

from app.core.config import settings
from app.core.security import hash_password
from app.models.attachment import Attachment
from app.models.role import Role
from app.models.ticket_assignment import TicketAssignment
from app.models.ticket_status import TicketStatus
from app.models.user import User
from app.models.user_role import UserRole
from tests.conftest import login_client


PDF_BYTES = b"%PDF-1.7\n% CV050 confidential attachment\n%%EOF\n"
ATTACHMENT_NAME = "cv050-security-evidence.pdf"


async def _auth_headers(client, credentials, **extra_headers):
    tokens = await login_client(client, credentials)
    return {
        "Authorization": f"Bearer {tokens['access_token']}",
        **extra_headers,
    }


def _ticket_payload(seeded_users, title):
    return {
        "title": title,
        "description": "Ticket dùng để kiểm thử phân quyền và truy cập trái phép.",
        "category_id": seeded_users["active_category_id"],
        "priority_id": seeded_users["active_priority_id"],
    }


@pytest.fixture
async def cv050_security_configuration(session_factory):
    password = "CorrectPassword123!"
    async with session_factory() as session:
        other_requester = User(
            email="cv050.other.requester@example.com",
            full_name="CV050 Other Requester",
            password_hash=hash_password(password),
            is_active=True,
        )
        session.add_all(
            [
                other_requester,
                TicketStatus(
                    status_code="ASSIGNED",
                    status_name="Đã phân công",
                    is_terminal=False,
                ),
            ]
        )
        await session.flush()
        requester_role_id = await session.scalar(
            select(Role.role_id).where(Role.role_code == "REQUESTER")
        )
        session.add(
            UserRole(
                user_id=other_requester.user_id,
                role_id=requester_role_id,
            )
        )
        await session.commit()
    return {
        "other_requester_id": other_requester.user_id,
        "other_requester_credentials": {
            "email": other_requester.email,
            "password": password,
        },
    }


@pytest.mark.business_rule
async def test_cv050_api_and_ui_role_boundaries(
    client,
    credentials,
    admin_credentials,
    processor_credentials,
    seeded_users,
    cv050_security_configuration,
):
    requester_headers = await _auth_headers(client, credentials)
    processor_headers = await _auth_headers(client, processor_credentials)
    admin_headers = await _auth_headers(client, admin_credentials)

    # SEC-FT-01 - Endpoint bảo vệ phải trả 401 khi chưa xác thực.
    unauthenticated = await client.get("/api/v1/admin/users?page=1&page_size=20")
    assert unauthenticated.status_code == 401
    assert unauthenticated.json()["code"] == "AUTH_TOKEN_MISSING"

    # SEC-FT-02 - Requester và Processor không được truy cập quản trị người dùng.
    requester_admin = await client.get(
        "/api/v1/admin/users?page=1&page_size=20",
        headers=requester_headers,
    )
    processor_admin = await client.get(
        "/api/v1/admin/users?page=1&page_size=20",
        headers=processor_headers,
    )
    assert requester_admin.status_code == 403
    assert processor_admin.status_code == 403
    assert requester_admin.json()["code"] == "FORBIDDEN_ACTION"
    assert processor_admin.json()["code"] == "FORBIDDEN_ACTION"

    # Header vai trò do client tự gửi không thể nâng quyền Requester thành Admin.
    spoofed_headers = await _auth_headers(
        client,
        credentials,
        **{"X-User-Role": "ADMIN"},
    )
    spoofed = await client.get(
        "/api/v1/admin/users?page=1&page_size=20",
        headers=spoofed_headers,
    )
    assert spoofed.status_code == 403
    assert spoofed.json()["code"] == "FORBIDDEN_ACTION"

    # Admin hợp lệ vẫn truy cập được chức năng quản trị.
    allowed_admin = await client.get(
        "/api/v1/admin/users?page=1&page_size=20",
        headers=admin_headers,
    )
    assert allowed_admin.status_code == 200, allowed_admin.text

    # SEC-FT-03 - Dashboard API chỉ dành cho Processor/Admin, chặn Requester.
    requester_dashboard = await client.get(
        "/api/v1/dashboard/overview",
        headers=requester_headers,
    )
    processor_dashboard = await client.get(
        "/api/v1/dashboard/overview",
        headers=processor_headers,
    )
    admin_dashboard = await client.get(
        "/api/v1/dashboard/overview",
        headers=admin_headers,
    )
    assert requester_dashboard.status_code == 403
    assert requester_dashboard.json()["code"] == "FORBIDDEN_ACTION"
    assert processor_dashboard.status_code == 200, processor_dashboard.text
    assert admin_dashboard.status_code == 200, admin_dashboard.text

    # SEC-FT-04 - Chỉ Requester được tạo ticket.
    payload = _ticket_payload(seeded_users, "CV050 - Kiểm thử ranh giới vai trò")
    processor_create = await client.post(
        "/api/v1/tickets",
        headers=processor_headers,
        json=payload,
    )
    admin_create = await client.post(
        "/api/v1/tickets",
        headers=admin_headers,
        json=payload,
    )
    assert processor_create.status_code == 403
    assert admin_create.status_code == 403
    assert processor_create.json()["code"] == "FORBIDDEN_ACTION"
    assert admin_create.json()["code"] == "FORBIDDEN_ACTION"

    created = await client.post(
        "/api/v1/tickets",
        headers=requester_headers,
        json=payload,
    )
    assert created.status_code == 201, created.text
    ticket_id = created.json()["data"]["ticket_id"]

    # Chỉ Admin được phân công; Requester và Processor đều bị chặn.
    assignment_payload = {
        "assignee_id": seeded_users["processor_user_id"],
        "reason": "Phân công kiểm thử security",
    }
    requester_assign = await client.put(
        f"/api/v1/tickets/{ticket_id}/assignment",
        headers=requester_headers,
        json=assignment_payload,
    )
    processor_assign = await client.put(
        f"/api/v1/tickets/{ticket_id}/assignment",
        headers=processor_headers,
        json=assignment_payload,
    )
    assert requester_assign.status_code == 403
    assert processor_assign.status_code == 403

    admin_assign = await client.put(
        f"/api/v1/tickets/{ticket_id}/assignment",
        headers=admin_headers,
        json=assignment_payload,
    )
    assert admin_assign.status_code == 200, admin_assign.text

    # SEC-FT-05 - UI ẩn dashboard mặc định và có role gate rõ ràng.
    dashboard_html = (await client.get("/dashboard")).text
    dashboard_script = (await client.get("/static/dashboard.js")).text
    assert 'id="dashboard-shell" class="app-shell" hidden' in dashboard_html
    assert 'id="access-denied-state"' in dashboard_html
    assert 'role="alert" hidden' in dashboard_html
    assert 'if (roles.has("ADMIN")) return "ADMIN";' in dashboard_script
    assert 'if (roles.has("PROCESSOR")) return "PROCESSOR";' in dashboard_script
    assert "if (!dashboardRole())" in dashboard_script
    assert "clearSession();" in dashboard_script
    assert "Tài khoản không có quyền xem dashboard." in dashboard_script
    assert 'if (dashboardRole() === "ADMIN")' in dashboard_script
    assert "/admin/users?role_code=PROCESSOR" in dashboard_script

@pytest.mark.business_rule
async def test_cv050_attachment_cannot_be_accessed_illegally(
    client,
    credentials,
    admin_credentials,
    processor_credentials,
    seeded_users,
    session_factory,
    cv050_security_configuration,
):
    owner_headers = await _auth_headers(client, credentials)
    processor_headers = await _auth_headers(client, processor_credentials)
    admin_headers = await _auth_headers(client, admin_credentials)
    foreign_headers = await _auth_headers(
        client,
        cv050_security_configuration["other_requester_credentials"],
    )

    created = await client.post(
        "/api/v1/tickets",
        headers=owner_headers,
        json=_ticket_payload(seeded_users, "CV050 - Attachment cần được bảo vệ"),
    )
    assert created.status_code == 201, created.text
    ticket_id = created.json()["data"]["ticket_id"]

    uploaded = await client.post(
        f"/api/v1/tickets/{ticket_id}/attachments",
        headers=owner_headers,
        files={
            "file": (ATTACHMENT_NAME, PDF_BYTES, "application/pdf"),
        },
    )
    assert uploaded.status_code == 201, uploaded.text
    attachment_data = uploaded.json()["data"]
    attachment_id = attachment_data["attachment_id"]
    assert "storage_path" not in attachment_data

    async with session_factory() as session:
        stored = await session.get(Attachment, attachment_id)
        stored_path = Path(settings.ATTACHMENT_STORAGE_DIR) / stored.storage_path
        assert stored_path.is_file()
        assert stored_path.read_bytes() == PDF_BYTES

    # SEC-FT-06 - Không đăng nhập, Requester khác và Processor chưa phân công
    # đều không tải được file bằng cách đoán attachment_id.
    download_url = f"/api/v1/attachments/{attachment_id}/download"
    unauthenticated = await client.get(download_url)
    foreign = await client.get(download_url, headers=foreign_headers)
    unassigned_processor = await client.get(
        download_url,
        headers=processor_headers,
    )
    assert unauthenticated.status_code == 401
    assert foreign.status_code == 403
    assert unassigned_processor.status_code == 403
    assert foreign.json()["code"] == "TICKET_ACCESS_DENIED"
    assert unassigned_processor.json()["code"] == "TICKET_ACCESS_DENIED"

    # Giả mạo header Admin vẫn không vượt qua quyền lấy từ database.
    spoofed_foreign_headers = {
        **foreign_headers,
        "X-User-Role": "ADMIN",
    }
    spoofed = await client.get(download_url, headers=spoofed_foreign_headers)
    assert spoofed.status_code == 403
    assert spoofed.json()["code"] == "TICKET_ACCESS_DENIED"

    for denied in (foreign, unassigned_processor, spoofed):
        assert ATTACHMENT_NAME not in denied.text
        assert "storage_path" not in denied.text
        assert "CV050 confidential attachment" not in denied.text

    # Người ngoài phạm vi cũng không thể upload thêm file vào ticket.
    count_before = None
    async with session_factory() as session:
        count_before = await session.scalar(
            select(func.count(Attachment.attachment_id)).where(
                Attachment.ticket_id == ticket_id
            )
        )
    foreign_upload = await client.post(
        f"/api/v1/tickets/{ticket_id}/attachments",
        headers=foreign_headers,
        files={"file": ("foreign.pdf", PDF_BYTES, "application/pdf")},
    )
    assert foreign_upload.status_code == 403
    assert foreign_upload.json()["code"] == "TICKET_ACCESS_DENIED"
    async with session_factory() as session:
        count_after = await session.scalar(
            select(func.count(Attachment.attachment_id)).where(
                Attachment.ticket_id == ticket_id
            )
        )
    assert count_after == count_before == 1

    # Processor chưa được phân công không được xóa file; bản ghi và object còn nguyên.
    denied_delete = await client.delete(
        f"/api/v1/attachments/{attachment_id}",
        headers=processor_headers,
    )
    assert denied_delete.status_code == 403
    assert denied_delete.json()["code"] == "ATTACHMENT_DELETE_FORBIDDEN"
    async with session_factory() as session:
        assert await session.get(Attachment, attachment_id) is not None
    assert stored_path.is_file()

    # SEC-FT-07 - Sau khi Admin phân công, Processor được tải nhưng không được xóa.
    assigned = await client.put(
        f"/api/v1/tickets/{ticket_id}/assignment",
        headers=admin_headers,
        json={
            "assignee_id": seeded_users["processor_user_id"],
            "reason": "Phân công để xác minh phạm vi attachment",
        },
    )
    assert assigned.status_code == 200, assigned.text

    assigned_processor_download = await client.get(
        download_url,
        headers=processor_headers,
    )
    admin_download = await client.get(download_url, headers=admin_headers)
    assert assigned_processor_download.status_code == 200
    assert admin_download.status_code == 200
    assert assigned_processor_download.content == PDF_BYTES
    assert admin_download.content == PDF_BYTES

    assigned_processor_delete = await client.delete(
        f"/api/v1/attachments/{attachment_id}",
        headers=processor_headers,
    )
    assert assigned_processor_delete.status_code == 403
    assert assigned_processor_delete.json()["code"] == "ATTACHMENT_DELETE_FORBIDDEN"
    async with session_factory() as session:
        assert await session.get(Attachment, attachment_id) is not None
    assert stored_path.is_file()
