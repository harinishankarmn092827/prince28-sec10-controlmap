"""Parse downloaded documents and load them into the database."""

import argparse
import asyncio
import hashlib
import json
from datetime import date
from pathlib import Path
from typing import Any

from sqlalchemy import select

from app.database.connection import AsyncSessionLocal
from app.database.models import Document, Page
from controlmap.ingest.parse import ParsedDocument, ParsedPage, parse_document

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DOCUMENTS_DIR = PROJECT_ROOT / "data" / "documents"
MANIFEST_PATH = PROJECT_ROOT / "data" / "manifest.jsonl"

SUPPORTED_EXTENSIONS = {".pdf", ".html", ".htm", ".json", ".txt", ".md"}


def calculate_sha256(file_path: Path) -> str:
    """Calculate the SHA-256 hash of a file."""
    sha256 = hashlib.sha256()

    with file_path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            sha256.update(chunk)

    return sha256.hexdigest()


def parse_publication_date(value: str | None) -> date | None:
    """Convert a date string into a date object."""
    if not value:
        return None

    try:
        return date.fromisoformat(value[:10])
    except (TypeError, ValueError):
        return None


def parse_local_file(file_path: Path) -> ParsedDocument:
    """Parse a text or Markdown file, or use the document parser."""
    extension = file_path.suffix.lower()

    if extension in {".txt", ".md"}:
        text = file_path.read_text(
            encoding="utf-8",
            errors="replace",
        ).strip()

        return ParsedDocument(
            filename=file_path.name,
            parser="plain-text",
            pages=[
                ParsedPage(
                    page_no=1,
                    text=text,
                    heading_path=[],
                    tables=[],
                )
            ],
            errors=[],
        )

    return parse_document(file_path)


def load_manifest() -> list[dict[str, Any]]:
    """Read downloaded documents from the JSONL manifest."""
    if not MANIFEST_PATH.is_file():
        return []

    records: list[dict[str, Any]] = []

    with MANIFEST_PATH.open("r", encoding="utf-8") as manifest:
        for line_number, line in enumerate(manifest, start=1):
            line = line.strip()

            if not line:
                continue

            try:
                record = json.loads(line)
            except json.JSONDecodeError as error:
                print(f"Warning: invalid manifest line {line_number}: {error}")
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
                print(f"Warning: skipping path outside project on line {line_number}")
                continue

            if file_path.suffix.lower() not in SUPPORTED_EXTENSIONS:
                continue

            if not file_path.is_file():
                print(f"Warning: file not found: {relative_path}")
                continue

            records.append(
                {
                    "path": file_path,
                    "metadata": record,
                }
            )

    return records


def discover_documents() -> list[dict[str, Any]]:
    """Find manifest documents and local text or Markdown files."""
    discovered: list[dict[str, Any]] = []
    seen_paths: set[Path] = set()

    for record in load_manifest():
        file_path = record["path"].resolve()

        if file_path not in seen_paths:
            discovered.append(record)
            seen_paths.add(file_path)

    if DOCUMENTS_DIR.is_dir():
        for file_path in sorted(DOCUMENTS_DIR.rglob("*")):
            if not file_path.is_file():
                continue

            if file_path.suffix.lower() not in {".txt", ".md"}:
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


async def load_document(
    file_path: Path,
    metadata: dict[str, Any] | None = None,
    dry_run: bool = False,
) -> str:
    """Parse a document and optionally save it and its pages."""
    metadata = metadata or {}

    if not file_path.is_file():
        raise FileNotFoundError(f"Document not found: {file_path}")

    file_hash = calculate_sha256(file_path)
    parsed = parse_local_file(file_path)

    if not parsed.pages:
        raise ValueError(f"No pages were extracted from {file_path.name}")

    if not any(page.text.strip() for page in parsed.pages):
        raise ValueError(f"No text was extracted from {file_path.name}")

    table_count = sum(len(page.tables) for page in parsed.pages)

    if dry_run:
        return (
            f"PARSED: {file_path.name} | "
            f"parser={parsed.parser} | "
            f"pages={len(parsed.pages)} | "
            f"tables={table_count}"
        )

    async with AsyncSessionLocal() as session:
        # Use scalar(), which is supported by SQLAlchemy AsyncSession
        # and by the FakeSession used in the unit tests.
        existing_document = await session.scalar(
            select(Document).where(Document.sha256 == file_hash)
        )

        if existing_document is not None:
            return f"Skipped duplicate: {file_path.name}"

        document = Document(
            title=metadata.get("title") or file_path.stem,
            source_url=metadata.get("url") or metadata.get("source_url"),
            licence=metadata.get("licence") or metadata.get("license"),
            doc_type=(
                metadata.get("doc_type")
                or metadata.get("document_type")
                or file_path.suffix.lower().lstrip(".")
            ),
            published_on=parse_publication_date(metadata.get("published_on")),
            sha256=file_hash,
            document_metadata={
                "filename": file_path.name,
                "loader": "scripts/load_db.py",
                "parser": parsed.parser,
                "source": metadata.get("source"),
                "downloaded_at": metadata.get("downloaded_at"),
                "content_type": metadata.get("content_type"),
                "http_status": metadata.get("http_status"),
                "parse_errors": parsed.errors,
            },
        )

        # Attach pages to the document relationship. SQLAlchemy's relationship
        # cascade will persist the pages when the document is committed.
        for parsed_page in parsed.pages:
            page = Page(
                page_no=parsed_page.page_no,
                text=parsed_page.text,
                heading_path=parsed_page.heading_path,
                tables=parsed_page.tables,
            )
            document.pages.append(page)

        session.add(document)
        await session.commit()

    return f"Loaded successfully: {file_path.name}"


async def main() -> None:
    """Discover, parse, and load documents."""
    parser = argparse.ArgumentParser(
        description="Parse downloaded documents and load them into the database."
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Parse documents without writing to the database.",
    )
    args = parser.parse_args()

    documents = discover_documents()

    if not documents:
        print("No supported documents found.")
        return

    print(f"Found {len(documents)} document(s).")

    if args.dry_run:
        print("Dry-run mode: the database will not be modified.")

    successful = 0
    failed = 0

    for record in documents:
        file_path: Path = record["path"]
        metadata: dict[str, Any] = record["metadata"]

        try:
            result = await load_document(
                file_path=file_path,
                metadata=metadata,
                dry_run=args.dry_run,
            )
            print(result)
            successful += 1

        except Exception as error:
            failed += 1
            print(f"FAILED: {file_path.name} | {error}")

    print("\nSummary")
    print(f"Total documents: {len(documents)}")
    print(f"Successful: {successful}")
    print(f"Failed: {failed}")

    if args.dry_run:
        print("Database changes: None")


if __name__ == "__main__":
    asyncio.run(main())
