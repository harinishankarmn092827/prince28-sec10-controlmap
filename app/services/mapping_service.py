"""Service layer for cross-framework mappings."""

import json
from pathlib import Path

from app.models.mapping import FrameworkMapping
from app.services.document_service import DocumentService


class MappingService:
    """Provides operations for framework mappings."""

    def __init__(self, data_file: Path | None = None) -> None:
        self.data_file = data_file or Path("app/data/mappings.json")
        self.document_service = DocumentService()

    def list_mappings(self) -> list[FrameworkMapping]:
        """Load all framework mappings from the JSON file."""

        if not self.data_file.is_file():
            raise FileNotFoundError(f"Mapping data file not found: {self.data_file}")

        with self.data_file.open(encoding="utf-8") as file:
            records = json.load(file)

        if not isinstance(records, list):
            raise ValueError("Mapping data must be a JSON list.")

        return [FrameworkMapping.model_validate(record) for record in records]

    def search_mappings(
        self,
        source_framework: str | None = None,
        source_control_id: str | None = None,
        target_framework: str | None = None,
        target_control_id: str | None = None,
    ) -> list[FrameworkMapping]:
        """Search mappings using framework names and control IDs."""

        mappings = self.list_mappings()

        if source_framework:
            mappings = [
                mapping
                for mapping in mappings
                if mapping.source_framework.casefold() == source_framework.casefold()
            ]

        if source_control_id:
            mappings = [
                mapping
                for mapping in mappings
                if mapping.source_control_id.casefold() == source_control_id.casefold()
            ]

        if target_framework:
            mappings = [
                mapping
                for mapping in mappings
                if mapping.target_framework.casefold() == target_framework.casefold()
            ]

        if target_control_id:
            mappings = [
                mapping
                for mapping in mappings
                if mapping.target_control_id.casefold() == target_control_id.casefold()
            ]

        return mappings

    def validate_mappings(self) -> list[str]:
        """Check whether mapping controls exist in the document dataset."""

        documents = self.document_service.list_documents()

        available_controls = {
            (document.framework.casefold(), document.control_id.casefold())
            for document in documents
        }

        errors = []

        for mapping in self.list_mappings():
            source = (
                mapping.source_framework.casefold(),
                mapping.source_control_id.casefold(),
            )

            target = (
                mapping.target_framework.casefold(),
                mapping.target_control_id.casefold(),
            )

            if source not in available_controls:
                errors.append(
                    f"Source control not found: "
                    f"{mapping.source_framework} - "
                    f"{mapping.source_control_id}"
                )

            if target not in available_controls:
                errors.append(
                    f"Target control not found: "
                    f"{mapping.target_framework} - "
                    f"{mapping.target_control_id}"
                )

        return errors
