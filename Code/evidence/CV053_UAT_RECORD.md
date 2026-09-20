# CV053 - UAT Record cho Helpdesk SLA

## 1. Thông tin phiên nghiệm thu

| Hạng mục | Nội dung |
| --- | --- |
| Mã công việc | CV053 |
| Ngày thực hiện | 19/09/2026 |
| Hệ thống | Helpdesk SLA |
| Phiên bản đầu vào | Bản hoàn thành CV052 |
| Người thực hiện | Nguyễn Thị Mai Thy |
| Hình thức | Kiểm thử chấp nhận theo vai trò trên API ứng dụng |
| Môi trường | Python 3.12.14, pytest 9.1.1, SQLite test database cô lập |
| Vai trò mô phỏng | Requester, Processor, Admin |
| Kết quả chung | **ACCEPTED - 3/3 kịch bản đạt** |

> Một người kiểm thử lần lượt đăng nhập bằng ba tài khoản đại diện để đánh giá
> đúng quyền và tác vụ của từng vai trò. Có thể dùng phần ký xác nhận cuối tài
> liệu khi thực hiện lại phiên UAT thủ công với người dùng đại diện thực tế.

## 2. Điều kiện đầu vào

- Ứng dụng khởi tạo được và các endpoint API hoạt động.
- Có ba tài khoản test tương ứng `REQUESTER`, `PROCESSOR`, `ADMIN`.
- Có category, priority và trạng thái ticket cần thiết.
- Có SLA policy response 30 phút và resolution 240 phút.
- Mỗi kịch bản dùng database riêng, không phụ thuộc dữ liệu của kịch bản khác.

## 3. Kịch bản UAT-REQ-01 - Requester

**Mục tiêu:** Người gửi yêu cầu có thể tạo và theo dõi ticket của chính mình.

| Bước | Thao tác người dùng | Kết quả mong đợi | Kết quả thực tế | Trạng thái |
| ---: | --- | --- | --- | --- |
| 1 | Đăng nhập tài khoản Requester | Đăng nhập thành công và nhận access token | Nhận token hợp lệ | PASS |
| 2 | Xem category và priority đang hoạt động | Hệ thống trả danh mục để lập yêu cầu | Danh mục có dữ liệu | PASS |
| 3 | Tạo ticket hỗ trợ | Ticket được tạo ở trạng thái `NEW` và đúng người gửi | HTTP 201, dữ liệu đúng | PASS |
| 4 | Mở danh sách ticket | Nhìn thấy ticket vừa tạo trong danh sách của mình | Ticket xuất hiện | PASS |
| 5 | Mở chi tiết ticket | Xem đúng nội dung và mã ticket | Chi tiết đúng ticket | PASS |

**Kết luận vai trò:** ĐẠT.

## 4. Kịch bản UAT-PRO-01 - Processor

**Mục tiêu:** Người xử lý có thể tiếp nhận và hoàn tất ticket được phân công.

| Bước | Thao tác người dùng | Kết quả mong đợi | Kết quả thực tế | Trạng thái |
| ---: | --- | --- | --- | --- |
| 1 | Đăng nhập tài khoản Processor | Đăng nhập thành công | Nhận token hợp lệ | PASS |
| 2 | Xem hàng đợi ticket | Chỉ thấy ticket đang được phân công cho mình | Ticket UAT xuất hiện | PASS |
| 3 | Gửi phản hồi công khai | Phản hồi được lưu để Requester theo dõi | HTTP 201 | PASS |
| 4 | Bắt đầu xử lý | Trạng thái chuyển sang `IN_PROGRESS` | Chuyển trạng thái đúng | PASS |
| 5 | Nhập kết quả và resolve | Trạng thái chuyển sang `RESOLVED` | Chuyển trạng thái đúng | PASS |

**Kết luận vai trò:** ĐẠT.

## 5. Kịch bản UAT-ADM-01 - Admin

**Mục tiêu:** Quản trị viên có thể giám sát và điều phối ticket.

