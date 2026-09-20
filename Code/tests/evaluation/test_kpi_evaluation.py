import json

import pytest

from scripts.evaluate_kpis import DATA_PATH, TARGETS, evaluate_file


pytestmark = pytest.mark.kpi_evaluation


def test_cv054_calculates_all_ten_kpis_from_simulated_data():
    report = evaluate_file()
    actual = {item["code"]: item["actual"] for item in report["results"]}

    assert report["ticket_count"] == 10
    assert actual == {
        "KPI01": 41.11,
        "KPI02": 88.89,
        "KPI03": 202.5,
        "KPI04": 87.5,
        "KPI05": 75.0,
        "KPI06": 1.0,
        "KPI07": 1.0,
        "KPI08": 12.5,
        "KPI09": 4.29,
        "KPI10": 100.0,
    }


def test_cv054_compares_targets_and_preserves_traceability():
    dataset = json.loads(DATA_PATH.read_text(encoding="utf-8"))
    report = evaluate_file()
    results = {item["code"]: item for item in report["results"]}

    assert len({ticket["ticket_id"] for ticket in dataset["tickets"]}) == 10
    assert set(results) == set(TARGETS)
    assert {code for code, item in results.items() if item["status"] == "CHƯA ĐẠT"} == {
        "KPI05",
        "KPI08",
    }
    assert report["summary"] == {
        "total_kpis": 10,
        "passed": 8,
        "failed": 2,
        "achievement_rate": 80.0,
        "conclusion": "ĐẠT CÓ ĐIỀU KIỆN",
    }
    assert results["KPI05"]["numerator"] == 6
    assert results["KPI05"]["denominator"] == 8
    assert results["KPI08"]["numerator"] == 1
    assert results["KPI08"]["denominator"] == 8
