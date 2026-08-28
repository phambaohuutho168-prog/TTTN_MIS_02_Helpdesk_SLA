from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, Request
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.errors import AppError
from app.core.response import success_response
from app.database.session import get_db
from app.services.auth_session_store import SessionStore, get_session_store


router = APIRouter(prefix="/health", tags=["System"])


@router.get("/live", summary="SYS-01 - Liveness")
async def live(request: Request):
    return success_response(
        request,
        data={
            "status": "UP",
            "timestamp": datetime.now(timezone.utc),
            "build_id": settings.BUILD_ID,
        },
        message="API đang hoạt động.",
    )


@router.get("/ready", summary="SYS-02 - Readiness")
async def ready(
    request: Request,
    session: Annotated[AsyncSession, Depends(get_db)],
    store: Annotated[SessionStore, Depends(get_session_store)],
):
    dependencies: list[dict[str, str]] = []
    errors: list[dict[str, str]] = []

    try:
        await session.execute(text("SELECT 1"))
        dependencies.append({"name": "postgresql", "status": "UP"})
    except Exception:
        dependencies.append({"name": "postgresql", "status": "DOWN"})
        errors.append({"field": "postgresql", "message": "Không thể kết nối database."})

    try:
        await store.ping()
        dependencies.append({"name": "redis", "status": "UP"})
    except Exception:
        dependencies.append({"name": "redis", "status": "DOWN"})
        errors.append({"field": "redis", "message": "Không thể kết nối Redis."})

    if errors:
        raise AppError(
            503,
            "SERVICE_UNAVAILABLE",
            "Một hoặc nhiều dịch vụ phụ thuộc chưa sẵn sàng.",
            errors=errors,
        )

    return success_response(
        request,
        data={
            "status": "UP",
            "timestamp": datetime.now(timezone.utc),
            "build_id": settings.BUILD_ID,
            "dependencies": dependencies,
        },
        message="Ứng dụng sẵn sàng phục vụ.",
    )
