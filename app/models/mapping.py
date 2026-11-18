"""Pydantic model for cross-framework mappings."""

from typing import Literal

from pydantic import BaseModel, Field


class FrameworkMapping(BaseModel):
    """Represents a relationship between framework controls."""

    id: int

    source_framework: str = Field(min_length=1)
    source_control_id: str = Field(min_length=1)

    target_framework: str = Field(min_length=1)
    target_control_id: str = Field(min_length=1)

    relationship: str = Field(min_length=1)

    rationale: str = Field(min_length=10)

    source_reference: str = Field(min_length=1)

    review_status: Literal["reviewed", "unverified"] = "unverified"
