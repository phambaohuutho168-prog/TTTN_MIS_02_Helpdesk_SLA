from datetime import datetime

from pydantic import BaseModel, ConfigDict


class AttachmentResponse(BaseModel):
    attachment_id: int
    ticket_id: int
    comment_id: int | None
    file_name: str
    mime_type: str
    file_size: int
    uploaded_by: int
    uploaded_at: datetime

    model_config = ConfigDict(from_attributes=True)
