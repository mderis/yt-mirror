"""Tests of ``ytmirror.core.naming``."""

import unicodedata

import pytest

from ytmirror.core.naming import MAX_NAME_BYTES, channel_folder_name, safe_name

CHANNEL_ID = "UCaaaaaaaaaaaaaaaaaaaaaa"


def test_a_plain_channel_name_is_the_folder_name() -> None:
    """R-FI-01: a channel gets a folder named after the channel."""
    assert channel_folder_name("Sample Channel", CHANNEL_ID, taken=()) == "Sample Channel"


def test_a_slash_and_a_colon_become_their_lookalikes() -> None:
    """R-FI-01: the folder name takes the substitutions of R-FN-02."""
    name = channel_folder_name("AC/DC: Live", CHANNEL_ID, taken=())

    assert name == "AC\u29f8DC\uff1a Live"
    assert "/" not in name
    assert ":" not in name


def test_control_characters_are_removed_and_spaces_trimmed() -> None:
    """R-FI-01: control characters go, and so do spaces at both ends (R-FN-02)."""
    assert safe_name("  Sample\tChan\x00nel\n ") == "SampleChannel"


def test_a_leading_dot_gets_an_underscore_so_the_folder_is_not_hidden() -> None:
    """R-FI-01: a leading dot gets a preceding underscore (R-FN-02)."""
    assert channel_folder_name(".hidden", CHANNEL_ID, taken=()) == "_.hidden"


def test_the_name_is_stored_in_nfc() -> None:
    """R-FI-01: names are in Unicode NFC (R-FN-03)."""
    decomposed = unicodedata.normalize("NFD", "Café Zoë")

    name = channel_folder_name(decomposed, CHANNEL_ID, taken=())

    assert name == unicodedata.normalize("NFC", "Café Zoë")
    assert name != decomposed


def test_emoji_and_other_scripts_stay_as_they_are() -> None:
    """R-FI-01: only what macOS cannot store is substituted."""
    assert channel_folder_name("کانال نمونه 🎬", CHANNEL_ID, taken=()) == "کانال نمونه 🎬"


def test_a_name_that_another_channel_has_gets_the_channel_id() -> None:
    """R-FI-01: when the folder belongs to another channel, the channel ID is appended."""
    name = channel_folder_name("Sample Channel", CHANNEL_ID, taken=["Sample Channel"])

    assert name == f"Sample Channel [{CHANNEL_ID}]"


def test_taken_names_are_compared_without_regard_to_case() -> None:
    """R-FI-01: macOS does not tell "sample" from "Sample", so neither does the name."""
    name = channel_folder_name("Sample Channel", CHANNEL_ID, taken=["sample channel"])

    assert name == f"Sample Channel [{CHANNEL_ID}]"


@pytest.mark.parametrize("title", ["", "   ", "\x00\x01"])
def test_a_name_with_nothing_storable_becomes_the_channel_id(title: str) -> None:
    """R-FI-01: a channel always gets a folder, also when its name leaves nothing."""
    assert channel_folder_name(title, CHANNEL_ID, taken=()) == CHANNEL_ID


@pytest.mark.parametrize("title", ["a" * 400, "é" * 300, "🎬" * 120, ("word " * 80)])
def test_a_long_name_is_cut_on_a_character_so_that_the_suffix_still_fits(title: str) -> None:
    """R-FI-01: the folder name fits into 255 bytes, with or without the channel ID."""
    plain = channel_folder_name(title, CHANNEL_ID, taken=())
    suffixed = channel_folder_name(title, CHANNEL_ID, taken=[plain])

    assert len(suffixed.encode()) <= MAX_NAME_BYTES
    assert suffixed == f"{plain} [{CHANNEL_ID}]"
    assert plain == plain.strip()
    assert title.startswith(plain)
