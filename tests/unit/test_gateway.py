"""Unit tests for the LLM gateway."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from src.controlmap.llm.gateway import (
    CircuitBreaker,
    CircuitOpenError,
    LLMGateway,
)


def make_response(
    content: str = "Test answer",
    prompt_tokens: int = 12,
    completion_tokens: int = 8,
):
    """Build a mock chat-completion response."""
    return SimpleNamespace(
        choices=[
            SimpleNamespace(
                message=SimpleNamespace(content=content),
            )
        ],
        usage=SimpleNamespace(
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
        ),
    )


def make_gateway(
    primary_client: AsyncMock,
    fallback_client: AsyncMock,
) -> LLMGateway:
    """Create a gateway with fast retries for unit tests."""
    return LLMGateway(
        primary_client=primary_client,
        fallback_client=fallback_client,
        system_prompt="Test system prompt",
        retry_attempts=3,
        retry_base_delay=0,
        retry_max_delay=0,
    )


@pytest.mark.asyncio
async def test_generate_uses_primary_provider():
    primary = AsyncMock()
    fallback = AsyncMock()
    primary.chat.completions.create.return_value = make_response()

    gateway = make_gateway(primary, fallback)

    result = await gateway.generate([{"role": "user", "content": "Explain MFA"}])

    assert result.content == "Test answer"
    assert result.provider == "gemini"
    assert result.prompt_tokens == 12
    assert result.completion_tokens == 8

    primary.chat.completions.create.assert_awaited_once()
    fallback.chat.completions.create.assert_not_awaited()


@pytest.mark.asyncio
async def test_generate_retries_primary_then_falls_back():
    primary = AsyncMock()
    fallback = AsyncMock()

    primary.chat.completions.create.side_effect = TimeoutError
    fallback.chat.completions.create.return_value = make_response(
        content="Fallback answer"
    )

    gateway = make_gateway(primary, fallback)

    result = await gateway.generate([{"role": "user", "content": "Explain MFA"}])

    assert result.content == "Fallback answer"
    assert result.provider == "groq"
    assert primary.chat.completions.create.await_count == 3
    fallback.chat.completions.create.assert_awaited_once()


@pytest.mark.asyncio
async def test_generate_raises_when_both_providers_fail():
    primary = AsyncMock()
    fallback = AsyncMock()

    primary.chat.completions.create.side_effect = TimeoutError
    fallback.chat.completions.create.side_effect = TimeoutError

    gateway = make_gateway(primary, fallback)

    with pytest.raises(RuntimeError, match="All LLM providers failed"):
        await gateway.generate([{"role": "user", "content": "Explain MFA"}])

    assert primary.chat.completions.create.await_count == 3
    assert fallback.chat.completions.create.await_count == 3


@pytest.mark.asyncio
async def test_generate_includes_system_prompt():
    primary = AsyncMock()
    fallback = AsyncMock()
    primary.chat.completions.create.return_value = make_response()

    gateway = make_gateway(primary, fallback)

    await gateway.generate([{"role": "user", "content": "Explain MFA"}])

    call = primary.chat.completions.create.await_args
    messages = call.kwargs["messages"]

    assert messages[0] == {
        "role": "system",
        "content": "Test system prompt",
    }
    assert messages[1]["content"] == "Explain MFA"


@pytest.mark.asyncio
async def test_generate_handles_missing_usage():
    primary = AsyncMock()
    fallback = AsyncMock()

    response = make_response()
    response.usage = None
    primary.chat.completions.create.return_value = response

    gateway = make_gateway(primary, fallback)

    result = await gateway.generate([{"role": "user", "content": "Explain MFA"}])

    assert result.prompt_tokens == 0
    assert result.completion_tokens == 0


@pytest.mark.asyncio
async def test_generate_retries_after_transient_failure():
    primary = AsyncMock()
    fallback = AsyncMock()

    primary.chat.completions.create.side_effect = [
        TimeoutError(),
        make_response(content="Recovered answer"),
    ]

    gateway = make_gateway(primary, fallback)

    result = await gateway.generate([{"role": "user", "content": "Explain MFA"}])

    assert result.content == "Recovered answer"
    assert result.provider == "gemini"
    assert primary.chat.completions.create.await_count == 2
    fallback.chat.completions.create.assert_not_awaited()


@pytest.mark.asyncio
async def test_retry_delay_uses_exponential_backoff_and_jitter():
    primary = AsyncMock()
    fallback = AsyncMock()

    gateway = LLMGateway(
        primary_client=primary,
        fallback_client=fallback,
        system_prompt="Test prompt",
        retry_base_delay=2,
        retry_max_delay=10,
    )

    with (
        patch(
            "src.controlmap.llm.gateway.random.uniform",
            return_value=0.25,
        ) as jitter,
        patch(
            "src.controlmap.llm.gateway.asyncio.sleep",
            new_callable=AsyncMock,
        ) as sleep,
    ):
        await gateway._retry_delay(1)

    # 2 seconds * 2**1 = 4 seconds, plus 0.25 seconds of jitter.
    sleep.assert_awaited_once_with(4.25)
    jitter.assert_called_once_with(0.0, 1.0)


def test_circuit_breaker_opens_after_threshold():
    breaker = CircuitBreaker(
        failure_threshold=3,
        cooldown_seconds=30,
    )

    breaker.record_failure()
    breaker.record_failure()

    assert breaker.failure_count == 2
    assert breaker.opened_at is None

    breaker.record_failure()

    assert breaker.failure_count == 3
    assert breaker.opened_at is not None

    with pytest.raises(CircuitOpenError, match="Circuit is open"):
        breaker.allow_request()


def test_circuit_breaker_success_resets_failures():
    breaker = CircuitBreaker(failure_threshold=3)

    breaker.record_failure()
    breaker.record_failure()
    breaker.record_success()

    assert breaker.failure_count == 0
    assert breaker.opened_at is None

    breaker.allow_request()


def test_circuit_breaker_allows_trial_after_cooldown():
    breaker = CircuitBreaker(
        failure_threshold=1,
        cooldown_seconds=30,
    )

    breaker.record_failure()

    assert breaker.opened_at is not None

    with patch(
        "src.controlmap.llm.gateway.time.monotonic",
        return_value=breaker.opened_at + 31,
    ):
        breaker.allow_request()

        with pytest.raises(CircuitOpenError, match="trial already in progress"):
            breaker.allow_request()

        breaker.record_success()

    assert breaker.failure_count == 0
    assert breaker.opened_at is None


@pytest.mark.asyncio
async def test_stream_yields_text_chunks():
    primary = AsyncMock()
    fallback = AsyncMock()

    chunks = [
        SimpleNamespace(
            choices=[
                SimpleNamespace(
                    delta=SimpleNamespace(content="Hello "),
                )
            ],
            usage=None,
        ),
        SimpleNamespace(
            choices=[
                SimpleNamespace(
                    delta=SimpleNamespace(content="world"),
                )
            ],
            usage=None,
        ),
    ]

    async def fake_stream():
        for chunk in chunks:
            yield chunk

    primary.chat.completions.create.return_value = fake_stream()

    gateway = make_gateway(primary, fallback)

    result = [
        chunk
        async for chunk in gateway.stream([{"role": "user", "content": "Say hello"}])
    ]

    assert result == ["Hello ", "world"]
    fallback.chat.completions.create.assert_not_awaited()


@pytest.mark.asyncio
async def test_stream_falls_back_if_primary_fails_before_output():
    primary = AsyncMock()
    fallback = AsyncMock()

    primary.chat.completions.create.side_effect = TimeoutError

    async def fake_stream():
        yield SimpleNamespace(
            choices=[
                SimpleNamespace(
                    delta=SimpleNamespace(content="Fallback stream"),
                )
            ],
            usage=None,
        )

    fallback.chat.completions.create.return_value = fake_stream()

    gateway = make_gateway(primary, fallback)

    result = [
        chunk
        async for chunk in gateway.stream([{"role": "user", "content": "Say hello"}])
    ]

    assert result == ["Fallback stream"]
    assert primary.chat.completions.create.await_count == 3
    fallback.chat.completions.create.assert_awaited_once()


@pytest.mark.asyncio
async def test_stream_does_not_switch_provider_after_output():
    primary = AsyncMock()
    fallback = AsyncMock()

    async def broken_stream():
        yield SimpleNamespace(
            choices=[
                SimpleNamespace(
                    delta=SimpleNamespace(content="Partial answer"),
                )
            ],
            usage=None,
        )
        raise TimeoutError

    primary.chat.completions.create.return_value = broken_stream()

    gateway = make_gateway(primary, fallback)

    received = []

    with pytest.raises(RuntimeError, match="after output began"):
        async for chunk in gateway.stream([{"role": "user", "content": "Say hello"}]):
            received.append(chunk)

    assert received == ["Partial answer"]
    fallback.chat.completions.create.assert_not_awaited()


@pytest.mark.asyncio
async def test_stream_captures_usage_from_final_chunk():
    """Capture token usage from a final chunk with no choices."""
    primary = AsyncMock()
    fallback = AsyncMock()

    chunks = [
        SimpleNamespace(
            choices=[
                SimpleNamespace(
                    delta=SimpleNamespace(content="Hello"),
                )
            ],
            usage=None,
        ),
        SimpleNamespace(
            choices=[],
            usage=SimpleNamespace(
                prompt_tokens=15,
                completion_tokens=7,
            ),
        ),
    ]

    async def fake_stream():
        for chunk in chunks:
            yield chunk

    primary.chat.completions.create.return_value = fake_stream()

    gateway = make_gateway(primary, fallback)

    result = [
        chunk
        async for chunk in gateway.stream([{"role": "user", "content": "Say hello"}])
    ]

    assert result == ["Hello"]
    assert gateway.last_provider == "gemini"
    assert gateway.last_model == gateway.primary_model
    assert gateway.last_prompt_tokens == 15
    assert gateway.last_completion_tokens == 7

    fallback.chat.completions.create.assert_not_awaited()


@pytest.mark.asyncio
async def test_generate_passes_structured_json_response_format():
    """Pass JSON response format through to the provider."""
    primary = AsyncMock()
    fallback = AsyncMock()
    primary.chat.completions.create.return_value = make_response(
        content='{"label":"docs","reason":"Security question"}'
    )

    gateway = make_gateway(primary, fallback)
    response_format = {"type": "json_object"}

    result = await gateway.generate(
        [{"role": "user", "content": "Classify this question"}],
        response_format=response_format,
    )

    assert result.content == '{"label":"docs","reason":"Security question"}'

    call = primary.chat.completions.create.await_args
    assert call.kwargs["response_format"] == response_format
    assert call.kwargs["stream"] is False
    fallback.chat.completions.create.assert_not_awaited()
