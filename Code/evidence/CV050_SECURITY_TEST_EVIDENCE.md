# CV050 - Security Test Evidence

## Thông tin thực thi

| Hạng mục | Kết quả |
| --- | --- |
| Ngày kiểm thử | 19/09/2026 |
| Loại kiểm thử | API/UI RBAC + Attachment Access Control + Regression |
| Môi trường | Python 3.12.14, pytest 9.1.1 |
| Database test | SQLite in-memory, cô lập theo test |
| Attachment storage | Thư mục tạm cô lập theo test |
| File test | `tests/functional/test_cv050_security_access.py` |

## Bằng chứng phân quyền API và UI

| Tình huống | Kết quả thực tế | Trạng thái |
| --- | --- | --- |
| Chưa đăng nhập gọi Admin API | HTTP 401 `AUTH_TOKEN_MISSING` | PASS |
| Requester gọi Admin API | HTTP 403 `FORBIDDEN_ACTION` | PASS |
| Processor gọi Admin API | HTTP 403 `FORBIDDEN_ACTION` | PASS |
| Giả mạo `X-User-Role: ADMIN` | Vẫn HTTP 403 | PASS |
| Admin gọi Admin API | HTTP 200 | PASS |
| Requester gọi Dashboard API | HTTP 403 | PASS |
| Processor/Admin gọi Dashboard API | HTTP 200 | PASS |
| Processor/Admin tạo ticket | HTTP 403 | PASS |
| Requester tạo ticket | HTTP 201 | PASS |
| Requester/Processor phân công ticket | HTTP 403 | PASS |
| Admin phân công ticket | HTTP 200 | PASS |

UI dashboard được xác nhận:

- Dashboard shell bị ẩn mặc định trước khi xác thực.
- Có access-denied state với `role="alert"`.
- Chỉ role `ADMIN` và `PROCESSOR` được UI chấp nhận.
- Role không hợp lệ bị xóa session và chuyển sang thông báo không có quyền.
- Nguồn dữ liệu quản trị người dùng chỉ được UI gọi trong nhánh Admin.
- API vẫn là lớp thực thi quyền cuối cùng, không tin role do client cung cấp.

## Bằng chứng bảo vệ attachment

| Tình huống | Kết quả thực tế | Trạng thái |
| --- | --- | --- |
| Chưa đăng nhập tải attachment | HTTP 401 | PASS |
| Requester khác đoán attachment ID | HTTP 403 `TICKET_ACCESS_DENIED` | PASS |
| Processor chưa phân công tải file | HTTP 403 `TICKET_ACCESS_DENIED` | PASS |
| Requester khác giả mạo role Admin | Vẫn HTTP 403 | PASS |
| Requester khác upload vào ticket | HTTP 403, tổng file vẫn là 1 | PASS |
| Processor xóa file của Requester | HTTP 403 `ATTACHMENT_DELETE_FORBIDDEN` | PASS |
| Processor được phân công tải file | HTTP 200, đúng nội dung | PASS |
| Admin tải file | HTTP 200, đúng nội dung | PASS |
| Processor được phân công thử xóa | Vẫn HTTP 403, file còn nguyên | PASS |

Response bị từ chối không chứa:

```text
cv050-security-evidence.pdf
storage_path
CV050 confidential attachment
```

Sau mọi lần truy cập và xóa trái phép, bản ghi attachment và object vật lý vẫn
tồn tại, đúng nội dung gốc.

## Kết quả chạy riêng CV050

Lệnh:

```powershell
python -m pytest .\tests\functional\test_cv050_security_access.py -v
```

Kết quả:

```text
collected 2 items
tests/functional/test_cv050_security_access.py .. [100%]
2 passed in 1.53s
```

## Kết quả regression toàn dự án

Lệnh:

```powershell
python -m pytest
```

Kết quả:

```text
290 passed in 101.70s (0:01:41)
```

## Kết luận

CV050 đạt yêu cầu. Các vai trò bị chặn đúng tại API và UI, giả mạo role header
không thể nâng quyền, attachment không bị tải, thêm hoặc xóa trái phép và thông
tin file không bị rò rỉ qua response lỗi. Toàn bộ 290 test đạt, không có
regression.
