# CV049 - Test Evidence: đóng và mở lại ticket

## Thông tin thực thi

| Hạng mục | Kết quả |
| --- | --- |
| Ngày kiểm thử | 19/09/2026 |
| Loại kiểm thử | Workflow Functional Test + Regression Test |
| Môi trường | Python 3.12.14, pytest 9.1.1 |
| Database test | SQLite in-memory, cô lập theo test |
| File test | `tests/functional/test_cv049_close_reopen_workflow.py` |

## Bằng chứng chức năng

| Mã | Nội dung xác nhận | Kết quả thực tế | Trạng thái |
| --- | --- | --- | --- |
| WF-FT-01 | Đóng ticket `RESOLVED` | Chuyển `CLOSED`, lưu đúng `closed_by` và `closed_at` | PASS |
| WF-FT-02 | Mở lại ticket `CLOSED` | HTTP 409 `TICKET_ALREADY_TERMINAL` | PASS |
| WF-FT-03 | Mở lại sau 73 giờ | HTTP 409 `REOPEN_WINDOW_EXPIRED` | PASS |
| WF-FT-04 | Kiểm tra atomicity | Trường hợp bị chặn không tăng history, audit hoặc SLA | PASS |
| WF-FT-05 | Mở lại trong 72 giờ | Chuyển `RESOLVED -> REOPENED`, giữ SLA cycle 1 | PASS |
| WF-FT-06 | Processor resume | Chuyển `REOPENED -> IN_PROGRESS`, tạo SLA cycle 2 | PASS |
| WF-FT-07 | History và audit | Đúng chuỗi trạng thái và đầy đủ audit context | PASS |

Chuỗi trạng thái được assertion cho trường hợp hợp lệ:

```text
NEW -> ASSIGNED -> IN_PROGRESS -> RESOLVED -> REOPENED -> IN_PROGRESS
```

Kết quả resolution SLA:

```text
Cycle 1: COMPLETED
Cycle 2: RUNNING
Cycle 2 deadline = started_at + 240 phút
```

Các audit trọng tâm:

```text
TICKET_REOPENED
SLA_RUNTIME_CREATED
TICKET_RESUMED
```

Audit mở lại ghi nhận source resolution cycle 1, next resolution cycle 2 và
hành động giữ nguyên chu kỳ đã hoàn tất cho tới khi Processor resume. Audit SLA
liên kết đúng `ticket_sla_id` của cycle 2.

## Kết quả chạy riêng CV049

Lệnh:

```powershell
python -m pytest .\tests\functional\test_cv049_close_reopen_workflow.py -v
```

Kết quả:

```text
collected 1 item
tests/functional/test_cv049_close_reopen_workflow.py . [100%]
1 passed in 1.22s
```

## Kết quả regression toàn dự án

Lệnh:

```powershell
python -m pytest
```

Kết quả:

```text
288 passed in 97.78s (0:01:37)
```

## Kết luận

CV049 đạt yêu cầu. Hệ thống chặn mở lại ticket đã đóng và ticket quá cửa sổ
72 giờ mà không tạo dữ liệu dở dang. Trường hợp hợp lệ cập nhật đúng trạng thái,
giữ chu kỳ SLA cũ, tạo resolution SLA cycle mới khi tiếp tục xử lý và ghi đầy
đủ status history cùng audit log. Toàn bộ 288 test đạt, không có regression.
