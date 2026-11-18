"""Database service for searching cybersecurity framework documents."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import Document as DocumentRecord
from app.models.document import Document


class DatabaseDocumentService:
    """Provides database operations for framework documents."""

    async def list_documents(
        self,
        session: AsyncSession,
        query: str = "",
        framework: str | None = None,
        function_or_family: str | None = None,
        category: str | None = None,
    ) -> list[Document]:
        """Retrieve and filter documents from PostgreSQL."""

        statement = select(DocumentRecord).where(
            DocumentRecord.doc_type == "control_record"
        )

        if framework:
            statement = statement.where(
                DocumentRecord.document_metadata["framework"].astext.ilike(framework)
            )

        if function_or_family:
            statement = statement.where(
                DocumentRecord.document_metadata["function_or_family"].astext.ilike(
                    function_or_family
                )
            )

        if category:
            statement = statement.where(
                DocumentRecord.document_metadata["applies_to_category"].astext.ilike(
                    category
                )
            )

        if query.strip():
            keyword = f"%{query.strip()}%"

            statement = statement.where(
                DocumentRecord.title.ilike(keyword)
                | DocumentRecord.document_metadata["framework"].astext.ilike(keyword)
                | DocumentRecord.document_metadata["control_id"].astext.ilike(keyword)
                | DocumentRecord.document_metadata["function_or_family"].astext.ilike(
                    keyword
                )
                | DocumentRecord.document_metadata["applies_to_category"].astext.ilike(
                    keyword
                )
            )

        result = await session.scalars(statement.order_by(DocumentRecord.id))

        records = result.all()

        return [
            Document(
                id=record.document_metadata["original_record_id"],
                framework=record.document_metadata["framework"],
                control_id=record.document_metadata["control_id"],
                title=record.title,
                function_or_family=record.document_metadata["function_or_family"],
                applies_to_category=record.document_metadata["applies_to_category"],
                source_date=record.document_metadata["source_date"],
            )
            for record in records
        ]

    async def get_document_by_id(
        self,
        session: AsyncSession,
        document_id: int,
    ) -> Document | None:
        """Retrieve a control document using its original JSON ID."""

        statement = select(DocumentRecord).where(
            DocumentRecord.doc_type == "control_record",
            DocumentRecord.document_metadata["original_record_id"].astext
            == str(document_id),
        )

        record = await session.scalar(statement)

        if record is None:
            return None

        return Document(
            id=record.document_metadata["original_record_id"],
            framework=record.document_metadata["framework"],
            control_id=record.document_metadata["control_id"],
            title=record.title,
            function_or_family=record.document_metadata["function_or_family"],
            applies_to_category=record.document_metadata["applies_to_category"],
            source_date=record.document_metadata["source_date"],
        )
