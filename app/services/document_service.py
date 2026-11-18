"""Service layer for loading and searching cybersecurity documents."""

import json
from pathlib import Path

from app.core.config import settings
from app.models.document import Document


class DocumentService:
    """Provides operations for cybersecurity framework documents."""

    def __init__(self, data_file: Path | None = None) -> None:
        self.data_file = data_file or settings.data_file

    def list_documents(self) -> list[Document]:
        """Load and return all framework documents."""

        if not self.data_file.is_file():
            raise FileNotFoundError(f"Document data file not found: {self.data_file}")

        with self.data_file.open(encoding="utf-8") as file:
            records = json.load(file)

        if not isinstance(records, list):
            raise ValueError("Document data must be a JSON list.")

        return [Document.model_validate(record) for record in records]

    def get_document_by_id(self, document_id: int) -> Document | None:
        """Find a document using its unique ID."""

        documents = self.list_documents()

        return next(
            (document for document in documents if document.id == document_id),
            None,
        )

    def search_documents(
        self,
        query: str = "",
        framework: str | None = None,
    ) -> list[Document]:
        """Search documents by keyword and optionally filter by framework."""

        documents = self.list_documents()

        if framework:
            documents = [
                document
                for document in documents
                if document.framework.casefold() == framework.casefold()
            ]

        keyword = query.strip().casefold()

        if not keyword:
            return documents

        return [
            document
            for document in documents
            if keyword
            in " ".join(
                [
                    document.framework,
                    document.control_id,
                    document.title,
                    document.function_or_family,
                    document.applies_to_category,
                ]
            ).casefold()
        ]
