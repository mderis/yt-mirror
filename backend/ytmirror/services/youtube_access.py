"""Everything the app asks of YouTube goes through here.

Implements R-ER-05 (docs/DECISIONS.md D-071). YouTube sometimes refuses
requests with its "not a bot" check, which depends on the network address
and not on the channel or the video. This module remembers that for the
whole app: what the app would ask by itself waits, first 15 minutes and
then twice as long each time. What the user starts by hand is still tried,
and the pause ends as soon as YouTube answers the kind of request it had
refused. An answer to another kind of request proves nothing: YouTube can
refuse lookups from an address and still answer listings.

This module must not know what a request is for, only whether the user
started it.

Tests: backend/tests/unit/services/test_youtube_access.py
"""

import threading
from collections.abc import Callable, Iterator

import structlog
from structlog.typing import FilteringBoundLogger

from ytmirror.core.channels import (
    ChannelFacts,
    ChannelListing,
    ChannelReference,
    ListedVideo,
    YouTubePause,
    YouTubePauseChanged,
)
from ytmirror.core.errors import AppError, ErrorCode
from ytmirror.core.pauses import next_pause_s
from ytmirror.ports.clock import Clock
from ytmirror.ports.youtube_gateway import YouTubeGateway
from ytmirror.services.events import EventBus

_log: FilteringBoundLogger = structlog.get_logger(__name__)

type CallLater = Callable[[float, Callable[[], None]], None]
"""Runs something after a number of seconds, without blocking the caller."""


class YouTubeAccess:
    """Asks YouTube, and pauses the whole app when YouTube refuses it."""

    def __init__(
        self, gateway: YouTubeGateway, clock: Clock, events: EventBus, call_later: CallLater
    ) -> None:
        """Create the access.

        Args:
            gateway: The gateway to YouTube.
            clock: The source of time.
            events: Where a change of the pause is published.
            call_later: Runs the end of a pause when its time has come.
        """
        self._gateway = gateway
        self._clock = clock
        self._events = events
        self._call_later = call_later
        self._lock = threading.Lock()
        self._pause: YouTubePause | None = None
        self._last_pause_s: int | None = None
        self._refused: str | None = None
        self._on_resume: list[Callable[[], None]] = []

    def pause(self) -> YouTubePause | None:
        """Return the pause that is in force, or None."""
        with self._lock:
            return self._pause

    def when_asking_again(self, work: Callable[[], None]) -> None:
        """Register work that the app does by itself and that a pause holds up.

        It runs when a pause ends: when its time has come, when YouTube
        answered something else, or when the user says "Try now".

        Args:
            work: What to do. It must come back quickly.
        """
        self._on_resume.append(work)

    def try_now(self) -> None:
        """End the pause because the user asked for it, and take up the work that waited."""
        self._end_pause("the user asked to try now")

    def lookup_channel(self, reference: ChannelReference) -> ChannelFacts:
        """Look a channel up for the user. A pause does not hold this up.

        Args:
            reference: The channel as the user named it.

        Raises:
            AppError: As the gateway raises it.
        """
        return self._ask("lookup", lambda: self._gateway.lookup_channel(reference), by_user=True)

    def preview_video_count(self, channel_id: str) -> int:
        """Ask for the video count of a preview for the user.

        Args:
            channel_id: The channel ID.

        Raises:
            AppError: As the gateway raises it.
        """
        return self._ask(
            "count", lambda: self._gateway.preview_video_count(channel_id), by_user=True
        )

    def list_channel(self, channel_id: str, *, by_user: bool) -> ChannelListing:
        """Start a listing of a channel.

        Args:
            channel_id: The channel ID.
            by_user: Whether the user started the check. Otherwise a pause holds it up.

        Raises:
            AppError: ``BOT_CHECK`` without asking YouTube while the app pauses, or as
                the gateway raises it, here or while the videos are read.
        """
        listing = self._ask(
            "listing", lambda: self._gateway.list_channel(channel_id), by_user=by_user
        )
        return ChannelListing(listing.facts, self._watched(listing.videos))

    def fetch_image(self, url: str, *, by_user: bool = False) -> bytes:
        """Fetch a picture. Unless the user waits for it, a pause holds it up.

        Args:
            url: The address of the picture.
            by_user: Whether the user waits for this picture, as for the avatar of a preview.

        Raises:
            AppError: ``BOT_CHECK`` without asking while the app pauses, or as the
                gateway raises it.
        """
        return self._ask("image", lambda: self._gateway.fetch_image(url), by_user=by_user)

    def _ask[T](self, request: str, ask: Callable[[], T], *, by_user: bool) -> T:
        pause = self.pause()
        if pause is not None and not by_user:
            raise AppError(ErrorCode.BOT_CHECK, {"paused_until": str(pause.until)})
        try:
            answer = ask()
        except AppError as error:
            self._note_failure(request, error)
            raise
        self._note_answer(request)
        return answer

    def _watched(self, videos: Iterator[ListedVideo]) -> Iterator[ListedVideo]:
        """Hand the videos of a listing on, and see whether YouTube refuses part of the way."""
        try:
            yield from videos
        except AppError as error:
            self._note_failure("listing", error)
            raise

    def _note_failure(self, request: str, error: AppError) -> None:
        if error.code is not ErrorCode.BOT_CHECK:
            return
        with self._lock:
            length = next_pause_s(self._last_pause_s)
            self._last_pause_s = length
            self._refused = request
            self._pause = YouTubePause(
                ErrorCode.BOT_CHECK, int(self._clock.now().timestamp()) + length
            )
            pause = self._pause
        _log.warning(
            "youtube.paused",
            msg="YouTube asked to confirm that the app is not a bot. The app pauses",
            error_code=ErrorCode.BOT_CHECK.value,
            request=request,
            pause_s=length,
            until=pause.until,
        )
        self._events.publish(YouTubePauseChanged(pause))
        self._call_later(length, lambda: self._pause_is_over(pause))

    def _note_answer(self, request: str) -> None:
        """End the pause when YouTube answered the kind of request it had refused."""
        with self._lock:
            if self._refused != request:
                return
            self._last_pause_s = None
        self._end_pause("YouTube answered")

    def _pause_is_over(self, pause: YouTubePause) -> None:
        """End a pause when its time has come, unless a newer one took its place."""
        if self.pause() == pause:
            self._end_pause("the time of the pause is over")

    def _end_pause(self, reason: str) -> None:
        with self._lock:
            if self._pause is None:
                return
            self._pause = None
            self._refused = None
        _log.info("youtube.resumed", msg="The app asks YouTube again", reason=reason)
        self._events.publish(YouTubePauseChanged(None))
        for work in list(self._on_resume):
            work()
