"""API routes for source documents and extracted metadata."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.connection import get_db
from app.models.source_document import SourceDocument
from app.services.source_document_service import SourceDocumentService

router = APIRouter(prefix="/v1", tags=["Source Documents"])
source_document_service = SourceDocumentService()


@router.get("/source-documents", response_model=list[SourceDocument])
async def get_source_documents(
    doc_kind: str | None = Query(default=None),
    language: str | None = Query(default=None),
    framework: str | None = Query(default=None),
    control_id: str | None = Query(default=None),
    function_or_family: str | None = Query(default=None),
    applies_to_category: str | None = Query(default=None),
    source_date: str | None = Query(default=None),
    session: AsyncSession = Depends(get_db),
) -> list[SourceDocument]:
    """Search source documents using their extracted metadata."""

    return await source_document_service.list_source_documents(
        session=session,
        doc_kind=doc_kind,
        language=language,
        framework=framework,
        control_id=control_id,
        function_or_family=function_or_family,
        applies_to_category=applies_to_category,
        source_date=source_date,
    )
