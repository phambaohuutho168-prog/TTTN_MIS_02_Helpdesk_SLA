from pydantic import BaseModel
from datetime import datetime
from typing import Optional

# Dữ liệu người dùng nhập khi tạo Ticket
class TicketCreate(BaseModel):
    title: str
    description: str
    category: str
    priority: Optional[str] = "Trung bình"

# Dữ liệu hệ thống phản hồi sau khi tạo thành công
class TicketResponse(BaseModel):
    id: int
    ticket_code: str
    title: str
    description: str
    category: str
    priority: str
    status: str
    created_at: datetime

    class Config:
        from_attributes = True