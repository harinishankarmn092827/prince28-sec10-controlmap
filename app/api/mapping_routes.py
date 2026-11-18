"""API routes for cross-framework mappings."""

from fastapi import APIRouter, Query

from app.models.mapping import FrameworkMapping
from app.services.mapping_service import MappingService

router = APIRouter(prefix="/v1", tags=["Mappings"])

mapping_service = MappingService()


@router.get("/mappings/validate")
def validate_mappings() -> dict[str, bool | list[str]]:
    """Validate whether mapping controls exist in the document dataset."""

    errors = mapping_service.validate_mappings()

    return {
        "valid": len(errors) == 0,
        "errors": errors,
    }


@router.get("/mappings", response_model=list[FrameworkMapping])
def get_mappings(
    source_framework: str | None = Query(default=None),
    source_control_id: str | None = Query(default=None),
    target_framework: str | None = Query(default=None),
    target_control_id: str | None = Query(default=None),
) -> list[FrameworkMapping]:
    """Retrieve and search cross-framework mappings."""

    return mapping_service.search_mappings(
        source_framework=source_framework,
        source_control_id=source_control_id,
        target_framework=target_framework,
        target_control_id=target_control_id,
    )
