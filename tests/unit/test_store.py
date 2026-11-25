"""Tests for storing parsed documents and recording parse failures."""

import asyncio

from app.database.models import Document, ParseFailure
from controlmap.ingest import store
from controlmap.ingest.parse import ParsedDocument, ParsedPage


class FakeSession:
    """Simulate an asynchronous SQLAlchemy session."""

    def __init__(self, existing=None):
        self.existing = existing
        self.added = []
        self.committed = False
        self.executed = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_value, traceback):
        return None

    async def scalar(self, statement):
        return self.existing

    def add(self, item):
        self.added.append(item)

    async def execute(self, statement):
        self.executed.append(statement)

    async def commit(self):
        self.committed = True


def sample_document(filename="sample.txt"):
    """Create a parsed document with page metadata."""
    return ParsedDocument(
        filename=filename,
        parser="text",
        pages=[
            ParsedPage(
                page_no=1,
                text="Sample cybersecurity control",
                heading_path=["Security", "Access Control"],
                headings=["Security", "Access Control"],
                tables=[],
            )
        ],
    )


def test_store_parsed_document_success(tmp_path, monkeypatch):
    """A new document should be stored with its page metadata."""
    file_path = tmp_path / "sample.txt"
    file_path.write_text("Sample cybersecurity control", encoding="utf-8")

    fake_session = FakeSession()
    monkeypatch.setattr(store, "AsyncSessionLocal", lambda: fake_session)

    result = asyncio.run(
        store.store_parsed_document(
            file_path,
            sample_document(),
            {
                "title": "Sample Control",
                "url": "https://example.com/sample",
                "licence": "Public",
                "source": "test",
            },
        )
    )

    assert result.startswith("Loaded successfully: sample.txt")
    assert len(fake_session.added) == 1
    assert isinstance(fake_session.added[0], Document)

    document = fake_session.added[0]
    assert document.title == "Sample Control"
    assert document.source_url == "https://example.com/sample"
    assert len(document.pages) == 1
    assert document.pages[0].text == "Sample cybersecurity control"
    assert document.pages[0].heading_path == ["Security", "Access Control"]
    assert document.pages[0].headings == ["Security", "Access Control"]
    assert fake_session.committed


def test_store_parsed_document_skips_duplicate(tmp_path, monkeypatch):
    """A document with an existing hash should not be inserted again."""
    file_path = tmp_path / "duplicate.txt"
    file_path.write_text("Existing document", encoding="utf-8")

    fake_session = FakeSession(existing=object())
    monkeypatch.setattr(store, "AsyncSessionLocal", lambda: fake_session)

    result = asyncio.run(store.store_parsed_document(file_path, sample_document()))

    assert result == "Skipped duplicate: duplicate.txt"
    assert fake_session.added == []
    assert fake_session.committed


def test_record_parse_failure_creates_record(tmp_path, monkeypatch):
    """A parsing error should be recorded in the database."""
    file_path = tmp_path / "broken.json"
    file_path.write_text("{invalid json", encoding="utf-8")

    fake_session = FakeSession()
    monkeypatch.setattr(store, "AsyncSessionLocal", lambda: fake_session)

    result = asyncio.run(
        store.record_parse_failure(
            file_path,
            ValueError("Invalid JSON"),
            {"url": "https://example.com/broken"},
        )
    )

    assert result == "Recorded failure: broken.json (parse_error)"
    assert len(fake_session.added) == 1

    failure = fake_session.added[0]
    assert isinstance(failure, ParseFailure)
    assert failure.path == str(file_path.resolve())
    assert failure.reason == "parse_error"
    assert failure.source_url == "https://example.com/broken"
    assert failure.attempts == 1
    assert fake_session.committed


def test_record_parse_failure_increments_attempts(tmp_path, monkeypatch):
    """Retrying a failure should update its record and attempt count."""
    file_path = tmp_path / "broken.json"
    file_path.write_text("{invalid json", encoding="utf-8")

    existing = ParseFailure(
        path=str(file_path.resolve()),
        sha256="a" * 64,
        reason="parse_error",
        detail="Previous error",
        attempts=1,
    )

    fake_session = FakeSession(existing=existing)
    monkeypatch.setattr(store, "AsyncSessionLocal", lambda: fake_session)

    result = asyncio.run(
        store.record_parse_failure(
            file_path,
            ValueError("Still invalid"),
        )
    )

    assert result == "Recorded failure: broken.json (parse_error)"
    assert existing.attempts == 2
    assert existing.detail == "ValueError: Still invalid"
    assert fake_session.added == []
    assert fake_session.committed
