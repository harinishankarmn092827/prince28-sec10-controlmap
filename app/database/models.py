"""SQLAlchemy models for ControlMap."""

from datetime import date, datetime

from sqlalchemy import (
    Date,
    DateTime,
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
