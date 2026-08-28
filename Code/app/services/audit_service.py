from math import ceil

from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories import audit_repository
from app.schemas.audit import AuditLogQuery, AuditLogResponse
from app.schemas.common import PageData


async def list_audit_logs(
    session: AsyncSession,
    *,
    query: AuditLogQuery,
) -> PageData[AuditLogResponse]:
    records, total = await audit_repository.list_audit_logs(session, query=query)
    return PageData[AuditLogResponse](
        items=[AuditLogResponse.model_validate(record) for record in records],
        page=query.page,
        page_size=query.page_size,
        total=total,
        total_pages=ceil(total / query.page_size) if total else 0,
    )
