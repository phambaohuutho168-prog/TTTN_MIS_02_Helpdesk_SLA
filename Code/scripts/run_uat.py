"""Run CV053 role-based UAT scenarios and persist reproducible evidence."""

from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path
import subprocess
import sys
import xml.etree.ElementTree as ET


PROJECT_ROOT = Path(__file__).resolve().parents[1]
EVIDENCE_DIR = PROJECT_ROOT / "evidence"
JUNIT_PATH = EVIDENCE_DIR / "CV053_JUNIT.xml"
OUTPUT_PATH = EVIDENCE_DIR / "CV053_PYTEST_OUTPUT.txt"
RESULT_PATH = EVIDENCE_DIR / "CV053_UAT_TEST_RESULT.txt"


def _suite_totals(path: Path) -> dict[str, int]:
    root = ET.parse(path).getroot()
    suites = [root] if root.tag == "testsuite" else list(root.findall("testsuite"))
    totals = {"tests": 0, "failures": 0, "errors": 0, "skipped": 0}
    for suite in suites:
        for key in totals:
            totals[key] += int(suite.attrib.get(key, 0))
    totals["passed"] = (
        totals["tests"]
        - totals["failures"]
        - totals["errors"]
        - totals["skipped"]
    )
    return totals


def main() -> int:
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    command = [
        sys.executable,
        "-m",
        "pytest",
        "-m",
        "uat",
        "-v",
        "--junitxml=evidence/CV053_JUNIT.xml",
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

    if JUNIT_PATH.is_file():
        totals = _suite_totals(JUNIT_PATH)
    else:
        totals = {"tests": 0, "passed": 0, "failures": 0, "errors": 1, "skipped": 0}

    pass_rate = totals["passed"] / totals["tests"] * 100 if totals["tests"] else 0.0
    generated_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    result = "\n".join(
        [
            "CV053 ROLE-BASED USER ACCEPTANCE TEST RESULT",
            f"Generated at (UTC): {generated_at}",
            "Command: python -m pytest -m uat -v --junitxml=evidence/CV053_JUNIT.xml",
            f"Tests: {totals['tests']}",
            f"Passed: {totals['passed']}",
            f"Failures: {totals['failures']}",
            f"Errors: {totals['errors']}",
            f"Skipped: {totals['skipped']}",
            f"Pass rate: {pass_rate:.2f}%",
            f"Exit code: {completed.returncode}",
            "Result: ACCEPTED" if completed.returncode == 0 else "Result: NOT ACCEPTED",
            "",
        ]
    )
    RESULT_PATH.write_text(result, encoding="utf-8")
    print(result, end="")
    return completed.returncode


if __name__ == "__main__":
    raise SystemExit(main())
