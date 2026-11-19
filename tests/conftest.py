"""Shared fixtures for ControlMap integration tests."""

import asyncio
import hashlib
import json
import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool

from app.database import models  # noqa: F401
from app.database.connection import Base, get_db
from app.database.models import Document as DocumentRecord
from app.main import app

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SAMPLE_DATA = PROJECT_ROOT / "app" / "data" / "sample_records.json"


def get_test_database_url() -> str:
    """Require an explicitly configured isolated test database."""

    database_url = os.getenv("TEST_DATABASE_URL")

    if not database_url:
        raise RuntimeError(
            "TEST_DATABASE_URL is missing. "
            "Set it to the local controlmap_test database."
        )

    if not database_url.startswith("postgresql+asyncpg://"):
        raise RuntimeError("TEST_DATABASE_URL must use the PostgreSQL asyncpg driver.")

    if not database_url.rsplit("/", 1)[-1].split("?")[0] == "controlmap_test":
        raise RuntimeError("Tests may only run against the controlmap_test database.")

    return database_url


async def create_test_records(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """Load sample cybersecurity controls into the test database."""

    with SAMPLE_DATA.open(encoding="utf-8") as file:
        records = json.load(file)

    async with session_factory() as session:
        for record in records:
            existing = await session.scalar(
                select(DocumentRecord).where(
                    DocumentRecord.doc_type == "control_record",
                    DocumentRecord.document_metadata["original_record_id"].astext
                    == str(record["id"]),
                )
            )

            if existing:
                continue

            document = DocumentRecord(
                title=record["title"],
                source_url=None,
                licence=None,
                doc_type="control_record",
                published_on=None,
                sha256=hashlib.sha256(
                    f"controlmap-test-{record['id']}".encode()
                ).hexdigest(),
                document_metadata={
                    "original_record_id": record["id"],
                    "framework": record["framework"],
                    "control_id": record["control_id"],
                    "function_or_family": record["function_or_family"],
                    "applies_to_category": record["applies_to_category"],
                    "source_date": record["source_date"],
                },
            )

            session.add(document)

        await session.commit()


@pytest.fixture(scope="session")
def test_session_factory():
    """Create and prepare the isolated PostgreSQL test database."""

    database_url = get_test_database_url()

    engine = create_async_engine(
        database_url,
        poolclass=NullPool,
    )

    session_factory = async_sessionmaker(
        bind=engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    async def setup_database():
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)

        await create_test_records(session_factory)

    async def cleanup_database():
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.drop_all)

        await engine.dispose()

    asyncio.run(setup_database())

    yield session_factory

    asyncio.run(cleanup_database())


@pytest.fixture
def override_database_dependency(test_session_factory):
    """Route API database requests to the isolated test database."""

    async def override_get_db():
        async with test_session_factory() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db

    yield

    app.dependency_overrides.pop(get_db, None)


@pytest.fixture
def test_client(override_database_dependency):
    """Provide a FastAPI test client with isolated database."""

    with TestClient(app) as client:
        yield client
