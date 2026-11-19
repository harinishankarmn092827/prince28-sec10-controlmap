"""Main FastAPI application for ControlMap."""

from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy import text
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api.mapping_routes import router as mapping_router
from app.api.routes import router
from app.core.config import settings
from app.core.logging import request_id_context, setup_logging
from app.database.connection import AsyncSessionLocal


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""

    setup_logging()

    application = FastAPI(
        title=settings.app_name,
        version=settings.api_version,
        debug=settings.debug,
        description="Cybersecurity Framework Crosswalk and Audit Evidence Mapping API",
    )

    @application.middleware("http")
    async def request_id_middleware(request: Request, call_next):
        request_id = request.headers.get("X-Request-ID") or str(uuid4())
        request.state.request_id = request_id

        token = request_id_context.set(request_id)

        try:
            response = await call_next(request)
            response.headers["X-Request-ID"] = request_id
            return response
        finally:
            request_id_context.reset(token)

    @application.exception_handler(StarletteHTTPException)
    async def http_exception_handler(
        request: Request,
        exc: StarletteHTTPException,
    ):
        """Return HTTP errors in problem-details format."""

        titles = {
            400: "Bad Request",
            401: "Unauthorized",
            403: "Forbidden",
            404: "Not Found",
        }

        return JSONResponse(
            status_code=exc.status_code,
            content={
                "type": "about:blank",
                "title": titles.get(exc.status_code, "HTTP Error"),
                "status": exc.status_code,
                "detail": str(exc.detail),
                "instance": request.url.path,
                "request_id": getattr(request.state, "request_id", None),
            },
            headers=exc.headers,
            media_type="application/problem+json",
        )

    @application.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        request: Request,
        exc: RequestValidationError,
    ):
        """Return request validation errors in problem-details format."""

        return JSONResponse(
            status_code=422,
            content={
                "type": "about:blank",
                "title": "Validation Error",
                "status": 422,
                "detail": "The request contains invalid data.",
                "instance": request.url.path,
                "request_id": getattr(request.state, "request_id", None),
            },
            media_type="application/problem+json",
        )

    @application.exception_handler(Exception)
    async def general_exception_handler(
        request: Request,
        exc: Exception,
    ):
        """Handle unexpected application errors."""

        return JSONResponse(
            status_code=500,
            content={
                "type": "about:blank",
                "title": "Internal Server Error",
                "status": 500,
                "detail": "An unexpected error occurred.",
                "instance": request.url.path,
                "request_id": getattr(request.state, "request_id", None),
            },
            media_type="application/problem+json",
        )

    application.include_router(router)
    application.include_router(mapping_router)

    @application.get("/health")
    def health_check() -> dict[str, str]:
        """Check whether the API process is running."""
        return {"status": "healthy"}

    @application.get("/ready")
    async def readiness_check():
        """Check whether the API can access PostgreSQL."""

        try:
            async with AsyncSessionLocal() as session:
                await session.execute(text("SELECT 1"))

            return {"status": "ready"}

        except Exception:
            return JSONResponse(
                status_code=503,
                content={"status": "not ready"},
            )

    return application


app = create_app()
