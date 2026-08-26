from fastapi import FastAPI, Request, Depends
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.config import settings
from app.database import engine, Base, get_db
from app.rbac import PermissionChecker, RoleEnum

Base.metadata.create_all(bind=engine)

# Mô tả các nhóm API 
tags_metadata = [
    {
        "name": "1. Hệ thống",
        "description": "Các đường dẫn kiểm tra trạng thái và giao diện chính.",
    },
    {
        "name": "2. Phân quyền (RBAC)",
        "description": "Các API yêu cầu xác thực vai trò người dùng (Quản trị viên / Người xử lí / Người gửi yêu cầu).",
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

# --- DEMO CÁC API PHÂN QUYỀN RBAC ---

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