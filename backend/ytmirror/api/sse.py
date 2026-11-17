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

from ytmirror.api.catalogue_schemas import (
    ApiKey,
    ApiKeyChangedEvent,
    BannerChangedEvent,
    Channel,
    ChannelUpdatedEvent,
    Download,
    JobProgressEvent,
    Pause,
    Progress,
    TaskProgressEvent,
    Video,
    VideoUpdatedEvent,
)
from ytmirror.api.schemas import Tool, ToolUpdatedEvent
from ytmirror.core.channels import ChannelUpdated, TaskProgressed
from ytmirror.core.exact_dates import KeyStateChanged
from ytmirror.core.jobs import JobProgressed, VideoUpdated
from ytmirror.core.models import AppEvent, ToolUpdated
from ytmirror.services.events import EventBus

KEEP_ALIVE_S = 15.0
"""A comment line is sent this often while nothing happens, so the connection stays open."""

TOOL_UPDATED = "tool.updated"
CHANNEL_UPDATED = "channel.updated"
TASK_PROGRESS = "task.progress"
VIDEO_UPDATED = "video.updated"
JOB_PROGRESS = "job.progress"
BANNER_CHANGED = "banner.changed"
API_KEY_CHANGED = "apikey.changed"

type EventData = (
    ToolUpdatedEvent
    | ChannelUpdatedEvent
    | TaskProgressEvent
    | BannerChangedEvent
    | VideoUpdatedEvent
    | JobProgressEvent
    | ApiKeyChangedEvent
)
"""The data of every event of the stream. It is named as the answer of the endpoint,
so that the generated frontend types know all of them."""


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
        if isinstance(event, ToolUpdated):
            data = ToolUpdatedEvent(tool=Tool.of(event.report), setup_required=setup_required())
            return encode(TOOL_UPDATED, data)
        if isinstance(event, ChannelUpdated):
            return encode(CHANNEL_UPDATED, ChannelUpdatedEvent(channel=Channel.of(event.view)))
        if isinstance(event, TaskProgressed):
            return encode(TASK_PROGRESS, TaskProgressEvent(progress=Progress.of(event.progress)))
        if isinstance(event, VideoUpdated):
            data = VideoUpdatedEvent(
                channel_id=event.view.video.channel_id, video=Video.of(event.view)
            )
            return encode(VIDEO_UPDATED, data)
        if isinstance(event, JobProgressed):
            return encode(JOB_PROGRESS, JobProgressEvent(download=Download.of(event.progress)))
        if isinstance(event, KeyStateChanged):
            return encode(API_KEY_CHANGED, ApiKeyChangedEvent(api_key=ApiKey.of(event.key)))
        return encode(BANNER_CHANGED, BannerChangedEvent(youtube_pause=Pause.of(event.pause)))

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
                "model": EventData,
                "description": (
                    "A stream of Server-Sent Events. The events ``tool.updated``, "
                    "``channel.updated``, ``task.progress``, ``banner.changed``, "
                    "``video.updated``, ``job.progress`` and ``apikey.changed`` carry "
                    "these data, in this order."
                ),
            }
        },
    )
    return router
