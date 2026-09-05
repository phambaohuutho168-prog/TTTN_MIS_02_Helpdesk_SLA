"""Create a small, coherent and repeatable dataset for UI/API demonstrations."""

import asyncio
import os
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from dotenv import load_dotenv
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password
from app.core.sla import calculate_deadline, calculate_result
from app.database.session import AsyncSessionLocal
from app.models.category import Category
from app.models.comment import Comment
from app.models.department import Department
from app.models.priority import Priority
from app.models.rating import Rating
from app.models.role import Role
from app.models.sla_policy import SLAPolicy
from app.models.ticket import Ticket
from app.models.ticket_assignment import TicketAssignment
from app.models.ticket_resolution import TicketResolution
from app.models.ticket_sla import TicketSLA
from app.models.ticket_status import TicketStatus
from app.models.ticket_status_history import TicketStatusHistory
from app.models.user import User
from app.models.user_role import UserRole
from scripts.seed_initial_data import required_seed_value, seed as seed_reference_data


load_dotenv()


DEMO_DEPARTMENT = "Trung tâm Công nghệ thông tin"
DEMO_REQUESTER_EMAIL = "demo.requester@example.com"
DEMO_PROCESSOR_EMAIL = "demo.processor@example.com"


@dataclass(frozen=True)
class DemoScenario:
    ticket_code: str
    title: str
    description: str
    category_name: str
    priority_code: str
    current_status_code: str
    created_ago: timedelta
    first_response_after_minutes: int | None
    transitions: tuple[tuple[str, int, str], ...]
    resolved_after_minutes: int | None = None
    closed_after_minutes: int | None = None
    reopened_after_minutes: int | None = None
    rejected_after_minutes: int | None = None
    rejection_reason: str | None = None
    comment: str | None = None


