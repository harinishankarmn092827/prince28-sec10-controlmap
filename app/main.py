"""Main FastAPI application for ControlMap."""

from fastapi import FastAPI

from app.api.routes import router
from app.core.config import settings

app = FastAPI(
    title=settings.app_name,
    version=settings.api_version,
    debug=settings.debug,
    description="Cybersecurity Framework Crosswalk and Audit Evidence Mapping API",
)

app.include_router(router)


@app.get("/health")
def health_check() -> dict[str, str]:
    """Check application health."""
    return {"status": "healthy"}


@app.get("/ready")
def readiness_check() -> dict[str, str]:
    """Check application readiness."""
    return {"status": "ready"}
