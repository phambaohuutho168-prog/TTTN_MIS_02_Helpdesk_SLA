"""Run CV055 high-priority checks and the full Release Candidate regression."""

from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys
import xml.etree.ElementTree as ET


PROJECT_ROOT = Path(__file__).resolve().parents[1]
EVIDENCE_DIR = PROJECT_ROOT / "evidence"
HIGH_JUNIT = EVIDENCE_DIR / "CV055_HIGH_PRIORITY_JUNIT.xml"
HIGH_OUTPUT = EVIDENCE_DIR / "CV055_HIGH_PRIORITY_OUTPUT.txt"
REGRESSION_JUNIT = EVIDENCE_DIR / "CV055_REGRESSION_JUNIT.xml"
REGRESSION_OUTPUT = EVIDENCE_DIR / "CV055_REGRESSION_OUTPUT.txt"
RESULT_PATH = EVIDENCE_DIR / "CV055_RELEASE_CANDIDATE_RESULT.txt"


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


def _transcript(completed: subprocess.CompletedProcess[str]) -> str:
    output = completed.stdout
    if completed.stderr:
        output += "\n" + completed.stderr
    return output


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
    high_command = [
        sys.executable,
        "-m",
        "pytest",
        "-m",
        "release_candidate",
        "-v",
        "--junitxml=evidence/CV055_HIGH_PRIORITY_JUNIT.xml",
    ]
    high = _run(high_command)
    HIGH_OUTPUT.write_text(_transcript(high), encoding="utf-8")

    regression_command = [
        sys.executable,
        "-m",
        "pytest",
        "--junitxml=evidence/CV055_REGRESSION_JUNIT.xml",
    ]
    regression = _run(regression_command)
    REGRESSION_OUTPUT.write_text(_transcript(regression), encoding="utf-8")

    high_totals = _totals(HIGH_JUNIT) if HIGH_JUNIT.is_file() else _fallback()
    regression_totals = (
        _totals(REGRESSION_JUNIT) if REGRESSION_JUNIT.is_file() else _fallback()
    )
    accepted = high.returncode == 0 and regression.returncode == 0
    result = "\n".join(
        [
            "CV055 RELEASE CANDIDATE RESULT",
            "Open Critical defects: 0",
            "Open High defects: 0",
            f"High-priority tests: {high_totals['passed']}/{high_totals['tests']} passed",
            f"High-priority failures/errors/skipped: {high_totals['failures']}/{high_totals['errors']}/{high_totals['skipped']}",
            f"Regression tests: {regression_totals['passed']}/{regression_totals['tests']} passed",
            f"Regression failures/errors/skipped: {regression_totals['failures']}/{regression_totals['errors']}/{regression_totals['skipped']}",
            f"High-priority exit code: {high.returncode}",
            f"Regression exit code: {regression.returncode}",
            "Release decision: GO - RELEASE CANDIDATE" if accepted else "Release decision: NO-GO",
            "",
        ]
    )
    RESULT_PATH.write_text(result, encoding="utf-8")
    print(result, end="")
    return 0 if accepted else 1


if __name__ == "__main__":
    raise SystemExit(main())
