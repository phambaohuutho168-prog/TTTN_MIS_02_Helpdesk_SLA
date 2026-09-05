from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies.authorization import ProcessorOrAdminContext
from app.core.response import success_response
from app.database.session import get_db
from app.schemas.common import SuccessResponse
from app.schemas.dashboard import (
    DashboardOverviewResponse,
    DashboardQuery,
    SLAPerformanceResponse,
)
from app.services import dashboard_service


router = APIRouter(prefix="/dashboard", tags=["Dashboard"])


@router.get(
    "/overview",
    response_model=SuccessResponse[DashboardOverviewResponse],
    summary="RPT-01 - KPI tổng quan dashboard",
)
async def get_dashboard_overview(
    request: Request,
    filters: Annotated[DashboardQuery, Query()],
    context: ProcessorOrAdminContext,
    session: Annotated[AsyncSession, Depends(get_db)],
):
    data = await dashboard_service.get_dashboard_overview(
        session,
        current_user=context.user,
        query=filters,
    )
    return success_response(
        request,
        data=data,
        code="DASHBOARD_OVERVIEW_RETRIEVED",
        message="Lấy KPI tổng quan dashboard thành công.",
    )


@router.get(
    "/sla-performance",
    response_model=SuccessResponse[SLAPerformanceResponse],
    summary="RPT-02 - Hiệu suất SLA",
)
async def get_sla_performance(
    request: Request,
    filters: Annotated[DashboardQuery, Query()],
    context: ProcessorOrAdminContext,
    session: Annotated[AsyncSession, Depends(get_db)],
):
    data = await dashboard_service.get_sla_performance(
        session,
        current_user=context.user,
        query=filters,
    )
    return success_response(
        request,
        data=data,
        code="SLA_PERFORMANCE_RETRIEVED",
        message="Lấy hiệu suất SLA thành công.",
    )
