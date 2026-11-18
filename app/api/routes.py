"""API routes for ControlMap."""

from fastapi import APIRouter, HTTPException, Query

from app.models.document import Document
from app.services.document_service import DocumentService

router = APIRouter(prefix="/v1", tags=["Documents"])

document_service = DocumentService()


@router.get("/documents", response_model=list[Document])
def get_documents(
    query: str = Query(default=""),
    framework: str | None = Query(default=None),
) -> list[Document]:
    """Retrieve and search framework documents."""

    return document_service.search_documents(
        query=query,
        framework=framework,
    )


@router.get("/documents/{document_id}", response_model=Document)
def get_document(document_id: int) -> Document:
    """Retrieve a document using its ID."""

    document = document_service.get_document_by_id(document_id)

    if document is None:
        raise HTTPException(
            status_code=404,
            detail="Document not found",
        )

    return document
