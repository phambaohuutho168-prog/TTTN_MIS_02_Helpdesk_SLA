import asyncio
import os

from dotenv import load_dotenv
from sqlalchemy import select

from app.core.security import hash_password
from app.database.session import AsyncSessionLocal
from app.models.category import Category
from app.models.priority import Priority
from app.models.role import Role
from app.models.ticket_status import TicketStatus
from app.models.user import User
from app.models.user_role import UserRole


load_dotenv()


ROLE_SEEDS = (
    ("REQUESTER", "Người gửi yêu cầu", "Tạo và theo dõi ticket của chính mình."),
    ("PROCESSOR", "Người xử lý", "Tiếp nhận và xử lý ticket được phân công."),
    ("ADMIN", "Quản trị viên", "Quản trị tài khoản, vai trò và toàn hệ thống."),
)

CATEGORY_SEEDS = (
    ("Phần cứng", "Máy tính, máy in và thiết bị ngoại vi."),
    ("Phần mềm", "Ứng dụng nội bộ và phần mềm nghiệp vụ."),
    ("Mạng", "Kết nối mạng, Internet và VPN."),
    ("Tài khoản", "Tài khoản, mật khẩu và quyền truy cập."),
)

PRIORITY_SEEDS = (
    ("P1", 1, "Khẩn cấp", "Gián đoạn dịch vụ quan trọng."),
    ("P2", 2, "Cao", "Ảnh hưởng đáng kể đến hoạt động."),
    ("P3", 3, "Trung bình", "Ảnh hưởng công việc của một người dùng."),
    ("P4", 4, "Thấp", "Ảnh hưởng nhỏ, có giải pháp tạm thời."),
)

STATUS_SEEDS = (
    ("NEW", "Mới", False, "Ticket vừa được tạo."),
    ("ASSIGNED", "Đã phân công", False, "Ticket đã có người xử lý."),
    ("IN_PROGRESS", "Đang xử lý", False, "Người xử lý đang thực hiện."),
    ("PENDING_INFO", "Chờ bổ sung", False, "Đang chờ requester bổ sung thông tin."),
    ("RESOLVED", "Đã xử lý", False, "Đã có kết quả xử lý, chờ xác nhận."),
    ("REOPENED", "Mở lại", False, "Requester yêu cầu xử lý lại."),
    ("CLOSED", "Đã đóng", True, "Ticket đã hoàn tất."),
    ("REJECTED", "Từ chối", True, "Ticket không hợp lệ hoặc ngoài phạm vi."),
)


def required_seed_value(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value or "CHANGE_ME" in value.upper():
        raise RuntimeError(f"Cần đặt {name} bằng giá trị cục bộ trước khi seed")
    return value


async def seed() -> None:
    admin_email = required_seed_value("SEED_ADMIN_EMAIL").lower()
    admin_name = required_seed_value("SEED_ADMIN_FULL_NAME")
    admin_password = required_seed_value("SEED_ADMIN_PASSWORD")
    if len(admin_password) < 12:
        raise RuntimeError("SEED_ADMIN_PASSWORD phải có ít nhất 12 ký tự")

    async with AsyncSessionLocal() as session:
        for category_name, description in CATEGORY_SEEDS:
            result = await session.execute(
                select(Category).where(Category.category_name == category_name)
            )
            if result.scalar_one_or_none() is None:
                session.add(
                    Category(
                        category_name=category_name,
                        description=description,
                        is_active=True,
                    )
                )

        for priority_code, priority_level, priority_name, description in PRIORITY_SEEDS:
            result = await session.execute(
                select(Priority).where(Priority.priority_code == priority_code)
            )
            if result.scalar_one_or_none() is None:
                session.add(
                    Priority(
                        priority_code=priority_code,
                        priority_level=priority_level,
                        priority_name=priority_name,
                        description=description,
                        is_active=True,
                    )
                )

        for status_code, status_name, is_terminal, description in STATUS_SEEDS:
            result = await session.execute(
                select(TicketStatus).where(TicketStatus.status_code == status_code)
            )
            if result.scalar_one_or_none() is None:
                session.add(
                    TicketStatus(
                        status_code=status_code,
                        status_name=status_name,
                        is_terminal=is_terminal,
                        description=description,
                    )
                )

        roles: dict[str, Role] = {}
        for role_code, role_name, description in ROLE_SEEDS:
            result = await session.execute(
                select(Role).where(Role.role_code == role_code)
            )
            role = result.scalar_one_or_none()
            if role is None:
                role = Role(
                    role_code=role_code,
                    role_name=role_name,
                    description=description,
                    is_active=True,
                )
                session.add(role)
                await session.flush()
            roles[role_code] = role

        result = await session.execute(select(User).where(User.email == admin_email))
        admin = result.scalar_one_or_none()
        if admin is None:
            admin = User(
                email=admin_email,
                full_name=admin_name,
                password_hash=hash_password(admin_password),
                is_active=True,
            )
            session.add(admin)
            await session.flush()

        assignment = await session.get(
            UserRole,
            {"user_id": admin.user_id, "role_id": roles["ADMIN"].role_id},
        )
        if assignment is None:
            session.add(
                UserRole(
                    user_id=admin.user_id,
                    role_id=roles["ADMIN"].role_id,
                    assigned_by=None,
                )
            )

        await session.commit()
        print(
            "Seed hoàn tất: vai trò, danh mục, mức ưu tiên, trạng thái ticket "
            "và tài khoản Admin cục bộ đã sẵn sàng."
        )


if __name__ == "__main__":
    asyncio.run(seed())
