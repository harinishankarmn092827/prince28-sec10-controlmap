"""SQLAlchemy models for ControlMap."""

from datetime import date, datetime

from sqlalchemy import (
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy import (
    text as sql_text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.connection import Base


class Document(Base):
    """Stores framework documents and their source information."""

    __tablename__ = "documents"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    source_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    licence: Mapped[str | None] = mapped_column(Text, nullable=True)

    doc_type: Mapped[str] = mapped_column(String(100), nullable=False)
    published_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)

    document_metadata: Mapped[dict] = mapped_column(
        "metadata",
        JSONB,
        nullable=False,
        default=dict,
    )

    pages: Mapped[list["Page"]] = relationship(
        back_populates="document",
        cascade="all, delete-orphan",
    )


class Page(Base):
    """Stores parsed pages and their extracted metadata."""

    __tablename__ = "pages"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )
    doc_id: Mapped[int] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
    )
    page_no: Mapped[int] = mapped_column(Integer, nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)

    heading_path: Mapped[list[str]] = mapped_column(
        JSONB,
        nullable=False,
        default=list,
        server_default=sql_text("'[]'::jsonb"),
    )

    headings: Mapped[list[str]] = mapped_column(
        JSONB,
        nullable=False,
        default=list,
        server_default="[]",
    )

    tables: Mapped[list[str]] = mapped_column(
        JSONB,
        nullable=False,
        default=list,
        server_default=sql_text("'[]'::jsonb"),
    )

    document: Mapped["Document"] = relationship(
        back_populates="pages",
    )

    __table_args__ = (
        UniqueConstraint("doc_id", "page_no", name="uq_document_page"),
        Index("ix_pages_doc_id", "doc_id"),
    )


class ParseFailure(Base):
    """Records files that could not be parsed successfully."""

    __tablename__ = "parse_failures"

    id: Mapped[int] = mapped_column(primary_key=True)

    path: Mapped[str] = mapped_column(
        Text,
        unique=True,
        nullable=False,
    )

    sha256: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
    )

    source_url: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    reason: Mapped[str] = mapped_column(
        String(40),
        index=True,
        nullable=False,
    )

    detail: Mapped[str] = mapped_column(
        Text,
        server_default="",
        nullable=False,
    )

    attempts: Mapped[int] = mapped_column(
        Integer,
        server_default="1",
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class LLMCall(Base):
    """Record LLM provider requests and usage statistics."""

    __tablename__ = "llm_calls"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )

    request_id: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        index=True,
    )

    provider: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
    )

    model: Mapped[str] = mapped_column(
        String(150),
        nullable=False,
    )

    prompt_tokens: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
    )

    completion_tokens: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
    )

    latency_ms: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    success: Mapped[bool] = mapped_column(
        nullable=False,
        default=True,
        server_default=sql_text("true"),
    )

    error_type: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )

    # Estimated request cost in Indian rupees.
    cost_inr: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        default=0.0,
        server_default="0",
    )

    # True when the fallback provider handled the request.
    fallback_used: Mapped[bool] = mapped_column(
        nullable=False,
        default=False,
        server_default=sql_text("false"),
    )

    # Version of the system prompt used for this request.
    prompt_version: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="chat_system_v1",
        server_default="chat_system_v1",
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        index=True,
    )


class IngestJob(Base):
    """Tracks the lifecycle and progress of an ingestion job."""

    __tablename__ = "ingest_jobs"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
    )

    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="queued",
        server_default="queued",
        index=True,
    )

    total_items: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
    )

    completed_items: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
    )

    failed_items: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
    )

    error_message: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    items: Mapped[list["IngestItem"]] = relationship(
        back_populates="job",
        cascade="all, delete-orphan",
    )


class IngestItem(Base):
    """Tracks an individual document within an ingestion job."""

    __tablename__ = "ingest_items"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )

    job_id: Mapped[str] = mapped_column(
        ForeignKey("ingest_jobs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    source_url: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="queued",
        server_default="queued",
        index=True,
    )

    attempts: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
    )

    error_message: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    document_id: Mapped[int | None] = mapped_column(
        ForeignKey("documents.id", ondelete="SET NULL"),
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    job: Mapped["IngestJob"] = relationship(
        back_populates="items",
    )

    __table_args__ = (
        UniqueConstraint(
            "job_id",
            "source_url",
            name="uq_ingest_item_job_source",
        ),
    )
