"""Reads what the user pasted to add a channel.

Implements R-CH-01 and R-CH-02: a channel address in one of its four forms,
with or without a tab, a bare ``@handle`` or a bare channel ID is accepted.
A video, a playlist or anything else is refused, with the reason, so the
interface can say what is accepted. Nothing is asked of YouTube here.

Tests: backend/tests/unit/core/test_channel_input.py
"""

import re
from enum import StrEnum
from urllib.parse import unquote, urlsplit

from ytmirror.core.channels import ChannelReference, ReferenceKind
from ytmirror.core.errors import AppError, ErrorCode


class RejectedInput(StrEnum):
    """Why the pasted text is not a channel (R-CH-02)."""

    EMPTY = "empty"
    VIDEO = "video"
    PLAYLIST = "playlist"
    OTHER = "other"


_YOUTUBE_HOSTS = frozenset({"youtube.com", "www.youtube.com", "m.youtube.com"})
_SHORT_VIDEO_HOST = "youtu.be"
_VIDEO_PATHS = frozenset({"watch", "shorts", "live", "embed", "v", "clip"})
_CHANNEL_ID = re.compile(r"UC[A-Za-z0-9_-]{22}")
_HANDLE = re.compile(r"@[^\s/@?#]+")
_NAME = re.compile(r"[^\s/?#]+")
_BARE_ADDRESS = re.compile(r"(?:www\.|m\.)?(?:youtube\.com|youtu\.be)(?:[/?#]|$)", re.IGNORECASE)


def parse_channel_input(text: str) -> ChannelReference:
    """Return the channel the user named.

    Args:
        text: What the user pasted or typed.

    Returns:
        The channel as named, to be looked up.

    Raises:
        AppError: ``INVALID_CHANNEL_INPUT`` when the text names no channel. Its
            detail ``reason`` is one of the values of ``RejectedInput``.
    """
    cleaned = text.strip()
    if not cleaned:
        raise _rejected(RejectedInput.EMPTY)
    if _HANDLE.fullmatch(cleaned):
        return ChannelReference(ReferenceKind.HANDLE, cleaned)
    if _CHANNEL_ID.fullmatch(cleaned):
        return ChannelReference(ReferenceKind.CHANNEL_ID, cleaned)
    if _BARE_ADDRESS.match(cleaned):
        cleaned = f"https://{cleaned}"
    parts = urlsplit(cleaned)
    host = (parts.hostname or "").lower()
    if parts.scheme not in ("http", "https"):
        raise _rejected(RejectedInput.OTHER)
    if host == _SHORT_VIDEO_HOST:
        raise _rejected(RejectedInput.VIDEO)
    if host not in _YOUTUBE_HOSTS:
        raise _rejected(RejectedInput.OTHER)
    return _from_path(parts.path)


def _from_path(path: str) -> ChannelReference:
    segments = [unquote(segment) for segment in path.split("/") if segment]
    if not segments:
        raise _rejected(RejectedInput.OTHER)
    first = segments[0]
    if first in _VIDEO_PATHS:
        raise _rejected(RejectedInput.VIDEO)
    if first == "playlist":
        raise _rejected(RejectedInput.PLAYLIST)
    if _HANDLE.fullmatch(first):
        return _with_optional_tab(ReferenceKind.HANDLE, first, segments[1:])
    if len(segments) >= 2:
        reference = _named(first, segments[1])
        if reference is not None:
            return _with_optional_tab(reference.kind, reference.value, segments[2:])
    raise _rejected(RejectedInput.OTHER)


def _named(prefix: str, name: str) -> ChannelReference | None:
    if prefix == "channel" and _CHANNEL_ID.fullmatch(name):
        return ChannelReference(ReferenceKind.CHANNEL_ID, name)
    if prefix == "c" and _NAME.fullmatch(name):
        return ChannelReference(ReferenceKind.CUSTOM_NAME, name)
    if prefix == "user" and _NAME.fullmatch(name):
        return ChannelReference(ReferenceKind.USER_NAME, name)
    return None


def _with_optional_tab(kind: ReferenceKind, value: str, rest: list[str]) -> ChannelReference:
    """Accept at most one more path segment: a tab such as ``videos`` (R-CH-01)."""
    if len(rest) > 1:
        raise _rejected(RejectedInput.OTHER)
    return ChannelReference(kind, value)


def _rejected(reason: RejectedInput) -> AppError:
    return AppError(ErrorCode.INVALID_CHANNEL_INPUT, {"reason": reason.value})
