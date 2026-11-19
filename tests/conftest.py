"""Shared fixtures for ControlMap integration tests."""

import asyncio
import hashlib
import json
import os
from pathlib import Path
from uuid import uuid4

import asyncpg
import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool

from app.database import models  # noqa: F401
from app.database.connection import get_db
from app.database.models import Document as DocumentRecord
from app.main import app

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SAMPLE_DATA = PROJECT_ROOT / "app" / "data" / "sample_records.json"


def get_test_database_url():
    """Validate the local PostgreSQL test database configuration."""

    database_url = os.getenv("TEST_DATABASE_URL")

    if not database_url:
        raise RuntimeError(
            "TEST_DATABASE_URL is missing. "
            "Set it to the local controlmap_test database."
        )

    url = make_url(database_url)

    if url.drivername != "postgresql+asyncpg":
        raise RuntimeError("TEST_DATABASE_URL must use postgresql+asyncpg.")

    if url.database != "controlmap_test":
        raise RuntimeError(
            "Tests may only use the controlmap_test database "
            "as their local database connection template."
        )

    if url.host not in {"localhost", "127.0.0.1", "::1"}:
        raise RuntimeError("Integration tests must use a local PostgreSQL server.")

    return url


async def create_test_database(admin_url, database_name):
    """Create a fresh temporary PostgreSQL database."""

    connection = await asyncpg.connect(
        host=admin_url.host,
        port=admin_url.port or 5432,
        user=admin_url.username,
        password=admin_url.password,
        database="postgres",
    )

    try:
        await connection.execute(f'CREATE DATABASE "{database_name}"')
    finally:
        await connection.close()


async def drop_test_database(admin_url, database_name):
    """Terminate connections and drop the temporary test database."""

    connection = await asyncpg.connect(
        host=admin_url.host,
        port=admin_url.port or 5432,
        user=admin_url.username,
        password=admin_url.password,
        database="postgres",
    )

    try:
        await connection.execute(
            """
            SELECT pg_terminate_backend(pid)
            FROM pg_stat_activity
            WHERE datname = $1
              AND pid <> pg_backend_pid()
            """,
            database_name,
        )

        await connection.execute(f'DROP DATABASE IF EXISTS "{database_name}"')
    finally:
        await connection.close()


async def create_test_records(session_factory):
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
    """Create a fresh database, migrate it, and prepare test records."""

    admin_url = get_test_database_url()

    database_name = f"controlmap_test_{uuid4().hex[:12]}"
    test_url = admin_url.set(database=database_name)

    engine = create_async_engine(
        test_url,
        poolclass=NullPool,
    )

    session_factory = async_sessionmaker(
        bind=engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    async def setup_database():
        await create_test_database(admin_url, database_name)

        alembic_config = Config(str(PROJECT_ROOT / "alembic.ini"))

        alembic_config.set_main_option(
            "script_location",
            str(PROJECT_ROOT / "migrations"),
        )

        migration_url = test_url.render_as_string(hide_password=False)

        alembic_config.set_main_option(
            "sqlalchemy.url",
            migration_url.replace("%", "%%"),
        )

        # Run synchronous Alembic migrations in a separate thread.
        await asyncio.to_thread(
            command.upgrade,
            alembic_config,
            "head",
        )

        await create_test_records(session_factory)

    async def cleanup_database():
        await engine.dispose()

        await drop_test_database(
            admin_url,
            database_name,
        )

    try:
        asyncio.run(setup_database())

        yield session_factory

    finally:
        asyncio.run(cleanup_database())


@pytest.fixture
def override_database_dependency(test_session_factory):
    """Route API database requests to the temporary test database."""

    async def override_get_db():
        async with test_session_factory() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db

    yield

    app.dependency_overrides.pop(get_db, None)


@pytest.fixture
def test_client(override_database_dependency):
    """Provide a FastAPI test client with an isolated database."""

    with TestClient(app) as client:
        yield client
