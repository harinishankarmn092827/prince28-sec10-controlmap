"""Compare PyMuPDF and pypdf on locally downloaded PDF files."""

from __future__ import annotations

import csv
import time
from pathlib import Path
from typing import Any

import pymupdf
from pypdf import PdfReader

ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = ROOT / "data" / "raw"
OUTPUT = ROOT / "data" / "parser_comparison.csv"

FIELDS = [
    "filename",
    "parser",
    "status",
    "pages",
    "characters",
    "empty_pages",
    "elapsed_seconds",
    "error",
]


def compare_pymupdf(path: Path) -> dict[str, Any]:
    """Extract text with PyMuPDF."""
    with pymupdf.open(path) as document:
        page_texts = [page.get_text("text", sort=True) for page in document]

    return {
        "pages": len(page_texts),
        "characters": sum(len(text.strip()) for text in page_texts),
        "empty_pages": sum(not text.strip() for text in page_texts),
    }


def compare_pypdf(path: Path) -> dict[str, Any]:
    """Extract text with pypdf."""
    reader = PdfReader(str(path))
    page_texts = [page.extract_text() or "" for page in reader.pages]

    return {
        "pages": len(page_texts),
        "characters": sum(len(text.strip()) for text in page_texts),
        "empty_pages": sum(not text.strip() for text in page_texts),
    }


def run_comparison() -> int:
    """Compare both parsers and write a CSV report."""
    pdf_files = sorted(RAW_DIR.rglob("*.pdf"))

    if not pdf_files:
        print(f"No PDF files found under {RAW_DIR}")
        return 1

    results: list[dict[str, Any]] = []
    parsers = {
        "pymupdf": compare_pymupdf,
        "pypdf": compare_pypdf,
    }

    print(f"Found {len(pdf_files)} PDF file(s).")
    print(f"Comparing {len(parsers)} parsers; database will not be modified.\n")

    for path in pdf_files:
        print(f"Document: {path.name}")

        for parser_name, parser_function in parsers.items():
            started = time.perf_counter()

            try:
                metrics = parser_function(path)
                result = {
                    "filename": path.name,
                    "parser": parser_name,
                    "status": "success",
                    **metrics,
                    "elapsed_seconds": round(time.perf_counter() - started, 4),
                    "error": "",
                }
            except Exception as exc:
                result = {
                    "filename": path.name,
                    "parser": parser_name,
                    "status": "failed",
                    "pages": 0,
                    "characters": 0,
                    "empty_pages": 0,
                    "elapsed_seconds": round(time.perf_counter() - started, 4),
                    "error": f"{type(exc).__name__}: {exc}",
                }

            results.append(result)
            print(
                f"  {parser_name}: {result['status']}, "
                f"pages={result['pages']}, "
                f"characters={result['characters']}, "
                f"empty_pages={result['empty_pages']}, "
                f"time={result['elapsed_seconds']}s"
            )

            if result["error"]:
                print(f"    Error: {result['error']}")

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)

    with OUTPUT.open("w", newline="", encoding="utf-8") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(results)

    print(f"\nComparison complete: {len(pdf_files)} PDFs tested.")
    print(f"Results saved to: {OUTPUT.relative_to(ROOT)}")
    print("Note: text length alone does not measure extraction quality.")
    return 0


if __name__ == "__main__":
    raise SystemExit(run_comparison())
