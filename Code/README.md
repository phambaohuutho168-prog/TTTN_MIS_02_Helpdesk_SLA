# Helpdesk Request and SLA Management System

Hệ thống quản lý yêu cầu hỗ trợ và SLA được xây dựng bằng FastAPI. Dự án bao
phủ quy trình từ tạo ticket, phân công, xử lý, theo dõi SLA, thông báo, đánh giá
đến Dashboard KPI và kiểm thử nghiệm thu.

Đề tài được triển khai theo 56 công việc, từ **CV001 đến CV056**. Mã `CVxxx`
chỉ dùng để theo dõi công việc trong kế hoạch; tên thư mục và tên file sử dụng
nội dung nghiệp vụ, không sử dụng mã công việc. Phần lập trình CV023–CV056 hiện
có **308 automated test Passed**.

## Công nghệ

- Python 3.11+
- FastAPI, Pydantic v2 và Uvicorn
- SQLAlchemy 2.x AsyncIO và Alembic
- PostgreSQL 16 và Redis 7
- JWT Bearer Authentication
- Argon2id thông qua `pwdlib`
- Pytest và Pytest AsyncIO
- HTML, CSS và JavaScript cho KPI Dashboard

## Phạm vi CV001–CV056

### Tuần 1 – Khởi động và phân tích nghiệp vụ

| Công việc | Nội dung | Kết quả |
| --- | --- | --- |
| CV001 | Khởi động đề tài và repository | Cấu trúc lưu trữ, quy tắc làm việc và quản lý phiên bản |
| CV002 | Xác định phạm vi đề tài | Phạm vi trong/ngoài hệ thống và quy trình nghiệp vụ cốt lõi |
| CV003 | Xác định stakeholder và vai trò | Requester, Processor và Admin |
| CV004 | Phân tích bài toán, mục tiêu và giá trị | Problem statement, mục tiêu và giá trị kỳ vọng |
| CV005 | Khảo sát quy trình hiện tại | Mô tả quy trình As-Is |
| CV006 | Phân tích nguyên nhân vấn đề | Nhóm nguyên nhân, điểm nghẽn và rủi ro vận hành |
| CV007 | Đề xuất quy trình tương lai | Mô tả quy trình To-Be có hệ thống hỗ trợ |
| CV008 | Xây dựng KPI | Bộ KPI phản hồi, SLA, xử lý, mở lại và hài lòng |
| CV009 | Xác định business rules | Quy tắc ticket, phân công, trạng thái, SLA và quyền |
| CV010 | Phân tích Use Case | Use Case tổng quát cho ba vai trò |
| CV011 | Xây dựng backlog | User Story và Acceptance Criteria |

### Tuần 2 – Thiết kế hệ thống

| Công việc | Nội dung | Kết quả |
| --- | --- | --- |
| CV012 | Thiết kế kiến trúc tổng thể | Kiến trúc client, server, database và các thành phần tích hợp |
| CV013 | Thiết kế phân quyền | Ma trận RBAC cho Requester, Processor và Admin |
| CV014 | Thiết kế vòng đời ticket | State machine và các transition hợp lệ |
| CV015 | Thiết kế SLA | Quy tắc SLA phản hồi và SLA xử lý |
| CV016 | Thiết kế escalation | Ngưỡng cảnh báo, quá hạn và leo thang |
| CV017 | Thiết kế ERD | Mô hình dữ liệu người dùng, ticket, SLA, audit và rating |
| CV018 | Xây dựng Data Dictionary | Khóa, kiểu dữ liệu, bắt buộc, ràng buộc và ý nghĩa nghiệp vụ |
| CV019 | Thiết kế API và mã lỗi | Endpoint, quyền, request/response và error contract |
| CV020 | Thiết kế Wireframe Requester | Tạo, theo dõi, trao đổi, mở lại và đánh giá ticket |
| CV021 | Thiết kế Wireframe Processor/Admin | Hàng đợi, phân công, SLA, workflow, Dashboard và quản trị |
| CV022 | Lập RTM và Test Plan | Traceability Matrix, phạm vi và kế hoạch kiểm thử |

### Tuần 3 – Lập trình chức năng cốt lõi

