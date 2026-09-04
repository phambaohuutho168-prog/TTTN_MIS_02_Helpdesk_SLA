from datetime import datetime

from sqlalchemy import Select, exists, false, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.audit_log import AuditLog
from app.models.category import Category
from app.models.comment import Comment
from app.models.priority import Priority
from app.models.sla_policy import SLAPolicy
from app.models.ticket import Ticket
from app.models.ticket_assignment import TicketAssignment
from app.models.ticket_resolution import TicketResolution
from app.models.ticket_sla import TicketSLA
from app.models.ticket_status import TicketStatus
from app.models.ticket_status_history import TicketStatusHistory
from app.models.user import User
from app.models.user_role import UserRole
from app.schemas.ticket import TicketListQuery


TICKET_LOAD_OPTIONS = (
    selectinload(Ticket.category),
    selectinload(Ticket.priority),
    selectinload(Ticket.current_status),
    selectinload(Ticket.requester)
    .selectinload(User.user_roles)
    .selectinload(UserRole.role),
    selectinload(
        Ticket.assignments.and_(TicketAssignment.is_current.is_(True))
    )
    .selectinload(TicketAssignment.assignee)
    .selectinload(User.user_roles)
    .selectinload(UserRole.role),
)

TICKET_DETAIL_LOAD_OPTIONS = (
    selectinload(Ticket.category),
    selectinload(Ticket.priority),
    selectinload(Ticket.current_status),
    selectinload(Ticket.requester)
    .selectinload(User.user_roles)
    .selectinload(UserRole.role),
    selectinload(Ticket.closer)
    .selectinload(User.user_roles)
    .selectinload(UserRole.role),
    selectinload(Ticket.attachments),
    selectinload(Ticket.assignments)
    .selectinload(TicketAssignment.assignee)
    .selectinload(User.user_roles)
    .selectinload(UserRole.role),
    selectinload(Ticket.assignments).selectinload(TicketAssignment.assigner),
    selectinload(Ticket.resolutions).selectinload(TicketResolution.resolver),
    selectinload(Ticket.sla_records).selectinload(TicketSLA.policy),
)


def _escape_like(value: str) -> str:
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def _list_conditions(
    query: TicketListQuery,
    *,
    current_user_id: int,
    role_codes: set[str],
):
    conditions = []
    if "ADMIN" not in role_codes:
        scope_conditions = []
        if "REQUESTER" in role_codes:
            scope_conditions.append(Ticket.requester_id == current_user_id)
        if "PROCESSOR" in role_codes:
            scope_conditions.append(
                exists().where(
                    TicketAssignment.ticket_id == Ticket.ticket_id,
                    TicketAssignment.assignee_id == current_user_id,
                    TicketAssignment.is_current.is_(True),
                )
            )
        conditions.append(or_(*scope_conditions) if scope_conditions else false())

    if query.status:
        conditions.append(Ticket.current_status_code.in_(query.status))
    if query.category_id is not None:
        conditions.append(Ticket.category_id == query.category_id)
    if query.priority_id is not None:
        conditions.append(Ticket.priority_id == query.priority_id)
    if query.requester_id is not None:
        conditions.append(Ticket.requester_id == query.requester_id)
    if query.assignee_id is not None:
        conditions.append(
            exists().where(
                TicketAssignment.ticket_id == Ticket.ticket_id,
                TicketAssignment.assignee_id == query.assignee_id,
                TicketAssignment.is_current.is_(True),
            )
        )
    if query.created_from is not None:
        conditions.append(Ticket.created_at >= query.created_from)
    if query.created_to is not None:
        conditions.append(Ticket.created_at <= query.created_to)
    if query.q:
        pattern = f"%{_escape_like(query.q.lower())}%"
        conditions.append(
            or_(
                func.lower(Ticket.ticket_code).like(pattern, escape="\\"),
                func.lower(Ticket.title).like(pattern, escape="\\"),
            )
        )
    return conditions


def _apply_sort(statement: Select, sort: str) -> Select:
    sort_map = {
        "created_at": Ticket.created_at.asc(),
        "-created_at": Ticket.created_at.desc(),
        "updated_at": Ticket.updated_at.asc(),
        "-updated_at": Ticket.updated_at.desc(),
        "priority_level": Priority.priority_level.asc(),
        "-priority_level": Priority.priority_level.desc(),
    }
    if sort in {"priority_level", "-priority_level"}:
        statement = statement.join(Priority, Ticket.priority_id == Priority.priority_id)
    return statement.order_by(sort_map[sort], Ticket.ticket_id.desc())


