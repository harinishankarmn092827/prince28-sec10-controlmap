"""Response model for source documents with extracted metadata."""

from pydantic import BaseModel, ConfigDict, Field


class SourceDocument(BaseModel):
    """A source document and its extracted metadata."""

    model_config = ConfigDict(extra="ignore")

    id: int
    title: str
    doc_kind: str | None = None
    year: int | None = None
    language: str | None = None
    summary: str | None = None
    topics: list[str] = Field(default_factory=list)
    framework: str | None = None
    control_id: str | None = None
    function_or_family: str | None = None
    applies_to_category: str | None = None
    source_date: str | None = None
