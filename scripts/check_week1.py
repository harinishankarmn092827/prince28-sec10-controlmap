"""Self-check script for the ControlMap Week 1 checklist."""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path
from urllib.error import URLError
from urllib.request import urlopen

ROOT = Path.cwd()

OK = "✅"
BAD = "❌"
WARN = "⚠️"

passed = 0
failed = 0
warnings = 0


def check(
    day: str,
    description: str,
    condition: bool,
    detail: str = "",
) -> None:
    """Print one checklist result and update the totals."""
    global passed, failed

    if condition:
        passed += 1
        print(f"{OK} {day}: {description}")
    else:
        failed += 1
        suffix = f" — {detail}" if detail else ""
        print(f"{BAD} {day}: {description}{suffix}")


def warn(day: str, description: str, detail: str = "") -> None:
    """Print a warning that does not count as a failure."""
    global warnings

    warnings += 1
    suffix = f" — {detail}" if detail else ""
    print(f"{WARN} {day}: {description}{suffix}")


def exists(path: str) -> bool:
    """Return whether a project-relative path exists."""
    return (ROOT / path).exists()


def read_text(path: str) -> str:
    """Read a project file, returning an empty string if unavailable."""
    file_path = ROOT / path

    try:
        return file_path.read_text(encoding="utf-8")
    except (OSError, UnicodeError):
        return ""


def run(cmd: list[str]) -> subprocess.CompletedProcess[str]:
    """Run a command from the project root with imports configured."""
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT)

    try:
        return subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            cwd=ROOT,
            env=env,
            timeout=180,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        return subprocess.CompletedProcess(
            args=cmd,
            returncode=1,
            stdout="",
            stderr=str(error),
        )


def check_file_exists(day: str, paths: list[str]) -> None:
    """Check that all listed project files exist."""
    for path in paths:
        check(day, f"{path} exists", exists(path), "file missing")


