# Helpdesk Request and SLA Management System

Mã nguồn từ CV023 đến CV032 của đề tài thực tập tốt nghiệp: môi trường,
xác thực, RBAC, quản trị tài khoản/vai trò, tạo và phân loại ticket, đính kèm,
danh sách/bộ lọc, chi tiết ticket, lịch sử thay đổi và phân công người xử lý.

## Công nghệ

- Python 3.11+
- FastAPI, Pydantic v2
- SQLAlchemy 2.x AsyncIO, Alembic
- PostgreSQL
- Redis
- JWT Bearer; Access Token 15 phút; Refresh Token 7 ngày có rotation
- Argon2id qua `pwdlib`

## 1. Chuẩn bị trên Windows PowerShell

Mở Terminal tại thư mục `Code`:

```powershell
py -m venv .venv
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
```

## 2. Tạo cấu hình cục bộ

```powershell
Copy-Item .env.example .env
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

Mở `.env`, thay `SECRET_KEY` bằng chuỗi vừa tạo. Đồng thời thay tất cả giá trị `CHANGE_ME` bằng giá trị chỉ dùng trên máy cục bộ. Không commit `.env`.

## 3. Chạy PostgreSQL và Redis

Yêu cầu Docker Desktop đang hoạt động:

```powershell
docker compose up -d
docker compose ps
```

Hai service phải ở trạng thái `healthy`.

## 4. Tạo database và dữ liệu ban đầu

```powershell
alembic upgrade head
python -m scripts.seed_initial_data
```

Script seed tạo ba vai trò `REQUESTER`, `PROCESSOR`, `ADMIN` và tài khoản Admin từ các biến `SEED_ADMIN_*` trong `.env`.

## 5. Chạy ứng dụng

```powershell
python -m uvicorn app.main:app --reload
```

Kiểm tra:

- Trang chính: <http://127.0.0.1:8000/>
- Swagger: <http://127.0.0.1:8000/docs>
- Liveness: <http://127.0.0.1:8000/api/v1/health/live>
- Readiness: <http://127.0.0.1:8000/api/v1/health/ready>

## 6. API Authentication

| ID | Phương thức và endpoint | Mục đích |
| --- | --- | --- |
| AUTH-01 | `POST /api/v1/auth/login` | Đăng nhập và cấp cặp token |
| AUTH-02 | `POST /api/v1/auth/refresh` | Rotation refresh token |
| AUTH-03 | `POST /api/v1/auth/logout` | Thu hồi refresh family và access token hiện tại |
| AUTH-04 | `GET /api/v1/auth/me` | Lấy hồ sơ, phòng ban và vai trò |
| AUTH-05 | `PATCH /api/v1/users/me` | Cập nhật họ tên hoặc số điện thoại |

Ví dụ đăng nhập:

```json
{
  "email": "admin@example.com",
  "password": "mật-khẩu-đã-đặt-trong-env"
}
```

## 7. Chạy kiểm thử

```powershell
python -m pytest
```

Hiện có 111 test bao phủ CV023-CV032: healthcheck, authentication, RBAC,
quản trị user/role, ticket, catalog, attachment, data scope, phân trang,
chi tiết ticket, trao đổi, phân công/tái phân công, audit, SLA và lịch sử trạng thái.

## 8. API Ticket detail/history (CV031)

| ID | Phương thức và endpoint | Phạm vi |
| --- | --- | --- |
| TKT-03 | `GET /api/v1/tickets/{ticket_id}` | Requester sở hữu; Processor đang được phân công; Admin toàn hệ thống |
| TKT-06 | `GET /api/v1/tickets/{ticket_id}/status-history` | Theo phạm vi ticket, có phân trang |
| COM-01 | `GET /api/v1/tickets/{ticket_id}/comments` | Requester không nhận comment `INTERNAL` |
| ASN-02 | `GET /api/v1/tickets/{ticket_id}/assignments` | Processor đang xử lý hoặc Admin |

TKT-03 tổng hợp nội dung, danh mục/ưu tiên/trạng thái, người gửi, phân công
hiện tại, tệp trực tiếp, kết quả xử lý, quyền thao tác và SLA. API chỉ trả metadata
attachment an toàn; không trả `storage_path`.

Migration CV031:

```powershell
alembic upgrade head
alembic current
```

Kết quả mong đợi của lệnh thứ hai là `20260828_0007 (head)`.

## 9. API Assignment (CV032)

| ID | Phương thức và endpoint | Quyền và hành vi |
| --- | --- | --- |
| ASN-01 | `PUT /api/v1/tickets/{ticket_id}/assignment` | Chỉ `ADMIN`; phân công lần đầu hoặc tái phân công |
| ASN-02 | `GET /api/v1/tickets/{ticket_id}/assignments` | `ADMIN` hoặc Processor đang xử lý; có phân trang |

Request ASN-01:

```json
{
  "assignee_id": 12,
  "reason": "Điều chuyển do chuyên môn phù hợp hơn"
}
```

- Người nhận phải là tài khoản hoạt động và có vai trò `PROCESSOR` đang hoạt động.
- Phân công lần đầu chỉ áp dụng cho ticket `NEW`, tạo trạng thái
  `NEW -> ASSIGNED` và ghi lịch sử trạng thái.
- Tái phân công đóng bản ghi hiện tại, tạo bản ghi hiện tại mới, giữ nguyên
  trạng thái ticket và bắt buộc có `reason`.
- Phân công, lịch sử trạng thái và audit được lưu trong cùng transaction.
- Audit lưu actor, thời gian máy chủ, ticket, assignment, giá trị cũ/mới,
  lý do và IP; ứng dụng không cung cấp thao tác sửa/xóa audit.

Migration CV032:

```powershell
python -m alembic upgrade head
python -m alembic current
```

Kiểm thử riêng CV032:

```powershell
python -m pytest .\tests\assignments\test_assignment.py -v
```

## 10. Kiểm tra secret trước khi commit

```powershell
git check-ignore .env
git ls-files | Select-String -Pattern '(^|/)\.env$|\.db$|\.sqlite$'
```

Lệnh thứ hai không được trả về `.env` hoặc database local.

Branch và commit đề xuất cho CV032:

```text
feature/ticket-assignment
feat(assignment): implement ticket assignment and reassignment
```
