from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from app.models.audit_log import AuditLog
from app.models.rating import Rating
from app.models.ticket import Ticket
from app.models.ticket_assignment import TicketAssignment
from app.models.ticket_status import TicketStatus
from tests.conftest import login_client


async def _headers(client, credentials):
    tokens = await login_client(client, credentials)
    return {"Authorization": f"Bearer {tokens['access_token']}"}


@pytest.fixture
async def rating_data(session_factory, seeded_users):
    now = datetime.now(timezone.utc).replace(microsecond=0)
    async with session_factory() as session:
        session.add_all(
            [
                TicketStatus(
                    status_code="IN_PROGRESS",
                    status_name="Đang xử lý",
                    is_terminal=False,
                ),
                TicketStatus(
                    status_code="RESOLVED",
                    status_name="Đã xử lý",
                    is_terminal=False,
                ),
                TicketStatus(
                    status_code="CLOSED",
                    status_name="Đã đóng",
                    is_terminal=True,
                ),
            ]
        )

        def make_ticket(
            key: str,
            status_code: str,
            *,
            requester_id: int | None = None,
        ) -> Ticket:
            is_closed = status_code == "CLOSED"
            return Ticket(
                ticket_code=f"TK-CV041-{key}",
                requester_id=requester_id or seeded_users["active_user_id"],
                category_id=seeded_users["active_category_id"],
                priority_id=seeded_users["active_priority_id"],
                current_status_code=status_code,
                title=f"CV041 {key}",
                description=(
                    "Kiểm thử đánh giá mức hài lòng của người gửi."
                ),
                closed_at=now - timedelta(hours=1) if is_closed else None,
                closed_by=(seeded_users["active_user_id"] if is_closed else None),
                created_at=now - timedelta(days=2),
                updated_at=now - timedelta(hours=1),
            )

        tickets = {
            "closed": make_ticket("CLOSED", "CLOSED"),
            "resolved": make_ticket("RESOLVED", "RESOLVED"),
            "open": make_ticket("OPEN", "IN_PROGRESS"),
            "foreign": make_ticket(
                "FOREIGN",
                "CLOSED",
                requester_id=seeded_users["inactive_user_id"],
            ),
            "assigned": make_ticket("ASSIGNED", "RESOLVED"),
            "unrated": make_ticket("UNRATED", "CLOSED"),
        }
        session.add_all(tickets.values())
        await session.flush()

        assigned = TicketAssignment(
            ticket_id=tickets["assigned"].ticket_id,
            assignee_id=seeded_users["processor_user_id"],
            assigned_by=seeded_users["admin_user_id"],
            assigned_at=now - timedelta(hours=2),
            is_current=True,
            reason="Phân công để kiểm thử quyền xem đánh giá.",
        )
        session.add(assigned)
        session.add_all(
            [
                Rating(
                    ticket_id=tickets["resolved"].ticket_id,
                    rated_by=seeded_users["active_user_id"],
                    score=4,
                    comment="Xử lý nhanh và rõ ràng.",
                    created_at=now,
                ),
                Rating(
                    ticket_id=tickets["assigned"].ticket_id,
                    rated_by=seeded_users["active_user_id"],
                    score=5,
                    comment=None,
                    created_at=now,
                ),
            ]
        )
        await session.commit()
        return {key: ticket.ticket_id for key, ticket in tickets.items()}


async def test_rating_requires_authentication(client, rating_data):
    response = await client.post(
        f"/api/v1/tickets/{rating_data['closed']}/rating",
        json={"score": 5},
    )
    assert response.status_code == 401


async def test_owner_rates_closed_ticket_and_audit_is_recorded(
    client,
    credentials,
    seeded_users,
    session_factory,
    rating_data,
):
    response = await client.post(
        f"/api/v1/tickets/{rating_data['closed']}/rating",
        headers=await _headers(client, credentials),
        json={"score": 5, "comment": "  Hỗ trợ rất tốt.  "},
    )
    assert response.status_code == 201, response.text
    assert response.json()["code"] == "RATING_CREATED"
    data = response.json()["data"]
    assert data["ticket_id"] == rating_data["closed"]
    assert data["rated_by"]["user_id"] == seeded_users["active_user_id"]
    assert data["score"] == 5
    assert data["comment"] == "Hỗ trợ rất tốt."
    assert data["created_at"] is not None

    async with session_factory() as session:
        rating = (
            await session.execute(
                select(Rating).where(Rating.ticket_id == rating_data["closed"])
            )
        ).scalar_one()
        audit = (
            await session.execute(
                select(AuditLog).where(
                    AuditLog.ticket_id == rating_data["closed"],
                    AuditLog.action_code == "TICKET_RATED",
                )
            )
        ).scalar_one()
        assert rating.rated_by == seeded_users["active_user_id"]
        assert audit.entity_type == "RATING"
        assert audit.entity_id == rating.rating_id
        assert audit.new_value_json["score"] == 5


async def test_owner_may_rate_resolved_ticket(
    client,
    credentials,
    session_factory,
    rating_data,
):
    async with session_factory() as session:
        existing = (
            await session.execute(
                select(Rating).where(Rating.ticket_id == rating_data["resolved"])
            )
        ).scalar_one()
        await session.delete(existing)
        await session.commit()

    response = await client.post(
        f"/api/v1/tickets/{rating_data['resolved']}/rating",
        headers=await _headers(client, credentials),
        json={"score": 4},
    )
    assert response.status_code == 201, response.text
    assert response.json()["data"]["score"] == 4


