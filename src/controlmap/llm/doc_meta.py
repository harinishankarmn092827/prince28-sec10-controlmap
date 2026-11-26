"""Validated metadata extracted from cybersecurity documents."""

from __future__ import annotations

from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, field_validator

ShortText = Annotated[str, Field(min_length=1, max_length=300)]
TopicList = Annotated[list[ShortText], Field(max_length=8)]


class DocumentMetadata(BaseModel):
    """Metadata fields shared across source documents and ControlMap."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    doc_kind: ShortText | None = None
    year: int | None = Field(default=None, ge=1900, le=2100)
    language: ShortText | None = None
    summary: Annotated[str, Field(max_length=2000)] | None = None
    topics: TopicList = Field(default_factory=list)

    framework: ShortText | None = None
    control_id: ShortText | None = None
    function_or_family: ShortText | None = None
    applies_to_category: ShortText | None = None
    source_date: ShortText | None = None

    @field_validator("topics")
    @classmethod
    def normalize_topics(cls, value: list[str]) -> list[str]:
        """Remove duplicate topics while preserving their original order."""
        return list(dict.fromkeys(topic.strip() for topic in value))

    @field_validator("doc_kind")
    @classmethod
    def normalize_doc_kind(cls, value: str | None) -> str | None:
        """Normalize document-kind values for predictable filtering."""
        return value.lower() if value is not None else None

    @field_validator("source_date")
    @classmethod
    def validate_source_date(cls, value: str | None) -> str | None:
        """Reject source dates that cannot be interpreted as ISO dates."""
        if value is None:
            return None

        from datetime import date

        try:
            date.fromisoformat(value[:10])
        except ValueError as exc:
            raise ValueError("source_date must begin with an ISO date") from exc

        return value
