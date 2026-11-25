"""Unit tests for the chat and usage API endpoints."""

from unittest.mock import AsyncMock, Mock, patch

import pytest
from fastapi.testclient import TestClient

from app.api.chat_routes import get_db
from app.main import app


@pytest.fixture
def client():
    """Provide a test client with a mocked database session."""
    session = AsyncMock()
    session.add = Mock()
    session.commit = AsyncMock()
    session.execute = AsyncMock()

    app.dependency_overrides[get_db] = lambda: session

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()


def test_chat_streams_response(client):
    """The chat endpoint should stream text and finish with a done event."""

    async def fake_stream(messages):
        yield "Hello "
        yield "from ControlMap!"

    with patch("app.api.chat_routes.LLMGateway") as gateway_class:
        gateway_class.return_value.stream.side_effect = fake_stream

        response = client.post(
            "/v1/chat",
            json={"messages": [{"role": "user", "content": "Hello"}]},
        )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert "event: metadata" in response.text
    assert "Hello " in response.text
    assert "from ControlMap!" in response.text
    assert "event: done" in response.text


def test_chat_rejects_empty_messages(client):
    """The chat endpoint should reject an empty messages list."""
    response = client.post("/v1/chat", json={"messages": []})

    assert response.status_code == 422


def test_chat_rejects_empty_message_content(client):
    """The chat endpoint should reject blank message content."""
    response = client.post(
        "/v1/chat",
        json={"messages": [{"role": "user", "content": ""}]},
    )

    assert response.status_code == 422


def test_chat_returns_sse_error_when_gateway_fails(client):
    """Provider errors should produce a safe SSE error event."""

    async def failing_stream(messages):
        raise RuntimeError("Internal provider details")
        yield "unreachable"

    with patch("app.api.chat_routes.LLMGateway") as gateway_class:
        gateway_class.return_value.stream.side_effect = failing_stream

        response = client.post(
            "/v1/chat",
            json={"messages": [{"role": "user", "content": "Hello"}]},
        )

    assert response.status_code == 200
    assert "event: error" in response.text
    assert "The AI response could not be completed." in response.text
    assert "Internal provider details" not in response.text


def test_usage_returns_aggregated_statistics(client):
    """The usage endpoint should return aggregate counts and token totals."""
    session = app.dependency_overrides[get_db]()

    result = Mock()
    result.one.return_value = (5, 4, 1, 120, 80)
    session.execute.return_value = result

    response = client.get("/v1/usage")

    assert response.status_code == 200
    assert response.json() == {
        "total_requests": 5,
        "successful_requests": 4,
        "failed_requests": 1,
        "prompt_tokens": 120,
        "completion_tokens": 80,
        "total_tokens": 200,
    }
