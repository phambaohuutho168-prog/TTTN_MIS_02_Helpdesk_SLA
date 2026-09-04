from datetime import datetime, timezone

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.core.rbac import RoleCode
from app.models.rating import Rating
from app.models.user import User
from app.repositories import audit_repository, rating_repository
from app.schemas.rating import RatingCreateRequest, RatingResponse
from app.schemas.ticket import TicketUserBrief
from app.services import ticket_detail_service


RATABLE_STATUSES = frozenset({"RESOLVED", "CLOSED"})


def _response(rating: Rating) -> RatingResponse:
    return RatingResponse(
        rating_id=rating.rating_id,
        ticket_id=rating.ticket_id,
        rated_by=TicketUserBrief.model_validate(rating.rater),
        score=rating.score,
        comment=rating.comment,
        created_at=rating.created_at,
    )


async def create_rating(
    session: AsyncSession,
    *,
    ticket_id: int,
    actor: User,
    payload: RatingCreateRequest,
    ip_address: str | None,
) -> RatingResponse:
    if RoleCode.REQUESTER.value not in actor.role_codes:
        raise AppError(
            409,
            "RATING_NOT_ALLOWED",
            "Chỉ Requester mới được gửi đánh giá mức hài lòng.",
        )
    ticket = await rating_repository.get_ticket_for_rating(
        session,
        ticket_id=ticket_id,
    )
    if ticket is None:
        raise AppError(404, "TICKET_NOT_FOUND", "Không tìm thấy ticket.")
    if ticket.requester_id != actor.user_id:
        raise AppError(
            403,
            "TICKET_ACCESS_DENIED",
            "Chỉ người gửi ticket mới được đánh giá mức hài lòng.",
        )
    if ticket.current_status_code not in RATABLE_STATUSES:
        raise AppError(
            409,
            "RATING_NOT_ALLOWED",
            "Chỉ có thể đánh giá ticket ở trạng thái RESOLVED "
            "hoặc CLOSED.",
        )
    if ticket.rating is not None:
        raise AppError(
            409,
            "DUPLICATE_RATING",
            "Ticket này đã được đánh giá mức hài lòng.",
        )

    now = datetime.now(timezone.utc)
    try:
        rating = await rating_repository.create_rating_record(
            session,
            ticket_id=ticket.ticket_id,
            rated_by=actor.user_id,
            score=payload.score,
            comment=payload.comment,
            created_at=now,
        )
        await audit_repository.append_audit(
            session,
            actor_user_id=actor.user_id,
            ticket_id=ticket.ticket_id,
            action_code="TICKET_RATED",
            entity_type="RATING",
            entity_id=rating.rating_id,
            new_value={
                "score": rating.score,
                "comment": rating.comment,
                "rated_by": actor.user_id,
            },
            ip_address=ip_address,
        )
        rating_id = rating.rating_id
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise AppError(
            409,
            "DUPLICATE_RATING",
            "Ticket này đã được đánh giá mức hài lòng.",
        ) from exc

    persisted = await rating_repository.get_rating_by_id(session, rating_id)
    if persisted is None:  # pragma: no cover - defensive consistency check
        raise AppError(
            500,
            "RATING_PERSISTENCE_ERROR",
            "Không thể đọc lại đánh giá.",
        )
    return _response(persisted)


async def get_rating(
    session: AsyncSession,
    *,
    ticket_id: int,
    current_user: User,
) -> RatingResponse:
    await ticket_detail_service.load_scoped_ticket(
        session,
        ticket_id=ticket_id,
        current_user=current_user,
    )
    rating = await rating_repository.get_rating_by_ticket_id(session, ticket_id)
    if rating is None:
        raise AppError(
            404,
            "RATING_NOT_FOUND",
            "Ticket chưa có đánh giá mức hài lòng.",
        )
    return _response(rating)
