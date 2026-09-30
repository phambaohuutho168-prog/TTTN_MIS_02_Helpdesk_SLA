# CV055 - Defect Log trước Release Candidate

## Tổng hợp

| Mức độ | Tổng phát hiện | Đã đóng | Đang mở |
| --- | ---: | ---: | ---: |
| Critical | 0 | 0 | **0** |
| High | 3 | 3 | **0** |
| Medium | 0 | 0 | 0 |
| Low | 0 | 0 | 0 |

## Chi tiết defect

| ID | Mức độ | Thành phần | Mô tả | Nguyên nhân | Cách khắc phục | Regression test | Trạng thái |
| --- | --- | --- | --- | --- | --- | --- | --- |
| HIGH-001 | High | Dashboard/SLA | KPI SLA tổng thể tính từng bản ghi SLA nên cùng một ticket bị tính hai lần | Ghép chung danh sách response và resolution rồi đếm trực tiếp | Tổng hợp theo `ticket_id`; yêu cầu đủ response + resolution; một ticket sinh một kết quả overall | `test_high_001_overall_sla_is_calculated_once_per_ticket` | **CLOSED** |
| HIGH-002 | High | Dashboard/KPI03 | Thời gian giải quyết lấy thời điểm đóng thay vì thời điểm resolve | Repository đọc `Ticket.closed_at` | Join subquery `TicketResolution`, lấy `MAX(resolved_at)` cho chu kỳ mới nhất | `test_high_002_resolution_duration_uses_resolved_at_not_closed_at` | **CLOSED** |
| HIGH-003 | High | Dashboard/KPI07 | Bộ lọc kỳ reopen dùng ngày tạo ticket, bỏ sót ticket cũ mở lại trong kỳ | Dùng chung điều kiện `Ticket.created_at` cho mọi KPI | Tách điều kiện phạm vi và lọc `TicketStatusHistory.changed_at` cho sự kiện reopen | `test_high_003_reopen_period_uses_event_time_not_ticket_created_time` | **CLOSED** |

## Xác nhận

- Không còn defect Critical/High đang mở.
- Không có thay đổi schema hoặc migration.
- Các sửa lỗi được bảo vệ bằng regression test riêng.
- Trạng thái phát hành chỉ được chốt `GO` khi bộ test CV055 và full regression đều pass.
