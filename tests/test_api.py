"""API tests for ControlMap."""

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_check():
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}


def test_readiness_check():
    response = client.get("/ready")

    assert response.status_code == 200
    assert response.json() == {"status": "ready"}


def test_get_mappings():
    response = client.get("/v1/mappings")

    assert response.status_code == 200
    assert isinstance(response.json(), list)


def test_search_mapping_by_source_control_id():
    response = client.get(
        "/v1/mappings",
        params={"source_control_id": "AC-2"},
    )

    assert response.status_code == 200
    assert len(response.json()) >= 1
    assert response.json()[0]["source_control_id"] == "AC-2"


def test_search_mapping_invalid_control_id():
    response = client.get(
        "/v1/mappings",
        params={"source_control_id": "INVALID-999"},
    )

    assert response.status_code == 200
    assert response.json() == []


def test_validate_mappings():
    response = client.get("/v1/mappings/validate")

    assert response.status_code == 200
    assert response.json() == {
        "valid": True,
        "errors": [],
    }


def test_validate_mappings_response_structure():
    response = client.get("/v1/mappings/validate")

    assert response.status_code == 200

    data = response.json()

    assert "valid" in data
    assert "errors" in data
    assert isinstance(data["valid"], bool)
    assert isinstance(data["errors"], list)


def test_document_not_found_problem_details():
    response = client.get("/v1/documents/9999")

    assert response.status_code == 404

    assert response.headers["content-type"].startswith("application/problem+json")

    data = response.json()

    assert data["type"] == "about:blank"
    assert data["title"] == "Not Found"
    assert data["status"] == 404
    assert data["detail"] == "Document not found"
    assert data["instance"] == "/v1/documents/9999"
    assert "request_id" in data
