"""Regenerate the CV054 KPI table and persist its automated test evidence."""

from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys
import xml.etree.ElementTree as ET

from evaluate_kpis import evaluate_file, main as generate_kpi_report


PROJECT_ROOT = Path(__file__).resolve().parents[1]
EVIDENCE_DIR = PROJECT_ROOT / "evidence"
JUNIT_PATH = EVIDENCE_DIR / "CV054_JUNIT.xml"
OUTPUT_PATH = EVIDENCE_DIR / "CV054_PYTEST_OUTPUT.txt"
RESULT_PATH = EVIDENCE_DIR / "CV054_TEST_RESULT.txt"


def _totals(path: Path) -> dict[str, int]:
    root = ET.parse(path).getroot()
    suites = [root] if root.tag == "testsuite" else list(root.findall("testsuite"))
    totals = {"tests": 0, "failures": 0, "errors": 0, "skipped": 0}
    for suite in suites:
        for key in totals:
            totals[key] += int(suite.attrib.get(key, 0))
    totals["passed"] = totals["tests"] - totals["failures"] - totals["errors"] - totals["skipped"]
    return totals


def main() -> int:
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    generate_kpi_report()
    command = [
        sys.executable,
        "-m",
        "pytest",
        "-m",
        "kpi_evaluation",
        "-v",
        "--junitxml=evidence/CV054_JUNIT.xml",
    ]
    environment = os.environ.copy()
    environment["PYTHONUTF8"] = "1"
    completed = subprocess.run(
        command,
        cwd=PROJECT_ROOT,
        env=environment,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    transcript = completed.stdout
    if completed.stderr:
        transcript += "\n" + completed.stderr
    OUTPUT_PATH.write_text(transcript, encoding="utf-8")
    totals = _totals(JUNIT_PATH) if JUNIT_PATH.is_file() else {
        "tests": 0,
        "passed": 0,
        "failures": 0,
        "errors": 1,
        "skipped": 0,
    }
    kpi_summary = evaluate_file()["summary"]
    result = "\n".join(
        [
            "CV054 KPI EVALUATION TEST RESULT",
            f"KPI passed: {kpi_summary['passed']}/{kpi_summary['total_kpis']}",
            f"KPI achievement rate: {kpi_summary['achievement_rate']:.2f}%",
            f"KPI conclusion: {kpi_summary['conclusion']}",
            f"Tests: {totals['tests']}",
            f"Passed: {totals['passed']}",
            f"Failures: {totals['failures']}",
            f"Errors: {totals['errors']}",
            f"Skipped: {totals['skipped']}",
            f"Exit code: {completed.returncode}",
            "Result: PASSED" if completed.returncode == 0 else "Result: FAILED",
            "",
        ]
    )
    RESULT_PATH.write_text(result, encoding="utf-8")
    print(result, end="")
    return completed.returncode


if __name__ == "__main__":
    raise SystemExit(main())
