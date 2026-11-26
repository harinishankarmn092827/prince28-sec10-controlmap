"""LLM gateway with retries, circuit breakers, fallback, and streaming."""

from __future__ import annotations

import asyncio
import random
import time
from collections.abc import AsyncIterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from openai import APIError, APIStatusError, AsyncOpenAI

from app.core.config import settings


class CircuitOpenError(RuntimeError):
    """Raised when a provider circuit is temporarily open."""


class EmptyResponseError(RuntimeError):
    """Raised when an LLM provider returns no usable text."""


class CircuitBreaker:
    """Prevent repeated requests to an unhealthy LLM provider."""

    def __init__(
        self,
        failure_threshold: int = 3,
        cooldown_seconds: float = 30.0,
    ) -> None:
        self.failure_threshold = failure_threshold
        self.cooldown_seconds = cooldown_seconds
        self.failure_count = 0
        self.opened_at: float | None = None
        self._half_open_in_flight = False

    def allow_request(self) -> None:
        """Allow requests when closed or permit one trial after cooldown."""
        if self.opened_at is None:
            return

        elapsed = time.monotonic() - self.opened_at

        if elapsed < self.cooldown_seconds:
            raise CircuitOpenError("Circuit is open")

        if self._half_open_in_flight:
            raise CircuitOpenError("Half-open trial already in progress")

        self._half_open_in_flight = True

    def record_success(self) -> None:
        """Reset the breaker after a successful provider request."""
        self.failure_count = 0
        self.opened_at = None
        self._half_open_in_flight = False

    def record_failure(self) -> None:
        """Count a failed provider request and open the circuit if necessary."""
        self._half_open_in_flight = False
        self.failure_count += 1

        if self.failure_count >= self.failure_threshold:
            self.opened_at = time.monotonic()

    def cancel_trial(self) -> None:
        """Release a half-open trial if a request is cancelled."""
        self._half_open_in_flight = False


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
    """Route LLM requests through Gemini with Groq fallback."""

    def __init__(
        self,
        primary_client: Any | None = None,
        fallback_client: Any | None = None,
        system_prompt: str | None = None,
        retry_attempts: int = 3,
        retry_base_delay: float = 0.5,
        retry_max_delay: float = 8.0,
        circuit_failure_threshold: int = 3,
        circuit_cooldown_seconds: float = 30.0,
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

        self.retry_attempts = max(1, retry_attempts)
        self.retry_base_delay = max(0.0, retry_base_delay)
        self.retry_max_delay = max(0.0, retry_max_delay)

        self.circuit_breakers = {
            "gemini": CircuitBreaker(
                failure_threshold=circuit_failure_threshold,
                cooldown_seconds=circuit_cooldown_seconds,
            ),
            "groq": CircuitBreaker(
                failure_threshold=circuit_failure_threshold,
                cooldown_seconds=circuit_cooldown_seconds,
            ),
        }

        # Metadata from the most recently completed streaming request.
        self.last_provider = "gateway"
        self.last_model = "primary-with-fallback"
        self.last_prompt_tokens = 0
        self.last_completion_tokens = 0
        self.last_fallback_used = False
        self.prompt_version = "chat_system_v1"

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

    @staticmethod
    def _is_retryable(exc: Exception) -> bool:
        """Identify transient failures that are safe to retry."""
        if isinstance(exc, (asyncio.TimeoutError, TimeoutError)):
            return True

        if isinstance(exc, APIStatusError):
            status_code = exc.status_code
            return status_code == 429 or status_code >= 500

        if isinstance(exc, APIError):
            return True

        if isinstance(exc, EmptyResponseError):
            return True

        return False

    async def _retry_delay(self, attempt: int) -> None:
        """Wait using exponential backoff and random jitter."""
        exponential_delay = min(
            self.retry_base_delay * (2**attempt),
            self.retry_max_delay,
        )

        jitter = random.uniform(0.0, exponential_delay * 0.25)
        await asyncio.sleep(exponential_delay + jitter)

    async def _create_completion(
        self,
        client: Any,
        model: str,
        messages: list[dict[str, str]],
    ) -> Any:
        """Create a non-streaming completion with retry handling."""
        last_error: Exception | None = None

        for attempt in range(self.retry_attempts):
            try:
                async with asyncio.timeout(self.timeout_seconds):
                    response = await client.chat.completions.create(
                        model=model,
                        messages=messages,
                        stream=False,
                    )

                if not self._extract_content(response):
                    raise EmptyResponseError("Provider returned an empty response")

                return response

            except Exception as exc:
                if isinstance(exc, asyncio.CancelledError):
                    raise

                last_error = exc

                if not self._is_retryable(exc):
                    raise

                if attempt + 1 < self.retry_attempts:
                    await self._retry_delay(attempt)

        if last_error is not None:
            raise last_error

        raise RuntimeError("Completion failed without an error")

    async def generate(self, messages: list[dict[str, str]]) -> LLMResponse:
        """Generate a response with retries and provider fallback."""
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
            breaker = self.circuit_breakers[provider]
            started = time.perf_counter()

            try:
                breaker.allow_request()

                response = await self._create_completion(
                    client,
                    model,
                    request_messages,
                )

                content = self._extract_content(response)
                prompt_tokens, completion_tokens = self._extract_usage(response)

                breaker.record_success()

                return LLMResponse(
                    content=content,
                    provider=provider,
                    model=model,
                    prompt_tokens=prompt_tokens,
                    completion_tokens=completion_tokens,
                    latency_ms=int((time.perf_counter() - started) * 1000),
                )

            except CircuitOpenError as exc:
                errors.append(f"{provider}: {type(exc).__name__}")

            except asyncio.CancelledError:
                breaker.cancel_trial()
                raise

            except Exception as exc:
                breaker.record_failure()
                errors.append(f"{provider}: {type(exc).__name__}")

        raise RuntimeError("All LLM providers failed: " + "; ".join(errors))

    async def stream(self, messages: list[dict[str, str]]) -> AsyncIterator[str]:
        """Stream text with retries before output and fallback between providers."""
        request_messages = [
            {"role": "system", "content": self.system_prompt},
            *messages,
        ]

        providers = (
            ("gemini", self.primary_client, self.primary_model),
            ("groq", self.fallback_client, self.fallback_model),
        )

        errors: list[str] = []

        self.last_provider = "gateway"
        self.last_model = "primary-with-fallback"
        self.last_prompt_tokens = 0
        self.last_completion_tokens = 0
        self.last_fallback_used = False

        for provider, client, model in providers:
            breaker = self.circuit_breakers[provider]

            try:
                breaker.allow_request()
            except CircuitOpenError as exc:
                errors.append(f"{provider}: {type(exc).__name__}")
                continue

            provider_succeeded = False

            try:
                for attempt in range(self.retry_attempts):
                    stream = None
                    output_started = False
                    prompt_tokens = 0
                    completion_tokens = 0

                    try:
                        async with asyncio.timeout(self.timeout_seconds):
                            stream = await client.chat.completions.create(
                                model=model,
                                messages=request_messages,
                                stream=True,
                                stream_options={"include_usage": True},
                            )

                            async for chunk in stream:
                                usage = getattr(chunk, "usage", None)

                                if usage is not None:
                                    prompt_tokens = int(
                                        getattr(usage, "prompt_tokens", 0) or 0
                                    )
                                    completion_tokens = int(
                                        getattr(chunk.usage, "completion_tokens", 0)
                                        or 0
                                    )

                                if not chunk.choices:
                                    continue

                                delta = chunk.choices[0].delta
                                content = getattr(delta, "content", None)

                                if content:
                                    output_started = True
                                    yield content

                        if not output_started:
                            raise EmptyResponseError(
                                "Provider returned an empty stream"
                            )

                        breaker.record_success()
                        provider_succeeded = True

                        self.last_provider = provider
                        self.last_model = model
                        self.last_prompt_tokens = prompt_tokens
                        self.last_completion_tokens = completion_tokens
                        self.last_fallback_used = provider == "groq"

                        return

                    except asyncio.CancelledError:
                        breaker.cancel_trial()
                        raise

                    except Exception as exc:
                        errors.append(f"{provider}: {type(exc).__name__}")

                        if output_started:
                            breaker.record_failure()
                            raise RuntimeError(
                                f"Streaming failed after output began ({provider})."
                            ) from exc

                        if (
                            not self._is_retryable(exc)
                            or attempt + 1 >= self.retry_attempts
                        ):
                            breaker.record_failure()
                            break

                        await self._retry_delay(attempt)

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
                                    # Cleanup must not hide the original outcome.
                                    pass

            finally:
                if not provider_succeeded:
                    breaker.cancel_trial()

        raise RuntimeError("All LLM providers failed: " + "; ".join(errors))
