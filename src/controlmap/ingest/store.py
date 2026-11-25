"""Persist parsed documents, pages, and parsing failures in PostgreSQL."""

from __future__ import annotations

import hashlib
from datetime import date
from pathlib import Path
from typing import Any

from sqlalchemy import delete, select

from app.database.connection import AsyncSessionLocal
from app.database.models import Document, Page, ParseFailure
from controlmap.ingest.parse import ParsedDocument


def calculate_sha256(file_path: str | Path) -> str:
    """Calculate the SHA-256 hash of a file."""
    sha256 = hashlib.sha256()

    with Path(file_path).open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            sha256.update(chunk)

    return sha256.hexdigest()


def _parse_date(value: Any) -> date | None:
    """Convert a date or ISO-formatted date string to a date."""
    if isinstance(value, date):
        return value

    if not isinstance(value, str) or not value.strip():
        return None

    try:
        return date.fromisoformat(value.strip()[:10])
    except ValueError:
        return None


def _failure_reason(error: Exception) -> str:
    """Return a short, stable category for a parsing failure."""
    if isinstance(error, FileNotFoundError):
        return "file_not_found"

    if isinstance(error, PermissionError):
        return "permission_error"

    if isinstance(error, ValueError):
        message = str(error).lower()

        if "unsupported" in message:
            return "unsupported_format"

        if "no text" in message or "no extractable text" in message:
            return "no_text"

        return "parse_error"

    if isinstance(error, OSError):
        return "file_io_error"

    return "parse_error"


async def record_parse_failure(
    file_path: str | Path,
    error: Exception,
    metadata: dict[str, Any] | None = None,
) -> str:
    """Insert or update the failure record for a file."""
    path = str(Path(file_path).resolve())
    metadata = metadata or {}

    try:
        file_hash = calculate_sha256(file_path)
    except OSError:
        file_hash = hashlib.sha256(path.encode("utf-8")).hexdigest()

    reason = _failure_reason(error)
    detail = f"{type(error).__name__}: {error}"[:10000]
    source_url = metadata.get("url") or metadata.get("source_url")

    async with AsyncSessionLocal() as session:
        existing = await session.scalar(
            select(ParseFailure).where(ParseFailure.path == path)
        )

        if existing is None:
            session.add(
                ParseFailure(
                    path=path,
                    sha256=file_hash,
                    source_url=source_url,
                    reason=reason,
                    detail=detail,
                    attempts=1,
                )
            )
        else:
            existing.sha256 = file_hash
            existing.source_url = source_url
            existing.reason = reason
            existing.detail = detail
            existing.attempts = (existing.attempts or 0) + 1

        await session.commit()

    return f"Recorded failure: {Path(file_path).name} ({reason})"


async def store_parsed_document(
    file_path: str | Path,
    parsed: ParsedDocument,
    metadata: dict[str, Any] | None = None,
) -> str:
    """Save a parsed document and its pages, or skip an existing document."""
    path = Path(file_path).resolve()
    metadata = metadata or {}

    if not path.is_file():
        raise FileNotFoundError(f"Document not found: {path}")

    if not parsed.pages:
        raise ValueError(f"No pages were extracted from {path.name}")

    if not any(page.text.strip() for page in parsed.pages):
        raise ValueError(f"No text was extracted from {path.name}")

    file_hash = calculate_sha256(path)

    async with AsyncSessionLocal() as session:
        existing_document = await session.scalar(
            select(Document).where(Document.sha256 == file_hash)
        )

        if existing_document is not None:
            await session.execute(
                delete(ParseFailure).where(ParseFailure.path == str(path))
            )
            await session.commit()
            return f"Skipped duplicate: {path.name}"

        document = Document(
            title=metadata.get("title") or path.stem,
            source_url=metadata.get("url") or metadata.get("source_url"),
            licence=metadata.get("licence") or metadata.get("license"),
            doc_type=(
                metadata.get("doc_type")
                or metadata.get("document_type")
                or path.suffix.lower().lstrip(".")
            ),
            published_on=_parse_date(metadata.get("published_on")),
            sha256=file_hash,
            document_metadata={
                "filename": path.name,
                "path": str(path),
                "loader": "controlmap.ingest.store",
                "parser": parsed.parser,
                "source": metadata.get("source"),
                "downloaded_at": metadata.get("downloaded_at"),
                "content_type": metadata.get("content_type"),
                "http_status": metadata.get("http_status"),
                "parse_errors": parsed.errors,
            },
        )

        for parsed_page in parsed.pages:
            document.pages.append(
                Page(
                    page_no=parsed_page.page_no,
                    text=parsed_page.text,
                    heading_path=parsed_page.heading_path,
                    headings=parsed_page.headings,
                    tables=parsed_page.tables,
                )
            )

        session.add(document)

        await session.execute(
            delete(ParseFailure).where(ParseFailure.path == str(path))
        )

        await session.commit()

    return (
        f"Loaded successfully: {path.name} | "
        f"pages={len(parsed.pages)} | "
        f"parser={parsed.parser}"
    )
