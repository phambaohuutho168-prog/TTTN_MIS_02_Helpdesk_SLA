# CV051 - Negative Test Evidence

## Thông tin thực thi

| Hạng mục | Kết quả |
| --- | --- |
| Ngày kiểm thử | 19/09/2026 |
| Loại kiểm thử | Validation/Negative Test + Regression Test |
| Môi trường | Python 3.12.14, pytest 9.1.1 |
| Database test | SQLite in-memory, cô lập theo test |
| File test | `tests/functional/test_cv051_negative_cases.py` |

## Bằng chứng năm nhóm lỗi

| Mã | Nhóm lỗi | Kết quả thực tế | Kiểm tra dữ liệu | Trạng thái |
| --- | --- | --- | --- | --- |
| NEG-FT-01 | Invalid data | HTTP 422 `VALIDATION_ERROR`, trả đủ 5 field lỗi | Ticket count giữ nguyên 0 | PASS |
| NEG-FT-02 | Invalid state | HTTP 409 `INVALID_STATE_TRANSITION` | Ticket vẫn `NEW`; không tăng history/audit | PASS |
| NEG-FT-03 | Duplicate | HTTP 409 `CATEGORY_NAME_CONFLICT` | Category count giữ nguyên 2 | PASS |
| NEG-FT-04 | Not found | HTTP 404 `TICKET_NOT_FOUND` | Error contract hợp lệ | PASS |
| NEG-FT-05 | System error | HTTP 500 `INTERNAL_SERVER_ERROR` | Response đã được làm sạch | PASS |

## Chi tiết validation

Payload ticket sai chứa năm vấn đề:

```text
title: quá ngắn
description: quá ngắn
category_id: không phải số dương
priority_id: không phải số dương
unexpected: field không được hỗ trợ
```

Response trả đủ năm field trong `errors` và không tạo ticket.

## Chi tiết atomicity

Khi thử đóng trực tiếp ticket `NEW`:

- Trạng thái vẫn là `NEW`.
- `closed_at` và `closed_by` vẫn rỗng.
- Số status history không thay đổi.
- Số audit log không thay đổi.

Khi tạo category trùng `PHẦN MỀM`, hệ thống chuẩn hóa hoa thường và khoảng
trắng, trả conflict và không tạo thêm bản ghi.

## Chi tiết system error

Test chủ động mô phỏng exception có chuỗi nội bộ:

```text
DATABASE_URL=postgresql://secret-user:secret-pass@db/cv051
```

Response cho client chỉ trả:

```text
code: INTERNAL_SERVER_ERROR
message: Hệ thống gặp lỗi không mong đợi.
```

Response không chứa URL database, username hoặc password. `meta.request_id` vẫn
được sinh để đối chiếu với server log.

## Error contract

Các response lỗi được kiểm tra:

```text
success = false
code
message
không có field data
errors
meta.request_id
meta.timestamp
```

Với lỗi validation, nghiệp vụ và not found, header `X-Request-ID` trùng với
`meta.request_id`.

## Kết quả chạy riêng CV051

Lệnh:

```powershell
python -m pytest .\tests\functional\test_cv051_negative_cases.py -v
```

Kết quả:

```text
collected 5 items
tests/functional/test_cv051_negative_cases.py ..... [100%]
5 passed in 1.90s
```

## Kết quả regression toàn dự án

Lệnh:

```powershell
python -m pytest
```

Kết quả:

```text
295 passed in 108.75s (0:01:48)
```

## Kết luận

CV051 đạt yêu cầu. Hệ thống xử lý đúng invalid data, invalid state, duplicate,
not found và system error; các lỗi nghiệp vụ bảo đảm atomicity, error response
nhất quán và lỗi 500 không rò rỉ thông tin nội bộ. Toàn bộ 295 test đạt, không
có regression.