DEMO_SCENARIOS = (
    DemoScenario(
        ticket_code="DEMO-NORMAL-001",
        title="[DEMO] Cài đặt phần mềm kế toán",
        description="Yêu cầu hỗ trợ thông thường, đang được xử lý và còn nhiều thời gian SLA.",
        category_name="Phần mềm",
        priority_code="P3",
        current_status_code="IN_PROGRESS",
        created_ago=timedelta(hours=2),
        first_response_after_minutes=35,
        transitions=(
            ("NEW", 0, "Requester tạo ticket demo."),
            ("ASSIGNED", 10, "Phân công cho Processor demo."),
            ("IN_PROGRESS", 20, "Processor bắt đầu xử lý."),
        ),
        comment="Đã tiếp nhận và đang kiểm tra cấu hình máy người dùng.",
    ),
    DemoScenario(
        ticket_code="DEMO-NEAR-DUE-001",
        title="[DEMO] VPN thường xuyên mất kết nối",
        description="Ticket đã sử dụng hơn 80% thời gian xử lý và đang ở ngưỡng sắp quá hạn.",
        category_name="Mạng",
        priority_code="P3",
        current_status_code="IN_PROGRESS",
        created_ago=timedelta(hours=20),
        first_response_after_minutes=50,
        transitions=(
            ("NEW", 0, "Requester tạo ticket demo gần hạn."),
            ("ASSIGNED", 10, "Phân công cho Processor demo."),
            ("IN_PROGRESS", 25, "Đang phân tích log kết nối VPN."),
        ),
        comment="Đang theo dõi log; deadline xử lý còn khoảng bốn giờ.",
    ),
    DemoScenario(
        ticket_code="DEMO-OVERDUE-001",
        title="[DEMO] Không đăng nhập được hệ thống ERP",
        description="Ticket ưu tiên cao đã vượt deadline xử lý để minh họa cảnh báo quá hạn.",
        category_name="Tài khoản",
        priority_code="P2",
        current_status_code="IN_PROGRESS",
        created_ago=timedelta(hours=10),
        first_response_after_minutes=20,
        transitions=(
            ("NEW", 0, "Requester tạo ticket demo quá hạn."),
            ("ASSIGNED", 5, "Phân công khẩn cho Processor demo."),
            ("IN_PROGRESS", 15, "Đang kiểm tra tài khoản ERP."),
        ),
        comment="Đã xác định lỗi đồng bộ tài khoản và đang chờ khôi phục.",
    ),
    DemoScenario(
        ticket_code="DEMO-CLOSED-001",
        title="[DEMO] Máy in phòng hành chính bị kẹt giấy",
        description="Ticket đã xử lý, có solution note, đóng đúng SLA và có đánh giá hài lòng.",
        category_name="Phần cứng",
        priority_code="P4",
        current_status_code="CLOSED",
        created_ago=timedelta(days=5),
        first_response_after_minutes=120,
        resolved_after_minutes=1_200,
        closed_after_minutes=1_260,
        transitions=(
            ("NEW", 0, "Requester tạo ticket demo đã đóng."),
            ("ASSIGNED", 30, "Phân công cho Processor demo."),
            ("IN_PROGRESS", 90, "Processor kiểm tra máy in."),
            ("RESOLVED", 1_200, "Đã vệ sinh cụm kéo giấy và in thử thành công."),
            ("CLOSED", 1_260, "Requester xác nhận sự cố đã được xử lý."),
        ),
        comment="Máy in đã hoạt động bình thường sau khi vệ sinh cụm kéo giấy.",
    ),
    DemoScenario(
        ticket_code="DEMO-REOPENED-001",
        title="[DEMO] Email gửi ra ngoài bị trả lại",
        description="Ticket từng đóng đúng SLA và được requester mở lại để bắt đầu chu kỳ SLA mới.",
        category_name="Phần mềm",
        priority_code="P2",
        current_status_code="REOPENED",
        created_ago=timedelta(days=4),
        first_response_after_minutes=25,
        resolved_after_minutes=360,
        closed_after_minutes=420,
        reopened_after_minutes=5_640,
        transitions=(
            ("NEW", 0, "Requester tạo ticket demo mở lại."),
            ("ASSIGNED", 10, "Phân công cho Processor demo."),
            ("IN_PROGRESS", 20, "Processor bắt đầu xử lý."),
            ("RESOLVED", 360, "Đã cập nhật cấu hình chuyển tiếp email."),
            ("CLOSED", 420, "Requester xác nhận email hoạt động."),
            ("REOPENED", 5_640, "Lỗi tái diễn khi gửi đến một miền đối tác."),
        ),
        comment="Lỗi tái diễn với miền đối tác; vui lòng kiểm tra thêm chính sách chống spam.",
    ),
    DemoScenario(
        ticket_code="DEMO-REJECTED-001",
        title="[DEMO] Yêu cầu mua điện thoại cá nhân",
        description="Yêu cầu ngoài phạm vi hỗ trợ CNTT, được Admin từ chối có lý do.",
        category_name="Phần cứng",
        priority_code="P4",
        current_status_code="REJECTED",
        created_ago=timedelta(days=2),
        first_response_after_minutes=None,
        rejected_after_minutes=15,
        rejection_reason="Yêu cầu mua thiết bị cá nhân nằm ngoài phạm vi hỗ trợ.",
        transitions=(
            ("NEW", 0, "Requester tạo ticket demo bị từ chối."),
            ("REJECTED", 15, "Yêu cầu nằm ngoài phạm vi hỗ trợ CNTT."),
        ),
    ),
)


async def _one_by(session: AsyncSession, model, field, value):
    result = await session.execute(select(model).where(field == value))
    return result.scalar_one_or_none()


async def _require_reference_data(session: AsyncSession):
    categories = {
        item.category_name: item
        for item in (await session.scalars(select(Category))).all()
    }
    priorities = {
        item.priority_code: item
        for item in (await session.scalars(select(Priority))).all()
    }
    statuses = {
        item.status_code: item
        for item in (await session.scalars(select(TicketStatus))).all()
    }
    roles = {
        item.role_code: item
        for item in (await session.scalars(select(Role))).all()
    }
    policies = {
        item.priority_id: item
        for item in (
            await session.scalars(
                select(SLAPolicy).where(
                    SLAPolicy.version_no == 1,
                    SLAPolicy.is_active.is_(True),
                )
            )
        ).all()
    }
    required_categories = {scenario.category_name for scenario in DEMO_SCENARIOS}
    required_priorities = {scenario.priority_code for scenario in DEMO_SCENARIOS}
    required_statuses = {
        status_code
        for scenario in DEMO_SCENARIOS
        for status_code, _offset, _reason in scenario.transitions
    }
    missing = []
    missing.extend(f"category:{name}" for name in required_categories - categories.keys())
    missing.extend(f"priority:{code}" for code in required_priorities - priorities.keys())
    missing.extend(f"status:{code}" for code in required_statuses - statuses.keys())
    missing.extend(f"role:{code}" for code in {"ADMIN", "PROCESSOR", "REQUESTER"} - roles.keys())
    for code in required_priorities:
        priority = priorities.get(code)
        if priority is not None and priority.priority_id not in policies:
            missing.append(f"sla_policy:{code}")
    if missing:
        raise RuntimeError("Thiếu dữ liệu nền: " + ", ".join(sorted(missing)))
    return categories, priorities, roles, policies


