"""Quality: which formats a download asks for.

Implements R-QL-01 to R-QL-04. A numeric quality means "the best quality not
above this height", and the lowest available when nothing is at or below
it. Video and audio are taken in the best codecs for that height and merged
into MKV without re-encoding: the selector only chooses streams, it never
converts them. The quality of a download is the channel's own when it has
one, else the default quality of the settings (R-QL-02).

This module must not know yt-dlp beyond the text of a format selector.

Tests: backend/tests/unit/core/test_quality.py
"""

from ytmirror.core.channels import Quality

BEST_SELECTOR = "bv*+ba/b"
"""The format selector of "Best available" (ARCHITECTURE section 7.3)."""


def format_selector(quality: Quality) -> str:
    """Return the yt-dlp format selector of a quality (R-QL-01, R-QL-04).

    Args:
        quality: The quality the download is for.

    Returns:
        The selector. For a height: the best video at or below it with the
        best audio, else the best single file at or below it, else the
        lowest video with the best audio, else the lowest single file.
    """
    if quality is Quality.BEST:
        return BEST_SELECTOR
    height = int(quality.value)
    return f"bv*[height<={height}]+ba/b[height<={height}]/wv*+ba/w"


def effective_quality(channel_quality: Quality | None, default_quality: Quality) -> Quality:
    """Return the quality a download of a channel is for (R-QL-02).

    Args:
        channel_quality: The channel's own quality, or None for "use the default".
        default_quality: The default quality of the settings.

    Returns:
        The channel's quality when it has one, else the default.
    """
    return channel_quality if channel_quality is not None else default_quality
