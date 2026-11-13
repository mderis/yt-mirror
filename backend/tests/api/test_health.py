"""Tests of ``GET /api/health``."""

from tests.api.conftest import Api


def test_health_reports_ok_with_the_app_and_schema_versions(api: Api) -> None:
    """R-PL-12: a started app answers on its health endpoint with its versions."""
    response = api.signed_in_client().get("/api/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "version": "1.2.3", "schema_version": "0002"}


def test_health_is_part_of_the_openapi_contract(api: Api) -> None:
    """infra: the frontend types are generated from the OpenAPI schema."""
    schema = api.app.openapi()

    operation = schema["paths"]["/api/health"]["get"]
    assert operation["operationId"] == "getHealth"
    assert set(operation["responses"]) >= {"200", "401", "403", "500"}
    assert set(schema["components"]["schemas"]) >= {
        "HealthResponse",
        "ErrorResponse",
        "ErrorBody",
    }


def test_the_schema_and_docs_pages_are_not_served(api: Api) -> None:
    """R-PL-11: the running app exposes nothing it does not need."""
    client = api.signed_in_client()

    for path in ("/openapi.json", "/docs", "/redoc"):
        assert client.get(path).status_code == 404, path
