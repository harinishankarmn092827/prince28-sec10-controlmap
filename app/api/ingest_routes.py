"""Authenticated API routes for asynchronous document ingestion."""

import logging
import secrets
from datetime import datetime, timezone
from uuid import uuid4

from arq import create_pool
from arq.connections import RedisSettings
from fastapi import APIRouter, Header, HTTPException, status
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select

from app.core.config import settings
from app.database.connection import AsyncSessionLocal
from app.database.models import IngestItem, IngestJob
from app.workers.ingest_worker import PROJECT_ROOT
from src.controlmap.ingest.fetch import read_sources

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/ingest", tags=["Async Ingestion"])

SOURCES_FILE = PROJECT_ROOT / "data" / "sources.csv"
MAX_ITEMS_PER_JOB = 50


class IngestJobRequest(BaseModel):
    """Request body for submitting an ingestion job."""

    urls: list[str] = Field(min_length=1, max_length=MAX_ITEMS_PER_JOB)

    @field_validator("urls")
    @classmethod
    def validate_unique_urls(cls, urls: list[str]) -> list[str]:
        """Reject duplicate URLs."""
        if len(urls) != len(set(urls)):
            raise ValueError("Duplicate URLs are not allowed.")
        return urls


def require_admin(authorization: str | None) -> None:
    """Require a configured administrator bearer token."""
    expected_token = settings.admin_token

    if not expected_token:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Ingestion administration is not configured.",
        )

    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="A valid bearer token is required.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    supplied_token = authorization.removeprefix("Bearer ").strip()

    if not secrets.compare_digest(supplied_token, expected_token):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="A valid bearer token is required.",
            headers={"WWW-Authenticate": "Bearer"},
        )


def utc_now() -> datetime:
    """Return the current UTC time."""
    return datetime.now(timezone.utc)


async def mark_job_failed(
    job_id: str,
    item_ids: list[int],
    *,
    job_error: str,
    failed_item_ids: set[int] | None = None,
) -> None:
    """Update failed items and recalculate their parent job counters."""
    failed_item_ids = set(item_ids) if failed_item_ids is None else failed_item_ids
    now = utc_now()

    async with AsyncSessionLocal() as session:
        job = await session.get(IngestJob, job_id)

        for item_id in failed_item_ids:
            item = await session.get(IngestItem, item_id)

            if item is not None:
                item.status = "failed"
                item.error_message = job_error
                item.updated_at = now

        if job is not None:
            result = await session.scalars(
                select(IngestItem).where(IngestItem.job_id == job_id)
            )
            items = list(result)

            job.total_items = len(items)
            job.completed_items = sum(item.status == "completed" for item in items)
            job.failed_items = sum(item.status == "failed" for item in items)
            job.error_message = job_error
            job.updated_at = now

            if items and all(item.status in {"completed", "failed"} for item in items):
                job.status = (
                    "failed" if job.failed_items == job.total_items else "completed"
                )
                job.completed_at = now
            else:
                job.status = "running"
                job.completed_at = None

        await session.commit()


@router.post("/jobs", status_code=status.HTTP_202_ACCEPTED)
async def create_ingest_job(
    payload: IngestJobRequest,
    authorization: str | None = Header(default=None),
):
    """Create a job and enqueue its approved source URLs."""
    require_admin(authorization)

    try:
        approved_sources = read_sources(SOURCES_FILE)
    except Exception as exc:
        logger.exception("Could not load the approved sources file.")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="The approved source list is unavailable.",
        ) from exc

    approved_urls = {source.url for source in approved_sources}
    unknown_urls = [url for url in payload.urls if url not in approved_urls]

    if unknown_urls:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "message": (
                    "Every URL must exactly match an entry in data/sources.csv."
                ),
                "unknown_count": len(unknown_urls),
            },
        )

    job_id = str(uuid4())
    now = utc_now()

    async with AsyncSessionLocal() as session:
        job = IngestJob(
            id=job_id,
            status="queued",
            total_items=len(payload.urls),
            completed_items=0,
            failed_items=0,
            created_at=now,
            updated_at=now,
        )
        session.add(job)

        items = [
            IngestItem(
                job_id=job_id,
                source_url=url,
                status="queued",
                attempts=0,
                created_at=now,
                updated_at=now,
            )
            for url in payload.urls
        ]

        session.add_all(items)
        await session.commit()

        item_ids = [item.id for item in items]

    try:
        redis_pool = await create_pool(RedisSettings.from_dsn(settings.redis_url))
    except Exception as exc:
        logger.exception("Could not connect to the ingestion queue.")

        try:
            await mark_job_failed(
                job_id,
                item_ids,
                job_error="Queue connection failed.",
            )
        except Exception:
            logger.exception(
                "Could not update the database after queue connection "
                "failure for job %s.",
                job_id,
            )

        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "message": "The ingestion queue is unavailable.",
                "job_id": job_id,
            },
        ) from exc

    enqueued_ids: set[int] = set()
    enqueue_error = None

    try:
        for item_id in item_ids:
            await redis_pool.enqueue_job(
                "process_ingest_item",
                item_id,
                _job_id=f"ingest-item-{item_id}",
            )
            enqueued_ids.add(item_id)

    except Exception as exc:
        enqueue_error = exc
        logger.exception("Failed to enqueue all items for job %s.", job_id)

    finally:
        try:
            await redis_pool.aclose()
        except Exception:
            logger.exception("Could not close the ingestion Redis pool.")

    if enqueue_error is not None:
        # Include the failed submission and every item not yet submitted.
        failed_ids = set(item_ids) - enqueued_ids

        try:
            await mark_job_failed(
                job_id,
                item_ids,
                job_error="Some items could not be submitted to the queue.",
                failed_item_ids=failed_ids,
            )
        except Exception:
            logger.exception(
                "Could not update the database after partial queue failure for job %s.",
                job_id,
            )

        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "message": "Some ingestion items could not be queued.",
                "job_id": job_id,
            },
        ) from enqueue_error

    return {
        "job_id": job_id,
        "status": "queued",
        "total_items": len(item_ids),
        "message": "Ingestion job submitted successfully.",
    }


@router.get("/jobs/{job_id}")
async def get_ingest_job(
    job_id: str,
    authorization: str | None = Header(default=None),
):
    """Retrieve an ingestion job and its individual item statuses."""
    require_admin(authorization)

    async with AsyncSessionLocal() as session:
        job = await session.get(IngestJob, job_id)

        if job is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Ingestion job not found.",
            )

        result = await session.scalars(
            select(IngestItem)
            .where(IngestItem.job_id == job_id)
            .order_by(IngestItem.id)
        )
        items = list(result)

        return {
            "job_id": job.id,
            "status": job.status,
            "total_items": job.total_items,
            "completed_items": job.completed_items,
            "failed_items": job.failed_items,
            "error_message": job.error_message,
            "created_at": job.created_at,
            "started_at": job.started_at,
            "completed_at": job.completed_at,
            "items": [
                {
                    "id": item.id,
                    "source_url": item.source_url,
                    "status": item.status,
                    "attempts": item.attempts,
                    "error_message": item.error_message,
                    "document_id": item.document_id,
                    "created_at": item.created_at,
                    "updated_at": item.updated_at,
                }
                for item in items
            ],
        }
