from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies.authorization import AdminContext
from app.core.response import success_response
from app.database.session import get_db
from app.schemas.audit import AuditLogQuery, AuditLogResponse
from app.schemas.common import PageData, SuccessResponse
from app.services import audit_service


router = APIRouter(prefix="/admin/audit-logs", tags=["Admin - Audit Log"])


@router.get(
    "",
    response_model=SuccessResponse[PageData[AuditLogResponse]],
    summary="ADM-08 - Tra cứu Audit Log",
)
async def list_audit_logs(
    request: Request,
    filters: Annotated[AuditLogQuery, Query()],
    _context: AdminContext,
    session: Annotated[AsyncSession, Depends(get_db)],
):
    data = await audit_service.list_audit_logs(session, query=filters)
    return success_response(
        request,
        data=data,
        code="AUDIT_LOG_LISTED",
        message="Lấy nhật ký kiểm toán thành công.",
    )
