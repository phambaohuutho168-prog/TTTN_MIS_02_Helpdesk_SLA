import uuid
from datetime import datetime
from fastapi import FastAPI, Request, Depends, status, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.config import settings
from app.database import engine, Base, get_db
from app.rbac import PermissionChecker, RoleEnum
from app.models import Ticket
from app.schemas import TicketCreate, TicketResponse

# Tự động tạo các bảng trong DB
Base.metadata.create_all(bind=engine)

# Định nghĩa các nhóm API hiển thị trên Swagger UI (Đã đồng bộ tên nhóm và bỏ CV027)
tags_metadata = [
    {
        "name": "1. Hệ thống",
        "description": "Các đường dẫn kiểm tra trạng thái và giao diện chính.",
    },
    {
        "name": "2. Phân quyền (RBAC)",
        "description": "Các API yêu cầu xác thực vai trò người dùng (Quản trị viên / Người xử lý / Người gửi yêu cầu).",
    },
    {
        "name": "3. Quản lý Ticket",
        "description": "Chức năng tạo và quản lý các yêu cầu hỗ trợ SLA.",
    },
]

app = FastAPI(
    title="Hệ Thống Helpdesk SLA",
    description="Tài liệu hướng dẫn và thử nghiệm API của Hệ Thống Helpdesk SLA.",
    version="1.0.0",
    openapi_tags=tags_metadata
)

app.mount("/static", StaticFiles(directory="app/static"), name="static")
templates = Jinja2Templates(directory="templates")

# --- 1. HỆ THỐNG ---

@app.get(
    "/",
    summary="Trang chủ ứng dụng",
    description="Trả về giao diện HTML trang chủ của hệ thống.",
    tags=["1. Hệ thống"]
)
def home_page(request: Request, db: Session = Depends(get_db)):
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={"app_name": settings.APP_NAME, "db_status": "SQLite Connected"}
    )

@app.get(
    "/healthcheck",
    summary="Kiểm tra kết nối",
    description="Trả về trạng thái hoạt động của Server.",
    tags=["1. Hệ thống"]
)
def health_check():
    return {"status": "ok"}

# --- 2. PHÂN QUYỀN (RBAC) ---

@app.get(
    "/api/admin/settings",
    summary="Cấu hình Quản trị viên",
    description="Yêu cầu vai trò: **admin**. Từ chối truy cập đối với vai trò khác.",
    dependencies=[Depends(PermissionChecker([RoleEnum.ADMIN]))],
    tags=["2. Phân quyền (RBAC)"]
)
def admin_only():
    return {"message": "Bạn đã truy cập vào khu vực Cấu hình Quản trị viên thành công!"}

@app.get(
    "/api/tickets/manage",
    summary="Quản lý Yêu cầu (Ticket)",
    description="Yêu cầu vai trò: **admin** hoặc **handler**.",
    dependencies=[Depends(PermissionChecker([RoleEnum.ADMIN, RoleEnum.HANDLER]))],
    tags=["2. Phân quyền (RBAC)"]
)
def handler_and_admin():
    return {"message": "Bạn đã truy cập vào khu vực Xử lý Ticket!"}

# --- 3. QUẢN LÝ TICKET ---

@app.post(
    "/api/tickets",
    response_model=TicketResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Tạo yêu cầu hỗ trợ mới (Create Ticket)",
    description="Người gửi nhập thông tin ticket; hệ thống tự động sinh Mã Ticket và Thời gian tạo.",
    tags=["3. Quản lý Ticket"]
)
def create_ticket(ticket_data: TicketCreate, db: Session = Depends(get_db)):
    # 1. Tự động sinh mã Ticket duy nhất (VD: TK-20260826-8A3F)
    today_str = datetime.now().strftime("%Y%m%d")
    random_code = str(uuid.uuid4())[:4].upper()
    generated_code = f"TK-{today_str}-{random_code}"

    # 2. Khởi tạo đối tượng Ticket mới
    new_ticket = Ticket(
        ticket_code=generated_code,
        title=ticket_data.title,
        description=ticket_data.description,
        category=ticket_data.category,
        priority=ticket_data.priority,
        status="Mới",
        created_at=datetime.now()
    )

    # 3. Lưu vào Cơ sở dữ liệu SQLite
    db.add(new_ticket)
    db.commit()
    db.refresh(new_ticket)

    return new_ticket