"""ARQ worker for asynchronous document ingestion."""

import asyncio
import json
import logging
from datetime import datetime, timezone
from pathlib import Path

from arq import Retry
from arq.connections import RedisSettings
from sqlalchemy import select

from app.core.config import settings
from app.database.connection import AsyncSessionLocal
from app.database.models import Document, IngestItem, IngestJob
from src.controlmap.ingest.fetch import Source, fetch_all, read_sources
from src.controlmap.ingest.parse import parse_document
from src.controlmap.ingest.store import (
    calculate_sha256,
    record_parse_failure,
    store_parsed_document,
)

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SOURCES_FILE = PROJECT_ROOT / "data" / "sources.csv"
MANIFEST_FILE = settings.manifest_file

TERMINAL_STATUSES = {"completed", "failed"}


def utc_now() -> datetime:
    """Return the current UTC time."""
    return datetime.now(timezone.utc)


def find_source(source_url: str) -> Source:
    """Resolve a submitted URL against the approved sources CSV."""
    sources = read_sources(SOURCES_FILE)

    for source in sources:
        if source.url == source_url:
            return source

    raise ValueError("The URL is not present in the approved sources CSV.")


def find_downloaded_record(source_url: str) -> dict:
    """Find the latest successful manifest record for a URL."""
    if not MANIFEST_FILE.is_absolute():
        manifest_path = PROJECT_ROOT / MANIFEST_FILE
    else:
        manifest_path = MANIFEST_FILE

    if not manifest_path.is_file():
        raise FileNotFoundError("The download manifest does not exist.")

    matching_record = None

    with manifest_path.open("r", encoding="utf-8") as manifest:
        for line in manifest:
            if not line.strip():
                continue

            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                logger.warning("Ignoring malformed manifest line.")
                continue

            if (
                record.get("url") == source_url
                and record.get("status") == "downloaded"
                and record.get("path")
            ):
                matching_record = record

    if matching_record is None:
        raise FileNotFoundError("No successful download was found in the manifest.")

    relative_path = Path(matching_record["path"])
    file_path = (PROJECT_ROOT / relative_path).resolve()

    # Prevent a manifest path from escaping the project directory.
    if not file_path.is_relative_to(PROJECT_ROOT.resolve()):
        raise ValueError("The manifest contains an unsafe file path.")

    if not file_path.is_file():
        raise FileNotFoundError("The downloaded document is missing.")

    return {**matching_record, "_file_path": file_path}


async def refresh_job_status(session, job_id: str) -> None:
    """Recalculate job counters from its current item states."""
    job = await session.get(IngestJob, job_id)

    if job is None:
        return

    result = await session.scalars(
        select(IngestItem).where(IngestItem.job_id == job_id)
    )
    items = list(result)

    job.total_items = len(items)
    job.completed_items = sum(item.status == "completed" for item in items)
    job.failed_items = sum(item.status == "failed" for item in items)
    job.updated_at = utc_now()

    if not items:
        job.status = "completed"
        job.completed_at = utc_now()
    elif all(item.status in TERMINAL_STATUSES for item in items):
        job.status = "failed" if job.failed_items == job.total_items else "completed"
        job.completed_at = utc_now()
    else:
        job.status = "running"
        job.completed_at = None


async def update_item(
    item_id: int,
    status: str,
    *,
    error_message: str | None = None,
    document_id: int | None = None,
) -> None:
    """Update an item and recalculate its parent job."""
    async with AsyncSessionLocal() as session:
        item = await session.get(IngestItem, item_id)

        if item is None:
            raise ValueError(f"Ingestion item {item_id} does not exist.")

        item.status = status
        item.error_message = error_message[:2000] if error_message else None
        item.updated_at = utc_now()

        if document_id is not None:
            item.document_id = document_id

        await refresh_job_status(session, item.job_id)
        await session.commit()


