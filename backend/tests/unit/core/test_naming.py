"""Tests of ``ytmirror.core.naming``."""

import unicodedata

import pytest
from hypothesis import given
from hypothesis import strategies as st

from ytmirror.core.naming import (
    MAX_NAME_BYTES,
    VIDEO_EXTENSION,
    channel_folder_name,
    safe_name,
    video_file_name,
)

CHANNEL_ID = "UCaaaaaaaaaaaaaaaaaaaaaa"
VIDEO_ID = "a1B2c3D4e5F"


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
    """R-FN-03: names are in Unicode NFC (R-FN-03)."""
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


# --- file names of videos


def test_the_file_name_is_the_title_and_mkv() -> None:
    """R-FN-01: the file name is the video title plus .mkv, nothing else."""
    assert video_file_name("How I organize my workshop", VIDEO_ID, taken=()) == (
        "How I organize my workshop.mkv"
    )


def test_a_slash_and_a_colon_in_a_title_become_their_lookalikes() -> None:
    """R-FN-02: "/" becomes U+29F8 and ":" becomes U+FF1A."""
    assert video_file_name("Part 1/2: The start", VIDEO_ID, taken=()) == (
        "Part 1\u29f82\uff1a The start.mkv"
    )


def test_a_title_with_a_leading_dot_does_not_make_a_hidden_file() -> None:
    """R-FN-02: a leading dot gets a preceding underscore, and spaces at both ends go."""
    assert video_file_name("  .env explained \n", VIDEO_ID, taken=()) == "_.env explained.mkv"


def test_a_title_is_stored_in_nfc() -> None:
    """R-FN-03: names are in Unicode NFC."""
    name = video_file_name(unicodedata.normalize("NFD", "Crème brûlée"), VIDEO_ID, taken=())

    assert name == unicodedata.normalize("NFC", "Crème brûlée") + ".mkv"


@pytest.mark.parametrize("title", ["a" * 300, "é" * 200, "🎬" * 80])
def test_a_long_title_is_cut_on_a_character_and_gets_the_video_id(title: str) -> None:
    """R-FN-04: over 255 bytes, the title is shortened and " [<video id>]" appended."""
    name = video_file_name(title, VIDEO_ID, taken=())

    assert len(name.encode()) <= MAX_NAME_BYTES
    assert name.endswith(f" [{VIDEO_ID}].mkv")
    assert title.startswith(name.removesuffix(f" [{VIDEO_ID}].mkv"))


def test_a_title_that_fits_exactly_is_not_cut() -> None:
    """R-FN-04: a name of exactly 255 bytes is kept as it is."""
    title = "a" * (MAX_NAME_BYTES - len(VIDEO_EXTENSION))

    assert video_file_name(title, VIDEO_ID, taken=()) == title + ".mkv"


def test_a_name_another_video_has_gets_the_video_id() -> None:
    """R-FN-05: the later of two videos with the same name gets " [<video id>]"."""
    name = video_file_name("Trailer", VIDEO_ID, taken=["Trailer.mkv"])

    assert name == f"Trailer [{VIDEO_ID}].mkv"


def test_names_are_compared_without_regard_to_case() -> None:
    """R-FN-05: "trailer.mkv" and "Trailer.mkv" are the same file on macOS."""
    name = video_file_name("Trailer", VIDEO_ID, taken=["TRAILER.MKV"])

    assert name == f"Trailer [{VIDEO_ID}].mkv"


def test_an_empty_title_becomes_the_video_id() -> None:
    """R-FN-01: a video without a title gets its video ID as the name."""
    assert video_file_name("", VIDEO_ID, taken=()) == f"{VIDEO_ID}.mkv"


def test_a_title_of_only_spaces_becomes_the_video_id() -> None:
    """R-FN-01: spaces are trimmed (R-FN-02), and nothing is left."""
    assert video_file_name("   ", VIDEO_ID, taken=()) == f"{VIDEO_ID}.mkv"


