from sqlalchemy import Column, Integer, String, DateTime, Text
from sqlalchemy.sql import func
from datetime import datetime
from app.database import Base

class SystemLog(Base):
    __tablename__ = "system_logs"

    id = Column(Integer, primary_key=True, index=True)
    action = Column(String(255), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class Ticket(Base):
    __tablename__ = "tickets"

    id = Column(Integer, primary_key=True, index=True)
    ticket_code = Column(String(50), unique=True, index=True, nullable=False) # Mã ticket tự động (VD: TK-20260826-101)
    title = Column(String(255), nullable=False)                               # Tiêu đề
    description = Column(Text, nullable=False)                               # Mô tả chi tiết
    category = Column(String(100), nullable=False)                            # Danh mục (VD: Phần mềm, Phần cứng, Mạng)
    priority = Column(String(50), default="Trung bình")                       # Mức độ ưu tiên (Thấp, Trung bình, Cao, Khẩn cấp)
    status = Column(String(50), default="Mới")                                # Trạng thái ticket
    created_at = Column(DateTime, default=datetime.now)                       # Thời gian tạo tự động