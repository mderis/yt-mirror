"""Tests of ``ytmirror.api.request_log``."""

from collections.abc import AsyncIterator

import pytest
from starlette.applications import Starlette
from starlette.middleware import Middleware
from starlette.requests import Request
from starlette.responses import PlainTextResponse, StreamingResponse
from starlette.routing import Route
from starlette.testclient import TestClient
from structlog.testing import capture_logs

from tests.api.conftest import Api
from tests.fixtures.fakes.clock import FakeClock
from ytmirror.api.request_log import RequestLogMiddleware


@pytest.fixture
def client(clock: FakeClock) -> TestClient:
    """A small app behind the middleware, with routes that work, crash and crash late."""

    async def fine(_request: Request) -> PlainTextResponse:
        clock.advance(0.042)
        return PlainTextResponse("fine")

    async def crash(_request: Request) -> PlainTextResponse:
        raise RuntimeError("the secret reason")

    async def crash_while_streaming(_request: Request) -> StreamingResponse:
        async def body() -> AsyncIterator[bytes]:
            yield b"first part"
            raise RuntimeError("broke after the start")

        return StreamingResponse(body())

    app = Starlette(
        routes=[
            Route("/fine", fine),
            Route("/crash", crash),
            Route("/crash-late", crash_while_streaming),
        ],
        # Added the way the real app adds it, so it sits inside Starlette's own error handling.
        middleware=[Middleware(RequestLogMiddleware, clock=clock)],
    )
    return TestClient(app)


def test_every_request_is_logged_at_debug_with_status_and_duration(client: TestClient) -> None:
    """R-LG-01: ``api.request`` records method, path, status and duration."""
    with capture_logs() as logs:
        client.get("/fine?token=not-logged")

    (line,) = logs
    assert line == {
        "event": "api.request",
        "log_level": "debug",
        "msg": "Request handled",
        "method": "GET",
        "path": "/fine",
        "status": 200,
        "duration_ms": 42,
    }


def test_an_unhandled_error_becomes_the_internal_error(client: TestClient) -> None:
    """R-ER-02: an unexpected exception reaches the client as INTERNAL, never as raw text."""
    response = client.get("/crash")

    assert response.status_code == 500
    assert response.json()["error"]["code"] == "INTERNAL"
    assert "the secret reason" not in response.text


def test_an_unhandled_error_is_logged_once_with_its_stack_trace(client: TestClient) -> None:
    """R-LG-01: INTERNAL is always logged at error level with a stack trace (rule 6)."""
    with capture_logs() as logs:
        client.get("/crash")

    errors = [line for line in logs if line["event"] == "api.error"]
    assert len(errors) == 1
    assert errors[0]["log_level"] == "error"
    assert errors[0]["error_code"] == "INTERNAL"
    assert errors[0]["path"] == "/crash"
    assert errors[0]["exc_info"] is True
    assert [line["status"] for line in logs if line["event"] == "api.request"] == [500]


def test_an_error_after_the_response_started_is_logged_without_a_second_answer(
    client: TestClient,
) -> None:
    """R-LG-01: a crash in the middle of a response is still logged, and nothing more is sent."""
    with capture_logs() as logs:
        response = client.get("/crash-late")

    assert response.status_code == 200
    assert response.text == "first part"
    assert [line["error_code"] for line in logs if line["event"] == "api.error"] == ["INTERNAL"]


def test_requests_through_the_real_app_are_logged_even_when_rejected(api: Api) -> None:
    """R-LG-01: the request log wraps the security checks, so rejections are counted too."""
    with capture_logs() as logs:
        api.client().get("/api/health")

    assert [line["status"] for line in logs if line["event"] == "api.request"] == [401]