async def _get_or_create_department(session: AsyncSession) -> Department:
    department = await _one_by(
        session,
        Department,
        Department.department_name,
        DEMO_DEPARTMENT,
    )
    if department is None:
        department = Department(
            department_name=DEMO_DEPARTMENT,
            description="Phòng ban dùng cho dữ liệu mô phỏng CV045.",
            is_active=True,
        )
        session.add(department)
        await session.flush()
    return department


async def _get_or_create_demo_user(
    session: AsyncSession,
    *,
    email: str,
    full_name: str,
    password: str,
    role: Role,
    assigned_by: int,
    department_id: int | None = None,
) -> User:
    user = await _one_by(session, User, User.email, email)
    if user is None:
        user = User(
            email=email,
            full_name=full_name,
            password_hash=hash_password(password),
            department_id=department_id,
            is_active=True,
        )
        session.add(user)
        await session.flush()
    else:
        user.full_name = full_name
        user.password_hash = hash_password(password)
        user.is_active = True
    role_assignment = await session.get(
        UserRole,
        {"user_id": user.user_id, "role_id": role.role_id},
    )
    if role_assignment is None:
        session.add(
            UserRole(
                user_id=user.user_id,
                role_id=role.role_id,
                assigned_by=assigned_by,
            )
        )
    return user


def _history_actor(status_code: str, *, requester: User, processor: User, admin: User) -> int:
    if status_code in {"NEW", "CLOSED", "REOPENED"}:
        return requester.user_id
    if status_code in {"ASSIGNED", "REJECTED"}:
        return admin.user_id
    return processor.user_id


def _add_sla_records(
    session: AsyncSession,
    *,
    scenario: DemoScenario,
    ticket: Ticket,
    policy: SLAPolicy,
    created_at: datetime,
) -> None:
    response_due = calculate_deadline(
        started_at=created_at,
        target_minutes=policy.response_target_minutes,
    )
    if scenario.rejected_after_minutes is not None:
        rejected_at = created_at + timedelta(minutes=scenario.rejected_after_minutes)
        session.add(
            TicketSLA(
                ticket_id=ticket.ticket_id,
                sla_policy_id=policy.sla_policy_id,
                sla_type="RESPONSE",
                cycle_no=1,
                started_at=created_at,
                due_at=response_due,
                completed_at=rejected_at,
                runtime_status="NOT_APPLICABLE",
                result="NOT_APPLICABLE",
                created_at=created_at,
                updated_at=rejected_at,
            )
        )
    else:
        response_at = created_at + timedelta(
            minutes=scenario.first_response_after_minutes or 0
        )
        session.add(
            TicketSLA(
                ticket_id=ticket.ticket_id,
                sla_policy_id=policy.sla_policy_id,
                sla_type="RESPONSE",
                cycle_no=1,
                started_at=created_at,
                due_at=response_due,
                completed_at=response_at,
                runtime_status="COMPLETED",
                result=calculate_result(completed_at=response_at, due_at=response_due),
                created_at=created_at,
                updated_at=response_at,
            )
        )

    resolution_due = calculate_deadline(
        started_at=created_at,
        target_minutes=policy.resolution_target_minutes,
    )
    if scenario.rejected_after_minutes is not None:
        rejected_at = created_at + timedelta(minutes=scenario.rejected_after_minutes)
        resolution_runtime = TicketSLA(
            ticket_id=ticket.ticket_id,
            sla_policy_id=policy.sla_policy_id,
            sla_type="RESOLUTION",
            cycle_no=1,
            started_at=created_at,
            due_at=resolution_due,
            completed_at=rejected_at,
            runtime_status="NOT_APPLICABLE",
            result="NOT_APPLICABLE",
            created_at=created_at,
            updated_at=rejected_at,
        )
    elif scenario.resolved_after_minutes is not None:
        resolved_at = created_at + timedelta(minutes=scenario.resolved_after_minutes)
        resolution_runtime = TicketSLA(
            ticket_id=ticket.ticket_id,
            sla_policy_id=policy.sla_policy_id,
            sla_type="RESOLUTION",
            cycle_no=1,
            started_at=created_at,
            due_at=resolution_due,
            completed_at=resolved_at,
            runtime_status="COMPLETED",
            result=calculate_result(completed_at=resolved_at, due_at=resolution_due),
            created_at=created_at,
            updated_at=resolved_at,
        )
    else:
        resolution_runtime = TicketSLA(
            ticket_id=ticket.ticket_id,
            sla_policy_id=policy.sla_policy_id,
            sla_type="RESOLUTION",
            cycle_no=1,
            started_at=created_at,
            due_at=resolution_due,
            runtime_status="RUNNING",
            result=None,
            created_at=created_at,
            updated_at=created_at,
        )
    session.add(resolution_runtime)

    if scenario.reopened_after_minutes is not None:
        reopened_at = created_at + timedelta(minutes=scenario.reopened_after_minutes)
        session.add(
            TicketSLA(
                ticket_id=ticket.ticket_id,
                sla_policy_id=policy.sla_policy_id,
                sla_type="RESOLUTION",
                cycle_no=2,
                started_at=reopened_at,
                due_at=calculate_deadline(
                    started_at=reopened_at,
                    target_minutes=policy.resolution_target_minutes,
                ),
                runtime_status="RUNNING",
                result=None,
                created_at=reopened_at,
                updated_at=reopened_at,
            )
        )


