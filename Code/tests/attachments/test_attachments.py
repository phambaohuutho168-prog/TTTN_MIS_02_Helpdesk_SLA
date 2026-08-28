from pathlib import Path

from sqlalchemy import select

from app.core.config import settings
from app.models.attachment import Attachment
from app.models.comment import Comment
from app.models.ticket import Ticket
from app.models.ticket_status import TicketStatus
from tests.conftest import login_client


PDF_BYTES = b"%PDF-1.7\n% Helpdesk evidence\n%%EOF\n"


def _ticket_payload(seeded_users):
    return {
        "title": "Không truy cập được hệ thống",
        "description": "Người dùng không thể đăng nhập vào hệ thống nội bộ.",
        "category_id": seeded_users["active_category_id"],
        "priority_id": seeded_users["active_priority_id"],
    }


async def _headers(client, credentials):
    tokens = await login_client(client, credentials)
    return {"Authorization": f"Bearer {tokens['access_token']}"}


async def _create_ticket(client, credentials, seeded_users):
    response = await client.post(
        "/api/v1/tickets",
        json=_ticket_payload(seeded_users),
        headers=await _headers(client, credentials),
    )
    assert response.status_code == 201, response.text
    return response.json()["data"]


async def _upload_pdf(client, headers, ticket_id, *, filename="evidence.pdf"):
    return await client.post(
        f"/api/v1/tickets/{ticket_id}/attachments",
        files={"file": (filename, PDF_BYTES, "application/pdf")},
        headers=headers,
    )


async def test_owner_uploads_and_downloads_attachment(
    client,
    credentials,
    seeded_users,
    session_factory,
):
    headers = await _headers(client, credentials)
    ticket = await _create_ticket(client, credentials, seeded_users)

    uploaded = await _upload_pdf(client, headers, ticket["ticket_id"])

    assert uploaded.status_code == 201, uploaded.text
    body = uploaded.json()
    assert body["success"] is True
    assert body["code"] == "ATTACHMENT_CREATED"
    attachment = body["data"]
    assert attachment["ticket_id"] == ticket["ticket_id"]
    assert attachment["comment_id"] is None
    assert attachment["file_name"] == "evidence.pdf"
    assert attachment["mime_type"] == "application/pdf"
    assert attachment["file_size"] == len(PDF_BYTES)
    assert attachment["uploaded_by"] == seeded_users["active_user_id"]
    assert "storage_path" not in attachment

    async with session_factory() as session:
        stored = await session.get(Attachment, attachment["attachment_id"])
        assert stored is not None
        assert stored.storage_path != stored.file_name
        stored_path = Path(settings.ATTACHMENT_STORAGE_DIR) / stored.storage_path
        assert stored_path.read_bytes() == PDF_BYTES

    downloaded = await client.get(
        f"/api/v1/attachments/{attachment['attachment_id']}/download",
        headers=headers,
    )
    assert downloaded.status_code == 200
    assert downloaded.content == PDF_BYTES
    assert downloaded.headers["content-type"] == "application/pdf"
    assert "evidence.pdf" in downloaded.headers["content-disposition"]


async def test_admin_can_download_requester_attachment(
    client,
    credentials,
    admin_credentials,
    seeded_users,
):
    ticket = await _create_ticket(client, credentials, seeded_users)
    owner_headers = await _headers(client, credentials)
    uploaded = await _upload_pdf(client, owner_headers, ticket["ticket_id"])
    attachment_id = uploaded.json()["data"]["attachment_id"]

    response = await client.get(
        f"/api/v1/attachments/{attachment_id}/download",
        headers=await _headers(client, admin_credentials),
    )

    assert response.status_code == 200
    assert response.content == PDF_BYTES


