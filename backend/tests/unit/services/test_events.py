"""Tests of ``ytmirror.services.events``."""

from ytmirror.core.models import AppEvent, ToolName, ToolReport, ToolStatus, ToolUpdated
from ytmirror.services.events import EventBus

EVENT = ToolUpdated(ToolReport(ToolName.DENO, ToolStatus.OK))
OTHER = ToolUpdated(ToolReport(ToolName.FFMPEG, ToolStatus.MISSING))


def test_every_listener_gets_every_event_in_order() -> None:
    """R-FB-03: a change reaches the interface without a manual refresh."""
    bus = EventBus()
    first: list[AppEvent | None] = []
    second: list[AppEvent | None] = []
    bus.subscribe(first.append)
    bus.subscribe(second.append)

    bus.publish(EVENT)
    bus.publish(OTHER)

    assert first == [EVENT, OTHER]
    assert second == [EVENT, OTHER]


def test_a_listener_that_left_gets_nothing_more() -> None:
    """R-FB-03: a closed window costs nothing: it is no longer told about changes."""
    bus = EventBus()
    seen: list[AppEvent | None] = []
    leave = bus.subscribe(seen.append)

    bus.publish(EVENT)
    leave()
    leave()
    bus.publish(OTHER)

    assert seen == [EVENT]


def test_closing_the_bus_tells_every_listener_once_and_ends_the_events() -> None:
    """R-PL-13: when the app stops, open event streams end instead of holding it up."""
    bus = EventBus()
    seen: list[AppEvent | None] = []
    bus.subscribe(seen.append)

    bus.close()
    bus.close()
    bus.publish(EVENT)

    assert seen == [None]


def test_a_listener_that_arrives_after_the_end_is_told_at_once() -> None:
    """R-PL-13: a stream opened while the app stops ends at once."""
    bus = EventBus()
    bus.close()
    seen: list[AppEvent | None] = []

    leave = bus.subscribe(seen.append)
    leave()

    assert seen == [None]
