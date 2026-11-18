"""SQLAlchemy models for ControlMap."""

from datetime import date

from sqlalchemy import (
    Date,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
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
    """Stores individual pages belonging to a document."""

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

    document: Mapped["Document"] = relationship(
        back_populates="pages",
    )

    __table_args__ = (
        UniqueConstraint("doc_id", "page_no", name="uq_document_page"),
        Index("ix_pages_doc_id", "doc_id"),
    )
