"""Run CV056 UI contract tests and the complete regression suite."""

from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys
import xml.etree.ElementTree as ET


PROJECT_ROOT = Path(__file__).resolve().parents[1]
EVIDENCE_DIR = PROJECT_ROOT / "evidence"
UI_JUNIT = EVIDENCE_DIR / "CV056_UI_JUNIT.xml"
UI_OUTPUT = EVIDENCE_DIR / "CV056_UI_TEST_OUTPUT.txt"
REGRESSION_JUNIT = EVIDENCE_DIR / "CV056_REGRESSION_JUNIT.xml"
REGRESSION_OUTPUT = EVIDENCE_DIR / "CV056_REGRESSION_OUTPUT.txt"
RESULT_PATH = EVIDENCE_DIR / "CV056_UI_TEST_RESULT.txt"


def _run(command: list[str]) -> subprocess.CompletedProcess[str]:
    environment = os.environ.copy()
    environment["PYTHONUTF8"] = "1"
    return subprocess.run(
        command,
        cwd=PROJECT_ROOT,
        env=environment,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )


def _write_output(path: Path, completed: subprocess.CompletedProcess[str]) -> None:
    transcript = completed.stdout
    if completed.stderr:
        transcript += "\n" + completed.stderr
    path.write_text(transcript, encoding="utf-8")


def _totals(path: Path) -> dict[str, int]:
    root = ET.parse(path).getroot()
    suites = [root] if root.tag == "testsuite" else list(root.findall("testsuite"))
    totals = {"tests": 0, "failures": 0, "errors": 0, "skipped": 0}
    for suite in suites:
        for key in totals:
            totals[key] += int(suite.attrib.get(key, 0))
    totals["passed"] = totals["tests"] - totals["failures"] - totals["errors"] - totals["skipped"]
    return totals


def _fallback() -> dict[str, int]:
    return {"tests": 0, "passed": 0, "failures": 0, "errors": 1, "skipped": 0}


def main() -> int:
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    ui = _run(
        [
            sys.executable,
            "-m",
            "pytest",
            "-m",
            "ui_complete",
            "-v",
            "--junitxml=evidence/CV056_UI_JUNIT.xml",
        ]
    )
    _write_output(UI_OUTPUT, ui)
    regression = _run(
        [
            sys.executable,
            "-m",
            "pytest",
            "--junitxml=evidence/CV056_REGRESSION_JUNIT.xml",
        ]
    )
    _write_output(REGRESSION_OUTPUT, regression)

    ui_totals = _totals(UI_JUNIT) if UI_JUNIT.is_file() else _fallback()
    regression_totals = (
        _totals(REGRESSION_JUNIT) if REGRESSION_JUNIT.is_file() else _fallback()
    )
    accepted = ui.returncode == 0 and regression.returncode == 0
    result = "\n".join(
        [
            "CV056 COMPLETE RESPONSIVE UI TEST RESULT",
            f"CV056 UI tests: {ui_totals['passed']}/{ui_totals['tests']} passed",
            f"CV056 failures/errors/skipped: {ui_totals['failures']}/{ui_totals['errors']}/{ui_totals['skipped']}",
            f"Regression tests: {regression_totals['passed']}/{regression_totals['tests']} passed",
            f"Regression failures/errors/skipped: {regression_totals['failures']}/{regression_totals['errors']}/{regression_totals['skipped']}",
            f"UI exit code: {ui.returncode}",
            f"Regression exit code: {regression.returncode}",
            "Result: PASSED - UI COMPLETE" if accepted else "Result: FAILED",
            "",
        ]
    )
    RESULT_PATH.write_text(result, encoding="utf-8")
    print(result, end="")
    return 0 if accepted else 1


if __name__ == "__main__":
    raise SystemExit(main())
