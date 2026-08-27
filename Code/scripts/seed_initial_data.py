import asyncio
import os

from sqlalchemy import select

from app.core.security import hash_password
from app.database.session import AsyncSessionLocal
from app.models.role import Role
from app.models.user import User
from app.models.user_role import UserRole


ROLE_SEEDS = (
    ("REQUESTER", "Người gửi yêu cầu", "Tạo và theo dõi ticket của chính mình."),
    ("PROCESSOR", "Người xử lý", "Tiếp nhận và xử lý ticket được phân công."),
    ("ADMIN", "Quản trị viên", "Quản trị tài khoản, vai trò và toàn hệ thống."),
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
        print("Seed hoàn tất: 3 vai trò và tài khoản Admin cục bộ đã sẵn sàng.")


if __name__ == "__main__":
    asyncio.run(seed())