| Công việc | Nội dung | Kết quả |
| --- | --- | --- |
| CV023 | Khởi tạo dự án | Cấu hình, database, healthcheck và Docker Compose |
| CV024 | Authentication | Login, current user, refresh token và logout |
| CV025 | Authorization | RBAC và dependency kiểm tra quyền phía server |
| CV026 | Quản trị tài khoản và vai trò | API User, Role và gán/gỡ vai trò |
| CV027 | Tạo ticket | Validation, mã ticket, trạng thái ban đầu và audit |
| CV028 | Danh mục và mức ưu tiên | Category, Priority và các ràng buộc dữ liệu |
| CV029 | Attachment | Upload, kiểm tra MIME/kích thước và kiểm soát truy cập |
| CV030 | Danh sách ticket | Tìm kiếm, lọc, phân trang và giới hạn phạm vi dữ liệu |
| CV031 | Chi tiết và lịch sử | Ticket detail, status history và timeline |
| CV032 | Phân công | Phân công, tái phân công và lịch sử người xử lý |
| CV033 | Workflow | Các transition từ NEW đến CLOSED/REJECTED |
| CV034 | Trao đổi và kết quả xử lý | Comment công khai/nội bộ và solution note |
| CV035 | Audit log | Nhật ký bất biến và khả năng truy vết hành động |

### Tuần 4 – SLA, báo cáo và tích hợp

| Công việc | Nội dung | Kết quả |
| --- | --- | --- |
| CV036 | SLA engine | Tạo và cập nhật Response/Resolution SLA runtime |
| CV037 | Trạng thái SLA | On track, near due, overdue, met và not applicable |
| CV038 | Cảnh báo và escalation | Event, notification, audit và idempotency |
| CV039 | Đóng ticket | Business rules, actor đóng và tự động đóng sau 72 giờ |
| CV040 | Mở lại ticket | Cửa sổ 72 giờ và Resolution SLA cycle mới |
| CV041 | Đánh giá hài lòng | CSAT 1–5, một đánh giá cho mỗi ticket |
| CV042 | Thông báo | Hộp thư cá nhân và đánh dấu đã đọc |
| CV043 | API KPI Dashboard | KPI tổng quan và hiệu suất SLA theo phạm vi quyền |
| CV044 | Giao diện KPI Dashboard | Bộ lọc, KPI, trạng thái giao diện và responsive |
| CV045 | Dữ liệu mô phỏng | Sáu tình huống ticket cố định và seed idempotent |
| CV046 | Tích hợp end-to-end | Luồng tạo, phân công, xử lý, đóng, đánh giá và đối soát |

### Tuần 5 – Kiểm thử và đánh giá

| Công việc | Nội dung | Kết quả |
| --- | --- | --- |
| CV047 | Functional Test luồng bình thường | Tạo, phân công, phản hồi, xử lý, đóng và đánh giá |
| CV048 | SLA Test | Gần hạn, quá hạn, cảnh báo, escalation và breach |
| CV049 | Workflow Test | Đóng, mở lại, rollback và SLA cycle |
| CV050 | Security Test | RBAC, giả mạo quyền và bảo vệ attachment |
| CV051 | Validation/Negative Test | Invalid data/state, duplicate, not found và system error |
| CV052 | Automated Business-Rule Test | Suite tự động, JUnit, transcript và pass rate |
| CV053 | User Acceptance Test | Kịch bản Requester, Processor và Admin |
| CV054 | Đánh giá KPI | Tính 10 KPI từ dữ liệu mô phỏng và so sánh mục tiêu |
| CV055 | Sửa lỗi và regression | Đóng lỗi High và xác nhận Release Candidate |
| CV056 | Hoàn thiện UI/UX | Loading, success, failure, empty, denied và responsive |

## Cấu trúc thư mục

```text
Code/
├── alembic/                  # Migration database
├── app/
│   ├── api/                  # Router và dependency
│   ├── core/                 # Config, security, RBAC, SLA, error contract
│   ├── database/             # PostgreSQL/Redis connection
│   ├── models/               # SQLAlchemy models
│   ├── repositories/         # Data-access layer
│   ├── schemas/              # Pydantic request/response
│   ├── services/             # Business logic
│   └── static/               # CSS và JavaScript
├── data/                     # Dữ liệu KPI mô phỏng
├── evidence/                 # Test evidence, JUnit và biên bản
├── scripts/                  # Seed, worker và test runner
├── templates/                # Trang chính và KPI Dashboard
├── tests/                    # Automated test
├── docker-compose.yml
├── pytest.ini
├── requirements.txt
└── README.md
```

Không đưa `.env`, `.venv`, `.pytest_cache`, `__pycache__` hoặc file `*.pyc`
vào GitHub và gói ZIP bàn giao.

## 1. Chuẩn bị môi trường trên Windows

Mở PowerShell tại thư mục `Code`:

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

