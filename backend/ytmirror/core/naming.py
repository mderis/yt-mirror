"""Names of folders and video files on disk.

Implements the folder name of R-FI-01 and the file name of R-FN-01 to
R-FN-05: a channel folder is named after the channel and a video file after
its title, with the substitutions of R-FN-02, in Unicode NFC (R-FN-03), and
short enough for macOS (R-FN-04). Only characters that macOS cannot store or
that break Finder are substituted, each by a character that looks the same.
A name never tells which video a file belongs to: files are tracked by video
ID (R-FN-07).

This module must not look at the disk: names that are taken are passed in.

Tests: backend/tests/unit/core/test_naming.py
"""

import unicodedata
from collections.abc import Collection

MAX_NAME_BYTES = 255
"""The longest name macOS stores, in bytes of UTF-8."""

# The lookalikes of R-FN-02: BIG SOLIDUS (U+29F8) for the slash and
# FULLWIDTH COLON (U+FF1A) for the colon.
_SUBSTITUTES = {"/": "\u29f8", ":": "\uff1a"}
_HIDDEN_PREFIX = "."
HIDDEN_DIR = ".yt-mirror"
"""The hidden folder inside a channel folder: metadata, thumbnails and temp files (R-FI-02)."""
TEMP_DIR = "tmp"
"""The folder of the temp folders of jobs, inside the hidden folder (R-FI-03)."""
VIDEO_EXTENSION = ".mkv"
"""The extension of every video file: the container is always MKV (R-QL-03)."""
_KEPT_VISIBLE = "_"


def safe_name(text: str) -> str:
    """Return a text as a name that macOS can store, as close to the text as possible.

    Implements the substitutions of R-FN-02 and the form of R-FN-03.

    Args:
        text: A title or a channel name, exactly as YouTube gives it.

    Returns:
        The name. It can be empty when the text has nothing that can be stored.
    """
    kept = "".join(
        _SUBSTITUTES.get(character, character)
        for character in unicodedata.normalize("NFC", text)
        if unicodedata.category(character) != "Cc"
    ).strip(" ")
    if kept.startswith(_HIDDEN_PREFIX):
        kept = _KEPT_VISIBLE + kept
    return kept


def channel_folder_name(title: str, channel_id: str, taken: Collection[str]) -> str:
    """Return the name of the folder of a channel inside the library (R-FI-01).

    Args:
        title: The name of the channel.
        channel_id: The channel ID. It is the name when the title leaves nothing,
            and the suffix when the name is taken.
        taken: Folder names in the library that belong to other channels,
            compared without regard to case.

    Returns:
        The folder name, at most 255 bytes long.
    """
    suffix = f" [{channel_id}]"
    name = _shortened(safe_name(title), MAX_NAME_BYTES - len(suffix.encode()))
    if not name:
        return channel_id
    if name.casefold() in {other.casefold() for other in taken}:
        return name + suffix
    return name


def video_file_name(title: str, video_id: str, taken: Collection[str]) -> str:
    """Return the name of the file of a video inside its channel folder (R-FN-01).

    The name is the title plus ``.mkv``, with the substitutions of R-FN-02.
    ``" [<video id>]"`` is appended when the name would be longer than 255
    bytes, after the title is shortened (R-FN-04), and when the name is
    taken, compared without regard to case (R-FN-05). A title that leaves
    nothing, or only dots and spaces (".", ".."), becomes the video ID
    (R-FN-01). A title that starts with a dot keeps its words and gets a
    preceding "_", so the file is never hidden (R-FN-02).

    Args:
        title: The title of the video, exactly as YouTube gives it.
        video_id: The video ID.
        taken: File names in the channel folder that belong to other videos
            or to no known video. A file of no known video is never
            overwritten, so its name counts as taken.

    Returns:
        The file name, at most 255 bytes long, ending in ``.mkv``.
    """
    suffix = f" [{video_id}]"
    title_part = safe_name(title)
    # Dots and spaces alone leave no name. Asked of the title before a leading dot gets its "_".
    printable = "".join(
        character
        for character in unicodedata.normalize("NFC", title)
        if unicodedata.category(character) != "Cc"
    )
    if not printable.strip(_HIDDEN_PREFIX + " "):
        title_part = video_id
    whole = title_part + VIDEO_EXTENSION
    taken_names = {other.casefold() for other in taken}
    if len(whole.encode()) <= MAX_NAME_BYTES and whole.casefold() not in taken_names:
        return whole
    room = MAX_NAME_BYTES - len((suffix + VIDEO_EXTENSION).encode())
    return _shortened(title_part, room) + suffix + VIDEO_EXTENSION


def _shortened(name: str, most_bytes: int) -> str:
    """Cut a name on a character boundary so that it fits into a number of bytes."""
    while len(name.encode()) > most_bytes:
        name = name[:-1]
    return name.rstrip(" ")
