from datetime import datetime
from ipaddress import ip_address as parse_ip_address
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.request_context import current_client_ip, current_request_id
from app.models.audit_log import AuditLog
from app.schemas.audit import AuditLogQuery


SENSITIVE_KEY_PARTS = (
    "password",
    "secret",
    "token",
    "authorization",
    "storage_path",
)
REDACTED = "[REDACTED]"


def sanitize_audit_value(value: Any) -> Any:
    """Recursively redact credentials and private storage locations."""

    if isinstance(value, dict):
        sanitized: dict[str, Any] = {}
        for key, item in value.items():
            normalized_key = str(key).lower()
            sanitized[str(key)] = (
                REDACTED
                if any(part in normalized_key for part in SENSITIVE_KEY_PARTS)
                else sanitize_audit_value(item)
            )
        return sanitized
    if isinstance(value, (list, tuple, set)):
        return [sanitize_audit_value(item) for item in value]
    if isinstance(value, datetime):
        return value.isoformat()
    return value


def normalize_ip_address(value: str | None) -> str | None:
    candidate = value or current_client_ip()
    if not candidate or candidate == "unknown":
        return None
    try:
        return str(parse_ip_address(candidate))
    except ValueError:
        return None


async def append_audit(
    session: AsyncSession,
    *,
    action_code: str,
    entity_type: str,
    entity_id: int | None = None,
    actor_user_id: int | None = None,
    ticket_id: int | None = None,
    old_value: dict[str, Any] | None = None,
    new_value: dict[str, Any] | None = None,
    reason: str | None = None,
    ip_address: str | None = None,
    request_id: str | None = None,
) -> AuditLog:
    audit = AuditLog(
        actor_user_id=actor_user_id,
        ticket_id=ticket_id,
        action_code=action_code.strip().upper(),
        entity_type=entity_type.strip().upper(),
        entity_id=entity_id,
        old_value_json=sanitize_audit_value(old_value),
        new_value_json=sanitize_audit_value(new_value),
        reason=reason,
        ip_address=normalize_ip_address(ip_address),
        request_id=request_id or current_request_id(),
    )
    session.add(audit)
    await session.flush()
    return audit


def _conditions(query: AuditLogQuery):
    conditions = []
    if query.actor_user_id is not None:
        conditions.append(AuditLog.actor_user_id == query.actor_user_id)
    if query.ticket_id is not None:
        conditions.append(AuditLog.ticket_id == query.ticket_id)
    if query.action_code is not None:
        conditions.append(AuditLog.action_code == query.action_code)
    if query.entity_type is not None:
        conditions.append(AuditLog.entity_type == query.entity_type)
    if query.entity_id is not None:
        conditions.append(AuditLog.entity_id == query.entity_id)
    if query.created_from is not None:
        conditions.append(AuditLog.created_at >= query.created_from)
    if query.created_to is not None:
        conditions.append(AuditLog.created_at <= query.created_to)
    return conditions


async def list_audit_logs(
    session: AsyncSession,
    *,
    query: AuditLogQuery,
) -> tuple[list[AuditLog], int]:
    conditions = _conditions(query)
    total = await session.scalar(
        select(func.count(AuditLog.audit_id)).where(*conditions)
    )
    result = await session.execute(
        select(AuditLog)
        .where(*conditions)
        .order_by(AuditLog.created_at.desc(), AuditLog.audit_id.desc())
        .offset((query.page - 1) * query.page_size)
        .limit(query.page_size)
    )
    return list(result.scalars().all()), int(total or 0)
