from datetime import datetime
from typing import Literal

from pydantic import BaseModel

from app.schemas.ticket import PriorityBrief


class SLAStatusResponse(BaseModel):
    code: Literal["ON_TRACK", "NEAR_DUE", "OVERDUE", "MET", "NOT_APPLICABLE"]
    label: str
    tone: Literal["INFO", "WARNING", "DANGER", "SUCCESS", "MUTED"]
    css_class: str


class TicketSLAItemResponse(BaseModel):
    ticket_sla_id: int
    sla_policy_id: int
    policy_version: int
    sla_type: str
    cycle_no: int
    target_minutes: int
    warning_percent: int
    escalation_percent: int
    started_at: datetime
    base_due_at: datetime
    due_at: datetime
    effective_due_at: datetime
    completed_at: datetime | None
    paused_at: datetime | None
    total_paused_seconds: int
    runtime_status: str
    result: str | None
    elapsed_seconds: int | None
    remaining_seconds: int | None
    progress_percent: float | None
    status: SLAStatusResponse


class TicketSLASummaryResponse(BaseModel):
    response_sla: TicketSLAItemResponse | None
    resolution_cycles: list[TicketSLAItemResponse]
    overall_status: SLAStatusResponse | None


class TicketSLAResponse(BaseModel):
    ticket_id: int
    ticket_code: str
    priority: PriorityBrief
    first_response_at: datetime | None
    response_sla: TicketSLAItemResponse | None
    resolution_cycles: list[TicketSLAItemResponse]
    overall_status: SLAStatusResponse
