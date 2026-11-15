"""The channel file: which channels a folder belongs to (R-FI-05).

``<channel folder>/.yt-mirror/channel.json`` lists the channels whose folder
it is, so that a folder can later be linked to its channels again: when it is
adopted or when the database is lost (milestone M8 reads it). Two channels
can share a folder, so it holds a list:
``{"version": 1, "channels": [{"id", "handle", "title"}, ...]}``. Adding a
channel to a folder adds its entry, removing it removes the entry, and the
file goes when the list is empty. It never holds a path or the API key. In a
shared folder, M8 matches each video file to its channel by the video ID
inside the file, not by the folder.

This module must not read or write files: the content is passed in and out.

Tests: backend/tests/unit/core/test_channel_file.py
"""

import json
from typing import cast

from ytmirror.core.channels import Channel

CHANNEL_FILE = "channel.json"
"""The name of the channel file in the hidden folder."""

FORMAT_VERSION = 1
"""The version of the content. It grows when the content changes in a way older readers miss."""


def channel_entries(content: bytes | None) -> list[dict[str, str | None]] | None:
    """Return the entries of a channel file: none when there is no file.

    Returns None when the file cannot be understood: it is not JSON, it has
    another shape, it comes from a newer version of the app, or an entry has
    no ID. Such a file is never replaced or removed: it may hold what this
    version cannot see.

    Args:
        content: The bytes of the file, or None when there is no file.
    """
    if content is None:
        return []
    try:
        data: object = json.loads(content)
    except ValueError:
        return None
    if not isinstance(data, dict):
        return None
    fields = cast(dict[str, object], data)
    version, listed = fields.get("version"), fields.get("channels")
    if type(version) is not int or not 1 <= version <= FORMAT_VERSION:
        return None
    if not isinstance(listed, list):
        return None
    entries: list[dict[str, str | None]] = []
    for item in cast(list[object], listed):
        if not isinstance(item, dict):
            return None
        entry = cast(dict[str, object], item)
        channel_id = entry.get("id")
        if not isinstance(channel_id, str):
            return None
        handle, title = entry.get("handle"), entry.get("title")
        entries.append(
            {
                "id": channel_id,
                "handle": handle if isinstance(handle, str) else None,
                "title": title if isinstance(title, str) else None,
            }
        )
    return entries


def _readable(content: bytes | None) -> list[dict[str, str | None]]:
    entries = channel_entries(content)
    if entries is None:
        raise ValueError("the channel file cannot be understood")
    return entries


def channel_file_with(content: bytes | None, channel: Channel) -> bytes:
    """Return the channel file with the entry of a channel added or brought up to date.

    The other entries keep their order, and a new entry goes last. The same
    channels always give the same bytes, so an unchanged file is not written.

    Args:
        content: The file as it is, or None when there is none.
        channel: The channel.

    Raises:
        ValueError: When the file cannot be understood (see ``channel_entries``).
    """
    entry: dict[str, str | None] = {
        "id": channel.id,
        "handle": channel.handle,
        "title": channel.title,
    }
    entries = _readable(content)
    places = [index for index, other in enumerate(entries) if other["id"] == channel.id]
    if places:
        entries[places[0]] = entry
    else:
        entries.append(entry)
    return _content(entries)


def channel_file_without(content: bytes | None, channel_id: str) -> bytes | None:
    """Return the channel file without the entry of a channel, or None when no entry is left.

    Args:
        content: The file as it is, or None when there is none.
        channel_id: The channel.

    Raises:
        ValueError: When the file cannot be understood (see ``channel_entries``).
    """
    entries = [entry for entry in _readable(content) if entry["id"] != channel_id]
    return _content(entries) if entries else None


def _content(entries: list[dict[str, str | None]]) -> bytes:
    data = {"version": FORMAT_VERSION, "channels": entries}
    return (json.dumps(data, ensure_ascii=False, indent=2) + "\n").encode()