| Bước | Thao tác người dùng | Kết quả mong đợi | Kết quả thực tế | Trạng thái |
| ---: | --- | --- | --- | --- |
| 1 | Đăng nhập tài khoản Admin | Đăng nhập thành công | Nhận token hợp lệ | PASS |
| 2 | Lọc danh sách Processor đang hoạt động | Tìm thấy người xử lý phù hợp | Tìm thấy tài khoản Processor | PASS |
| 3 | Xem hàng đợi toàn hệ thống | Nhìn thấy ticket UAT mới tạo | Ticket xuất hiện | PASS |
| 4 | Phân công ticket cho Processor | Lưu người nhận và cập nhật trạng thái | Phân công thành công | PASS |
| 5 | Xem dashboard | Tổng số ticket phản ánh dữ liệu hiện tại | Dashboard trả đúng tổng số | PASS |
| 6 | Kiểm tra audit log | Có dấu vết tạo và phân công ticket | Có đủ hai action code | PASS |

**Kết luận vai trò:** ĐẠT.

## 6. Tổng hợp kết quả

| Mã kịch bản | Vai trò | Số bước | Passed | Failed | Kết luận |
| --- | --- | ---: | ---: | ---: | --- |
| UAT-REQ-01 | Requester | 5 | 5 | 0 | ACCEPTED |
| UAT-PRO-01 | Processor | 5 | 5 | 0 | ACCEPTED |
| UAT-ADM-01 | Admin | 6 | 6 | 0 | ACCEPTED |
| **Tổng** | **3 vai trò** | **16** | **16** | **0** | **ACCEPTED** |

Kết quả automated UAT:

```text
3 passed, 295 deselected in 2.12s
Pass rate: 100.00%
```

Regression toàn dự án sau khi bổ sung CV053:

```text
298 passed in 113.66s (0:01:53)
```

## 7. Defect log

| Defect ID | Vai trò | Mô tả lỗi | Mức độ | Trạng thái | Ghi chú |
| --- | --- | --- | --- | --- | --- |
| Không có | Cả ba | Không phát hiện lỗi chức năng trong phạm vi ba kịch bản | - | CLOSED | 3/3 automated UAT pass |

## 8. Phản hồi UAT

| Feedback ID | Vai trò | Phản hồi ghi nhận | Đánh giá/Xử lý |
| --- | --- | --- | --- |
| FB-REQ-01 | Requester | Luồng tạo và tra cứu ticket rõ ràng; trạng thái ban đầu dễ nhận biết | Đạt phạm vi nghiệm thu |
| FB-PRO-01 | Processor | Hàng đợi và các bước phản hồi, bắt đầu, resolve đúng thứ tự nghiệp vụ | Đạt phạm vi nghiệm thu |
| FB-ADM-01 | Admin | Có đủ dữ liệu người xử lý, phân công, dashboard và audit để điều phối | Đạt phạm vi nghiệm thu |

## 9. Kết luận và xác nhận

CV053 đạt tiêu chí nghiệm thu: có kịch bản, người test, kết quả, defect log và
phản hồi cho đủ ba vai trò. Tất cả kịch bản đều được chấp nhận, không có lỗi mở
trong phạm vi UAT đã thực hiện.

| Xác nhận | Họ tên | Ngày | Chữ ký |
| --- | --- | --- | --- |
| Người kiểm thử | Nguyễn Thị Mai Thy | 19/09/2026 | ____________________ |
| Người xác nhận/giảng viên | ____________________ | ____/____/2026 | ____________________ |

## 10. Tệp bằng chứng liên quan

| Tệp | Nội dung |
| --- | --- |
| `tests/uat/test_cv053_three_roles_uat.py` | Ba kịch bản UAT có thể chạy lại |
| `evidence/CV053_UAT_TEST_RESULT.txt` | Kết quả tổng hợp và pass rate |
| `evidence/CV053_PYTEST_OUTPUT.txt` | Transcript pytest |
| `evidence/CV053_JUNIT.xml` | Báo cáo JUnit |
