"""Smoke tests for the deployed ControlMap API."""

import os

import httpx
import pytest


def test_deployed_health_endpoint():
    """Verify that the deployed API health endpoint responds correctly."""
    base_url = os.getenv("SMOKE_TEST_BASE_URL")

    if not base_url:
        pytest.skip("SMOKE_TEST_BASE_URL is not configured")

    response = httpx.get(
        f"{base_url.rstrip('/')}/health",
        timeout=30,
    )

    assert response.status_code == 200

    data = response.json()

    assert data["status"] == "healthy"
    assert data["version"]
    assert data["commit"]