async def get_existing_status_codes(
    session: AsyncSession,
    status_codes: list[str],
) -> set[str]:
    result = await session.execute(
        select(TicketStatus.status_code).where(
            TicketStatus.status_code.in_(status_codes)
        )
    )
    return set(result.scalars().all())


async def list_tickets(
    session: AsyncSession,
    *,
    query: TicketListQuery,
    current_user_id: int,
    role_codes: set[str],
) -> tuple[list[Ticket], int]:
    conditions = _list_conditions(
        query,
        current_user_id=current_user_id,
        role_codes=role_codes,
    )
    total = await session.scalar(
        select(func.count(Ticket.ticket_id)).where(*conditions)
    )
    statement = (
        select(Ticket)
        .where(*conditions)
        .options(*TICKET_LOAD_OPTIONS)
        .offset((query.page - 1) * query.page_size)
        .limit(query.page_size)
        .execution_options(populate_existing=True)
    )
    statement = _apply_sort(statement, query.sort)
    result = await session.execute(statement)
    return list(result.scalars().all()), int(total or 0)


async def get_category_by_id(
    session: AsyncSession,
    category_id: int,
) -> Category | None:
    return await session.get(Category, category_id)


async def get_priority_by_id(
    session: AsyncSession,
    priority_id: int,
) -> Priority | None:
    return await session.get(Priority, priority_id)


async def get_status_by_code(
    session: AsyncSession,
    status_code: str,
) -> TicketStatus | None:
    return await session.get(TicketStatus, status_code)


async def create_ticket_record(
    session: AsyncSession,
    *,
    ticket_code: str,
    requester_id: int,
    category_id: int,
    priority_id: int,
    title: str,
    description: str,
) -> Ticket:
    ticket = Ticket(
        ticket_code=ticket_code,
        requester_id=requester_id,
        category_id=category_id,
        priority_id=priority_id,
        current_status_code="NEW",
        title=title,
        description=description,
    )
    session.add(ticket)
    await session.flush()
    return ticket


async def get_ticket_by_id(
    session: AsyncSession,
    ticket_id: int,
) -> Ticket | None:
    result = await session.execute(
        select(Ticket)
        .where(Ticket.ticket_id == ticket_id)
        .options(*TICKET_LOAD_OPTIONS)
        .execution_options(populate_existing=True)
    )
    return result.scalar_one_or_none()


async def get_ticket_detail_by_id(
    session: AsyncSession,
    ticket_id: int,
) -> Ticket | None:
    result = await session.execute(
        select(Ticket)
        .where(Ticket.ticket_id == ticket_id)
        .options(*TICKET_DETAIL_LOAD_OPTIONS)
        .execution_options(populate_existing=True)
    )
    return result.scalar_one_or_none()


