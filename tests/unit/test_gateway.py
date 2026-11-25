"""Unit tests for the LLM gateway."""

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from src.controlmap.llm.gateway import LLMGateway


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
    """Create a gateway with mocked provider clients."""
    return LLMGateway(
        primary_client=primary_client,
        fallback_client=fallback_client,
        system_prompt="Test system prompt",
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
async def test_generate_falls_back_when_primary_fails():
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

    primary.chat.completions.create.assert_awaited_once()
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
async def test_stream_yields_text_chunks():
    primary = AsyncMock()
    fallback = AsyncMock()

    chunks = [
        SimpleNamespace(
            choices=[
                SimpleNamespace(
                    delta=SimpleNamespace(content="Hello "),
                )
            ]
        ),
        SimpleNamespace(
            choices=[
                SimpleNamespace(
                    delta=SimpleNamespace(content="world"),
                )
            ]
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
            ]
        )

    fallback.chat.completions.create.return_value = fake_stream()

    gateway = make_gateway(primary, fallback)

    result = [
        chunk
        async for chunk in gateway.stream([{"role": "user", "content": "Say hello"}])
    ]

    assert result == ["Fallback stream"]
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
            ]
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