def test_a_title_of_only_control_characters_becomes_the_video_id() -> None:
    """R-FN-01: control characters are removed (R-FN-02), and nothing is left."""
    assert video_file_name("\x00\x07", VIDEO_ID, taken=()) == f"{VIDEO_ID}.mkv"


def test_a_title_of_one_dot_becomes_the_video_id() -> None:
    """R-FN-01: "." is no name for a file, so it counts as nothing storable."""
    assert video_file_name(".", VIDEO_ID, taken=()) == f"{VIDEO_ID}.mkv"


def test_a_title_of_two_dots_becomes_the_video_id() -> None:
    """R-FN-01: ".." is no name for a file, so it counts as nothing storable."""
    assert video_file_name("..", VIDEO_ID, taken=()) == f"{VIDEO_ID}.mkv"


def test_a_title_of_only_dots_and_spaces_becomes_the_video_id() -> None:
    """R-FN-01: dots and spaces alone leave nothing storable."""
    assert video_file_name(" . . ... ", VIDEO_ID, taken=()) == f"{VIDEO_ID}.mkv"


def test_a_title_that_starts_with_a_dot_keeps_its_words_and_is_not_hidden() -> None:
    """R-FN-02: a leading dot gets a preceding underscore, so Finder shows the file."""
    assert video_file_name("...and then it worked", VIDEO_ID, taken=()) == (
        "_...and then it worked.mkv"
    )


def test_the_video_id_name_follows_the_collision_rule_too() -> None:
    """R-FN-05: a file of no known video named like the ID is never overwritten."""
    assert video_file_name("..", VIDEO_ID, taken=[f"{VIDEO_ID}.mkv"]) == (
        f"{VIDEO_ID} [{VIDEO_ID}].mkv"
    )


_VIDEO_IDS = st.text(
    alphabet="abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_",
    min_size=11,
    max_size=11,
)


@given(title=st.text(max_size=400), video_id=_VIDEO_IDS, taken=st.lists(st.text(max_size=40)))
def test_every_title_gives_a_valid_macos_file_name(
    title: str, video_id: str, taken: list[str]
) -> None:
    """R-FN-01, R-FN-02, R-FN-03, R-FN-04: any title gives a valid, visible, NFC MKV name."""
    name = video_file_name(title, video_id, taken)

    assert name.endswith(".mkv")
    assert 0 < len(name.encode()) <= MAX_NAME_BYTES
    assert "/" not in name
    assert ":" not in name
    assert "\x00" not in name
    assert not name.startswith(".")
    assert name == unicodedata.normalize("NFC", name)
    assert name.casefold() not in {other.casefold() for other in taken} or name.endswith(
        f" [{video_id}].mkv"
    )


@given(title=st.text(max_size=300), video_id=_VIDEO_IDS, taken=st.lists(st.text(max_size=40)))
def test_the_same_title_always_gives_the_same_name(
    title: str, video_id: str, taken: list[str]
) -> None:
    """R-FN-01: the name is stable: the same title and folder give the same name."""
    assert video_file_name(title, video_id, taken) == video_file_name(title, video_id, taken)


@given(title=st.text(min_size=1, max_size=300), video_id=_VIDEO_IDS)
def test_a_taken_name_never_comes_back(title: str, video_id: str) -> None:
    """R-FN-05: a name in the folder is never given again, so no file is overwritten."""
    first = video_file_name(title, video_id, taken=())

    second = video_file_name(title, video_id, taken=[first.upper()])

    assert second.casefold() != first.casefold() or first.endswith(f" [{video_id}].mkv")


def test_a_title_of_underscores_keeps_its_name() -> None:
    """R-FN-01: only dots and spaces leave nothing; underscores are a name."""
    assert video_file_name("___", VIDEO_ID, taken=()) == "___.mkv"
    assert video_file_name("_.", VIDEO_ID, taken=()) == "_..mkv"