Mở `.env` và thực hiện các việc sau:

- thay `SECRET_KEY` bằng chuỗi ngẫu nhiên vừa tạo;
- thay tất cả giá trị `CHANGE_ME`;
- cấu hình tài khoản PostgreSQL và tài khoản seed;
- chỉ lưu `.env` trên máy cục bộ.

## 3. Khởi động PostgreSQL, Redis và migration

Yêu cầu Docker Desktop đang hoạt động:

```powershell
docker compose up -d
docker compose ps
python -m alembic upgrade head
python -m alembic current
```

Kết quả mong đợi:

- `postgres` và `redis` ở trạng thái `healthy`;
- Alembic trả `20260904_0012 (head)`.

Tạo dữ liệu nền:

```powershell
python -m scripts.seed_initial_data
```

Tạo sáu ticket demo của CV045:

```powershell
python -m scripts.seed_demo_data
```

Script tạo các trường hợp bình thường, gần hạn, quá hạn, đã đóng, mở lại và bị
từ chối. Mã ticket cố định giúp chạy lại mà không tạo trùng dữ liệu.

## 4. Chạy ứng dụng

```powershell
python -m uvicorn app.main:app --reload
```

| Thành phần | Địa chỉ |
| --- | --- |
| Trang chính | <http://127.0.0.1:8000/> |
| Cổng quản lý ticket | <http://127.0.0.1:8000/portal> |
| Quản trị hệ thống | <http://127.0.0.1:8000/admin> |
| KPI Dashboard | <http://127.0.0.1:8000/dashboard> |
| Swagger | <http://127.0.0.1:8000/docs> |
| Liveness | <http://127.0.0.1:8000/api/v1/health/live> |
| Readiness | <http://127.0.0.1:8000/api/v1/health/ready> |

### Giao diện Web

Các giao diện sử dụng chung phiên đăng nhập lưu trong `sessionStorage`:

- `/portal`: đăng nhập, danh sách và bộ lọc ticket, tạo ticket, xem chi tiết,
  phân công, workflow, trao đổi công khai/nội bộ, chỉnh sửa trao đổi, tệp đính
  kèm, đánh giá, thông báo, hồ sơ cá nhân, lịch sử trạng thái/phân công và SLA;
- `/admin`: quản lý tài khoản, vai trò, trạng thái hoạt động, danh mục, mức ưu
  tiên và Audit Log;
- `/dashboard`: theo dõi KPI và hiệu suất SLA theo phạm vi của Admin hoặc
  Processor.

Requester chỉ truy cập ticket của mình. Processor chỉ truy cập ticket được
phân công. Admin có phạm vi quản trị và giám sát toàn hệ thống. Các thao tác bị
giới hạn đồng thời ở giao diện và API.

## 5. Vai trò và phạm vi truy cập

| Vai trò | Quyền chính |
| --- | --- |
| Requester | Tạo và theo dõi ticket của mình, bổ sung thông tin, mở lại, đóng và đánh giá |
| Processor | Xem ticket được phân công, phản hồi và thực hiện workflow xử lý |
| Admin | Quản trị người dùng/danh mục, phân công, giám sát, xem audit và KPI toàn hệ thống |

Quyền được kiểm tra từ database tại thời điểm xử lý request. Hệ thống không tin
role header do phía client tự gửi.

## 6. Workflow ticket

| ID | Endpoint | Transition | Quyền chính |
| --- | --- | --- | --- |
| WF-01 | `POST /api/v1/tickets/{ticket_id}/start` | `ASSIGNED -> IN_PROGRESS` | Processor được giao hoặc Admin |
| WF-02 | `POST /api/v1/tickets/{ticket_id}/request-info` | `IN_PROGRESS -> PENDING_INFO` | Processor được giao hoặc Admin |
| WF-03 | `POST /api/v1/tickets/{ticket_id}/provide-info` | `PENDING_INFO -> IN_PROGRESS` | Requester sở hữu |
| WF-04 | `POST /api/v1/tickets/{ticket_id}/resolve` | `IN_PROGRESS -> RESOLVED` | Processor được giao hoặc Admin |
| WF-05 | `POST /api/v1/tickets/{ticket_id}/close` | `RESOLVED -> CLOSED` | Requester sở hữu hoặc Admin |
| WF-06 | `POST /api/v1/tickets/{ticket_id}/reopen` | `RESOLVED -> REOPENED` | Requester sở hữu, trong 72 giờ |
| WF-07 | `POST /api/v1/tickets/{ticket_id}/resume` | `REOPENED -> IN_PROGRESS` | Processor được giao hoặc Admin |
| WF-08 | `POST /api/v1/tickets/{ticket_id}/reject` | `NEW -> REJECTED` | Admin |

