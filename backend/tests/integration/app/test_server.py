"""Tests of ``ytmirror.app.server``."""

import socket

import httpx2
import pytest
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import PlainTextResponse
from starlette.routing import Route

from ytmirror.app.server import BackgroundServer, bind_local_socket


async def _hello(_request: Request) -> PlainTextResponse:
    return PlainTextResponse("hello")


APP = Starlette(routes=[Route("/", _hello)])


def test_the_socket_listens_on_the_loopback_address_only() -> None:
    """R-PL-04: the local server listens on 127.0.0.1 only."""
    sock = bind_local_socket(None)

    try:
        address, port = sock.getsockname()
    finally:
        sock.close()

    assert address == "127.0.0.1"
    assert port > 0


def test_a_fixed_port_is_used_when_given() -> None:
    """R-PL-04: tests can choose the port (docs/ARCHITECTURE.md section 10)."""
    probe = bind_local_socket(None)
    free_port: int = probe.getsockname()[1]
    probe.close()

    sock = bind_local_socket(free_port)

    try:
        assert sock.getsockname()[1] == free_port
    finally:
        sock.close()


def test_the_server_answers_after_start_and_not_after_stop() -> None:
    """R-IN-02: the backend starts in a background thread and stops cleanly."""
    server = BackgroundServer(APP, bind_local_socket(None))

    server.start()
    try:
        response = httpx2.get(server.url + "/")
    finally:
        server.stop()

    assert response.status_code == 200
    assert response.text == "hello"
    assert server.url.startswith("http://127.0.0.1:")
    with pytest.raises(httpx2.TransportError):
        httpx2.get(server.url + "/", timeout=2)


def test_a_server_that_cannot_start_reports_it() -> None:
    """R-ER-03: a failed start is an error the app can report, not a silent hang."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind(("127.0.0.1", 0))
    server = BackgroundServer(APP, sock)
    port = sock.getsockname()[1]
    sock.close()

    with pytest.raises(RuntimeError, match="stopped while starting"):
        server.start()

    assert port > 0
