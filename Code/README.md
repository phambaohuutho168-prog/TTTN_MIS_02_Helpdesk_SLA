# Helpdesk Request and SLA Management System

Mã nguồn CV023–CV037 của đề tài thực tập tốt nghiệp: môi trường, xác thực,
RBAC, quản trị tài khoản/vai trò, ticket, danh mục/ưu tiên, attachment, danh
sách/bộ lọc, chi tiết/lịch sử, phân công, workflow, trao đổi, audit log và SLA.

## Công nghệ

- Python 3.11+, FastAPI và Pydantic v2
- SQLAlchemy 2.x AsyncIO và Alembic
- PostgreSQL và Redis
- JWT Bearer; Access Token 15 phút; Refresh Token 7 ngày có rotation
- Argon2id qua `pwdlib`

## 1. Chuẩn bị trên Windows PowerShell

Mở Terminal tại thư mục `Code`:

```powershell
py -m venv .venv
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

## 2. Tạo cấu hình cục bộ

```powershell
Copy-Item .env.example .env
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

Mở `.env`, thay `SECRET_KEY` và tất cả giá trị `CHANGE_ME` bằng giá trị chỉ
dùng trên máy cục bộ. Không commit `.env`.

## 3. Chạy PostgreSQL, Redis và migration

Yêu cầu Docker Desktop đang hoạt động:

```powershell
docker compose up -d
docker compose ps
python -m alembic upgrade head
python -m alembic current
```

Hai service phải ở trạng thái `healthy`; Alembic phải trả về
`20260828_0009 (head)`.

Tạo dữ liệu ban đầu sau khi đã đặt các biến `SEED_ADMIN_*` trong `.env`:

```powershell
python -m scripts.seed_initial_data
```

## 4. Chạy ứng dụng

```powershell
python -m uvicorn app.main:app --reload
```

- Trang chính: <http://127.0.0.1:8000/>
- Swagger: <http://127.0.0.1:8000/docs>
- Liveness: <http://127.0.0.1:8000/api/v1/health/live>
- Readiness: <http://127.0.0.1:8000/api/v1/health/ready>

## 5. API Workflow CV033

| ID | Phương thức và endpoint | Transition | Quyền chính |
| --- | --- | --- | --- |
| WF-01 | `POST /api/v1/tickets/{ticket_id}/start` | `ASSIGNED -> IN_PROGRESS` | Processor đang được phân công hoặc Admin |
| WF-02 | `POST /api/v1/tickets/{ticket_id}/request-info` | `IN_PROGRESS -> PENDING_INFO` | Processor đang được phân công hoặc Admin |
| WF-03 | `POST /api/v1/tickets/{ticket_id}/provide-info` | `PENDING_INFO -> IN_PROGRESS` | Requester sở hữu ticket |
| WF-04 | `POST /api/v1/tickets/{ticket_id}/resolve` | `IN_PROGRESS -> RESOLVED` | Processor đang được phân công hoặc Admin |
| WF-05 | `POST /api/v1/tickets/{ticket_id}/close` | `RESOLVED -> CLOSED` | Requester sở hữu hoặc Admin |
| WF-06 | `POST /api/v1/tickets/{ticket_id}/reopen` | `RESOLVED -> REOPENED` | Requester sở hữu, trong 72 giờ |
| WF-07 | `POST /api/v1/tickets/{ticket_id}/resume` | `REOPENED -> IN_PROGRESS` | Processor đang được phân công hoặc Admin |
| WF-08 | `POST /api/v1/tickets/{ticket_id}/reject` | `NEW -> REJECTED` | Chỉ Admin |

Mỗi transition hợp lệ cập nhật ticket, tạo `ticket_status_history` và ghi
`audit_logs` trong cùng transaction. WF-02/WF-03 ghi nhận khoảng dừng SLA;
WF-04 hoàn tất chu kỳ SLA hiện tại; WF-07 tạo chu kỳ Resolution SLA mới;
WF-08 kết thúc các SLA còn chạy. `CLOSED` và `REJECTED` là trạng thái cuối.

Tự động đóng ticket `RESOLVED` quá 72 giờ bằng tác nhân hệ thống:

```powershell
python -m scripts.auto_close_resolved
```

## 6. SLA engine CV036

Khi tạo ticket, hệ thống chọn phiên bản SLA policy đang hiệu lực theo mức ưu
tiên và tạo hai runtime: `RESPONSE` và `RESOLUTION`. Mốc phản hồi được lưu khi
người xử lý hiện tại gửi phản hồi công khai đầu tiên; mốc hoàn tất được lưu khi
ticket chuyển sang `RESOLVED`. Resolution SLA dừng trong `PENDING_INFO`, tiếp
tục sau khi requester bổ sung thông tin và tạo chu kỳ mới khi ticket mở lại.

Rule mặc định do `scripts.seed_initial_data` tạo (đơn vị: phút):

| Ưu tiên | Phản hồi | Xử lý |
| --- | ---: | ---: |
| P1 | 15 | 240 |
| P2 | 30 | 480 |
| P3 | 60 | 1440 |
| P4 | 240 | 2880 |

Xem SLA của ticket bằng endpoint có kiểm tra phạm vi truy cập:

```text
GET /api/v1/tickets/{ticket_id}/sla
```

`due_at`/`base_due_at` là deadline gốc theo policy; `effective_due_at` là
deadline hiệu lực sau các khoảng pause đã hoàn tất. Hệ thống đang tính theo
phút lịch UTC vì chưa có lịch làm việc/ngày nghỉ trong mô hình dữ liệu hiện tại.

## 7. Trạng thái SLA CV037

SLA-01 và phần `sla_summary` trong chi tiết ticket trả về `status` cho từng
runtime cùng `overall_status` của ticket. Giao diện dùng cùng `code` và
`css_class`, nên màu sắc không bị lệch với business rule phía server.

| Mã | Nhãn giao diện | Điều kiện |
| --- | --- | --- |
| `ON_TRACK` | Còn hạn | Chưa đạt `warning_percent` |
| `NEAR_DUE` | Sắp quá hạn | Đạt ngưỡng cảnh báo nhưng chưa trễ deadline |
| `OVERDUE` | Quá hạn | Đã trễ deadline hoặc kết quả là `BREACHED` |
| `MET` | Đúng SLA | Runtime hoàn tất trong deadline hiệu lực |
| `NOT_APPLICABLE` | Không áp dụng | SLA không áp dụng cho ticket |

`runtime_status=PAUSED` vẫn được giữ riêng; trạng thái hiển thị được đóng băng
tại thời điểm pause. Trang chủ `/` có bộ badge màu minh họa bốn trạng thái
chính.

## 8. Chạy kiểm thử

```powershell
python -m pytest .\tests\sla\test_sla_status.py -v
python -m pytest
```

Kết quả mong đợi:

- CV037: `13 passed`.
- Toàn bộ CV023–CV037: `175 passed`.

## 9. Kiểm tra secret trước khi commit

```powershell
git check-ignore .env
git ls-files | Select-String -Pattern '(^|/)\.env$|\.db$|\.sqlite$'
```

Lệnh thứ hai không được trả về `.env` hoặc database local.

Branch và commit đề xuất:

```text
feature/sla-status
feat(sla): expose SLA status for API and UI
```

