"""Pydantic model for cybersecurity framework documents."""

from pydantic import BaseModel, Field


class Document(BaseModel):
    id: int
    framework: str = Field(min_length=1)
    control_id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    function_or_family: str = Field(min_length=1)
    applies_to_category: str = Field(min_length=1)
    source_date: str = Field(min_length=1)
