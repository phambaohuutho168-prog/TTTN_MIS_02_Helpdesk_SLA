import os
from collections import defaultdict
from typing import Any

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool


os.environ.setdefault("APP_ENV", "test")
os.environ.setdefault("DEBUG", "false")
os.environ.setdefault("SECRET_KEY", "test-secret-key-that-is-longer-than-thirty-two-characters")
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/15")

from app.core.security import hash_password  # noqa: E402
from app.core.config import settings  # noqa: E402
from app.database.base import Base  # noqa: E402
from app.database.session import get_db  # noqa: E402
from app.main import app  # noqa: E402
from app.models import (  # noqa: E402,F401
    Attachment,
    AuditLog,
    Category,
    Comment,
    Department,
    Notification,
    Priority,
    Rating,
    Role,
    SLAPolicy,
    SLAEvent,
    Ticket,
    TicketAssignment,
    TicketResolution,
    TicketSLA,
    TicketStatus,
    TicketStatusHistory,
    User,
    UserRole,
)
from app.services.auth_session_store import get_session_store  # noqa: E402


@pytest.fixture(autouse=True)
def isolated_attachment_storage(tmp_path, monkeypatch):
    monkeypatch.setattr(
        settings,
        "ATTACHMENT_STORAGE_DIR",
        str(tmp_path / "attachments"),
    )


class FakeSessionStore:
    def __init__(self) -> None:
        self.refresh_sessions: dict[str, dict[str, str]] = {}
        self.families: dict[str, set[str]] = defaultdict(set)
        self.revoked_access: set[str] = set()
        self.login_failures: dict[str, int] = defaultdict(int)

    async def ping(self) -> bool:
        return True

    async def create_refresh_session(self, claims: dict[str, Any]) -> None:
        jti = str(claims["jti"])
        family_id = str(claims["family_id"])
        self.refresh_sessions[jti] = {
            "status": "active",
            "family_id": family_id,
            "user_id": str(claims["sub"]),
        }
        self.families[family_id].add(jti)

    async def get_refresh_status(self, jti: str) -> str | None:
        session = self.refresh_sessions.get(jti)
        return session["status"] if session else None

    async def rotate_refresh_session(
        self,
        old_claims: dict[str, Any],
        new_claims: dict[str, Any],
    ) -> bool:
        old_jti = str(old_claims["jti"])
        old_session = self.refresh_sessions.get(old_jti)
        if old_session is None or old_session["status"] != "active":
            return False
        old_session["status"] = "used"
        await self.create_refresh_session(new_claims)
        return True

    async def revoke_family(self, family_id: str) -> None:
        for jti in self.families.get(family_id, set()):
            self.refresh_sessions[jti]["status"] = "revoked"

    async def revoke_access(self, jti: str, exp: int) -> None:
        self.revoked_access.add(jti)

    async def is_access_revoked(self, jti: str) -> bool:
        return jti in self.revoked_access

    @staticmethod
    def _login_key(email: str, ip_address: str) -> str:
        return f"{email.lower()}|{ip_address}"

    async def login_retry_after(self, email: str, ip_address: str) -> int:
        key = self._login_key(email, ip_address)
        return 300 if self.login_failures[key] >= 5 else 0

    async def record_login_failure(self, email: str, ip_address: str) -> None:
        self.login_failures[self._login_key(email, ip_address)] += 1

    async def clear_login_failures(self, email: str, ip_address: str) -> None:
        self.login_failures.pop(self._login_key(email, ip_address), None)


@pytest.fixture
async def test_engine():
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest.fixture
async def session_factory(test_engine):
    return async_sessionmaker(test_engine, expire_on_commit=False)


