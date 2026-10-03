# Complete Web UI Test Evidence

## 1. Thông tin kiểm thử

| Thuộc tính | Giá trị |
| --- | --- |
| Ngày kiểm thử | 03/10/2026 |
| Người kiểm thử | Phạm Bao Hữu Thọ |
| Nhánh | `feature/complete-web-ui` |
| Commit chức năng gần nhất | `2b45a64` |
| Môi trường | Windows, Chrome, FastAPI/Uvicorn |
| Database | PostgreSQL 16 |
| Session/Cache | Redis 7 |

## 2. Phạm vi

Kiểm thử giao diện Web hoàn chỉnh cho ba vai trò:

- Requester;
- Processor;
- Admin.

Các giao diện được kiểm thử:

- `/portal`;
- `/admin`;
- `/dashboard`.

## 3. Kết quả kiểm thử thủ công

| Nhóm chức năng | Requester | Processor | Admin | Kết quả |
| --- | --- | --- | --- | --- |
| Đăng nhập, đăng xuất và điều hướng | Đạt | Đạt | Đạt | Passed |
| Danh sách, tìm kiếm và lọc ticket | Đạt | Đạt | Đạt | Passed |
| Tạo và xem chi tiết ticket | Đạt | Theo quyền | Đạt | Passed |
| Phân công người xử lý | Không hiển thị | Không hiển thị | Đạt | Passed |
| Workflow ticket | Theo quyền | Đạt | Đạt | Passed |
| Trao đổi công khai/nội bộ | Chỉ công khai | Đạt | Đạt | Passed |
| Chỉnh sửa trao đổi | Trao đổi của mình | Trao đổi của mình | Theo quyền quản trị | Passed |
| Tải lên và tải xuống tệp | Đạt | Đạt | Đạt | Passed |
| Xóa tệp đính kèm | Tệp của mình | Tệp của mình | Đạt | Passed |
| Đánh giá hài lòng | Gửi và xem | Chỉ xem | Chỉ xem | Passed |
| Thông báo và mở ticket từ thông báo | Đạt | Đạt | Đạt | Passed |
| Cập nhật hồ sơ cá nhân | Đạt | Đạt | Đạt | Passed |
| Lịch sử trạng thái và phân công | Đạt | Đạt | Đạt | Passed |
| Chi tiết SLA | Đạt | Đạt | Đạt | Passed |
| Giám sát cảnh báo SLA | Không hiển thị | Đạt | Đạt | Passed |
| Quản lý tài khoản | Không truy cập | Không truy cập | Đạt | Passed |
| Quản lý danh mục và mức ưu tiên | Không truy cập | Không truy cập | Đạt | Passed |
| Tra cứu Audit Log | Không truy cập | Không truy cập | Đạt | Passed |

## 4. Kiểm thử quy tắc và phân quyền

Các trường hợp sau đã được xác nhận:

- Requester chỉ xem ticket của mình.
- Processor chỉ xem ticket được phân công.
- Requester không thấy trao đổi nội bộ.
- Người dùng không chỉnh sửa trao đổi của người khác.
- Requester và Processor không xóa tệp của người khác.
- Ticket kết thúc không cho Requester/Processor tải lên hoặc xóa tệp.
- Admin được bảo vệ khỏi tự khóa hoặc tự thu hồi vai trò Admin.
- Người dùng không có vai trò Admin bị chặn khỏi `/admin`.
- Rating chỉ được gửi một lần tại trạng thái hợp lệ.
- Thông báo chỉ hiển thị cho người nhận tương ứng.

## 5. Responsive và trạng thái giao diện

Đã kiểm tra trên desktop và mobile, bao gồm chiều rộng khoảng `390px`.

Các trạng thái giao diện đã đạt:

- loading;
- success;
- error;
- empty;
- access denied;
- disabled/busy;
- dialog và bảng có thể sử dụng trên màn hình nhỏ.

Các khu vực Portal, Admin, Dashboard, thông báo, hồ sơ, timeline, SLA,
trao đổi và tệp đính kèm hiển thị đúng trên mobile.

## 6. Automated regression

Lệnh thực thi:

```powershell
python -m pytest -o addopts="" -q
```

Kết quả:

```text
339 passed in 190.88s (0:03:10)
```

- Passed: 339;
- Failed: 0;
- Error: 0;
- Skipped: 0.

## 7. Kết luận

Giao diện Web hoàn chỉnh cho Requester, Processor và Admin đã đạt yêu cầu.
Toàn bộ 339 automated test passed, không phát sinh regression.