Mỗi transition hợp lệ cập nhật ticket, status history và audit log trong cùng
transaction. `CLOSED` và `REJECTED` là trạng thái cuối.

Tự động đóng ticket `RESOLVED` quá 72 giờ:

```powershell
python -m scripts.auto_close_resolved
```

## 7. SLA

Khi tạo ticket, hệ thống tạo hai runtime SLA:

- `RESPONSE`: thời gian phản hồi đầu tiên;
- `RESOLUTION`: thời gian hoàn tất xử lý.

| Ưu tiên | Phản hồi | Xử lý |
| --- | ---: | ---: |
| P1 | 15 phút | 240 phút |
| P2 | 30 phút | 480 phút |
| P3 | 60 phút | 1.440 phút |
| P4 | 240 phút | 2.880 phút |

Resolution SLA dừng trong `PENDING_INFO`, tiếp tục khi Requester bổ sung thông
tin và tạo cycle mới sau khi ticket được mở lại.

Các trạng thái hiển thị:

| Mã | Ý nghĩa |
| --- | --- |
| `ON_TRACK` | Còn hạn |
| `NEAR_DUE` | Sắp quá hạn |
| `OVERDUE` | Quá hạn |
| `MET` | Hoàn tất đúng SLA |
| `NOT_APPLICABLE` | Không áp dụng |

Chạy worker cảnh báo và escalation:

```powershell
python -m scripts.process_sla_escalations
```

Worker tạo các event `WARNING`, `OVERDUE` và `ESCALATED`, đồng thời gửi
notification và ghi audit. Cơ chế idempotent ngăn tạo trùng event khi chạy lại.

## 8. Rating và notification

Requester có thể đánh giá một lần khi ticket ở `RESOLVED` hoặc `CLOSED`:

```text
POST /api/v1/tickets/{ticket_id}/rating
GET  /api/v1/tickets/{ticket_id}/rating
```

Điểm hợp lệ từ 1 đến 5. Database có check constraint và unique constraint theo
`ticket_id`.

API notification:

```text
GET   /api/v1/notifications
PATCH /api/v1/notifications/{notification_id}/read
PATCH /api/v1/notifications/read-all
```

Người dùng chỉ được đọc và cập nhật notification của chính mình.

## 9. KPI Dashboard

API dành cho Admin và Processor:

```text
GET /api/v1/dashboard/overview
GET /api/v1/dashboard/sla-performance
```

Admin xem dữ liệu toàn hệ thống. Processor chỉ xem các ticket đang được phân
công cho mình. Bộ lọc hỗ trợ thời gian, danh mục, mức ưu tiên, phòng ban và
người xử lý.

Dashboard tại `/dashboard` có các trạng thái:

- loading;
- success;
- failure;
- empty;
- access denied;
- data.

Access token được lưu trong `sessionStorage`, không dùng `localStorage`.

## 10. Chạy toàn bộ kiểm thử

```powershell
python -m pytest
```

Kết quả hiện tại:

```text
339 passed
```

Các nhóm test chính:

| Phạm vi | Số test |
| --- | ---: |
| CV023–CV043 | 264 |
| CV044 Dashboard UI | 12 |
| CV045 Seed demo | 6 |
| CV046 Integration | 3 |
| CV047–CV051 Functional/Security/Negative | 10 |
| CV053 Automated UAT | 3 |
| CV054 KPI evaluation | 2 |
| CV055 High-priority regression | 3 |
| CV056 UI completion | 5 |
| **Tổng cộng hiện tại** | **308** |

CV052 sử dụng lại 10 test CV047–CV051 thông qua marker `business_rule`, nên
không làm tăng tổng số test.

## 11. Kiểm thử CV047–CV051

```powershell
python -m pytest .\tests\functional\test_normal_ticket_flow.py -v
python -m pytest .\tests\functional\test_sla_deadlines.py -v
python -m pytest .\tests\functional\test_close_reopen_workflow.py -v
python -m pytest .\tests\functional\test_security_access.py -v
python -m pytest .\tests\functional\test_negative_cases.py -v
```

| CV | Nội dung | Kết quả mong đợi |
| --- | --- | ---: |
| CV047 | Luồng tạo đến đánh giá | 1 passed |
| CV048 | Gần hạn, quá hạn, escalation và breach | 1 passed |
| CV049 | Đóng, mở lại và SLA cycle | 1 passed |
| CV050 | RBAC, UI gate và attachment access | 2 passed |
| CV051 | Invalid data/state, duplicate, not found và system error | 5 passed |

