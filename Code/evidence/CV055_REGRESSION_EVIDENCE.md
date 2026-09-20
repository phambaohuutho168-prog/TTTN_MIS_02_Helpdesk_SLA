# CV055 - Release Candidate Regression Evidence

## 1. Kết quả phát hành

| Điều kiện | Kết quả |
| --- | --- |
| Critical đang mở | **0** |
| High đang mở | **0** |
| High-priority regression | **3/3 passed** |
| Full regression | **303/303 passed** |
| Failed | **0** |
| Errors | **0** |
| Skipped | **0** |
| Quyết định | **GO - RELEASE CANDIDATE** |

## 2. Test sửa lỗi ưu tiên cao

Lệnh:

```powershell
python -m pytest -m release_candidate -v
```

Kết quả:

```text
tests/regression/test_cv055_high_priority_fixes.py ... [100%]
3 passed, 300 deselected in 0.70s
```

| Test | Defect được bảo vệ | Kết quả |
| --- | --- | --- |
| `test_high_001_overall_sla_is_calculated_once_per_ticket` | HIGH-001 | PASS |
| `test_high_002_resolution_duration_uses_resolved_at_not_closed_at` | HIGH-002 | PASS |
| `test_high_003_reopen_period_uses_event_time_not_ticket_created_time` | HIGH-003 | PASS |

## 3. Full regression

Lệnh:

```powershell
python -m pytest
```

Kết quả:

```text
303 passed in 109.35s (0:01:49)
```

## 4. Phạm vi kiểm tra lại

- Authentication, refresh và logout.
- Authorization/RBAC và quản trị người dùng.
- Ticket, assignment, comment, attachment và notification.
- Workflow, close/reopen, rating, SLA, escalation và audit.
- Dashboard API/UI và các KPI đã sửa.
- Functional, security, negative, automated business rules và UAT.
- CV054 KPI evaluation và ba regression test CV055.

## 5. Đối chiếu defect

| Defect | Trước sửa | Sau sửa | Trạng thái |
| --- | --- | --- | --- |
| HIGH-001 | Overall SLA đếm record | Một kết quả/ticket, bắt buộc đủ hai SLA | CLOSED |
| HIGH-002 | Resolution time dùng `closed_at` | Dùng resolution cycle mới nhất `resolved_at` | CLOSED |
| HIGH-003 | Reopen period dùng `created_at` | Dùng thời gian sự kiện `changed_at` | CLOSED |

## 6. Kết luận

Không còn defect Critical/High đang mở. Test chính và toàn bộ regression đều
Passed, không có failed/error/skipped. Source đủ điều kiện được đóng gói thành
Release Candidate CV055.

## 7. File bằng chứng

| File | Nội dung |
| --- | --- |
| `CV055_DEFECT_LOG.md` | Defect log và trạng thái đóng lỗi |
| `CV055_RELEASE_CANDIDATE_RESULT.txt` | Kết luận tự động GO/NO-GO |
| `CV055_HIGH_PRIORITY_OUTPUT.txt` | Transcript test defect High |
| `CV055_HIGH_PRIORITY_JUNIT.xml` | JUnit test defect High |
| `CV055_REGRESSION_OUTPUT.txt` | Transcript full regression |
| `CV055_REGRESSION_JUNIT.xml` | JUnit full regression |
