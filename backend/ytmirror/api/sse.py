"""The event stream: live updates for the window as Server-Sent Events.

Implements the transport of R-FB-03 (docs/ARCHITECTURE.md section 7.6).
There is one stream per window. Services publish on the event bus from any
thread. This module passes each event into the server's loop and writes it
to the stream. When the app stops, the bus says so and every stream ends,
so an open window never holds up the shutdown (R-PL-13).

The data of every event is named as the answer of the endpoint, so that
it is part of the API schema and the generated frontend types know it.
This module must not decide what is published.

Tests: backend/tests/api/test_events.py
"""

import asyncio
from collections.abc import AsyncIterator, Callable

from fastapi import APIRouter
from pydantic import BaseModel
from starlette.responses import StreamingResponse

from ytmirror.api.schemas import Tool, ToolUpdatedEvent
from ytmirror.core.models import AppEvent, ToolUpdated
from ytmirror.services.events import EventBus

KEEP_ALIVE_S = 15.0
"""A comment line is sent this often while nothing happens, so the connection stays open."""

TOOL_UPDATED = "tool.updated"


def encode(name: str, data: BaseModel) -> str:
    """Return one event in the wire format of Server-Sent Events.

    Args:
        name: The event name.
        data: Its data, sent as JSON.
    """
    return f"event: {name}\ndata: {data.model_dump_json()}\n\n"


def build_router(events: EventBus, setup_required: Callable[[], bool]) -> APIRouter:
    """Return the router for ``/events``.

    Args:
        events: The bus the services publish on.
        setup_required: Tells whether the first-run screen is still needed.

    Returns:
        The router, to be mounted under ``/api``.
    """
    router = APIRouter(tags=["events"])

    def wire_form(event: AppEvent) -> str:
        if isinstance(event, ToolUpdated):  # pyright: ignore[reportUnnecessaryIsInstance]  (later milestones add events)
            data = ToolUpdatedEvent(tool=Tool.of(event.report), setup_required=setup_required())
            return encode(TOOL_UPDATED, data)
        raise TypeError(f"No wire format for {type(event).__name__}")  # pragma: no cover

    async def stream() -> AsyncIterator[str]:
        loop = asyncio.get_running_loop()
        queue: asyncio.Queue[AppEvent | None] = asyncio.Queue()

        def pass_on(event: AppEvent | None) -> None:
            loop.call_soon_threadsafe(queue.put_nowait, event)

        leave = events.subscribe(pass_on)
        try:
            yield ": connected\n\n"
            while True:
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=KEEP_ALIVE_S)
                except TimeoutError:
                    yield ": keep-alive\n\n"
                    continue
                if event is None:
                    return
                yield wire_form(event)
        finally:
            leave()

    def get_events() -> StreamingResponse:
        """Open the event stream of this window."""
        return StreamingResponse(
            stream(), media_type="text/event-stream", headers={"Cache-Control": "no-cache"}
        )

    router.add_api_route(
        "/events",
        get_events,
        methods=["GET"],
        operation_id="getEvents",
        response_class=StreamingResponse,
        responses={
            200: {
                "model": ToolUpdatedEvent,
                "description": (
                    "A stream of Server-Sent Events. The event ``tool.updated`` carries this data."
                ),
            }
        },
    )
    return router
