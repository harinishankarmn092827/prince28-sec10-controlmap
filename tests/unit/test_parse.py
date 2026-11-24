"""Unit tests for document parsing."""

import json
from pathlib import Path

import pymupdf
import pytest

from controlmap.ingest.parse import (
    ParsedDocument,
    parse_document,
    parsed_document_to_dict,
)


def test_parse_json(tmp_path: Path) -> None:
    """JSON documents should be extracted into readable sections."""

    file_path = tmp_path / "sample.json"
    file_path.write_text(
        json.dumps(
            {
                "title": "Cybersecurity Controls",
                "version": "2.0",
                "controls": [
                    {"id": "AC-1", "name": "Access Control"},
                    {"id": "AU-1", "name": "Audit"},
                ],
            }
        ),
        encoding="utf-8",
    )

    result = parse_document(file_path)

    assert result.filename == "sample.json"
    assert result.parser == "json"
    assert len(result.pages) == 1
    assert "Cybersecurity Controls" in result.pages[0].text
    assert "AC-1" in result.pages[0].text


def test_parse_pdf(tmp_path: Path) -> None:
    """PDF documents should preserve page numbers and extract text."""

    file_path = tmp_path / "sample.pdf"

    pdf = pymupdf.open()
    page = pdf.new_page()
    page.insert_text((72, 72), "Cybersecurity Control AC-1")
    pdf.save(file_path)
    pdf.close()

    result = parse_document(file_path)

    assert result.filename == "sample.pdf"
    assert result.parser == "pymupdf"
    assert len(result.pages) == 1
    assert result.pages[0].page_no == 1
    assert "Cybersecurity Control AC-1" in result.pages[0].text


def test_parse_html(tmp_path: Path) -> None:
    """HTML documents should produce readable text."""

    file_path = tmp_path / "sample.html"
    file_path.write_text(
        """
        <!DOCTYPE html>
        <html>
        <head><title>Security Controls</title></head>
        <body>
            <main>
                <h1>Cybersecurity Framework</h1>
                <p>Control AC-1 requires an access control policy.</p>
            </main>
        </body>
        </html>
        """,
        encoding="utf-8",
    )

    result = parse_document(file_path)

    assert result.filename == "sample.html"
    assert len(result.pages) == 1
    assert "Cybersecurity Framework" in result.pages[0].text
    assert "access control policy" in result.pages[0].text


def test_missing_file_raises_error(tmp_path: Path) -> None:
    """Missing files should raise FileNotFoundError."""

    with pytest.raises(FileNotFoundError):
        parse_document(tmp_path / "missing.pdf")


def test_unsupported_extension_raises_error(tmp_path: Path) -> None:
    """Unsupported file extensions should raise ValueError."""

    file_path = tmp_path / "sample.docx"
    file_path.write_text("Example document", encoding="utf-8")

    with pytest.raises(ValueError, match="Unsupported document extension"):
        parse_document(file_path)


def test_invalid_json_raises_error(tmp_path: Path) -> None:
    """Invalid JSON should raise a parsing error."""

    file_path = tmp_path / "invalid.json"
    file_path.write_text("{invalid json", encoding="utf-8")

    with pytest.raises(json.JSONDecodeError):
        parse_document(file_path)


def test_parsed_document_to_dict() -> None:
    """Parsed documents should convert to JSON-serializable dictionaries."""

    document = ParsedDocument(
        filename="sample.json",
        parser="json",
        pages=[],
    )

    result = parsed_document_to_dict(document)

    assert result["filename"] == "sample.json"
    assert result["parser"] == "json"
    assert result["pages"] == []
    assert result["errors"] == []
