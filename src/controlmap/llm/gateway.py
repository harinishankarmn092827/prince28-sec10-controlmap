"""LLM gateway with primary-provider fallback and streaming support."""

from __future__ import annotations

import asyncio
import time
from collections.abc import AsyncIterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from openai import APIError, AsyncOpenAI

from app.core.config import settings


@dataclass
class LLMResponse:
    """Normalized response from an LLM provider."""

    content: str
    provider: str
    model: str
    prompt_tokens: int
    completion_tokens: int
    latency_ms: int


class LLMGateway:
    """Route LLM requests through Gemini, falling back to Groq."""

    def __init__(
        self,
        primary_client: Any | None = None,
        fallback_client: Any | None = None,
        system_prompt: str | None = None,
    ) -> None:
        self.primary_model = settings.llm_primary_model
        self.fallback_model = settings.llm_fallback_model
        self.timeout_seconds = settings.llm_timeout_seconds

        self.primary_client = primary_client or AsyncOpenAI(
            api_key=settings.gemini_api_key or "missing-gemini-key",
            base_url=settings.llm_primary_base_url,
            timeout=self.timeout_seconds,
            max_retries=0,
        )

        self.fallback_client = fallback_client or AsyncOpenAI(
            api_key=settings.groq_api_key or "missing-groq-key",
            base_url=settings.llm_fallback_base_url,
            timeout=self.timeout_seconds,
            max_retries=0,
        )

        self.system_prompt = (
            system_prompt if system_prompt is not None else self._load_system_prompt()
        )

    @staticmethod
    def _load_system_prompt() -> str:
        """Load the versioned system prompt from disk."""
        prompt_path: Path = settings.prompts_dir / "chat_system_v1.md"

        try:
            return prompt_path.read_text(encoding="utf-8")
        except OSError:
            return (
                "You are the ControlMap cybersecurity compliance assistant. "
                'If you are not sure, say "I am not sure" instead of guessing. '
                "Never invent regulatory requirements or control identifiers."
            )

    @staticmethod
    def _extract_content(response: Any) -> str:
        """Extract text from a chat-completion response."""
        if not response.choices:
            return ""

        content = response.choices[0].message.content

        if isinstance(content, str):
            return content.strip()

        return ""

    @staticmethod
    def _extract_usage(response: Any) -> tuple[int, int]:
        """Return prompt and completion token counts."""
        usage = getattr(response, "usage", None)

        if usage is None:
            return 0, 0

        return (
            int(getattr(usage, "prompt_tokens", 0) or 0),
            int(getattr(usage, "completion_tokens", 0) or 0),
        )

    async def generate(self, messages: list[dict[str, str]]) -> LLMResponse:
        """Generate a response, trying Groq if Gemini fails or returns no text."""
        request_messages = [
            {"role": "system", "content": self.system_prompt},
            *messages,
        ]

        errors: list[str] = []

        providers = (
            ("gemini", self.primary_client, self.primary_model),
            ("groq", self.fallback_client, self.fallback_model),
        )

        for provider, client, model in providers:
            started = time.perf_counter()

            try:
                async with asyncio.timeout(self.timeout_seconds):
                    response = await client.chat.completions.create(
                        model=model,
                        messages=request_messages,
                        stream=False,
                    )

                content = self._extract_content(response)

                if not content:
                    errors.append(f"{provider}: EmptyResponse")
                    continue

                prompt_tokens, completion_tokens = self._extract_usage(response)

                return LLMResponse(
                    content=content,
                    provider=provider,
                    model=model,
                    prompt_tokens=prompt_tokens,
                    completion_tokens=completion_tokens,
                    latency_ms=int((time.perf_counter() - started) * 1000),
                )

            except (APIError, asyncio.TimeoutError, TimeoutError) as exc:
                errors.append(f"{provider}: {type(exc).__name__}")

        raise RuntimeError("All LLM providers failed: " + "; ".join(errors))

    async def stream(self, messages: list[dict[str, str]]) -> AsyncIterator[str]:
        """Stream response text, falling back before output if a provider fails."""
        request_messages = [
            {"role": "system", "content": self.system_prompt},
            *messages,
        ]

        providers = (
            ("gemini", self.primary_client, self.primary_model),
            ("groq", self.fallback_client, self.fallback_model),
        )

        errors: list[str] = []

        for provider, client, model in providers:
            stream = None
            output_started = False

            try:
                async with asyncio.timeout(self.timeout_seconds):
                    stream = await client.chat.completions.create(
                        model=model,
                        messages=request_messages,
                        stream=True,
                    )

                    async for chunk in stream:
                        if not chunk.choices:
                            continue

                        delta = chunk.choices[0].delta
                        content = getattr(delta, "content", None)

                        if content:
                            output_started = True
                            yield content

                if not output_started:
                    errors.append(f"{provider}: EmptyResponse")
                    continue

                return

            except (APIError, asyncio.TimeoutError, TimeoutError) as exc:
                errors.append(f"{provider}: {type(exc).__name__}")

                if output_started:
                    raise RuntimeError(
                        f"Streaming failed after output began ({provider})."
                    ) from exc

            finally:
                if stream is not None:
                    close = getattr(stream, "aclose", None)

                    if close is None:
                        close = getattr(stream, "close", None)

                    if close is not None:
                        try:
                            result = close()
                            if hasattr(result, "__await__"):
                                await result
                        except Exception:
                            # Cleanup errors must not hide the original outcome.
                            pass

        raise RuntimeError("All LLM providers failed: " + "; ".join(errors))
