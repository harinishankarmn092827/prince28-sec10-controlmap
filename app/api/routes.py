"""API routes for ControlMap."""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.connection import get_db
from app.models.document import Document
from app.services.database_document_service import DatabaseDocumentService

router = APIRouter(prefix="/v1", tags=["Documents"])

document_service = DatabaseDocumentService()


@router.get("/documents", response_model=list[Document])
async def get_documents(
    query: str = Query(default=""),
    framework: str | None = Query(default=None),
    applies_to_category: str | None = Query(default=None),
    session: AsyncSession = Depends(get_db),
) -> list[Document]:
    """Retrieve and search framework documents from PostgreSQL."""

    return await document_service.list_documents(
        session=session,
        query=query,
        framework=framework,
        category=applies_to_category,
    )


@router.get("/documents/{document_id}", response_model=Document)
async def get_document(
    document_id: int,
    session: AsyncSession = Depends(get_db),
) -> Document:
    """Retrieve a framework document using its original ID."""

    document = await document_service.get_document_by_id(
        session=session,
        document_id=document_id,
    )

    if document is None:
        raise HTTPException(
            status_code=404,
            detail="Document not found",
        )

    return document