async def test_unassigned_processor_cannot_download_attachment(
    client,
    credentials,
    processor_credentials,
    seeded_users,
):
    ticket = await _create_ticket(client, credentials, seeded_users)
    uploaded = await _upload_pdf(
        client,
        await _headers(client, credentials),
        ticket["ticket_id"],
    )
    attachment_id = uploaded.json()["data"]["attachment_id"]

    response = await client.get(
        f"/api/v1/attachments/{attachment_id}/download",
        headers=await _headers(client, processor_credentials),
    )

    assert response.status_code == 403
    assert response.json()["code"] == "TICKET_ACCESS_DENIED"
    assert "file_name" not in response.text


async def test_upload_rejects_extension_declared_mime_and_fake_content(
    client,
    credentials,
    seeded_users,
    session_factory,
):
    ticket = await _create_ticket(client, credentials, seeded_users)
    headers = await _headers(client, credentials)
    cases = [
        ("malware.exe", b"MZ", "application/octet-stream"),
        ("evidence.pdf", PDF_BYTES, "text/plain"),
        ("fake.pdf", b"this is not a pdf", "application/pdf"),
        ("empty.pdf", b"", "application/pdf"),
    ]

    for filename, content, content_type in cases:
        response = await client.post(
            f"/api/v1/tickets/{ticket['ticket_id']}/attachments",
            files={"file": (filename, content, content_type)},
            headers=headers,
        )
        assert response.status_code == 415, response.text
        assert response.json()["code"] == "ATTACHMENT_TYPE_NOT_ALLOWED"

    async with session_factory() as session:
        rows = (await session.execute(select(Attachment))).scalars().all()
        assert rows == []
    storage = Path(settings.ATTACHMENT_STORAGE_DIR)
    assert not storage.exists() or list(storage.rglob("*")) == []


async def test_upload_rejects_file_over_configured_size(
    client,
    credentials,
    seeded_users,
    session_factory,
    monkeypatch,
):
    monkeypatch.setattr(settings, "MAX_ATTACHMENT_SIZE_MB", 1)
    ticket = await _create_ticket(client, credentials, seeded_users)

    response = await client.post(
        f"/api/v1/tickets/{ticket['ticket_id']}/attachments",
        files={
            "file": (
                "large.pdf",
                b"%PDF-" + b"x" * (1024 * 1024),
                "application/pdf",
            )
        },
        headers=await _headers(client, credentials),
    )

    assert response.status_code == 413
    assert response.json()["code"] == "ATTACHMENT_SIZE_EXCEEDED"
    async with session_factory() as session:
        assert (await session.execute(select(Attachment))).scalars().all() == []


async def test_path_traversal_filename_is_never_used_as_storage_path(
    client,
    credentials,
    seeded_users,
    session_factory,
):
    ticket = await _create_ticket(client, credentials, seeded_users)
    response = await _upload_pdf(
        client,
        await _headers(client, credentials),
        ticket["ticket_id"],
        filename="../../evidence.pdf",
    )

    assert response.status_code == 201
    data = response.json()["data"]
    assert data["file_name"] == "evidence.pdf"
    async with session_factory() as session:
        stored = await session.get(Attachment, data["attachment_id"])
        assert stored is not None
        assert ".." not in stored.storage_path
        resolved = (Path(settings.ATTACHMENT_STORAGE_DIR) / stored.storage_path).resolve()
        resolved.relative_to(Path(settings.ATTACHMENT_STORAGE_DIR).resolve())


async def test_comment_must_belong_to_same_ticket(
    client,
    credentials,
    seeded_users,
    session_factory,
):
    first = await _create_ticket(client, credentials, seeded_users)
    second = await _create_ticket(client, credentials, seeded_users)
    async with session_factory() as session:
        comment = Comment(
            ticket_id=second["ticket_id"],
            author_id=seeded_users["active_user_id"],
            content="Minh chứng của ticket khác",
            visibility="PUBLIC",
            comment_type="REPLY",
        )
        session.add(comment)
        await session.commit()
        comment_id = comment.comment_id

    response = await client.post(
        f"/api/v1/tickets/{first['ticket_id']}/attachments",
        data={"comment_id": str(comment_id)},
        files={"file": ("evidence.pdf", PDF_BYTES, "application/pdf")},
        headers=await _headers(client, credentials),
    )

    assert response.status_code == 409
    assert response.json()["code"] == "COMMENT_TICKET_MISMATCH"


