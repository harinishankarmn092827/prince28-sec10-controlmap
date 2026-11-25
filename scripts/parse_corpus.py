"""Parse the downloaded corpus and persist pages or parse failures."""

from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path
from typing import Any

from controlmap.ingest.parse import SUPPORTED_TYPES, parse_document
from controlmap.ingest.store import record_parse_failure, store_parsed_document

PROJECT_ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = PROJECT_ROOT / "data" / "manifest.jsonl"
DOCUMENTS_DIR = PROJECT_ROOT / "data" / "documents"


def discover_documents() -> list[dict[str, Any]]:
    """Discover supported files listed in the manifest and local documents."""
    discovered: list[dict[str, Any]] = []
    seen_paths: set[Path] = set()

    if MANIFEST_PATH.is_file():
        with MANIFEST_PATH.open("r", encoding="utf-8") as manifest:
            for line_number, line in enumerate(manifest, start=1):
                if not line.strip():
                    continue

                try:
                    record = json.loads(line)
                except json.JSONDecodeError as error:
                    print(f"WARNING: Invalid manifest line {line_number}: {error}")
                    continue

                if not isinstance(record, dict):
                    continue

                if record.get("status") != "downloaded":
                    continue

                relative_path = record.get("path")
                if not isinstance(relative_path, str) or not relative_path.strip():
                    continue

                file_path = (PROJECT_ROOT / relative_path).resolve()

                if not file_path.is_relative_to(PROJECT_ROOT.resolve()):
                    print(f"WARNING: Skipping path outside project: {relative_path}")
                    continue

                if file_path.suffix.lower() not in SUPPORTED_TYPES:
                    continue

                if not file_path.is_file():
                    print(f"WARNING: File not found: {relative_path}")
                    continue

                if file_path not in seen_paths:
                    discovered.append({"path": file_path, "metadata": record})
                    seen_paths.add(file_path)

    if DOCUMENTS_DIR.is_dir():
        for file_path in sorted(DOCUMENTS_DIR.rglob("*")):
            if not file_path.is_file():
                continue

            if file_path.suffix.lower() not in SUPPORTED_TYPES:
                continue

            resolved_path = file_path.resolve()

            if resolved_path in seen_paths:
                continue

            discovered.append(
                {
                    "path": resolved_path,
                    "metadata": {
                        "title": file_path.stem,
                        "source": "local",
                    },
                }
            )
            seen_paths.add(resolved_path)

    return discovered


async def process_corpus(dry_run: bool = False) -> tuple[int, int]:
    """Parse each discovered file and persist results unless dry-run is enabled."""
    documents = discover_documents()

    if not documents:
        print("No supported documents found.")
        return 0, 0

    print(f"Found {len(documents)} supported document(s).")

    if dry_run:
        print("DRY RUN: The database will not be modified.")

    successful = 0
    failed = 0

    for record in documents:
        file_path: Path = record["path"]
        metadata: dict[str, Any] = record["metadata"]

        try:
            parsed = parse_document(file_path)

            if not parsed.pages or not any(page.text.strip() for page in parsed.pages):
                raise ValueError("No extractable text was found in the document.")

            page_count = len(parsed.pages)
            table_count = sum(len(page.tables) for page in parsed.pages)

            if dry_run:
                print(
                    f"PARSED: {file_path.name} | parser={parsed.parser} | "
                    f"pages={page_count} | tables={table_count}"
                )
            else:
                result = await store_parsed_document(
                    file_path=file_path,
                    parsed=parsed,
                    metadata=metadata,
                )
                print(result)

            successful += 1

        except Exception as error:
            failed += 1
            print(f"FAILED: {file_path.name} | {type(error).__name__}: {error}")

            if not dry_run:
                try:
                    result = await record_parse_failure(
                        file_path=file_path,
                        error=error,
                        metadata=metadata,
                    )
                    print(result)
                except Exception as storage_error:
                    print(
                        "ERROR: Could not record failure for "
                        f"{file_path.name}: {storage_error}"
                    )

    print("\nCorpus summary")
    print(f"Total documents: {len(documents)}")
    print(f"Successful: {successful}")
    print(f"Failed: {failed}")

    if dry_run:
        print("Database changes: None")

    return successful, failed


async def main() -> None:
    """Run corpus parsing."""
    parser = argparse.ArgumentParser(
        description="Parse the document corpus and save results to PostgreSQL."
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Parse files without writing to the database.",
    )
    args = parser.parse_args()

    await process_corpus(dry_run=args.dry_run)


if __name__ == "__main__":
    asyncio.run(main())
