"""Compare versioned classification prompts against the labelled test set."""

from __future__ import annotations

import argparse
import asyncio
import json
from collections import Counter
from pathlib import Path
from typing import Any

from controlmap.llm.classify import classify_question

ROOT = Path(__file__).resolve().parents[1]
TESTSET = ROOT / "eval" / "prompt_testset.jsonl"
CACHE_DIR = ROOT / "eval" / "cache"
REPORT_PATH = ROOT / "eval" / "prompt_comparison.json"


def load_testset() -> list[dict[str, str]]:
    """Load and validate the labelled JSONL test set."""
    if not TESTSET.is_file():
        raise FileNotFoundError(f"Test set not found: {TESTSET}")

    rows: list[dict[str, str]] = []

    for line_number, line in enumerate(
        TESTSET.read_text(encoding="utf-8-sig").splitlines(), start=1
    ):
        if not line.strip():
            continue

        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Invalid JSON on test-set line {line_number}") from exc

        question = row.get("question")
        label = row.get("label")

        if not isinstance(question, str) or not question.strip():
            raise ValueError(f"Missing question on line {line_number}")

        if label not in {"docs", "personal", "off_topic"}:
            raise ValueError(f"Invalid label on line {line_number}: {label!r}")

        rows.append({"question": question.strip(), "label": label})

    if not rows:
        raise ValueError("The prompt test set is empty")

    return rows


def load_cache(path: Path) -> dict[str, dict[str, Any]]:
    """Read cached results, if available."""
    if not path.exists():
        return {}

    cache: dict[str, dict[str, Any]] = {}

    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue

        try:
            item = json.loads(line)
        except json.JSONDecodeError:
            continue

        if isinstance(item, dict) and isinstance(item.get("question"), str):
            cache[item["question"]] = item

    return cache


def save_cache(
    path: Path,
    cache: dict[str, dict[str, Any]],
) -> None:
    """Write cached results in a stable order."""
    path.parent.mkdir(parents=True, exist_ok=True)

    content = "".join(
        json.dumps(item, ensure_ascii=False) + "\n" for item in cache.values()
    )
    path.write_text(content, encoding="utf-8")


async def evaluate_version(
    version: int,
    rows: list[dict[str, str]],
    *,
    retry_failed: bool,
) -> dict[str, Any]:
    """Evaluate one prompt version, reusing previously cached responses."""
    cache_path = CACHE_DIR / f"classify_v{version}.jsonl"
    cache = load_cache(cache_path)
    misses: list[dict[str, str]] = []
    correct = 0
    evaluated = 0
    errors = 0

    print(f"\nEvaluating classify_v{version} ({len(rows)} questions)")

    for index, row in enumerate(rows, start=1):
        question = row["question"]
        expected = row["label"]
        cached = cache.get(question)

        if (
            cached
            and cached.get("predicted") in {"docs", "personal", "off_topic"}
            and not retry_failed
        ):
            predicted = cached.get("predicted")
            error = cached.get("error")
        else:
            predicted = None
            error = None

            try:
                result = await classify_question(question, version=version)
                predicted = result.label
                reason = result.reason
            except Exception as exc:
                error = f"{type(exc).__name__}: {exc}"
                reason = ""

            cache[question] = {
                "version": version,
                "question": question,
                "expected": expected,
                "predicted": predicted,
                "reason": reason,
                "error": error,
            }
            save_cache(cache_path, cache)

        if predicted not in {"docs", "personal", "off_topic"}:
            errors += 1
            print(f"  {index:02}/{len(rows)} ERROR: {error or 'Invalid label'}")
            continue

        evaluated += 1

        if predicted == expected:
            correct += 1
            status = "PASS"
        else:
            status = "MISS"
            misses.append(
                {
                    "question": question,
                    "expected": expected,
                    "predicted": predicted,
                }
            )

        print(
            f"  {index:02}/{len(rows)} {status}: "
            f"expected={expected}, predicted={predicted}"
        )

    accuracy = correct / len(rows) if rows else 0.0

    result_summary = {
        "version": version,
        "total_questions": len(rows),
        "evaluated": evaluated,
        "correct": correct,
        "accuracy": round(accuracy, 4),
        "errors": errors,
        "misses": misses,
    }

    print(
        f"  SUMMARY: {correct}/{evaluated} correct; "
        f"accuracy={accuracy:.1%}; errors={errors}"
    )

    return result_summary


async def main() -> None:
    parser = argparse.ArgumentParser(
        description="Compare versioned classification prompts."
    )
    parser.add_argument(
        "--versions",
        type=int,
        nargs="+",
        default=[1, 2, 3],
        help="Prompt versions to evaluate (default: 1 2 3).",
    )
    parser.add_argument(
        "--retry-failed",
        action="store_true",
        help="Re-run all questions, including cached results.",
    )
    args = parser.parse_args()

    rows = load_testset()
    print(f"Loaded {len(rows)} labelled questions.")
    print("Label distribution:", dict(Counter(row["label"] for row in rows)))

    summaries = []

    for version in args.versions:
        summaries.append(
            await evaluate_version(
                version,
                rows,
                retry_failed=args.retry_failed,
            )
        )

    report = {
        "testset": str(TESTSET.relative_to(ROOT)),
        "question_count": len(rows),
        "results": summaries,
    }

    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    print(f"\nReport saved to: {REPORT_PATH.relative_to(ROOT)}")
    print("\nAccuracy summary:")
    for summary in summaries:
        print(
            f"  v{summary['version']}: "
            f"{summary['correct']}/{summary['evaluated']} correct "
            f"({summary['accuracy']:.1%}), "
            f"errors={summary['errors']}"
        )


if __name__ == "__main__":
    asyncio.run(main())
