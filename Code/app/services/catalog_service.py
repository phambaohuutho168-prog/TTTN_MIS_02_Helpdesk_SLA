from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.repositories import catalog_repository
from app.schemas.catalog import (
    CategoryCreateRequest,
    CategoryResponse,
    CategoryUpdateRequest,
    PriorityCreateRequest,
    PriorityResponse,
    PriorityUpdateRequest,
    TicketStatusResponse,
)


async def list_categories(
    session: AsyncSession,
    *,
    q: str | None,
    is_active: bool | None,
) -> list[CategoryResponse]:
    categories = await catalog_repository.list_categories(
        session,
        q=q,
        is_active=is_active,
    )
    return [CategoryResponse.model_validate(item) for item in categories]


async def create_category(
    session: AsyncSession,
    payload: CategoryCreateRequest,
) -> CategoryResponse:
    if await catalog_repository.get_category_by_name(session, payload.category_name):
        raise AppError(
            409,
            "CATEGORY_NAME_CONFLICT",
            "Tên danh mục đã tồn tại.",
        )
    try:
        category = await catalog_repository.create_category_record(
            session,
            category_name=payload.category_name,
            description=payload.description,
            is_active=payload.is_active,
        )
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise AppError(
            409,
            "CATEGORY_NAME_CONFLICT",
            "Tên danh mục đã tồn tại.",
        ) from exc
    await session.refresh(category)
    return CategoryResponse.model_validate(category)


async def update_category(
    session: AsyncSession,
    *,
    category_id: int,
    payload: CategoryUpdateRequest,
) -> CategoryResponse:
    category = await catalog_repository.get_category_by_id(session, category_id)
    if category is None:
        raise AppError(404, "CATEGORY_NOT_FOUND", "Không tìm thấy danh mục.")

    if "category_name" in payload.model_fields_set:
        duplicate = await catalog_repository.get_category_by_name(
            session,
            payload.category_name or "",
        )
        if duplicate is not None and duplicate.category_id != category_id:
            raise AppError(
                409,
                "CATEGORY_NAME_CONFLICT",
                "Tên danh mục đã tồn tại.",
            )
        category.category_name = payload.category_name  # type: ignore[assignment]
    if "description" in payload.model_fields_set:
        category.description = payload.description
    if "is_active" in payload.model_fields_set:
        category.is_active = payload.is_active  # type: ignore[assignment]

    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise AppError(
            409,
            "CATEGORY_NAME_CONFLICT",
            "Tên danh mục đã tồn tại.",
        ) from exc
    await session.refresh(category)
    return CategoryResponse.model_validate(category)


async def list_priorities(
    session: AsyncSession,
    *,
    q: str | None,
    is_active: bool | None,
) -> list[PriorityResponse]:
    priorities = await catalog_repository.list_priorities(
        session,
        q=q,
        is_active=is_active,
    )
    return [PriorityResponse.model_validate(item) for item in priorities]


async def create_priority(
    session: AsyncSession,
    payload: PriorityCreateRequest,
) -> PriorityResponse:
    if await catalog_repository.get_priority_by_code(session, payload.priority_code):
        raise AppError(
            409,
            "PRIORITY_CODE_CONFLICT",
            "Mã mức ưu tiên đã tồn tại.",
        )
    if await catalog_repository.get_priority_by_level(session, payload.priority_level):
        raise AppError(
            409,
            "PRIORITY_LEVEL_CONFLICT",
            "Thứ tự mức ưu tiên đã tồn tại.",
        )

    try:
        priority = await catalog_repository.create_priority_record(
            session,
            priority_code=payload.priority_code,
            priority_level=payload.priority_level,
            priority_name=payload.priority_name,
            description=payload.description,
            is_active=payload.is_active,
        )
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        if await catalog_repository.get_priority_by_code(
            session,
            payload.priority_code,
        ):
            raise AppError(
                409,
                "PRIORITY_CODE_CONFLICT",
                "Mã mức ưu tiên đã tồn tại.",
            ) from exc
        raise AppError(
            409,
            "PRIORITY_LEVEL_CONFLICT",
            "Thứ tự mức ưu tiên đã tồn tại.",
        ) from exc
    return PriorityResponse.model_validate(priority)


async def update_priority(
    session: AsyncSession,
    *,
    priority_id: int,
    payload: PriorityUpdateRequest,
) -> PriorityResponse:
    priority = await catalog_repository.get_priority_by_id(session, priority_id)
    if priority is None:
        raise AppError(404, "PRIORITY_NOT_FOUND", "Không tìm thấy mức ưu tiên.")

    if "priority_name" in payload.model_fields_set:
        priority.priority_name = payload.priority_name  # type: ignore[assignment]
    if "description" in payload.model_fields_set:
        priority.description = payload.description
    if "is_active" in payload.model_fields_set:
        priority.is_active = payload.is_active  # type: ignore[assignment]

    await session.commit()
    return PriorityResponse.model_validate(priority)


async def list_ticket_statuses(
    session: AsyncSession,
) -> list[TicketStatusResponse]:
    statuses = await catalog_repository.list_ticket_statuses(session)
    return [TicketStatusResponse.model_validate(item) for item in statuses]
