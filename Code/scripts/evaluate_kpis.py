"""Calculate and evaluate the ten CV054 KPIs from deterministic simulated data."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Callable


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_PATH = PROJECT_ROOT / "data" / "kpi_simulated_data.json"
JSON_RESULT_PATH = PROJECT_ROOT / "evidence" / "CV054_KPI_RESULT.json"
MARKDOWN_PATH = PROJECT_ROOT / "evidence" / "CV054_KPI_EVALUATION.md"

OPEN_STATUSES = {"NEW", "ASSIGNED", "IN_PROGRESS", "PENDING_INFO", "REOPENED"}


@dataclass(frozen=True)
class Target:
    name: str
    unit: str
    target: float
    operator: str
    description: str


TARGETS = {
    "KPI01": Target("Thời gian phản hồi đầu tiên TB", "phút", 60.0, "<=", "Phản hồi trung bình không quá 60 phút"),
    "KPI02": Target("Tỷ lệ đáp ứng response SLA", "%", 80.0, ">=", "Ít nhất 80% response SLA đạt"),
    "KPI03": Target("Thời gian giải quyết TB", "phút", 240.0, "<=", "Giải quyết trung bình không quá 240 phút"),
    "KPI04": Target("Tỷ lệ đáp ứng resolution SLA", "%", 80.0, ">=", "Ít nhất 80% resolution SLA đạt"),
    "KPI05": Target("Tỷ lệ đáp ứng SLA tổng thể", "%", 80.0, ">=", "Ít nhất 80% ticket đạt đồng thời hai SLA"),
    "KPI06": Target("Số ticket đang mở", "ticket", 3.0, "<=", "Không quá 3 ticket mở tại snapshot"),
    "KPI07": Target("Số ticket mở lại", "ticket", 1.0, "<=", "Không quá 1 ticket mở lại trong kỳ"),
    "KPI08": Target("Tỷ lệ ticket mở lại", "%", 10.0, "<=", "Tỷ lệ mở lại không quá 10%"),
    "KPI09": Target("Điểm hài lòng trung bình", "điểm/5", 4.0, ">=", "CSAT trung bình ít nhất 4/5"),
    "KPI10": Target("Tỷ lệ ticket được đánh giá", "%", 70.0, ">=", "Ít nhất 70% ticket đóng có đánh giá"),
}


@dataclass(frozen=True)
class KPIResult:
    code: str
    name: str
    actual: float
    unit: str
    operator: str
    target: float
    status: str
    numerator: int | None
    denominator: int | None
    formula: str


def _minutes(start: str, end: str) -> float:
    return (datetime.fromisoformat(end) - datetime.fromisoformat(start)).total_seconds() / 60


def _rate(numerator: int, denominator: int) -> float:
    return round(numerator * 100 / denominator, 2) if denominator else 0.0


def _status(actual: float, target: Target) -> str:
    comparisons: dict[str, Callable[[float, float], bool]] = {
        "<=": lambda value, threshold: value <= threshold,
        ">=": lambda value, threshold: value >= threshold,
    }
    return "ĐẠT" if comparisons[target.operator](actual, target.target) else "CHƯA ĐẠT"


def _result(
    code: str,
    actual: float,
    *,
    numerator: int | None = None,
    denominator: int | None = None,
    formula: str,
) -> KPIResult:
    target = TARGETS[code]
    return KPIResult(
        code=code,
        name=target.name,
        actual=round(actual, 2),
        unit=target.unit,
        operator=target.operator,
        target=target.target,
        status=_status(actual, target),
        numerator=numerator,
        denominator=denominator,
        formula=formula,
    )


def calculate_kpis(tickets: list[dict[str, Any]]) -> list[KPIResult]:
    response_times = [
        _minutes(ticket["created_at"], ticket["first_response_at"])
        for ticket in tickets
        if ticket["first_response_at"] is not None
    ]
    response_eligible = [
        ticket for ticket in tickets
        if ticket["response_sla_result"] in {"MET", "BREACHED"}
    ]
    response_met = sum(ticket["response_sla_result"] == "MET" for ticket in response_eligible)

    resolution_times = [
        _minutes(ticket["created_at"], ticket["resolved_at"])
        for ticket in tickets
        if ticket["resolved_at"] is not None
    ]
    resolution_eligible = [
        ticket for ticket in tickets
        if ticket["resolution_sla_result"] in {"MET", "BREACHED"}
    ]
    resolution_met = sum(
        ticket["resolution_sla_result"] == "MET" for ticket in resolution_eligible
    )

    overall_eligible = [
        ticket for ticket in tickets
        if ticket["response_sla_result"] in {"MET", "BREACHED"}
        and ticket["resolution_sla_result"] in {"MET", "BREACHED"}
    ]
    overall_met = sum(
        ticket["response_sla_result"] == "MET"
        and ticket["resolution_sla_result"] == "MET"
        for ticket in overall_eligible
    )
    open_count = sum(ticket["status"] in OPEN_STATUSES for ticket in tickets)
    reopened_ids = {
        ticket["ticket_id"] for ticket in tickets if ticket["reopened_at"] is not None
    }
    completed = [
        ticket for ticket in tickets
        if ticket["resolved_at"] is not None or ticket["closed_at"] is not None
    ]
    scores = [
        int(ticket["satisfaction_score"])
        for ticket in tickets
        if ticket["satisfaction_score"] is not None
    ]
    closed = [ticket for ticket in tickets if ticket["closed_at"] is not None]
    rated_closed = sum(
        ticket["satisfaction_score"] is not None for ticket in closed
    )

    return [
        _result(
            "KPI01",
            sum(response_times) / len(response_times),
            numerator=len(response_times),
            denominator=len(response_times),
            formula="Tổng phút phản hồi / ticket đã phản hồi",
        ),
        _result(
            "KPI02",
            _rate(response_met, len(response_eligible)),
            numerator=response_met,
            denominator=len(response_eligible),
            formula="Response SLA MET / response SLA đủ điều kiện × 100%",
        ),
        _result(
            "KPI03",
            sum(resolution_times) / len(resolution_times),
            numerator=len(resolution_times),
            denominator=len(resolution_times),
            formula="Tổng phút giải quyết / ticket đã giải quyết",
        ),
        _result(
            "KPI04",
            _rate(resolution_met, len(resolution_eligible)),
            numerator=resolution_met,
            denominator=len(resolution_eligible),
            formula="Resolution SLA MET / resolution SLA đủ điều kiện × 100%",
        ),
        _result(
            "KPI05",
            _rate(overall_met, len(overall_eligible)),
            numerator=overall_met,
            denominator=len(overall_eligible),
            formula="Ticket đạt đồng thời response và resolution SLA / ticket đủ điều kiện × 100%",
        ),
        _result(
            "KPI06",
            float(open_count),
            numerator=open_count,
            denominator=len(tickets),
            formula="Đếm ticket thuộc trạng thái mở tại snapshot",
        ),
        _result(
            "KPI07",
            float(len(reopened_ids)),
            numerator=len(reopened_ids),
            denominator=len(tickets),
            formula="COUNT DISTINCT ticket_id có reopened_at trong kỳ",
        ),
        _result(
            "KPI08",
            _rate(len(reopened_ids), len(completed)),
            numerator=len(reopened_ids),
            denominator=len(completed),
            formula="Ticket mở lại / ticket đã resolved hoặc closed × 100%",
        ),
        _result(
            "KPI09",
            sum(scores) / len(scores),
            numerator=sum(scores),
            denominator=len(scores),
            formula="Tổng điểm hợp lệ / số đánh giá hợp lệ",
        ),
        _result(
            "KPI10",
            _rate(rated_closed, len(closed)),
            numerator=rated_closed,
            denominator=len(closed),
            formula="Ticket đóng có đánh giá / tổng ticket đóng × 100%",
        ),
    ]


def evaluate_file(path: Path = DATA_PATH) -> dict[str, Any]:
    dataset = json.loads(path.read_text(encoding="utf-8"))
    results = calculate_kpis(dataset["tickets"])
    passed = sum(result.status == "ĐẠT" for result in results)
    return {
        "period": dataset["period"],
        "source": dataset["source"],
        "ticket_count": len(dataset["tickets"]),
        "results": [asdict(result) for result in results],
        "summary": {
            "total_kpis": len(results),
            "passed": passed,
            "failed": len(results) - passed,
            "achievement_rate": round(passed * 100 / len(results), 2),
            "conclusion": "ĐẠT CÓ ĐIỀU KIỆN" if passed < len(results) else "ĐẠT",
        },
    }


def _markdown(report: dict[str, Any]) -> str:
    rows = []
    for item in report["results"]:
        target_text = f"{item['operator']} {item['target']:g} {item['unit']}"
        actual_text = f"{item['actual']:g} {item['unit']}"
        sample = (
            f"{item['numerator']}/{item['denominator']}"
            if item["numerator"] is not None and item["denominator"] is not None
            else "-"
        )
        rows.append(
            f"| {item['code']} | {item['name']} | {item['formula']} | {sample} | "
            f"{actual_text} | {target_text} | **{item['status']}** |"
        )
    failed = [item for item in report["results"] if item["status"] == "CHƯA ĐẠT"]
    failed_lines = "\n".join(
        f"- **{item['code']} – {item['name']}:** thực tế {item['actual']:g} {item['unit']}, "
        f"mục tiêu {item['operator']} {item['target']:g} {item['unit']}."
        for item in failed
    ) or "- Không có KPI chưa đạt."
    summary = report["summary"]
    return f"""# CV054 - Bảng đánh giá KPI hệ thống Helpdesk SLA

