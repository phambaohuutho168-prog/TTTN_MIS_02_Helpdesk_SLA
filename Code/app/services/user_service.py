from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.repositories.user_repository import update_profile
from app.schemas.user import ProfileUpdateRequest, UserDetail
from app.services.auth_service import build_user_detail


async def update_own_profile(
    session: AsyncSession,
    user: User,
    payload: ProfileUpdateRequest,
) -> UserDetail:
    updated = await update_profile(
        session,
        user,
        full_name=payload.full_name,
        phone=payload.phone,
        provided_fields=payload.model_fields_set,
    )
    return build_user_detail(updated)
