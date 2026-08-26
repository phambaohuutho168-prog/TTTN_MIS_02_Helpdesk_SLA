from fastapi import Header, HTTPException, status
from enum import Enum

class RoleEnum(str, Enum):
    ADMIN = "admin"
    HANDLER = "handler"
    USER = "user"

class PermissionChecker:
    """Dependency kiểm tra vai trò người dùng (RBAC)"""
    def __init__(self, allowed_roles: list[RoleEnum]):
        self.allowed_roles = [role.value for role in allowed_roles]

    def __call__(self, x_user_role: str = Header(default="user", alias="X-User-Role")):
        # Kiểm tra vai trò gửi lên qua Header X-User-Role
        if x_user_role not in self.allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Truy cập bị từ chối: Vai trò '{x_user_role}' không có quyền thực hiện thao tác này."
            )
        return x_user_role