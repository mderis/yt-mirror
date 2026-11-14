"""Tests of ``ytmirror.api.errors``: one error shape for every failure."""

import json

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from starlette.exceptions import HTTPException
from starlette.responses import JSONResponse
from structlog.testing import capture_logs

from tests.api.conftest import Api
from ytmirror.api.errors import error_response, install_error_handlers
from ytmirror.core.errors import AppError, ErrorCode

EXPECTED_STATUS = {
    ErrorCode.UNAUTHORIZED: 401,
    ErrorCode.ORIGIN_REJECTED: 403,
    ErrorCode.NOT_FOUND: 404,
    ErrorCode.INVALID_REQUEST: 422,
    ErrorCode.LOCAL_SERVER_UNREACHABLE: 503,
    ErrorCode.NETWORK_UNREACHABLE: 502,
    ErrorCode.RATE_LIMITED: 503,
    ErrorCode.BOT_CHECK: 503,
    ErrorCode.YOUTUBE_CHANGED: 502,
    ErrorCode.CHANNEL_NOT_FOUND: 404,
    ErrorCode.INVALID_CHANNEL_INPUT: 422,
    ErrorCode.FOLDER_UNAVAILABLE: 503,
    ErrorCode.PERMISSION_DENIED: 403,
    ErrorCode.CHECKSUM_MISMATCH: 502,
    ErrorCode.DISK_FULL: 507,
    ErrorCode.TOOL_MISSING: 503,
    ErrorCode.INTERNAL: 500,
}


def body_of(code: ErrorCode, details: dict[str, str] | None = None) -> dict[str, object]:
    """Return the parsed body of the response for a code."""
    parsed: dict[str, object] = json.loads(bytes(error_response(code, details).body))
    return parsed


def response_message(response: JSONResponse) -> str:
    """Return the message text of an error response."""
    parsed: dict[str, dict[str, str]] = json.loads(bytes(response.body))
    return parsed["error"]["message"]


@pytest.fixture
def client() -> TestClient:
    """A small app with routes that fail in each handled way."""
    app = FastAPI()
    install_error_handlers(app)

    def raise_app_error() -> None:
        raise AppError(ErrorCode.NOT_FOUND, {"what": "channel"})

    def raise_teapot() -> None:
        raise HTTPException(status_code=418)

    def raise_bad_gateway() -> None:
        raise HTTPException(status_code=502)

    def needs_number(count: int) -> int:
        return count

    app.add_api_route("/app-error", raise_app_error)
    app.add_api_route("/teapot", raise_teapot)
    app.add_api_route("/bad-gateway", raise_bad_gateway)
    app.add_api_route("/number", needs_number)
    return TestClient(app)


@pytest.mark.parametrize("code", list(ErrorCode))
def test_every_error_code_maps_to_a_status_and_the_one_shape(code: ErrorCode) -> None:
    """R-ER-02: every error has a stable code and a text written for that code."""
    response = error_response(code)
    body = body_of(code)

    assert response.status_code == EXPECTED_STATUS[code]
    assert set(body) == {"error"}
    assert body == {
        "error": {"code": code.value, "message": response_message(response), "details": {}}
    }
    assert response_message(response)


def test_details_are_passed_through() -> None:
    """R-ER-02: technical details travel with the error."""
    assert body_of(ErrorCode.NOT_FOUND, {"what": "channel"})["error"] == {
        "code": "NOT_FOUND",
        "message": "There is nothing at this address.",
        "details": {"what": "channel"},
    }


def test_an_app_error_raised_in_a_route_becomes_its_code(client: TestClient) -> None:
    """R-ER-02: an expected failure reaches the client as its code, not as an exception text."""
    with capture_logs() as logs:
        response = client.get("/app-error")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "NOT_FOUND"
    assert response.json()["error"]["details"] == {"what": "channel"}
    assert [(line["event"], line["error_code"]) for line in logs] == [("api.error", "NOT_FOUND")]


def test_an_unknown_path_is_not_found_in_the_one_shape(api: Api) -> None:
    """R-ER-02: even a wrong address answers in the error shape."""
    client = api.signed_in_client()

    for path in ("/api/no-such-endpoint", "/no-such-file.js"):
        response = client.get(path)

        assert response.status_code == 404, path
        assert response.json()["error"]["code"] == "NOT_FOUND", path


def test_a_wrong_method_keeps_its_status_and_is_an_invalid_request(api: Api) -> None:
    """R-ER-02: other client errors keep their HTTP status and use INVALID_REQUEST."""
    response = api.signed_in_client().post("/api/health")

    assert response.status_code == 405
    assert response.json()["error"]["code"] == "INVALID_REQUEST"


def test_other_client_errors_are_invalid_requests(client: TestClient) -> None:
    """R-ER-02: a client error without its own code is an INVALID_REQUEST."""
    response = client.get("/teapot")

    assert response.status_code == 418
    assert response.json()["error"]["code"] == "INVALID_REQUEST"


def test_server_side_http_errors_are_internal(client: TestClient) -> None:
    """R-ER-02: a server error without its own code is INTERNAL."""
    response = client.get("/bad-gateway")

    assert response.status_code == 502
    assert response.json()["error"]["code"] == "INTERNAL"


def test_a_request_that_fails_validation_names_the_fields(client: TestClient) -> None:
    """R-ER-02: a malformed request is an INVALID_REQUEST that says which field is wrong."""
    response = client.get("/number", params={"count": "many"})

    assert response.status_code == 422
    assert response.json()["error"] == {
        "code": "INVALID_REQUEST",
        "message": "The request is not valid.",
        "details": {"fields": "query.count"},
    }
