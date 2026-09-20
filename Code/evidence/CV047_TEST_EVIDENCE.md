# CV047 - Test Evidence: Normal Ticket Flow

## Thông tin thực thi

| Hạng mục | Kết quả |
| --- | --- |
| Ngày kiểm thử | 19/09/2026 |
| Loại kiểm thử | Functional Test + Regression Test |
| Môi trường | Python 3.12.14, pytest 9.1.1 |
| Database test | SQLite in-memory, cô lập theo test |
| File test | `tests/functional/test_cv047_normal_ticket_flow.py` |

## Bằng chứng luồng nghiệp vụ

| Bước | Endpoint | Kết quả xác nhận | Trạng thái |
| --- | --- | --- | --- |
| FT-01 Tạo | `POST /api/v1/tickets` | HTTP 201, `TICKET_CREATED`, ticket `NEW` | PASS |
| FT-02 Phân công | `PUT /api/v1/tickets/{id}/assignment` | HTTP 200, đúng Processor | PASS |
| FT-03 Phản hồi | `POST /api/v1/tickets/{id}/comments` | HTTP 201, public reply, hoàn tất first-response SLA | PASS |
| FT-04 Xử lý | `POST .../start`, `POST .../resolve` | `IN_PROGRESS` rồi `RESOLVED` | PASS |
| FT-05 Đóng | `POST /api/v1/tickets/{id}/close` | HTTP 200, `CLOSED`, đúng Requester đóng | PASS |
| FT-06 Đánh giá | `POST /api/v1/tickets/{id}/rating` | HTTP 201, đánh giá 5 sao | PASS |
| FT-07 Đối soát | History, notification, audit, dashboard | Dữ liệu xuyên suốt đầy đủ và nhất quán | PASS |

Chuỗi trạng thái thực tế được assertion:

```text
NEW -> ASSIGNED -> IN_PROGRESS -> RESOLVED -> CLOSED
```

Các audit action được assertion:

```text
TICKET_CREATED
TICKET_ASSIGNED
COMMENT_CREATED
TICKET_STARTED
TICKET_RESOLVED
TICKET_CLOSED
TICKET_RATED
```

## Kết quả chạy riêng CV047

Lệnh:

```powershell
python -m pytest .\tests\functional\test_cv047_normal_ticket_flow.py -v
```

Kết quả:

```text
collected 1 item
tests/functional/test_cv047_normal_ticket_flow.py . [100%]
1 passed in 0.84s
```

## Kết quả regression toàn dự án

Lệnh:

```powershell
python -m pytest
```

Kết quả:

```text
286 passed in 97.15s (0:01:37)
```

## Kết luận

CV047 đạt yêu cầu. Luồng ticket bình thường hoạt động xuyên suốt từ tạo đến
đánh giá; các dữ liệu liên quan gồm lịch sử trạng thái, thông báo, audit log,
KPI dashboard và SLA đều được đối soát tự động. Toàn bộ 286 test của dự án đạt,
không phát hiện regression.
