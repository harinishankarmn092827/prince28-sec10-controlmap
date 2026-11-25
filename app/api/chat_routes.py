"""Chat streaming and LLM usage endpoints."""

from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.connection import get_db
from app.database.models import LLMCall
from controlmap.llm.gateway import LLMGateway

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1", tags=["Chat"])


class ChatMessage(BaseModel):
    """A message supplied to the LLM gateway."""

    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=8000)


class ChatRequest(BaseModel):
    """Validated chat request."""

    messages: list[ChatMessage] = Field(min_length=1, max_length=20)


class UsageSummary(BaseModel):
    """Aggregated LLM usage statistics."""

    total_requests: int
    successful_requests: int
    failed_requests: int
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int


async def record_call(
    session: AsyncSession,
    *,
    request_id: str,
    provider: str,
    model: str,
    latency_ms: int,
    success: bool,
    error_type: str | None = None,
    prompt_tokens: int = 0,
    completion_tokens: int = 0,
) -> None:
    """Persist usage metadata without storing prompt or response text."""

    session.add(
        LLMCall(
            request_id=request_id,
            provider=provider,
            model=model,
            latency_ms=max(0, latency_ms),
            success=success,
            error_type=error_type,
            prompt_tokens=max(0, prompt_tokens),
            completion_tokens=max(0, completion_tokens),
        )
    )

    await session.commit()


@router.post("/chat")
async def chat(
    payload: ChatRequest,
    request: Request,
    session: AsyncSession = Depends(get_db),
):
    """Stream a chat response as Server-Sent Events."""

    request_id = request.state.request_id
    messages = [message.model_dump() for message in payload.messages]

    async def event_stream():
        gateway = LLMGateway()
        started = datetime.now().astimezone()
        output_started = False

        yield (f"event: metadata\ndata: {json.dumps({'request_id': request_id})}\n\n")

        try:
            async for chunk in gateway.stream(messages):
                output_started = True
                yield f"data: {json.dumps({'content': chunk})}\n\n"

            if not output_started:
                raise RuntimeError("The LLM providers returned an empty response.")

            yield "event: done\ndata: {}\n\n"

        except Exception:
            logger.exception(
                "Chat streaming failed",
                extra={"request_id": request_id},
            )

            # Do not expose provider error details, credentials, or internals.
            yield (
                "event: error\n"
                + "data: "
                + json.dumps(
                    {
                        "request_id": request_id,
                        "detail": "The AI response could not be completed.",
                    }
                )
                + "\n\n"
            )

        finally:
            # This initial implementation records the request outcome.
            # Provider-level details and token counts will be added when
            # the gateway exposes per-attempt streaming metadata.
            elapsed_ms = int(
                (datetime.now().astimezone() - started).total_seconds() * 1000
            )

            try:
                await record_call(
                    session,
                    request_id=request_id,
                    provider="gateway",
                    model="primary-with-fallback",
                    latency_ms=elapsed_ms,
                    success=output_started,
                    error_type=None if output_started else "StreamError",
                )
            except Exception:
                logger.exception(
                    "Failed to record LLM usage",
                    extra={"request_id": request_id},
                )

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "X-Request-ID": request_id,
        },
    )


@router.get("/usage", response_model=UsageSummary)
async def usage(
    session: AsyncSession = Depends(get_db),
) -> UsageSummary:
    """Return aggregate LLM usage statistics."""

    statement = select(
        func.count(LLMCall.id),
        func.count(LLMCall.id).filter(LLMCall.success.is_(True)),
        func.count(LLMCall.id).filter(LLMCall.success.is_(False)),
        func.coalesce(func.sum(LLMCall.prompt_tokens), 0),
        func.coalesce(func.sum(LLMCall.completion_tokens), 0),
    )

    try:
        result = await session.execute(statement)
        row = result.one()
    except Exception as exc:
        logger.exception("Unable to retrieve LLM usage")
        raise HTTPException(
            status_code=503,
            detail="Usage statistics are temporarily unavailable.",
        ) from exc

    prompt_tokens = int(row[3])
    completion_tokens = int(row[4])

    return UsageSummary(
        total_requests=int(row[0]),
        successful_requests=int(row[1]),
        failed_requests=int(row[2]),
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        total_tokens=prompt_tokens + completion_tokens,
    )
