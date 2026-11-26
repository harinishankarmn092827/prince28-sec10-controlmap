"""Extract and persist validated metadata for source documents."""

from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.database.connection import AsyncSessionLocal
from app.database.models import Document
from controlmap.llm.doc_meta import DocumentMetadata
from controlmap.llm.extract import extract_metadata

ROOT = Path(__file__).resolve().parents[1]

RATE_LIMIT_SECONDS = 5
MAX_DOCUMENT_CHARS = 20_000
EXTRACTION_MARKER = "_metadata_extraction"


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Extract validated metadata from source documents."
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Maximum number of documents to process.",
    )
    parser.add_argument(
        "--retry-failed",
        action="store_true",
        help="Retry documents whose previous extraction failed.",
    )
    parser.add_argument(
        "--schema",
        action="store_true",
        help="Print the metadata JSON schema and exit.",
    )
    parser.add_argument(
        "--prompt-version",
        type=int,
        default=1,
        help="Extraction prompt version (default: 1).",
    )
    return parser.parse_args()


def is_source_document(document: Document) -> bool:
    """Exclude existing control records from source-document extraction."""
    return document.doc_type.lower() not in {"control_record", "record"}


def document_text(document: Document) -> str:
    """Combine a document's stored page text in page order."""
    ordered_pages = sorted(document.pages, key=lambda page: page.page_no)
    parts = [
        page.text.strip() for page in ordered_pages if page.text and page.text.strip()
    ]
    return "\n\n".join(parts)[:MAX_DOCUMENT_CHARS]


def has_useful_metadata(metadata: dict[str, object]) -> bool:
    """Return whether extraction produced at least one useful field."""
    return any(value not in (None, "", [], {}) for value in metadata.values())


async def run(args: argparse.Namespace) -> int:
    """Process eligible documents, committing each result for resumability."""
    if args.limit is not None and args.limit < 1:
        print("ERROR: --limit must be greater than zero.")
        return 2

    if args.schema:
        print(json.dumps(DocumentMetadata.model_json_schema(), indent=2))
        return 0

    if args.prompt_version < 1:
        print("ERROR: --prompt-version must be greater than zero.")
        return 2

    counts = {
        "processed": 0,
        "succeeded": 0,
        "failed": 0,
        "skipped": 0,
    }

    async with AsyncSessionLocal() as session:
        statement = (
            select(Document)
            .options(selectinload(Document.pages))
            .where(Document.doc_type.notin_(["control_record", "record"]))
            .order_by(Document.id)
        )
        documents = list((await session.scalars(statement)).all())

        candidates: list[Document] = []

        for document in documents:
            if not is_source_document(document):
                counts["skipped"] += 1
                continue

            metadata = dict(document.document_metadata or {})
            previous = metadata.get(EXTRACTION_MARKER, {})
            status = previous.get("status") if isinstance(previous, dict) else None

            if status == "success":
                counts["skipped"] += 1
                continue

            if status == "failed" and not args.retry_failed:
                counts["skipped"] += 1
                continue

            if not document_text(document):
                metadata[EXTRACTION_MARKER] = {
                    "status": "failed",
                    "error": "No stored page text available",
                }
                document.document_metadata = metadata
                await session.commit()
                counts["failed"] += 1
                print(f"SKIP: document {document.id} has no page text")
                continue

            candidates.append(document)

        if args.limit is not None:
            candidates = candidates[: args.limit]

        print(f"Eligible documents selected: {len(candidates)}")
        print(f"Previously skipped documents: {counts['skipped']}")

        for index, document in enumerate(candidates):
            metadata = dict(document.document_metadata or {})
            source_text = document_text(document)

            print(
                f"[{index + 1}/{len(candidates)}] "
                f"Extracting document {document.id}: {document.title[:100]}"
            )

            try:
                extracted = await extract_metadata(
                    source_text,
                    version=args.prompt_version,
                    prompts_dir=ROOT / "prompts",
                )
                extracted_fields = extracted.model_dump(exclude_none=True)

                # Reject responses containing no useful extracted metadata.
                if not has_useful_metadata(extracted_fields):
                    raise ValueError("Extraction returned no useful metadata fields")

                # Preserve original metadata and populate extracted fields
                # only where the existing value is missing or empty.
                for key, value in extracted_fields.items():
                    if key not in metadata or metadata[key] in (None, "", [], {}):
                        metadata[key] = value

                metadata[EXTRACTION_MARKER] = {
                    "status": "success",
                    "prompt_version": args.prompt_version,
                }
                document.document_metadata = metadata
                await session.commit()

                counts["succeeded"] += 1
                print(
                    f"  PASS: kind={extracted.doc_kind!r}, "
                    f"language={extracted.language!r}, "
                    f"topics={len(extracted.topics)}"
                )

            except Exception as exc:
                await session.rollback()

                # Reload the current document before recording the failure.
                refreshed = await session.get(Document, document.id)

                if refreshed is not None:
                    refreshed_metadata = dict(refreshed.document_metadata or {})
                    previous = refreshed_metadata.get(EXTRACTION_MARKER, {})
                    attempts = (
                        previous.get("attempts", 0) + 1
                        if isinstance(previous, dict)
                        else 1
                    )

                    refreshed_metadata[EXTRACTION_MARKER] = {
                        "status": "failed",
                        "attempts": attempts,
                        "error": str(exc)[:500],
                    }
                    refreshed.document_metadata = refreshed_metadata
                    await session.commit()

                counts["failed"] += 1
                print(f"  FAIL: {type(exc).__name__}: {exc}")

            counts["processed"] += 1

            if index + 1 < len(candidates):
                await asyncio.sleep(RATE_LIMIT_SECONDS)

    print("\nEXTRACTION SUMMARY")
    print("=" * 40)

    for key, value in counts.items():
        print(f"{key.capitalize()}: {value}")

    return 1 if counts["failed"] else 0


def main() -> None:
    """CLI entry point."""
    raise SystemExit(asyncio.run(run(parse_args())))


if __name__ == "__main__":
    main()
