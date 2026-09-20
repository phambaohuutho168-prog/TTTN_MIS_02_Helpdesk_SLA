# CV052 - Automated Business-Rule Test Evidence

## Thông tin thực thi

| Hạng mục | Kết quả |
| --- | --- |
| Ngày kiểm thử | 19/09/2026 |
| Suite | `business_rule` |
| Công cụ | pytest 9.1.1 + pytest-asyncio 1.4.0 |
| Môi trường | Python 3.12.14 |
| Tổng test trong suite | 10 |
| Passed | 10 |
| Failed | 0 |
| Errors | 0 |
| Skipped | 0 |
| **Pass rate** | **100.00%** |
| Kết quả | **PASSED** |

## Phạm vi business rules

| Module | Nội dung tự động kiểm thử | Test | Kết quả |
| --- | --- | ---: | --- |
| CV047 | Normal flow từ tạo ticket đến đánh giá | 1 | PASS |
| CV048 | SLA deadline, warning, overdue, escalation, breach | 1 | PASS |
| CV049 | Đóng, reopen, cửa sổ 72 giờ và SLA cycle | 1 | PASS |
| CV050 | RBAC API/UI và attachment access control | 2 | PASS |
| CV051 | Invalid data/state, duplicate, not found, system error | 5 | PASS |
| **Tổng** | **Automated business-rule suite** | **10** | **PASS** |

## Lệnh thực thi

Runner tự động:

```powershell
python .\scripts\run_cv052_automated_tests.py
```

Lệnh pytest tương đương:

```powershell
python -m pytest -m business_rule -v --junitxml=evidence/CV052_JUNIT.xml
```

## Kết quả thực chạy

```text
Tests: 10
Passed: 10
Failures: 0
Errors: 0
Skipped: 0
Pass rate: 100.00%
Exit code: 0
Result: PASSED
```

Pytest xác nhận:

```text
tests/functional/test_cv047_normal_ticket_flow.py .          [ 10%]
tests/functional/test_cv048_sla_deadlines.py .               [ 20%]
tests/functional/test_cv049_close_reopen_workflow.py .       [ 30%]
tests/functional/test_cv050_security_access.py ..            [ 50%]
tests/functional/test_cv051_negative_cases.py .....          [100%]
10 passed, 285 deselected in 7.15s
```

## File kết quả đã lưu

| File | Trạng thái |
| --- | --- |
| `evidence/CV052_JUNIT.xml` | Đã tạo, dùng cho CI/CD hoặc công cụ đọc JUnit |
| `evidence/CV052_PYTEST_OUTPUT.txt` | Đã lưu transcript pytest |
| `evidence/CV052_AUTOMATED_TEST_RESULT.txt` | Đã lưu số lượng và pass rate |

## Regression toàn dự án

Lệnh:

```powershell
python -m pytest
```

Kết quả:

```text
295 passed in 105.95s (0:01:45)
```

## Kết luận

CV052 đạt yêu cầu. Mười business-rule test quan trọng được tập hợp thành suite
tự động có marker riêng, có runner dùng được trên Windows/Linux, tự sinh kết
quả JUnit, transcript và báo cáo tỷ lệ pass. Suite đạt 100% và toàn bộ 295 test
của dự án đạt, không có regression.
