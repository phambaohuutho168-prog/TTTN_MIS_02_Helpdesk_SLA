# CV033 - Workflow chuyển trạng thái ticket

## 1. Kết quả cần đạt

Workflow chỉ cho phép tám transition hợp lệ, kiểm tra vai trò và phạm vi dữ
liệu, đồng thời ghi lịch sử trạng thái và audit trong cùng transaction. Các
transition sai trạng thái hoặc sai quyền không được làm thay đổi dữ liệu.

## 2. Chuẩn bị PowerShell

Mở terminal tại thư mục `Code` rồi chạy:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

Nếu chưa có `.venv`:

```powershell
py -m venv .venv
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

## 3. Khởi động dịch vụ và cập nhật database

```powershell
docker compose up -d
docker compose ps
python -m alembic upgrade head
python -m alembic current
```

Kết quả migration phải là:

```text
20260828_0008 (head)
```

Migration mới tạo `sla_pause_periods`, dùng để lưu chính xác thời điểm dừng,
tiếp tục và tổng thời gian pause của Resolution SLA.

## 4. Chạy kiểm thử

```powershell
python -m pytest .\tests\workflow\test_workflow.py -v
python -m pytest
```

Kết quả mong đợi:

- CV033: `19 passed`.
- Toàn bộ dự án: `130 passed`.

## 5. Chạy ứng dụng

```powershell
python -m uvicorn app.main:app --reload
```

Mở `http://127.0.0.1:8000/docs`, đăng nhập tại `POST /api/v1/auth/login`, sao
chép `access_token`, bấm **Authorize** và nhập `Bearer <access_token>`.

## 6. Thử workflow đúng thứ tự

1. Admin phân công ticket `NEW` bằng ASN-01 để ticket thành `ASSIGNED`.
2. Processor gọi WF-01 để chuyển sang `IN_PROGRESS`.
3. Processor có thể gọi WF-02 để yêu cầu bổ sung; Requester gọi WF-03 để tiếp tục.
4. Processor gọi WF-04 và nhập kết quả xử lý để chuyển sang `RESOLVED`.
5. Requester gọi WF-05 nếu đồng ý, hoặc WF-06 trong 72 giờ nếu không đồng ý.
6. Sau WF-06, Processor gọi WF-07 để bắt đầu chu kỳ xử lý mới.
7. Với ticket `NEW` không hợp lệ, Admin dùng WF-08 và bắt buộc nhập lý do.

## 7. Kiểm tra minh chứng

Lưu các minh chứng sau cho báo cáo:

- Ảnh Swagger hiển thị đủ WF-01 đến WF-08.
- Kết quả `20260828_0008 (head)`.
- Kết quả `19 passed` và `130 passed`.
- Một response thành công và một response `INVALID_STATE_TRANSITION`.
- Dữ liệu tương ứng trong `ticket_status_history`, `audit_logs` và
  `sla_pause_periods`.

## 8. Commit đề xuất

```text
Branch: feature/ticket-workflow
Commit: feat(workflow): enforce ticket state transitions
```

Trước khi commit, xác nhận `.env`, `.venv`, cache, database cục bộ và thư mục
upload không xuất hiện trong danh sách changed files.