async def test_owner_reads_existing_rating(client, credentials, rating_data):
    response = await client.get(
        f"/api/v1/tickets/{rating_data['resolved']}/rating",
        headers=await _headers(client, credentials),
    )
    assert response.status_code == 200, response.text
    assert response.json()["code"] == "RATING_RETRIEVED"
    assert response.json()["data"]["score"] == 4


async def test_admin_and_assigned_processor_can_read_rating(
    client,
    admin_credentials,
    processor_credentials,
    rating_data,
):
    url = f"/api/v1/tickets/{rating_data['assigned']}/rating"
    admin_response = await client.get(
        url,
        headers=await _headers(client, admin_credentials),
    )
    processor_response = await client.get(
        url,
        headers=await _headers(client, processor_credentials),
    )
    assert admin_response.status_code == 200
    assert processor_response.status_code == 200
    assert processor_response.json()["data"]["score"] == 5


async def test_foreign_requester_cannot_rate_ticket(
    client,
    credentials,
    rating_data,
):
    response = await client.post(
        f"/api/v1/tickets/{rating_data['foreign']}/rating",
        headers=await _headers(client, credentials),
        json={"score": 3},
    )
    assert response.status_code == 403
    assert response.json()["code"] == "TICKET_ACCESS_DENIED"


@pytest.mark.parametrize(
    "credential_fixture",
    ["processor_credentials", "admin_credentials"],
)
async def test_non_requester_roles_cannot_submit_rating(
    client,
    request,
    credential_fixture,
    rating_data,
):
    credentials = request.getfixturevalue(credential_fixture)
    response = await client.post(
        f"/api/v1/tickets/{rating_data['closed']}/rating",
        headers=await _headers(client, credentials),
        json={"score": 5},
    )
    assert response.status_code == 409
    assert response.json()["code"] == "RATING_NOT_ALLOWED"


async def test_rating_wrong_ticket_state_is_rejected(
    client,
    credentials,
    rating_data,
):
    response = await client.post(
        f"/api/v1/tickets/{rating_data['open']}/rating",
        headers=await _headers(client, credentials),
        json={"score": 4},
    )
    assert response.status_code == 409
    assert response.json()["code"] == "RATING_NOT_ALLOWED"


async def test_duplicate_rating_is_rejected_without_duplicate_audit(
    client,
    credentials,
    session_factory,
    rating_data,
):
    response = await client.post(
        f"/api/v1/tickets/{rating_data['resolved']}/rating",
        headers=await _headers(client, credentials),
        json={"score": 1, "comment": "Thử gửi lần hai."},
    )
    assert response.status_code == 409
    assert response.json()["code"] == "DUPLICATE_RATING"
    async with session_factory() as session:
        rating_count = await session.scalar(
            select(func.count(Rating.rating_id)).where(
                Rating.ticket_id == rating_data["resolved"]
            )
        )
        audit_count = await session.scalar(
            select(func.count(AuditLog.audit_id)).where(
                AuditLog.ticket_id == rating_data["resolved"],
                AuditLog.action_code == "TICKET_RATED",
            )
        )
        assert rating_count == 1
        assert audit_count == 0


@pytest.mark.parametrize("score", [0, 6])
async def test_score_outside_one_to_five_is_rejected(
    client,
    credentials,
    rating_data,
    score,
):
    response = await client.post(
        f"/api/v1/tickets/{rating_data['closed']}/rating",
        headers=await _headers(client, credentials),
        json={"score": score},
    )
    assert response.status_code == 422
    assert response.json()["code"] == "VALIDATION_ERROR"


async def test_comment_over_limit_is_rejected(client, credentials, rating_data):
    response = await client.post(
        f"/api/v1/tickets/{rating_data['closed']}/rating",
        headers=await _headers(client, credentials),
        json={"score": 5, "comment": "x" * 2_001},
    )
    assert response.status_code == 422


async def test_blank_optional_comment_is_saved_as_null(
    client,
    credentials,
    rating_data,
):
    response = await client.post(
        f"/api/v1/tickets/{rating_data['closed']}/rating",
        headers=await _headers(client, credentials),
        json={"score": 3, "comment": "   \n  "},
    )
    assert response.status_code == 201, response.text
    assert response.json()["data"]["comment"] is None


async def test_unrated_ticket_returns_rating_not_found(
    client,
    credentials,
    rating_data,
):
    response = await client.get(
        f"/api/v1/tickets/{rating_data['unrated']}/rating",
        headers=await _headers(client, credentials),
    )
    assert response.status_code == 404
    assert response.json()["code"] == "RATING_NOT_FOUND"


async def test_rating_read_obeys_ticket_scope(client, credentials, rating_data):
    response = await client.get(
        f"/api/v1/tickets/{rating_data['foreign']}/rating",
        headers=await _headers(client, credentials),
    )
    assert response.status_code == 403
    assert response.json()["code"] == "TICKET_ACCESS_DENIED"


async def test_database_rejects_invalid_score(
    session_factory,
    seeded_users,
    rating_data,
):
    async with session_factory() as session:
        session.add(
            Rating(
                ticket_id=rating_data["unrated"],
                rated_by=seeded_users["active_user_id"],
                score=0,
            )
        )
        with pytest.raises(IntegrityError):
            await session.flush()