async def process_ingest_item(ctx: dict, item_id: int) -> dict:
    """Download, parse, and store one approved source document."""
    async with AsyncSessionLocal() as session:
        item = await session.get(IngestItem, item_id)

        if item is None:
            raise ValueError(f"Ingestion item {item_id} does not exist.")

        if item.status == "completed":
            return {"item_id": item_id, "status": "completed"}

        item.status = "processing"
        item.attempts += 1
        item.error_message = None
        item.updated_at = utc_now()

        job_id = item.job_id
        source_url = item.source_url

        job = await session.get(IngestJob, job_id)
        if job is not None:
            job.status = "running"
            job.started_at = job.started_at or utc_now()
            job.updated_at = utc_now()

        await session.commit()

    file_path = None
    source = None

    try:
        source = find_source(source_url)

        # Reuse the existing downloader and manifest.
        counts = await fetch_all(
            [source],
            root=PROJECT_ROOT,
            max_concurrency=settings.ingest_concurrency,
            max_attempts=settings.ingest_max_tries,
            per_host_delay=(
                60.0 / settings.ingest_rpm if settings.ingest_rpm > 0 else 0.0
            ),
        )

        if counts.get("blocked", 0):
            raise ValueError(
                "The source could not be downloaded because access "
                "was blocked by the source's robots rules."
            )

        if counts.get("failed", 0):
            raise RuntimeError(
                "The downloader could not retrieve the source "
                "after its configured retries."
            )

        record = find_downloaded_record(source_url)
        file_path = record["_file_path"]

        # Parsing is synchronous, so run it outside the event loop.
        parsed = await asyncio.to_thread(parse_document, file_path)

        metadata = {
            "url": record.get("url"),
            "source_url": record.get("url"),
            "source": record.get("source"),
            "title": record.get("title"),
            "licence": record.get("licence"),
            "content_type": record.get("content_type"),
            "http_status": record.get("http_status"),
            "downloaded_at": record.get("downloaded_at"),
        }

        await store_parsed_document(
            file_path=file_path,
            parsed=parsed,
            metadata=metadata,
        )

        # Resolve the stored document ID, including duplicate documents.
        file_hash = calculate_sha256(file_path)

        async with AsyncSessionLocal() as session:
            document = await session.scalar(
                select(Document).where(Document.sha256 == file_hash)
            )

            if document is None:
                raise RuntimeError(
                    "Document storage returned without a matching database document."
                )

            document_id = document.id

        await update_item(
            item_id,
            "completed",
            document_id=document_id,
        )

        logger.info(
            "Ingestion item %s completed for job %s.",
            item_id,
            job_id,
        )

        return {
            "item_id": item_id,
            "job_id": job_id,
            "status": "completed",
            "document_id": document_id,
        }

    except Exception as exc:
        job_try = max(1, int(ctx.get("job_try", 1)))
        max_tries = max(1, settings.ingest_max_tries)

        logger.warning(
            "Ingestion item %s failed on attempt %s of %s: %s",
            item_id,
            job_try,
            max_tries,
            exc,
        )

        # Invalid input and robots-policy blocks are not transient errors.
        retryable = not isinstance(exc, ValueError)

        if retryable and job_try < max_tries:
            await update_item(
                item_id,
                "queued",
                error_message=(f"Attempt {job_try} failed; retry scheduled: {exc}"),
            )

            raise Retry(defer=min(5 * job_try, 30)) from exc

        logger.error(
            "Ingestion item %s permanently failed.",
            item_id,
            exc_info=True,
        )

        # Record a parse failure when a downloaded file is available.
        try:
            if file_path is not None and Path(file_path).is_file():
                await record_parse_failure(
                    file_path,
                    exc,
                    metadata={
                        "url": source_url,
                        "source": source.source if source else None,
                    },
                )
        except Exception:
            logger.exception(
                "Could not record parse failure for item %s.",
                item_id,
            )

        await update_item(
            item_id,
            "failed",
            error_message=str(exc),
        )

        raise


class WorkerSettings:
    """ARQ worker configuration."""

    functions = [process_ingest_item]
    redis_settings = RedisSettings.from_dsn(settings.redis_url)
    max_jobs = settings.ingest_concurrency
    job_timeout = settings.ingest_job_timeout
    max_tries = settings.ingest_max_tries