def main() -> int:
    """Run the Week 1 self-checks."""
    global passed, failed, warnings

    if not (ROOT / "scripts/check_week1.py").exists():
        print("Please run this script from the project root directory.")
        return 1

    live_url = (
        sys.argv[1].rstrip("/")
        if len(sys.argv) > 1
        else "https://prince28-sec10-controlmap.onrender.com"
    )

    print("=" * 65)
    print("ControlMap — Week 1 Self-Check")
    print(f"Project root: {ROOT}")
    print(f"Live URL: {live_url}")
    print("=" * 65)

    # D01 — Project setup and documentation
    print("\n--- D01: Project Setup ---")

    check_file_exists(
        "D01",
        [
            "README.md",
            "pyproject.toml",
            ".pre-commit-config.yaml",
            "docs/QUESTIONS.md",
        ],
    )

    questions_text = read_text("docs/QUESTIONS.md")
    question_rows = re.findall(
        r"^\s*\|\s*\d+\s*\|",
        questions_text,
        flags=re.MULTILINE,
    )
    check(
        "D01",
        "At least 10 practice questions",
        len(question_rows) >= 10,
        f"{len(question_rows)} numbered table rows found",
    )

    tracked = run(["git", "ls-files"]).stdout.split()
    check(
        "D01",
        ".env is not tracked by Git",
        ".env" not in tracked,
        "Review Git tracking before committing secrets",
    )

    # D02 — Application and sample data
    print("\n--- D02: Application ---")

    check_file_exists(
        "D02",
        [
            "app/main.py",
            "app/core/config.py",
            "app/data/sample_records.json",
        ],
    )

    records_path = ROOT / "app/data/sample_records.json"

    try:
        records = json.loads(records_path.read_text(encoding="utf-8"))
        record_count = len(records)
        records_valid = isinstance(records, (list, dict))
    except (OSError, json.JSONDecodeError, TypeError):
        record_count = 0
        records_valid = False

    check(
        "D02",
        "Sample records JSON is valid",
        records_valid,
        "Could not parse app/data/sample_records.json",
    )

    check(
        "D02",
        "Sample records file contains at least 20 records",
        records_valid and record_count >= 20,
        f"{record_count} records found",
    )

    # D03 — Database and migrations
    print("\n--- D03: Database ---")

    check_file_exists(
        "D03",
        [
            "app/database/models.py",
            "scripts/load_db.py",
        ],
    )

    migration_dir = ROOT / "migrations/versions"
    migration_files = list(migration_dir.glob("*.py")) if migration_dir.exists() else []

    check(
        "D03",
        "At least three migration files exist",
        len(migration_files) >= 3,
        f"{len(migration_files)} migration files found",
    )

    notes_text = read_text("NOTES.md")

    check(
        "D03",
        "NOTES.md contains the D03 section",
        "## D03" in notes_text,
        "Add a D03 database and migration section",
    )

    # D04 — Tests and local running instructions
    print("\n--- D04: Tests and Local Setup ---")

    check_file_exists(
        "D04",
        [
            "tests/unit",
            "tests/integration",
            "scripts/smoke.py",
        ],
    )

    readme_text = read_text("README.md")

    check(
        "D04",
        "README explains how to run the project locally",
        "Run locally in one command" in readme_text,
        "Add the required heading to README.md",
    )

    test_result = run(
        [
            "uv",
            "run",
            "python",
            "-m",
            "pytest",
            "tests/unit",
            "-q",
        ]
    )

    test_output = f"{test_result.stdout}\n{test_result.stderr}".strip()

    check(
        "D04",
        "Unit tests pass",
        test_result.returncode == 0,
        test_output[-1200:] or "No test output",
    )

    # D05 — CI/CD and deployment
    print("\n--- D05: CI/CD and Deployment ---")

    check_file_exists(
        "D05",
        [
            ".github/workflows/ci.yml",
            ".github/workflows/cd.yml",
            "Dockerfile",
            ".dockerignore",
            "docker-compose.yml",
            "Makefile",
        ],
    )

    check(
        "D05",
        "NOTES.md contains the D05 section",
        "## D05" in notes_text,
        "Add a D05 CI/CD and deployment section",
    )

    check(
        "D05",
        "README contains a live application URL",
        "prince28-sec10-controlmap.onrender.com" in readme_text,
        "Add the deployed application URL",
    )

    tag_result = run(["git", "tag", "--list", "week-1"])

    check(
        "D05",
        "week-1 Git tag exists locally",
        "week-1" in tag_result.stdout.split(),
        "Create or fetch the week-1 tag",
    )

    # Live deployment health
    print("\n--- Live Deployment ---")

    try:
        with urlopen(f"{live_url}/health", timeout=15) as response:
            status = response.status
            body = response.read().decode("utf-8", errors="replace")

        check(
            "LIVE",
            "Health endpoint returns HTTP 200",
            status == 200,
            f"HTTP {status}",
        )

        try:
            health_data = json.loads(body)
        except json.JSONDecodeError:
            health_data = {}

        print(f"Health response: {body[:500]}")

        # A version mismatch is informational because the deployed
        # service may not yet be running the latest local commit.
        current_commit = run(["git", "rev-parse", "HEAD"]).stdout.strip()

        reported_version = str(health_data.get("version", ""))

        if reported_version and current_commit:
            if reported_version in current_commit:
                check(
                    "LIVE",
                    "Deployed version matches local commit",
                    True,
                )
            else:
                warn(
                    "LIVE",
                    "Deployed version may differ from local commit",
                    (
                        f"API version={reported_version}; "
                        f"local HEAD={current_commit[:12]}"
                    ),
                )
        else:
            warn(
                "LIVE",
                "Could not compare deployed version with local commit",
                "The health response or Git commit did not provide a version",
            )

    except (URLError, TimeoutError, OSError) as error:
        check(
            "LIVE",
            "Health endpoint returns HTTP 200",
            False,
            str(error),
        )

    # Final summary
    total = passed + failed

    print("\n" + "=" * 65)
    print("WEEK 1 SELF-CHECK SUMMARY")
    print("=" * 65)
    print(f"Passed:   {passed}")
    print(f"Failed:   {failed}")
    print(f"Warnings: {warnings}")
    print(f"Total checks counted: {total}")

    if failed == 0:
        print(f"\n{OK} All automated checks passed.")
        print("Review any warnings and confirm the official checklist.")
        return 0

    print(f"\n{BAD} Some checks need attention.")
    print("Fix the failed items above and run the self-check again.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
