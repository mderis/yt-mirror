"""Error codes and the error taxonomy of yt-mirror.

Every expected failure has a stable code from the table in docs/LOGGING.md
section 4. This module holds the codes that exist in the code base so far.
A milestone that introduces a new failure adds its code here and to that
table in the same commit.

This module must not format user-facing text. Text is written per code in
the frontend (R-ER-02).

Tests: backend/tests/unit/core/test_errors.py
"""

from enum import StrEnum


class ErrorKind(StrEnum):
    """Whether trying again can help."""

    PERMANENT = "permanent"
    TRANSIENT = "transient"


class ErrorCode(StrEnum):
    """Stable error codes. The value is what appears in logs and API responses."""

    UNAUTHORIZED = "UNAUTHORIZED"
    ORIGIN_REJECTED = "ORIGIN_REJECTED"
    NOT_FOUND = "NOT_FOUND"
    INVALID_REQUEST = "INVALID_REQUEST"
    LOCAL_SERVER_UNREACHABLE = "LOCAL_SERVER_UNREACHABLE"
    NETWORK_UNREACHABLE = "NETWORK_UNREACHABLE"
    RATE_LIMITED = "RATE_LIMITED"
    BOT_CHECK = "BOT_CHECK"
    YOUTUBE_CHANGED = "YOUTUBE_CHANGED"
    CHANNEL_NOT_FOUND = "CHANNEL_NOT_FOUND"
    INVALID_CHANNEL_INPUT = "INVALID_CHANNEL_INPUT"
    FOLDER_UNAVAILABLE = "FOLDER_UNAVAILABLE"
    PERMISSION_DENIED = "PERMISSION_DENIED"
    CHECKSUM_MISMATCH = "CHECKSUM_MISMATCH"
    DISK_FULL = "DISK_FULL"
    TOOL_MISSING = "TOOL_MISSING"
    INTERNAL = "INTERNAL"

    @property
    def kind(self) -> ErrorKind:
        """Return whether this failure is permanent or transient."""
        return _KINDS[self]

    @property
    def text_key(self) -> str:
        """Return the key of the user-facing text for this code."""
        return f"errors.{self.value.lower()}"


_KINDS: dict[ErrorCode, ErrorKind] = {
    ErrorCode.UNAUTHORIZED: ErrorKind.PERMANENT,
    ErrorCode.ORIGIN_REJECTED: ErrorKind.PERMANENT,
    ErrorCode.NOT_FOUND: ErrorKind.PERMANENT,
    ErrorCode.INVALID_REQUEST: ErrorKind.PERMANENT,
    # Raised by the window when it cannot reach this server (R-ER-04). The server never sends it.
    ErrorCode.LOCAL_SERVER_UNREACHABLE: ErrorKind.TRANSIENT,
    ErrorCode.NETWORK_UNREACHABLE: ErrorKind.TRANSIENT,
    ErrorCode.RATE_LIMITED: ErrorKind.TRANSIENT,
    ErrorCode.BOT_CHECK: ErrorKind.TRANSIENT,
    ErrorCode.YOUTUBE_CHANGED: ErrorKind.TRANSIENT,
    ErrorCode.CHANNEL_NOT_FOUND: ErrorKind.PERMANENT,
    ErrorCode.INVALID_CHANNEL_INPUT: ErrorKind.PERMANENT,
    ErrorCode.FOLDER_UNAVAILABLE: ErrorKind.TRANSIENT,
    ErrorCode.PERMISSION_DENIED: ErrorKind.PERMANENT,
    ErrorCode.CHECKSUM_MISMATCH: ErrorKind.TRANSIENT,
    ErrorCode.DISK_FULL: ErrorKind.TRANSIENT,
    ErrorCode.TOOL_MISSING: ErrorKind.TRANSIENT,
    ErrorCode.INTERNAL: ErrorKind.TRANSIENT,
}


class AppError(Exception):
    """An expected failure with an error code.

    Raise it where the failure is detected. The layer that handles it logs it
    once and maps the code to a response.

    Attributes:
        code: The error code.
        details: Extra facts for the technical details, safe to show and log.
    """

    def __init__(self, code: ErrorCode, details: dict[str, str] | None = None) -> None:
        """Create the error.

        Args:
            code: The error code.
            details: Extra facts for the technical details. Never secrets.
        """
        super().__init__(code.value)
        self.code = code
        self.details: dict[str, str] = dict(details) if details else {}
