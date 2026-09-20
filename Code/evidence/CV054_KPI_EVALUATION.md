# CV054 - Bảng đánh giá KPI hệ thống Helpdesk SLA

## 1. Phạm vi đánh giá

| Hạng mục | Giá trị |
| --- | --- |
| Kỳ đánh giá | 2026-09-01T00:00:00Z đến 2026-09-30T23:59:59Z |
| Nguồn dữ liệu | `CV054 deterministic simulated dataset` |
| Số ticket mô phỏng | 10 |
| Số KPI | 10 |
| KPI đạt | 8 |
| KPI chưa đạt | 2 |
| Tỷ lệ hoàn thành mục tiêu | 80.00% |
| Kết luận | **ĐẠT CÓ ĐIỀU KIỆN** |

Ngưỡng trong bảng là ngưỡng đánh giá được chốt cho CV054. CV008 cung cấp danh
mục và công thức KPI nhưng không quy định giá trị mục tiêu số.

## 2. Bảng KPI đánh giá

| Mã | KPI | Công thức | Tử số/Mẫu số | Thực tế | Mục tiêu CV054 | Kết quả |
| --- | --- | --- | ---: | ---: | ---: | --- |
| KPI01 | Thời gian phản hồi đầu tiên TB | Tổng phút phản hồi / ticket đã phản hồi | 9/9 | 41.11 phút | <= 60 phút | **ĐẠT** |
| KPI02 | Tỷ lệ đáp ứng response SLA | Response SLA MET / response SLA đủ điều kiện × 100% | 8/9 | 88.89 % | >= 80 % | **ĐẠT** |
| KPI03 | Thời gian giải quyết TB | Tổng phút giải quyết / ticket đã giải quyết | 8/8 | 202.5 phút | <= 240 phút | **ĐẠT** |
| KPI04 | Tỷ lệ đáp ứng resolution SLA | Resolution SLA MET / resolution SLA đủ điều kiện × 100% | 7/8 | 87.5 % | >= 80 % | **ĐẠT** |
| KPI05 | Tỷ lệ đáp ứng SLA tổng thể | Ticket đạt đồng thời response và resolution SLA / ticket đủ điều kiện × 100% | 6/8 | 75 % | >= 80 % | **CHƯA ĐẠT** |
| KPI06 | Số ticket đang mở | Đếm ticket thuộc trạng thái mở tại snapshot | 1/10 | 1 ticket | <= 3 ticket | **ĐẠT** |
| KPI07 | Số ticket mở lại | COUNT DISTINCT ticket_id có reopened_at trong kỳ | 1/10 | 1 ticket | <= 1 ticket | **ĐẠT** |
| KPI08 | Tỷ lệ ticket mở lại | Ticket mở lại / ticket đã resolved hoặc closed × 100% | 1/8 | 12.5 % | <= 10 % | **CHƯA ĐẠT** |
| KPI09 | Điểm hài lòng trung bình | Tổng điểm hợp lệ / số đánh giá hợp lệ | 30/7 | 4.29 điểm/5 | >= 4 điểm/5 | **ĐẠT** |
| KPI10 | Tỷ lệ ticket được đánh giá | Ticket đóng có đánh giá / tổng ticket đóng × 100% | 7/7 | 100 % | >= 70 % | **ĐẠT** |

## 3. KPI chưa đạt và nhận định

- **KPI05 – Tỷ lệ đáp ứng SLA tổng thể:** thực tế 75 %, mục tiêu >= 80 %.
- **KPI08 – Tỷ lệ ticket mở lại:** thực tế 12.5 %, mục tiêu <= 10 %.

- KPI05 chưa đạt cho thấy một ticket vi phạm response và một ticket vi phạm
  resolution làm tỷ lệ ticket đạt đồng thời cả hai SLA còn 75%.
- KPI08 chưa đạt do 1/8 ticket đã có kết quả phải mở lại, tương đương 12,5%.
- Các KPI tốc độ xử lý, SLA riêng lẻ, số ticket mở và mức hài lòng đều đạt mục tiêu.

## 4. Khuyến nghị

1. Theo dõi nguyên nhân response chậm và phân công sớm hơn tại giờ cao điểm.
2. Bổ sung checklist xác nhận kết quả trước khi chuyển `RESOLVED` để giảm reopen.
3. Theo dõi KPI05 và KPI08 theo tuần; chỉ kết luận cải thiện khi có nhiều kỳ dữ liệu.
4. Không dùng bộ dữ liệu mô phỏng này để khẳng định hiệu quả vận hành thực tế.

## 5. Kết luận

Bộ dữ liệu mô phỏng cho thấy **8/10 KPI đạt**,
tương đương **80.00%**. Hệ thống được đánh giá
**ĐẠT CÓ ĐIỀU KIỆN**; cần ưu tiên cải thiện SLA tổng thể và tỷ lệ mở lại.

## 6. Truy vết bằng chứng

| Tệp | Vai trò |
| --- | --- |
| `data/kpi_simulated_data.json` | Dữ liệu nguồn mô phỏng cố định |
| `scripts/evaluate_cv054_kpis.py` | Công thức tính, so sánh ngưỡng và sinh báo cáo |
| `evidence/CV054_KPI_RESULT.json` | Kết quả máy đọc được |
| `tests/evaluation/test_cv054_kpi_evaluation.py` | Kiểm thử công thức và tính tái lập |

## 7. Xác nhận kiểm thử

```text
2 passed, 298 deselected
300 passed in 114.56s (0:01:54)
```

Automated test CV054 và toàn bộ regression test đều đạt. Hai KPI `CHƯA ĐẠT`
là kết quả đánh giá nghiệp vụ của dữ liệu mô phỏng, không phải lỗi test.
