# Helpdesk Request and SLA Management System

Mã nguồn CV023 (Project skeleton) và CV024 (Authentication) của đề tài thực tập tốt nghiệp.

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

Các test CV023-CV024 bao phủ healthcheck, đăng nhập đúng/sai, tài khoản inactive, thiếu token, refresh rotation, reuse detection, logout/revocation và cập nhật hồ sơ.

## 8. Kiểm tra secret trước khi commit

```powershell
git check-ignore .env
git ls-files | Select-String -Pattern '(^|/)\.env$|\.db$|\.sqlite$'
```

Lệnh thứ hai không được trả về `.env` hoặc database local.

Commit đề xuất:

```text
feat(auth): complete project skeleton and secure authentication
```
