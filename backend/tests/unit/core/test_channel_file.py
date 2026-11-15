"""Tests of ``ytmirror.core.channel_file``."""

import dataclasses
import json

from tests.fixtures.catalogue import OTHER_CHANNEL_ID, make_channel
from ytmirror.core.channel_file import (
    FORMAT_VERSION,
    channel_entries,
    channel_file_with,
    channel_file_without,
)

CHANNEL = dataclasses.replace(
    make_channel(), handle="@samplechannel", folder="/Users/sam/Movies/YouTube/Sample"
)
OTHER = dataclasses.replace(make_channel(channel_id=OTHER_CHANNEL_ID), title="Other Channel")


def test_a_new_channel_file_lists_the_channel_and_nothing_else() -> None:
    """R-FI-05: the version and the ID, handle and title of the channel, never a path."""
    content = channel_file_with(None, CHANNEL)

    assert json.loads(content) == {
        "version": FORMAT_VERSION,
        "channels": [{"id": CHANNEL.id, "handle": "@samplechannel", "title": CHANNEL.title}],
    }
    assert "/Users" not in content.decode()


def test_a_second_channel_of_a_shared_folder_is_added_to_the_list() -> None:
    """R-FI-05: two channels in one folder are both listed, in the order they came."""
    content = channel_file_with(channel_file_with(None, CHANNEL), OTHER)

    assert [entry["id"] for entry in channel_entries(content)] == [CHANNEL.id, OTHER.id]


def test_a_channel_that_changed_keeps_its_place() -> None:
    """R-FI-05: a new title updates the entry; the same channel gives the same bytes."""
    both = channel_file_with(channel_file_with(None, CHANNEL), OTHER)
    renamed = dataclasses.replace(CHANNEL, title="A new title")

    updated = channel_file_with(both, renamed)

    assert [entry["title"] for entry in channel_entries(updated)] == [
        "A new title",
        "Other Channel",
    ]
    assert channel_file_with(both, CHANNEL) == both


def test_removing_a_channel_removes_its_entry_and_the_last_one_removes_the_file() -> None:
    """R-FI-05: the file goes only when no channel is left in it."""
    both = channel_file_with(channel_file_with(None, CHANNEL), OTHER)

    one_left = channel_file_without(both, CHANNEL.id)
    none_left = channel_file_without(one_left, OTHER.id)

    assert [entry["id"] for entry in channel_entries(one_left)] == [OTHER.id]
    assert none_left is None
    assert channel_file_without(None, CHANNEL.id) is None


def test_a_file_that_cannot_be_read_lists_no_channel() -> None:
    """R-FI-05: a damaged or foreign file lists nothing, and a new list replaces it."""
    for content in (b"not json", b"[1]", b'{"channels": 3}', b'{"channels": [7, {"id": 2}]}'):
        assert channel_entries(content) == []
    assert channel_entries(b'{"channels": [{"id": "UCa", "title": 5}]}') == [
        {"id": "UCa", "handle": None, "title": None}
    ]
