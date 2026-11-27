"""Unit tests for the asynchronous ingestion API."""

import pytest
from fastapi.testclient import TestClient

from app.api import ingest_routes
from app.main import app
from src.controlmap.ingest.fetch import Source


@pytest.fixture
def client():
    """Provide a FastAPI test client."""
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def admin_token(monkeypatch):
    """Configure a test-only administrator token."""
    monkeypatch.setattr(
        ingest_routes.settings,
        "admin_token",
        "test-admin-token",
    )
    return "test-admin-token"


@pytest.fixture
def approved_source(monkeypatch):
    """Provide one approved source without reading external resources."""
    source = Source(
        url="https://example.com/approved-document.pdf",
        source="test",
        licence="Public domain",
        title="Approved test document",
    )

    monkeypatch.setattr(
        ingest_routes,
        "read_sources",
        lambda path: [source],
    )

    return source


def test_create_job_rejects_missing_token(client, monkeypatch):
    """Requests without a bearer token must be rejected."""
    monkeypatch.setattr(
        ingest_routes.settings,
        "admin_token",
        "test-admin-token",
    )

    response = client.post(
        "/api/ingest/jobs",
        json={"urls": ["https://example.com/approved-document.pdf"]},
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "A valid bearer token is required."


def test_create_job_rejects_invalid_token(client, admin_token):
    """Requests with an incorrect bearer token must be rejected."""
    response = client.post(
        "/api/ingest/jobs",
        headers={"Authorization": "Bearer wrong-token"},
        json={"urls": ["https://example.com/approved-document.pdf"]},
    )

    assert response.status_code == 401


def test_create_job_rejects_unconfigured_admin_token(client, monkeypatch):
    """Administration must be disabled when no token is configured."""
    monkeypatch.setattr(ingest_routes.settings, "admin_token", "")

    response = client.post(
        "/api/ingest/jobs",
        headers={"Authorization": "Bearer any-token"},
        json={"urls": ["https://example.com/approved-document.pdf"]},
    )

    assert response.status_code == 503
    assert response.json()["detail"] == ("Ingestion administration is not configured.")


def test_create_job_rejects_unknown_url(
    client,
    admin_token,
    approved_source,
):
    """URLs outside the approved source list must be rejected."""
    response = client.post(
        "/api/ingest/jobs",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"urls": ["https://example.com/not-approved.pdf"]},
    )

    assert response.status_code == 422
    assert response.json()["status"] == 422


def test_create_job_rejects_duplicate_urls(
    client,
    admin_token,
    approved_source,
):
    """A request cannot submit the same URL more than once."""
    url = approved_source.url

    response = client.post(
        "/api/ingest/jobs",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"urls": [url, url]},
    )

    assert response.status_code == 422
    assert response.json()["status"] == 422


def test_create_job_rejects_empty_url_list(
    client,
    admin_token,
):
    """A job must contain at least one URL."""
    response = client.post(
        "/api/ingest/jobs",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"urls": []},
    )

    assert response.status_code == 422


def test_create_job_rejects_more_than_maximum_urls(
    client,
    admin_token,
):
    """A job cannot exceed the configured maximum number of URLs."""
    urls = [
        f"https://example.com/document-{index}.pdf"
        for index in range(ingest_routes.MAX_ITEMS_PER_JOB + 1)
    ]

    response = client.post(
        "/api/ingest/jobs",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"urls": urls},
    )

    assert response.status_code == 422


def test_get_job_rejects_missing_token(client):
    """Job status must not be available without authentication."""
    response = client.get(
        "/api/ingest/jobs/test-job-id",
    )

    assert response.status_code == 401


def test_get_job_rejects_invalid_token(client, admin_token):
    """Job status must reject an incorrect bearer token."""
    response = client.get(
        "/api/ingest/jobs/test-job-id",
        headers={"Authorization": "Bearer wrong-token"},
    )

    assert response.status_code == 401


@pytest.fixture
def mock_ingest_database(monkeypatch):
    """Provide a mocked database for ingestion failure tests."""
    from types import SimpleNamespace
    from unittest.mock import AsyncMock

    from app.database.models import IngestItem, IngestJob

    job = SimpleNamespace(
        id="test-job-id",
        status="queued",
        total_items=2,
        completed_items=0,
        failed_items=0,
        error_message=None,
        completed_at=None,
        updated_at=None,
    )

    items = [
        SimpleNamespace(
            id=1,
            job_id=job.id,
            status="queued",
            error_message=None,
            updated_at=None,
        ),
        SimpleNamespace(
            id=2,
            job_id=job.id,
            status="queued",
            error_message=None,
            updated_at=None,
        ),
    ]

    session = AsyncMock()

    async def get_model(model, identifier):
        if model is IngestJob:
            return job if identifier == job.id else None

        if model is IngestItem:
            return next(
                (item for item in items if item.id == identifier),
                None,
            )

        return None

    async def get_items(statement):
        return items

    session.get.side_effect = get_model
    session.scalars.side_effect = get_items
    session.commit = AsyncMock()

    class MockSessionContext:
        async def __aenter__(self):
            return session

        async def __aexit__(self, exc_type, exc_value, traceback):
            return False

    monkeypatch.setattr(
        ingest_routes,
        "AsyncSessionLocal",
        lambda: MockSessionContext(),
    )

    return SimpleNamespace(job=job, items=items, session=session)


@pytest.mark.asyncio
async def test_mark_job_failed_updates_all_failure_counters(
    mock_ingest_database,
):
    """A queue connection failure updates every item and job counter."""
    database = mock_ingest_database

    await ingest_routes.mark_job_failed(
        database.job.id,
        [item.id for item in database.items],
        job_error="Queue connection failed.",
    )

    assert database.job.status == "failed"
    assert database.job.total_items == 2
    assert database.job.completed_items == 0
    assert database.job.failed_items == 2
    assert database.job.completed_at is not None

    assert all(item.status == "failed" for item in database.items)
    assert all(
        item.error_message == "Queue connection failed." for item in database.items
    )
    database.session.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_mark_job_failed_preserves_queued_items(
    mock_ingest_database,
):
    """A partial queue failure preserves successfully queued items."""
    database = mock_ingest_database

    await ingest_routes.mark_job_failed(
        database.job.id,
        [item.id for item in database.items],
        job_error="Some items could not be submitted to the queue.",
        failed_item_ids={2},
    )

    assert database.items[0].status == "queued"
    assert database.items[1].status == "failed"

    assert database.job.status == "running"
    assert database.job.total_items == 2
    assert database.job.completed_items == 0
    assert database.job.failed_items == 1
    assert database.job.completed_at is None

    database.session.commit.assert_awaited_once()