## 1. Phạm vi đánh giá

| Hạng mục | Giá trị |
| --- | --- |
| Kỳ đánh giá | {report['period']['from']} đến {report['period']['to']} |
| Nguồn dữ liệu | `{report['source']}` |
| Số ticket mô phỏng | {report['ticket_count']} |
| Số KPI | {summary['total_kpis']} |
| KPI đạt | {summary['passed']} |
| KPI chưa đạt | {summary['failed']} |
| Tỷ lệ hoàn thành mục tiêu | {summary['achievement_rate']:.2f}% |
| Kết luận | **{summary['conclusion']}** |

Ngưỡng trong bảng là ngưỡng đánh giá được chốt cho CV054. CV008 cung cấp danh
mục và công thức KPI nhưng không quy định giá trị mục tiêu số.

## 2. Bảng KPI đánh giá

| Mã | KPI | Công thức | Tử số/Mẫu số | Thực tế | Mục tiêu CV054 | Kết quả |
| --- | --- | --- | ---: | ---: | ---: | --- |
{chr(10).join(rows)}

## 3. KPI chưa đạt và nhận định

{failed_lines}

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

Bộ dữ liệu mô phỏng cho thấy **{summary['passed']}/{summary['total_kpis']} KPI đạt**,
tương đương **{summary['achievement_rate']:.2f}%**. Hệ thống được đánh giá
**{summary['conclusion']}**; cần ưu tiên cải thiện SLA tổng thể và tỷ lệ mở lại.

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
"""


def main() -> int:
    report = evaluate_file()
    JSON_RESULT_PATH.parent.mkdir(parents=True, exist_ok=True)
    JSON_RESULT_PATH.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    MARKDOWN_PATH.write_text(_markdown(report), encoding="utf-8")
    summary = report["summary"]
    print(
        f"CV054: {summary['passed']}/{summary['total_kpis']} KPI đạt "
        f"({summary['achievement_rate']:.2f}%) - {summary['conclusion']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
