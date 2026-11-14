"""Names of folders on disk. File names of videos arrive in milestone M3.

Implements the folder name of R-FI-01: a channel folder is named after the
channel, with the substitutions of R-FN-02, in Unicode NFC (R-FN-03), and
short enough for macOS. Only characters that macOS cannot store or that
break Finder are substituted, each by a character that looks the same.

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


def _shortened(name: str, most_bytes: int) -> str:
    """Cut a name on a character boundary so that it fits into a number of bytes."""
    while len(name.encode()) > most_bytes:
        name = name[:-1]
    return name.rstrip(" ")
