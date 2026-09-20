# CV048 - Test Evidence: SLA sắp hạn và quá hạn

## Thông tin thực thi

| Hạng mục | Kết quả |
| --- | --- |
| Ngày kiểm thử | 19/09/2026 |
| Loại kiểm thử | SLA Functional Test + Regression Test |
| Môi trường | Python 3.12.14, pytest 9.1.1 |
| Database test | SQLite in-memory, cô lập theo test |
| File test | `tests/functional/test_cv048_sla_deadlines.py` |

## Dữ liệu kiểm thử

| Ticket | Target | Thời gian đã dùng | Thời gian còn lại | Tiến độ |
| --- | ---: | ---: | ---: | ---: |
| Sắp hạn | 100 phút | 85 phút | 15 phút | 85% |
| Quá hạn | 100 phút | 160 phút | -60 phút | 160% |

Policy áp dụng ngưỡng cảnh báo 80% và escalation 150%.

## Bằng chứng chức năng

| Mã | Nội dung xác nhận | Kết quả thực tế | Trạng thái |
| --- | --- | --- | --- |
| SLA-FT-01 | Deadline | Cả hai runtime có `due_at - started_at = 100 phút` | PASS |
| SLA-FT-02 | Worker | Tạo 4 event và 8 SLA notification | PASS |
| SLA-FT-03 | Trạng thái API | Ticket 85% là `NEAR_DUE`; ticket 160% là `OVERDUE` | PASS |
| SLA-FT-04 | Escalation | Ticket 160% có `WARNING`, `OVERDUE`, `ESCALATED` | PASS |
| SLA-FT-05 | Idempotency | Chạy lại tạo 0 event và 0 notification | PASS |
| SLA-FT-06 | Vi phạm SLA | Phản hồi trễ hoàn tất runtime với `BREACHED` | PASS |
| SLA-FT-07 | Audit | Ghi đủ warning, overdue, escalated và completed | PASS |

Event của ticket sắp hạn:

```text
WARNING (80%)
```

Event của ticket quá hạn:

```text
WARNING (80%)
OVERDUE (100%)
ESCALATED (150%)
```

Mỗi event SLA tạo notification cho đúng Processor đang được phân công và Admin
đang hoạt động. Worker chạy lại không tạo bản ghi trùng.

## Kết quả chạy riêng CV048

Lệnh:

```powershell
python -m pytest .\tests\functional\test_cv048_sla_deadlines.py -v
```

Kết quả:

```text
collected 1 item
tests/functional/test_cv048_sla_deadlines.py . [100%]
1 passed in 0.84s
```

## Kết quả regression toàn dự án

Lệnh:

```powershell
python -m pytest
```

Kết quả:

```text
287 passed in 97.96s (0:01:37)
```

## Kết luận

CV048 đạt yêu cầu. Deadline, cảnh báo sắp hạn, trạng thái quá hạn, escalation,
notification, audit log và kết quả vi phạm SLA đều được ghi đúng. Toàn bộ 287
test của dự án đạt, không phát hiện regression.
