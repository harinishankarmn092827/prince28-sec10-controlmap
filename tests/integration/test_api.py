"""API tests for ControlMap."""


def test_health_check(test_client):
    response = test_client.get("/health")

    assert response.status_code == 200

    data = response.json()

    assert data["status"] == "healthy"
    assert "version" in data
    assert "commit" in data


def test_readiness_check(test_client):
    response = test_client.get("/ready")

    assert response.status_code == 200
    assert response.json() == {"status": "ready"}


def test_get_mappings(test_client):
    response = test_client.get("/v1/mappings")

    assert response.status_code == 200
    assert isinstance(response.json(), list)


def test_search_mapping_by_source_control_id(test_client):
    response = test_client.get(
        "/v1/mappings",
        params={"source_control_id": "AC-2"},
    )

    assert response.status_code == 200
    assert len(response.json()) >= 1
    assert response.json()[0]["source_control_id"] == "AC-2"


def test_search_mapping_invalid_control_id(test_client):
    response = test_client.get(
        "/v1/mappings",
        params={"source_control_id": "INVALID-999"},
    )

    assert response.status_code == 200
    assert response.json() == []


def test_validate_mappings(test_client):
    response = test_client.get("/v1/mappings/validate")

    assert response.status_code == 200
    assert response.json() == {
        "valid": True,
        "errors": [],
    }


def test_validate_mappings_response_structure(test_client):
    response = test_client.get("/v1/mappings/validate")

    assert response.status_code == 200

    data = response.json()

    assert "valid" in data
    assert "errors" in data
    assert isinstance(data["valid"], bool)
    assert isinstance(data["errors"], list)


def test_document_not_found_problem_details(test_client):
    response = test_client.get("/v1/documents/9999")

    assert response.status_code == 404
    assert response.headers["content-type"].startswith("application/problem+json")

    data = response.json()

    assert data["type"] == "about:blank"
    assert data["title"] == "Not Found"
    assert data["status"] == 404
    assert data["detail"] == "Document not found"
    assert data["instance"] == "/v1/documents/9999"
    assert "request_id" in data


def test_get_all_documents_from_database(test_client):
    response = test_client.get("/v1/documents")

    assert response.status_code == 200

    data = response.json()

    assert isinstance(data, list)
    assert len(data) == 20
    assert data[0]["framework"] == "NIST CSF 2.0"


def test_search_document_by_control_id(test_client):
    response = test_client.get(
        "/v1/documents",
        params={"query": "AC-2"},
    )

    assert response.status_code == 200

    data = response.json()

    assert len(data) == 1
    assert data[0]["control_id"] == "AC-2"


def test_filter_documents_by_framework(test_client):
    response = test_client.get(
        "/v1/documents",
        params={"framework": "NIST CSF 2.0"},
    )

    assert response.status_code == 200

    data = response.json()

    assert len(data) == 6

    assert all(document["framework"] == "NIST CSF 2.0" for document in data)


def test_filter_documents_by_category(test_client):
    response = test_client.get(
        "/v1/documents",
        params={"applies_to_category": "Mid-size"},
    )

    assert response.status_code == 200

    data = response.json()

    assert len(data) == 2

    assert all(document["applies_to_category"] == "Mid-size" for document in data)


def test_filter_documents_by_function_or_family(test_client):
    response = test_client.get(
        "/v1/documents",
        params={"function_or_family": "Govern"},
    )

    assert response.status_code == 200

    data = response.json()

    assert len(data) == 1
    assert data[0]["function_or_family"] == "Govern"
    assert data[0]["control_id"] == "GV.OC-01"


def test_get_document_by_id(test_client):
    response = test_client.get("/v1/documents/7")

    assert response.status_code == 200

    data = response.json()

    assert data["id"] == 7
    assert data["control_id"] == "AC-2"
    assert data["title"] == "Account Management"