async def get_ticket_for_assignment(
    session: AsyncSession,
    *,
    ticket_id: int,
) -> Ticket | None:
    """Lock the ticket row so concurrent assignment requests serialize."""

    result = await session.execute(
        select(Ticket)
        .where(Ticket.ticket_id == ticket_id)
        .options(
            selectinload(Ticket.current_status),
            selectinload(Ticket.assignments)
            .selectinload(TicketAssignment.assignee),
            selectinload(Ticket.assignments)
            .selectinload(TicketAssignment.assigner),
        )
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    return result.scalar_one_or_none()


async def close_current_assignment(
    session: AsyncSession,
    *,
    assignment: TicketAssignment,
    ended_at: datetime,
) -> None:
    assignment.is_current = False
    assignment.ended_at = ended_at
    # Flush the UPDATE before INSERT so the unique current-assignment index
    # remains valid on every supported database.
    await session.flush()


async def create_assignment_record(
    session: AsyncSession,
    *,
    ticket_id: int,
    assignee_id: int,
    assigned_by: int,
    assigned_at: datetime,
    reason: str | None,
) -> TicketAssignment:
    assignment = TicketAssignment(
        ticket_id=ticket_id,
        assignee_id=assignee_id,
        assigned_by=assigned_by,
        assigned_at=assigned_at,
        is_current=True,
        reason=reason,
    )
    session.add(assignment)
    await session.flush()
    return assignment


async def create_assignment_audit_record(
    session: AsyncSession,
    *,
    actor_user_id: int,
    ticket_id: int,
    assignment_id: int,
    action_code: str,
    old_value: dict,
    new_value: dict,
    reason: str | None,
    ip_address: str | None,
) -> AuditLog:
    audit = AuditLog(
        actor_user_id=actor_user_id,
        ticket_id=ticket_id,
        action_code=action_code,
        entity_type="TICKET_ASSIGNMENT",
        entity_id=assignment_id,
        old_value_json=old_value,
        new_value_json=new_value,
        reason=reason,
        ip_address=ip_address,
    )
    session.add(audit)
    await session.flush()
    return audit


async def get_assignment_by_id(
    session: AsyncSession,
    assignment_id: int,
) -> TicketAssignment | None:
    result = await session.execute(
        select(TicketAssignment)
        .where(TicketAssignment.assignment_id == assignment_id)
        .options(
            selectinload(TicketAssignment.assignee),
            selectinload(TicketAssignment.assigner),
        )
        .execution_options(populate_existing=True)
    )
    return result.scalar_one_or_none()


async def create_status_history_record(
    session: AsyncSession,
    *,
    ticket_id: int,
    from_status_code: str | None,
    to_status_code: str,
    changed_by: int | None,
    reason: str | None,
) -> TicketStatusHistory:
    history = TicketStatusHistory(
        ticket_id=ticket_id,
        from_status_code=from_status_code,
        to_status_code=to_status_code,
        changed_by=changed_by,
        reason=reason,
    )
    session.add(history)
    await session.flush()
    return history


async def get_effective_sla_policy(
    session: AsyncSession,
    *,
    priority_id: int,
    effective_at: datetime,
) -> SLAPolicy | None:
    result = await session.execute(
        select(SLAPolicy)
        .where(
            SLAPolicy.priority_id == priority_id,
            SLAPolicy.is_active.is_(True),
            SLAPolicy.effective_from <= effective_at,
            or_(
                SLAPolicy.effective_to.is_(None),
                SLAPolicy.effective_to > effective_at,
            ),
        )
        .order_by(SLAPolicy.version_no.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def create_ticket_sla_record(
    session: AsyncSession,
    *,
    ticket_id: int,
    sla_policy_id: int,
    sla_type: str,
    cycle_no: int,
    started_at: datetime,
    due_at: datetime,
) -> TicketSLA:
    ticket_sla = TicketSLA(
        ticket_id=ticket_id,
        sla_policy_id=sla_policy_id,
        sla_type=sla_type,
        cycle_no=cycle_no,
        started_at=started_at,
        due_at=due_at,
        runtime_status="RUNNING",
    )
    session.add(ticket_sla)
    await session.flush()
    return ticket_sla


async def list_status_history(
    session: AsyncSession,
    *,
    ticket_id: int,
    page: int,
    page_size: int,
) -> tuple[list[TicketStatusHistory], int]:
    total = await session.scalar(
        select(func.count(TicketStatusHistory.history_id)).where(
            TicketStatusHistory.ticket_id == ticket_id
        )
    )
    result = await session.execute(
        select(TicketStatusHistory)
        .where(TicketStatusHistory.ticket_id == ticket_id)
        .options(selectinload(TicketStatusHistory.actor))
        .order_by(
            TicketStatusHistory.changed_at.asc(),
            TicketStatusHistory.history_id.asc(),
        )
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    return list(result.scalars().all()), int(total or 0)


async def list_comments(
    session: AsyncSession,
    *,
    ticket_id: int,
    include_internal: bool,
    page: int,
    page_size: int,
) -> tuple[list[Comment], int]:
    conditions = [Comment.ticket_id == ticket_id]
    if not include_internal:
        conditions.append(Comment.visibility == "PUBLIC")
    total = await session.scalar(
        select(func.count(Comment.comment_id)).where(*conditions)
    )
    result = await session.execute(
        select(Comment)
        .where(*conditions)
        .options(
            selectinload(Comment.author),
            selectinload(Comment.attachments),
        )
        .order_by(Comment.created_at.asc(), Comment.comment_id.asc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    return list(result.scalars().all()), int(total or 0)


async def list_assignments(
    session: AsyncSession,
    *,
    ticket_id: int,
    page: int,
    page_size: int,
) -> tuple[list[TicketAssignment], int]:
    total = await session.scalar(
        select(func.count(TicketAssignment.assignment_id)).where(
            TicketAssignment.ticket_id == ticket_id
        )
    )
    result = await session.execute(
        select(TicketAssignment)
        .where(TicketAssignment.ticket_id == ticket_id)
        .options(
            selectinload(TicketAssignment.assignee),
            selectinload(TicketAssignment.assigner),
        )
        .order_by(
            TicketAssignment.assigned_at.asc(),
            TicketAssignment.assignment_id.asc(),
        )
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    return list(result.scalars().all()), int(total or 0)