## 12. Runner CV052–CV056

### CV052 – Automated Business Rules

```powershell
python .\scripts\run_automated_tests.py
```

Kết quả mong đợi: `10/10 passed`.

### CV053 – Automated UAT ba vai trò

```powershell
python .\scripts\run_uat.py
```

Kết quả mong đợi: `3/3 accepted`.

Automated UAT không thay thế phiên UAT thủ công. Biên bản UAT trong thư mục
`evidence` chỉ hoàn tất khi người kiểm thử thực tế xác nhận, ghi ngày và ký tên.

### CV054 – Đánh giá KPI

```powershell
python .\scripts\run_evaluation.py
```

Kết quả hiện tại:

- `8/10` KPI đạt;
- `2/2` automated test passed;
- kết luận: **ĐẠT CÓ ĐIỀU KIỆN**.

Hai KPI chưa đạt:

- KPI05 – tỷ lệ đáp ứng SLA tổng thể: 75%, mục tiêu từ 80%;
- KPI08 – tỷ lệ ticket mở lại: 12,5%, mục tiêu không quá 10%.

### CV055 – Release Candidate

```powershell
python .\scripts\run_release_candidate.py
```

Điều kiện `GO - RELEASE CANDIDATE`:

- không còn Critical/High đang mở trong defect log thuộc thư mục `evidence`;
- `3/3` high-priority regression test passed;
- full regression passed.

### CV056 – UI/UX và responsive

```powershell
python .\scripts\run_ui_tests.py
```

Kết quả mong đợi:

- `5/5` CV056 UI contract test passed;
- full regression `339/339 passed`;
- kết luận `PASSED - UI COMPLETE`.

Test tự động kiểm tra cấu trúc HTML/CSS/JavaScript. Trước khi bàn giao vẫn cần
mở Chrome và kiểm tra hiển thị thực tế tại 320, 390, 560, 768, 900 và 1.180 px.

## 13. Test evidence

Thư mục `evidence` lưu các nhóm bằng chứng sau:

- kết quả Functional Test luồng ticket bình thường;
- kết quả SLA, workflow, security và negative test;
- JUnit, transcript và pass rate của automated business-rule suite;
- biên bản UAT ba vai trò;
- bảng đánh giá KPI và dữ liệu kết quả;
- defect log và regression evidence của Release Candidate;
- checklist và test evidence của UI/UX responsive.

Tên file bằng chứng phải mô tả đúng nội dung, không dùng mã `CVxxx` làm tên
file. Mã công việc chỉ được ghi bên trong tài liệu để đối chiếu với kế hoạch.

## 14. Kiểm tra trước khi commit hoặc đóng gói

Kiểm tra secret:

```powershell
git check-ignore .env
git ls-files | Select-String -Pattern '(^|/)\.env$|\.db$|\.sqlite$'
```

Lệnh thứ hai không được trả về `.env` hoặc database cục bộ.

Kiểm tra file không cần thiết:

```powershell
Get-ChildItem -Recurse -Force | Where-Object {
    $_.FullName -match '\\.venv|__pycache__|\\.pytest_cache|\.pyc$'
}
```

Không đưa các file trên vào gói ZIP nộp bài. Giữ `.env.example` để người khác
biết các biến cần cấu hình nhưng không để lộ secret thật.

## 15. Giới hạn kiểm thử

Automated test sử dụng SQLite in-memory và session store giả để bảo đảm chạy
nhanh, cô lập. Trước khi nộp cần thực hiện thêm:

1. chạy migration trên PostgreSQL 16;
2. kiểm tra Redis 7 và refresh-token rotation;
3. chạy seed dữ liệu thật;
4. smoke test các API chính trên Swagger;
5. UAT thủ công ba vai trò;
6. kiểm tra responsive trên trình duyệt.

## Trạng thái hiện tại

- Phân tích và thiết kế CV001–CV022: hoàn thành.
- Source code và kiểm thử CV023–CV056: hoàn thành.
- Automated regression: `339/339 passed`.
- KPI: `8/10`, đạt có điều kiện.
- UAT: automated test đạt; cần chữ ký xác nhận thực tế.
- UI: Portal, Admin và Dashboard đã hoàn thiện chức năng, trạng thái giao diện, phân quyền và responsive; smoke test thủ công ba vai trò đã đạt.