async def test_requester_cannot_upload_to_internal_comment(
    client,
    credentials,
    seeded_users,
    session_factory,
):
    ticket = await _create_ticket(client, credentials, seeded_users)
    async with session_factory() as session:
        comment = Comment(
            ticket_id=ticket["ticket_id"],
            author_id=seeded_users["admin_user_id"],
            content="Ghi chú nội bộ",
            visibility="INTERNAL",
            comment_type="SYSTEM_NOTE",
        )
        session.add(comment)
        await session.commit()
        comment_id = comment.comment_id

    response = await client.post(
        f"/api/v1/tickets/{ticket['ticket_id']}/attachments",
        data={"comment_id": str(comment_id)},
        files={"file": ("evidence.pdf", PDF_BYTES, "application/pdf")},
        headers=await _headers(client, credentials),
    )

    assert response.status_code == 403
    assert response.json()["code"] == "TICKET_ACCESS_DENIED"


async def test_terminal_ticket_rejects_new_attachment(
    client,
    credentials,
    seeded_users,
    session_factory,
):
    ticket = await _create_ticket(client, credentials, seeded_users)
    async with session_factory() as session:
        session.add(
            TicketStatus(
                status_code="CLOSED",
                status_name="Đã đóng",
                is_terminal=True,
                description="Ticket đã kết thúc",
            )
        )
        stored_ticket = await session.get(Ticket, ticket["ticket_id"])
        stored_ticket.current_status_code = "CLOSED"
        await session.commit()

    response = await _upload_pdf(
        client,
        await _headers(client, credentials),
        ticket["ticket_id"],
    )

    assert response.status_code == 409
    assert response.json()["code"] == "TICKET_ALREADY_TERMINAL"


async def test_uploader_can_delete_and_object_is_removed(
    client,
    credentials,
    seeded_users,
    session_factory,
):
    ticket = await _create_ticket(client, credentials, seeded_users)
    headers = await _headers(client, credentials)
    uploaded = await _upload_pdf(client, headers, ticket["ticket_id"])
    attachment_id = uploaded.json()["data"]["attachment_id"]
    async with session_factory() as session:
        attachment = await session.get(Attachment, attachment_id)
        path = Path(settings.ATTACHMENT_STORAGE_DIR) / attachment.storage_path
        assert path.is_file()

    response = await client.delete(
        f"/api/v1/attachments/{attachment_id}",
        headers=headers,
    )

    assert response.status_code == 204
    assert response.content == b""
    assert not path.exists()
    async with session_factory() as session:
        assert await session.get(Attachment, attachment_id) is None


async def test_missing_attachment_returns_not_found(
    client,
    credentials,
):
    response = await client.get(
        "/api/v1/attachments/999999/download",
        headers=await _headers(client, credentials),
    )

    assert response.status_code == 404
    assert response.json()["code"] == "ATTACHMENT_NOT_FOUND"


async def test_non_owner_cannot_delete_attachment(
    client,
    credentials,
    processor_credentials,
    seeded_users,
    session_factory,
):
    ticket = await _create_ticket(client, credentials, seeded_users)
    uploaded = await _upload_pdf(
        client,
        await _headers(client, credentials),
        ticket["ticket_id"],
    )
    attachment_id = uploaded.json()["data"]["attachment_id"]

    response = await client.delete(
        f"/api/v1/attachments/{attachment_id}",
        headers=await _headers(client, processor_credentials),
    )

    assert response.status_code == 403
    assert response.json()["code"] == "ATTACHMENT_DELETE_FORBIDDEN"
    async with session_factory() as session:
        assert await session.get(Attachment, attachment_id) is not None
