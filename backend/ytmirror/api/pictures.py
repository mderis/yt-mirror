"""Answers a request with a cached picture.

Implements the serving half of R-CH-16 and the pictures of R-PL-11: the
interface gets thumbnails and avatars from the local server by ID, never by
a path, and never from YouTube directly. A picture that is not cached is
answered with ``NOT_FOUND`` at once (docs/DECISIONS.md D-067).

Tests: backend/tests/api/test_videos.py
"""

from starlette.responses import Response

from ytmirror.api.errors import error_response
from ytmirror.core.errors import ErrorCode

_KINDS = (
    (b"\x89PNG\r\n\x1a\n", "image/png"),
    (b"\xff\xd8\xff", "image/jpeg"),
    (b"GIF8", "image/gif"),
)
_WEBP_START, _WEBP_MARK = b"RIFF", b"WEBP"
_UNKNOWN = "application/octet-stream"
# A cached picture changes only when the interface asks with a new address.
_CACHE_FOR = "private, max-age=86400"


def content_type_of(picture: bytes) -> str:
    """Return the content type of a picture, read from its first bytes.

    Args:
        picture: The bytes of the picture.
    """
    for start, content_type in _KINDS:
        if picture.startswith(start):
            return content_type
    if picture.startswith(_WEBP_START) and picture[8:12] == _WEBP_MARK:
        return "image/webp"
    return _UNKNOWN


def picture_response(picture: bytes | None, what: str) -> Response:
    """Return the HTTP answer for a cached picture, or ``NOT_FOUND`` when there is none.

    Args:
        picture: The bytes of the picture, or None when it is not cached.
        what: What was asked for, for the technical details of the error.
    """
    if picture is None:
        return error_response(ErrorCode.NOT_FOUND, {"missing": what})
    return Response(
        picture,
        media_type=content_type_of(picture),
        headers={"Cache-Control": _CACHE_FOR, "X-Content-Type-Options": "nosniff"},
    )