@pytest.fixture
async def seeded_users(session_factory):
    async with session_factory() as session:
        department = Department(
            department_name="Information Technology",
            description="Bộ phận CNTT",
            is_active=True,
        )
        requester_role = Role(
            role_code="REQUESTER",
            role_name="Người gửi yêu cầu",
            is_active=True,
        )
        processor_role = Role(
            role_code="PROCESSOR",
            role_name="Người xử lý",
            is_active=True,
        )
        admin_role = Role(
            role_code="ADMIN",
            role_name="Quản trị viên",
            is_active=True,
        )
        active_category = Category(
            category_name="Phần mềm",
            description="Ứng dụng nghiệp vụ",
            is_active=True,
        )
        inactive_category = Category(
            category_name="Danh mục ngừng dùng",
            description="Dùng để kiểm thử",
            is_active=False,
        )
        active_priority = Priority(
            priority_code="P3",
            priority_level=3,
            priority_name="Trung bình",
            description="Mức ưu tiên mặc định",
            is_active=True,
        )
        inactive_priority = Priority(
            priority_code="P4",
            priority_level=4,
            priority_name="Mức cũ",
            description="Dùng để kiểm thử",
            is_active=False,
        )
        new_status = TicketStatus(
            status_code="NEW",
            status_name="Mới",
            is_terminal=False,
            description="Ticket vừa được tạo",
        )
        session.add_all(
            [
                department,
                requester_role,
                processor_role,
                admin_role,
                active_category,
                inactive_category,
                active_priority,
                inactive_priority,
                new_status,
            ]
        )
        await session.flush()

        active_user = User(
            email="requester@example.com",
            full_name="Requester Active",
            password_hash=hash_password("CorrectPassword123!"),
            is_active=True,
        )
        inactive_user = User(
            email="inactive@example.com",
            full_name="Requester Inactive",
            password_hash=hash_password("CorrectPassword123!"),
            is_active=False,
        )
        processor_user = User(
            email="processor@example.com",
            full_name="Processor Active",
            password_hash=hash_password("CorrectPassword123!"),
            department_id=department.department_id,
            is_active=True,
        )
        admin_user = User(
            email="admin@example.com",
            full_name="Admin Active",
            password_hash=hash_password("CorrectPassword123!"),
            department_id=department.department_id,
            is_active=True,
        )
        session.add_all([active_user, inactive_user, processor_user, admin_user])
        await session.flush()
        session.add_all(
            [
                UserRole(user_id=active_user.user_id, role_id=requester_role.role_id),
                UserRole(user_id=inactive_user.user_id, role_id=requester_role.role_id),
                UserRole(user_id=processor_user.user_id, role_id=processor_role.role_id),
                UserRole(user_id=admin_user.user_id, role_id=admin_role.role_id),
            ]
        )
        await session.commit()
    return {
        "active_email": "requester@example.com",
        "inactive_email": "inactive@example.com",
        "processor_email": "processor@example.com",
        "admin_email": "admin@example.com",
        "password": "CorrectPassword123!",
        "active_user_id": active_user.user_id,
        "inactive_user_id": inactive_user.user_id,
        "processor_user_id": processor_user.user_id,
        "admin_user_id": admin_user.user_id,
        "requester_role_id": requester_role.role_id,
        "processor_role_id": processor_role.role_id,
        "admin_role_id": admin_role.role_id,
        "department_id": department.department_id,
        "active_category_id": active_category.category_id,
        "inactive_category_id": inactive_category.category_id,
        "active_priority_id": active_priority.priority_id,
        "inactive_priority_id": inactive_priority.priority_id,
    }


@pytest.fixture
async def store():
    return FakeSessionStore()


@pytest.fixture
async def client(session_factory, store, seeded_users):
    async def override_get_db():
        async with session_factory() as session:
            yield session

    def override_store():
        return store

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_session_store] = override_store
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def credentials(seeded_users):
    return {
        "email": seeded_users["active_email"],
        "password": seeded_users["password"],
    }


@pytest.fixture
def admin_credentials(seeded_users):
    return {
        "email": seeded_users["admin_email"],
        "password": seeded_users["password"],
    }


@pytest.fixture
def processor_credentials(seeded_users):
    return {
        "email": seeded_users["processor_email"],
        "password": seeded_users["password"],
    }


async def login_client(client: AsyncClient, credentials: dict[str, str]) -> dict[str, Any]:
    response = await client.post("/api/v1/auth/login", json=credentials)
    assert response.status_code == 200, response.text
    return response.json()["data"]
