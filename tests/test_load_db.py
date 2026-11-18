"""Tests for the ControlMap document database loader."""

import asyncio

import pytest

from app.database.models import Document
from scripts import load_db


class FakeSession:
    """Simulate an asynchronous SQLAlchemy session."""

    def __init__(self, existing=None):
        self.existing = existing
        self.added_document = None
        self.committed = False

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_value, traceback):
        return None

    async def scalar(self, statement):
        return self.existing

    def add(self, document):
        self.added_document = document

    async def commit(self):
        self.committed = True


def test_load_document_success(tmp_path, monkeypatch):
    """A new document should be inserted with its page."""

    file_path = tmp_path / "sample.txt"
    file_path.write_text("ControlMap database test", encoding="utf-8")

    fake_session = FakeSession()

    monkeypatch.setattr(
        load_db,
        "AsyncSessionLocal",
        lambda: fake_session,
    )

    result = asyncio.run(load_db.load_document(file_path))

    assert result == "Loaded successfully: sample.txt"
    assert isinstance(fake_session.added_document, Document)
    assert fake_session.added_document.title == "sample"
    assert fake_session.added_document.doc_type == "txt"
    assert len(fake_session.added_document.pages) == 1
    assert fake_session.added_document.pages[0].page_no == 1
    assert fake_session.added_document.pages[0].text == ("ControlMap database test")
    assert fake_session.committed is True


def test_load_document_skips_duplicate(tmp_path, monkeypatch):
    """An existing document hash should not be inserted again."""

    file_path = tmp_path / "sample.txt"
    file_path.write_text("Existing document", encoding="utf-8")

    fake_session = FakeSession(existing=object())

    monkeypatch.setattr(
        load_db,
        "AsyncSessionLocal",
        lambda: fake_session,
    )

    result = asyncio.run(load_db.load_document(file_path))

    assert result == "Skipped duplicate: sample.txt"
    assert fake_session.added_document is None
    assert fake_session.committed is False


def test_load_markdown_document(tmp_path, monkeypatch):
    """Markdown files should be supported."""

    file_path = tmp_path / "guide.md"
    file_path.write_text("# ControlMap Guide", encoding="utf-8")

    fake_session = FakeSession()

    monkeypatch.setattr(
        load_db,
        "AsyncSessionLocal",
        lambda: fake_session,
    )

    result = asyncio.run(load_db.load_document(file_path))

    assert result == "Loaded successfully: guide.md"
    assert fake_session.added_document.doc_type == "md"


def test_missing_document_raises_error(tmp_path):
    """A missing file should raise FileNotFoundError."""

    file_path = tmp_path / "missing.txt"

    with pytest.raises(FileNotFoundError):
        asyncio.run(load_db.load_document(file_path))
