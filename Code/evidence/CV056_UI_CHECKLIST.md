# CV056 - UI/UX Completion Checklist

## Trạng thái giao diện

| ID | Nội dung kiểm tra | Evidence trong source | Kết quả |
| --- | --- | --- | --- |
| UI-STATE-01 | Loading có spinner, mô tả, skeleton và `aria-busy` | `loading-state`, `setDashboardBusy` | PASS |
| UI-STATE-02 | Success có xác nhận, đóng thủ công và tự ẩn | `dashboard-success`, `dismiss-success` | PASS |
| UI-STATE-03 | Failure có thông báo, focus và retry | `dashboard-alert`, `retry-dashboard` | PASS |
| UI-STATE-04 | Empty có hướng dẫn và reset filter | `empty-state`, `empty-reset-filters` | PASS |
| UI-STATE-05 | Không quyền có giải thích và đăng nhập lại | `access-denied-state` | PASS |
| UI-STATE-06 | Dữ liệu có KPI, sample size, biểu đồ và chú giải | `dashboard-content`, `status-legend` | PASS |

## Trạng thái ticket

| Mã | Nhãn UI | Hiển thị |
| --- | --- | --- |
| NEW | Mới | PASS |
| ASSIGNED | Đã phân công | PASS |
| IN_PROGRESS | Đang xử lý | PASS |
| PENDING_INFO | Chờ thông tin | PASS |
| RESOLVED | Đã xử lý | PASS |
| CLOSED | Đã đóng | PASS |
| REOPENED | Đã mở lại | PASS |
| REJECTED | Bị từ chối | PASS |

## Responsive

| Kích thước | Bố cục kiểm tra | Kết quả contract test |
| --- | --- | --- |
| ≥ 1181 px | Sidebar + 6 KPI + dashboard 2 cột | PASS |
| 901–1180 px | 3 KPI/hàng | PASS |
| 769–900 px | Mobile navigation + panel 1 cột | PASS |
| 561–768 px | 2 KPI/hàng + filter 2 cột | PASS |
| 320–560 px | 1 KPI/hàng + filter 1 cột | PASS |

## Accessibility và an toàn frontend

| Nội dung | Kết quả |
| --- | --- |
| Skip link và landmark rõ ràng | PASS |
| Focus visible và Escape đóng menu | PASS |
| Live region, role status/alert | PASS |
| Reduced motion/high contrast | PASS |
| Không dùng `innerHTML` để render API | PASS |
| Không nhúng credential/token | PASS |
| Session token không lưu `localStorage` | PASS |

Checklist trên được bảo vệ bởi
`tests/ui/test_cv056_complete_responsive_ui.py` và các test dashboard UI hiện có.
