"""A local HTTP server that answers like the YouTube API's ``videos.list``.

The real adapter is tested against it: what it sends (the key in a header,
never in the address), and how it reads answers and errors. Nothing here
reaches the network.
"""

import json
import threading
from collections.abc import Callable, Generator, Mapping
from contextlib import contextmanager
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import parse_qs, urlparse


@dataclass
class Asked:
    """One request the server received."""

    path: str
    query: dict[str, list[str]]
    headers: dict[str, str]


@dataclass
class ApiServer:
    """What the server answers, and what it was asked.

    Attributes:
        address: The address to give the adapter.
        items: The item of each video ID the API returns.
        answer: When set, answers every request with this status and body instead.
        asked: Every request, in order.
    """

    address: str = ""
    items: dict[str, Mapping[str, Any]] = field(default_factory=dict[str, Mapping[str, Any]])
    answer: tuple[int, Any] | None = None
    asked: list[Asked] = field(default_factory=list[Asked])


def premiere(video_id: str, uploaded: str, started: str | None) -> Mapping[str, Any]:
    """Return an item of a premiere, as the API gives it."""
    live: dict[str, str] = {"scheduledStartTime": uploaded}
    if started is not None:
        live["actualStartTime"] = started
    return {"id": video_id, "snippet": {"publishedAt": uploaded}, "liveStreamingDetails": live}


def regular(video_id: str, published: str) -> Mapping[str, Any]:
    """Return an item of a regular video, as the API gives it."""
    return {"id": video_id, "snippet": {"publishedAt": published}}


def error_body(reason: str, message: str = "") -> Mapping[str, Any]:
    """Return the body of an error of the API."""
    return {"error": {"code": 400, "message": message, "errors": [{"reason": reason}]}}


@contextmanager
def api_server(
    answers: Callable[[ApiServer, Asked], tuple[int, Any]] | None = None,
) -> Generator[ApiServer]:
    """Run the server on a free local port for the time of a test."""
    state = ApiServer()

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            url = urlparse(self.path)
            asked = Asked(
                url.path, parse_qs(url.query), {k.lower(): v for k, v in self.headers.items()}
            )
            state.asked.append(asked)
            if state.answer is not None:
                status, body = state.answer
            elif answers is not None:
                status, body = answers(state, asked)
            else:
                ids = asked.query.get("id", [""])[0].split(",")
                status, body = 200, {"items": [state.items[i] for i in ids if i in state.items]}
            data = json.dumps(body).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def log_message(self, format: str, *args: Any) -> None:
            """Keep the test output quiet."""

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    state.address = f"http://127.0.0.1:{server.server_address[1]}/youtube/v3"
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield state
    finally:
        server.shutdown()
        server.server_close()
