from collections.abc import Awaitable, Callable
from typing import Annotated

from fastapi import Depends

from app.api.dependencies.authentication import get_auth_context
from app.core.errors import AppError
from app.core.rbac import RoleCode
from app.services.auth_service import AuthContext


RoleDependency = Callable[[AuthContext], Awaitable[AuthContext]]


def require_roles(*allowed_roles: RoleCode) -> RoleDependency:
    """Enforce at least one role using current database assignments.

    JWT role claims and client headers are not trusted for the final decision,
    because assignments may change after a token is issued.
    """

    if not allowed_roles:
        raise ValueError("require_roles cần ít nhất một vai trò được phép.")

    allowed_codes = frozenset(role.value for role in allowed_roles)

    async def authorize(
        context: Annotated[AuthContext, Depends(get_auth_context)],
    ) -> AuthContext:
        database_role_codes = set(context.user.role_codes)
        if database_role_codes.isdisjoint(allowed_codes):
            raise AppError(
                403,
                "FORBIDDEN_ACTION",
                "Bạn không có quyền thực hiện thao tác này.",
            )
        return context

    return authorize


AnyBusinessRoleContext = Annotated[
    AuthContext,
    Depends(
        require_roles(
            RoleCode.REQUESTER,
            RoleCode.PROCESSOR,
            RoleCode.ADMIN,
        )
    ),
]
RequesterContext = Annotated[
    AuthContext,
    Depends(require_roles(RoleCode.REQUESTER)),
]
ProcessorContext = Annotated[
    AuthContext,
    Depends(require_roles(RoleCode.PROCESSOR)),
]
ProcessorOrAdminContext = Annotated[
    AuthContext,
    Depends(require_roles(RoleCode.PROCESSOR, RoleCode.ADMIN)),
]
AdminContext = Annotated[
    AuthContext,
    Depends(require_roles(RoleCode.ADMIN)),
]
