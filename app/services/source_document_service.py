"""Database service for source documents and extracted metadata."""

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import Document as DocumentRecord
from app.models.source_document import SourceDocument


class SourceDocumentService:
    """Search source documents using extracted metadata."""

    FILTER_FIELDS = (
        "doc_kind",
        "language",
        "framework",
        "control_id",
        "function_or_family",
        "applies_to_category",
        "source_date",
    )

    async def list_source_documents(
        self,
        session: AsyncSession,
        doc_kind: str | None = None,
        language: str | None = None,
        framework: str | None = None,
        control_id: str | None = None,
        function_or_family: str | None = None,
        applies_to_category: str | None = None,
        source_date: str | None = None,
    ) -> list[SourceDocument]:
        """Return source documents matching the requested metadata filters."""

        statement = select(DocumentRecord).where(
            DocumentRecord.doc_type.notin_(["control_record", "record"]),
            DocumentRecord.document_metadata["_metadata_extraction"]["status"].astext
            == "success",
        )

        filters: dict[str, str | None] = {
            "doc_kind": doc_kind,
            "language": language,
            "framework": framework,
            "control_id": control_id,
            "function_or_family": function_or_family,
            "applies_to_category": applies_to_category,
            "source_date": source_date,
        }

        for field, value in filters.items():
            if value and value.strip():
                statement = statement.where(
                    DocumentRecord.document_metadata[field].astext.ilike(
                        f"%{value.strip()}%"
                    )
                )

        result = await session.scalars(statement.order_by(DocumentRecord.id))
        records = result.all()

        documents: list[SourceDocument] = []

        for record in records:
            metadata: dict[str, Any] = record.document_metadata or {}

            documents.append(
                SourceDocument(
                    id=record.id,
                    title=record.title,
                    doc_kind=metadata.get("doc_kind"),
                    year=metadata.get("year"),
                    language=metadata.get("language"),
                    summary=metadata.get("summary"),
                    topics=metadata.get("topics") or [],
                    framework=metadata.get("framework"),
                    control_id=metadata.get("control_id"),
                    function_or_family=metadata.get("function_or_family"),
                    applies_to_category=metadata.get("applies_to_category"),
                    source_date=metadata.get("source_date"),
                )
            )

        return documents