async def _create_scenario(
    session: AsyncSession,
    *,
    scenario: DemoScenario,
    now: datetime,
    categories: dict[str, Category],
    priorities: dict[str, Priority],
    policies: dict[int, SLAPolicy],
    requester: User,
    processor: User,
    admin: User,
) -> bool:
    existing = await _one_by(
        session,
        Ticket,
        Ticket.ticket_code,
        scenario.ticket_code,
    )
    if existing is not None:
        return False

    created_at = now - scenario.created_ago
    first_response_at = (
        created_at + timedelta(minutes=scenario.first_response_after_minutes)
        if scenario.first_response_after_minutes is not None
        else None
    )
    closed_at = (
        created_at + timedelta(minutes=scenario.closed_after_minutes)
        if scenario.current_status_code == "CLOSED"
        and scenario.closed_after_minutes is not None
        else None
    )
    rejected_at = (
        created_at + timedelta(minutes=scenario.rejected_after_minutes)
        if scenario.rejected_after_minutes is not None
        else None
    )
    last_transition_at = created_at + timedelta(minutes=scenario.transitions[-1][1])
    priority = priorities[scenario.priority_code]
    ticket = Ticket(
        ticket_code=scenario.ticket_code,
        requester_id=requester.user_id,
        category_id=categories[scenario.category_name].category_id,
        priority_id=priority.priority_id,
        current_status_code=scenario.current_status_code,
        title=scenario.title,
        description=scenario.description,
        first_response_at=first_response_at,
        closed_at=closed_at,
        closed_by=requester.user_id if closed_at is not None else None,
        rejected_at=rejected_at,
        rejection_reason=scenario.rejection_reason,
        created_at=created_at,
        updated_at=last_transition_at,
    )
    session.add(ticket)
    await session.flush()

    previous_status = None
    for status_code, offset_minutes, reason in scenario.transitions:
        session.add(
            TicketStatusHistory(
                ticket_id=ticket.ticket_id,
                from_status_code=previous_status,
                to_status_code=status_code,
                changed_by=_history_actor(
                    status_code,
                    requester=requester,
                    processor=processor,
                    admin=admin,
                ),
                reason=reason,
                changed_at=created_at + timedelta(minutes=offset_minutes),
            )
        )
        previous_status = status_code

    if scenario.current_status_code != "REJECTED":
        assigned_after_minutes = next(
            offset
            for status_code, offset, _reason in scenario.transitions
            if status_code == "ASSIGNED"
        )
        session.add(
            TicketAssignment(
                ticket_id=ticket.ticket_id,
                assignee_id=processor.user_id,
                assigned_by=admin.user_id,
                assigned_at=created_at + timedelta(minutes=assigned_after_minutes),
                is_current=True,
                reason="Phân công dữ liệu mô phỏng CV045.",
            )
        )

    if scenario.resolved_after_minutes is not None:
        resolved_at = created_at + timedelta(minutes=scenario.resolved_after_minutes)
        session.add(
            TicketResolution(
                ticket_id=ticket.ticket_id,
                resolved_by=processor.user_id,
                cycle_no=1,
                resolution_note=(
                    "Đã xử lý nguyên nhân, kiểm thử lại thành công và hướng dẫn người dùng."
                ),
                resolved_at=resolved_at,
            )
        )

    if scenario.comment:
        comment_author = (
            requester if scenario.current_status_code == "REOPENED" else processor
        )
        session.add(
            Comment(
                ticket_id=ticket.ticket_id,
                author_id=comment_author.user_id,
                content=scenario.comment,
                visibility="PUBLIC",
                comment_type="REPLY",
                created_at=last_transition_at,
            )
        )

    if scenario.current_status_code == "CLOSED" and closed_at is not None:
        session.add(
            Rating(
                ticket_id=ticket.ticket_id,
                rated_by=requester.user_id,
                score=5,
                comment="Hỗ trợ nhanh, hướng dẫn rõ ràng.",
                created_at=closed_at + timedelta(minutes=30),
            )
        )

    _add_sla_records(
        session,
        scenario=scenario,
        ticket=ticket,
        policy=policies[priority.priority_id],
        created_at=created_at,
    )
    return True


