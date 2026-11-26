"""Unit tests for LLM-based metadata extraction."""

import json
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from pydantic import ValidationError

from controlmap.llm.doc_meta import DocumentMetadata
from controlmap.llm.extract import (
    extract_metadata,
    load_extraction_prompt,
    parse_extracted_metadata,
)


def test_load_extraction_prompt():
    prompt = load_extraction_prompt()
    assert len(prompt) > 100
    assert "doc_kind" in prompt


def test_load_missing_prompt_raises():
    with pytest.raises(FileNotFoundError):
        load_extraction_prompt(version=999)


def test_parse_valid_metadata():
    result = parse_extracted_metadata(
        json.dumps(
            {
                "doc_kind": "STANDARD",
                "year": 2024,
                "language": "English",
                "topics": ["security", "access control"],
            }
        )
    )

    assert isinstance(result, DocumentMetadata)
    assert result.doc_kind == "standard"
    assert result.year == 2024
    assert result.topics == ["security", "access control"]


def test_parse_duplicate_topics():
    result = parse_extracted_metadata(
        '{"topics":["security","security","access control"]}'
    )

    assert result.topics == ["security", "access control"]


def test_parse_invalid_json_raises():
    with pytest.raises(ValueError, match="invalid JSON"):
        parse_extracted_metadata("not valid JSON")


def test_parse_non_object_raises():
    with pytest.raises(ValueError, match="JSON object"):
        parse_extracted_metadata('["security"]')


def test_parse_invalid_year_raises():
    with pytest.raises(ValidationError):
        parse_extracted_metadata('{"year":2200}')


def test_parse_unknown_field_raises():
    with pytest.raises(ValidationError):
        parse_extracted_metadata('{"unexpected_field":"value"}')


@pytest.mark.asyncio
async def test_extract_metadata_uses_gateway(monkeypatch):
    from controlmap.llm import extract

    fake_gateway = SimpleNamespace(
        generate=AsyncMock(
            return_value=SimpleNamespace(
                content='{"doc_kind":"standard","year":2024,"topics":["security"]}'
            )
        )
    )

    monkeypatch.setattr(
        extract,
        "LLMGateway",
        lambda system_prompt: fake_gateway,
    )

    result = await extract_metadata("A cybersecurity standard.")

    assert result.doc_kind == "standard"
    assert result.year == 2024
    fake_gateway.generate.assert_awaited_once()


@pytest.mark.asyncio
async def test_extract_empty_text_raises():
    with pytest.raises(ValueError, match="must not be empty"):
        await extract_metadata("   ")
