from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.attachment import AttachmentResponse
from app.schemas.ticket import (
    CategoryBrief,
    PriorityBrief,
    TicketStatusBrief,
    TicketUserBrief,
)


class TicketTimelineQuery(BaseModel):
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=100)

    model_config = ConfigDict(extra="forbid")


class AssignmentResponse(BaseModel):
    assignment_id: int
    ticket_id: int
    assignee: TicketUserBrief
    assigned_by: TicketUserBrief
    assigned_at: datetime
    ended_at: datetime | None
    is_current: bool
    reason: str | None


class StatusHistoryResponse(BaseModel):
    history_id: int
    ticket_id: int
    from_status_code: str | None
    to_status_code: str
    changed_by: TicketUserBrief | None
    reason: str | None
    changed_at: datetime


class CommentResponse(BaseModel):
    comment_id: int
    ticket_id: int
    author: TicketUserBrief
    content: str
    visibility: str
    comment_type: str
    attachments: list[AttachmentResponse]
    created_at: datetime
    updated_at: datetime | None


class TicketResolutionResponse(BaseModel):
    resolution_id: int
    ticket_id: int
    resolved_by: TicketUserBrief
    cycle_no: int
    resolution_note: str
    resolved_at: datetime


class TicketSLAItemResponse(BaseModel):
    ticket_sla_id: int
    sla_type: str
    cycle_no: int
    started_at: datetime
    due_at: datetime
    completed_at: datetime | None
    paused_at: datetime | None
    total_paused_seconds: int
    runtime_status: str
    result: str | None
    remaining_seconds: int | None


class TicketSLASummaryResponse(BaseModel):
    response_sla: TicketSLAItemResponse | None
    resolution_cycles: list[TicketSLAItemResponse]


class TicketDetailResponse(BaseModel):
    ticket_id: int
    ticket_code: str
    title: str
    description: str
    category: CategoryBrief
    priority: PriorityBrief
    status: TicketStatusBrief
    requester: TicketUserBrief
    current_assignee: TicketUserBrief | None
    current_assignment: AssignmentResponse | None
    attachments: list[AttachmentResponse]
    resolutions: list[TicketResolutionResponse]
    first_response_at: datetime | None
    closed_at: datetime | None
    rejected_at: datetime | None
    rejection_reason: str | None
    permissions: list[str]
    sla_summary: TicketSLASummaryResponse
    created_at: datetime
    updated_at: datetime