async def seed_demo_dataset(
    session: AsyncSession,
    *,
    admin_email: str,
    demo_password: str,
    requester_email: str = DEMO_REQUESTER_EMAIL,
    processor_email: str = DEMO_PROCESSOR_EMAIL,
    now: datetime | None = None,
) -> dict[str, int]:
    """Seed demo users and six stable scenarios without duplicating tickets."""

    if len(demo_password) < 12:
        raise RuntimeError("SEED_DEMO_PASSWORD phải có ít nhất 12 ký tự")
    now = (now or datetime.now(timezone.utc)).astimezone(timezone.utc).replace(
        microsecond=0
    )
    categories, priorities, roles, policies = await _require_reference_data(session)
    admin = await _one_by(session, User, User.email, admin_email.lower())
    if admin is None:
        raise RuntimeError("Không tìm thấy Admin. Hãy chạy seed dữ liệu nền trước.")

    department = await _get_or_create_department(session)
    requester = await _get_or_create_demo_user(
        session,
        email=requester_email.lower(),
        full_name="Phạm Bao Hữu Thọ",
        password=demo_password,
        role=roles["REQUESTER"],
        assigned_by=admin.user_id,
    )
    processor = await _get_or_create_demo_user(
        session,
        email=processor_email.lower(),
        full_name="Nguyễn Thị Mai Thy",
        password=demo_password,
        role=roles["PROCESSOR"],
        assigned_by=admin.user_id,
        department_id=department.department_id,
    )
    await session.flush()

    created = 0
    for scenario in DEMO_SCENARIOS:
        created += int(
            await _create_scenario(
                session,
                scenario=scenario,
                now=now,
                categories=categories,
                priorities=priorities,
                policies=policies,
                requester=requester,
                processor=processor,
                admin=admin,
            )
        )
    return {
        "created": created,
        "skipped": len(DEMO_SCENARIOS) - created,
        "total": len(DEMO_SCENARIOS),
    }


async def run() -> None:
    admin_email = required_seed_value("SEED_ADMIN_EMAIL").lower()
    demo_password = required_seed_value("SEED_DEMO_PASSWORD")
    if len(demo_password) < 12:
        raise RuntimeError("SEED_DEMO_PASSWORD phải có ít nhất 12 ký tự")
    requester_email = os.getenv(
        "SEED_DEMO_REQUESTER_EMAIL",
        DEMO_REQUESTER_EMAIL,
    ).strip().lower()
    processor_email = os.getenv(
        "SEED_DEMO_PROCESSOR_EMAIL",
        DEMO_PROCESSOR_EMAIL,
    ).strip().lower()

    await seed_reference_data()
    async with AsyncSessionLocal() as session:
        try:
            result = await seed_demo_dataset(
                session,
                admin_email=admin_email,
                demo_password=demo_password,
                requester_email=requester_email,
                processor_email=processor_email,
            )
            await session.commit()
        except Exception:
            await session.rollback()
            raise
    print(
        "Seed demo hoàn tất: "
        f"tạo mới {result['created']}, bỏ qua {result['skipped']}, "
        f"tổng {result['total']} ticket CV045."
    )


if __name__ == "__main__":
    asyncio.run(run())
