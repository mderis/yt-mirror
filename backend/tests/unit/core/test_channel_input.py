"""Tests of ``ytmirror.core.channel_input``."""

import pytest

from ytmirror.core.channel_input import RejectedInput, parse_channel_input
from ytmirror.core.channels import ChannelReference, ReferenceKind
from ytmirror.core.errors import AppError, ErrorCode

CHANNEL_ID = "UCaaaaaaaaaaaaaaaaaaaaaa"
HANDLE = ChannelReference(ReferenceKind.HANDLE, "@sample")
BY_ID = ChannelReference(ReferenceKind.CHANNEL_ID, CHANNEL_ID)
CUSTOM = ChannelReference(ReferenceKind.CUSTOM_NAME, "sample")
USER = ChannelReference(ReferenceKind.USER_NAME, "sample")


def rejection(text: str) -> AppError:
    """Return the error with which a text is refused."""
    with pytest.raises(AppError) as refused:
        parse_channel_input(text)
    return refused.value


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("https://www.youtube.com/@sample", HANDLE),
        (f"https://www.youtube.com/channel/{CHANNEL_ID}", BY_ID),
        ("https://www.youtube.com/c/sample", CUSTOM),
        ("https://www.youtube.com/user/sample", USER),
    ],
)
def test_the_four_forms_of_a_channel_address_are_accepted(
    text: str, expected: ChannelReference
) -> None:
    """R-CH-01: /@handle, /channel/UC..., /c/name and /user/name name a channel."""
    assert parse_channel_input(text) == expected


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("https://www.youtube.com/@sample/videos", HANDLE),
        ("https://www.youtube.com/@sample/shorts", HANDLE),
        ("https://www.youtube.com/@sample/featured/", HANDLE),
        (f"https://www.youtube.com/channel/{CHANNEL_ID}/videos", BY_ID),
        ("https://www.youtube.com/c/sample/streams", CUSTOM),
        ("https://www.youtube.com/user/sample/videos?view=0", USER),
    ],
)
def test_a_tab_after_the_channel_is_allowed(text: str, expected: ChannelReference) -> None:
    """R-CH-01: an address is accepted with or without a tab suffix such as /videos."""
    assert parse_channel_input(text) == expected


def test_a_bare_handle_is_accepted() -> None:
    """R-CH-01: a bare @handle names a channel."""
    assert parse_channel_input("@sample") == HANDLE


def test_a_bare_channel_id_is_accepted() -> None:
    """R-CH-01: a bare channel ID names a channel."""
    assert parse_channel_input(CHANNEL_ID) == BY_ID


@pytest.mark.parametrize(
    "text",
    [
        "  https://www.youtube.com/@sample  ",
        "http://www.youtube.com/@sample",
        "https://youtube.com/@sample",
        "https://m.youtube.com/@sample",
        "https://WWW.YouTube.com/@sample",
        "www.youtube.com/@sample",
        "youtube.com/@sample",
        "https://www.youtube.com/@sample?si=abc#top",
    ],
)
def test_an_address_is_accepted_as_people_paste_it(text: str) -> None:
    """R-CH-01: spaces around it, another scheme or host spelling do not matter."""
    assert parse_channel_input(text) == HANDLE


def test_a_handle_with_letters_of_another_script_is_accepted() -> None:
    """R-CH-01: a handle is whatever follows the @, also when it is written percent-encoded."""
    encoded = parse_channel_input("https://www.youtube.com/@%D9%86%D9%85%D9%88%D9%86%D9%87")

    assert encoded == ChannelReference(ReferenceKind.HANDLE, "@نمونه")
    assert parse_channel_input("@نمونه") == encoded


@pytest.mark.parametrize(
    "text",
    [
        "https://www.youtube.com/watch?v=abcdefghijk",
        "https://youtu.be/abcdefghijk",
        "youtu.be/abcdefghijk",
        "https://www.youtube.com/shorts/abcdefghijk",
        "https://www.youtube.com/live/abcdefghijk",
        "https://www.youtube.com/embed/abcdefghijk",
        "https://www.youtube.com/watch?v=abcdefghijk&list=PLxyz",
    ],
)
def test_a_video_is_refused_as_a_video(text: str) -> None:
    """R-CH-02: a video address is rejected, and the reason says that it is a video."""
    refused = rejection(text)

    assert refused.code is ErrorCode.INVALID_CHANNEL_INPUT
    assert refused.details == {"reason": RejectedInput.VIDEO.value}


def test_a_playlist_is_refused_as_a_playlist() -> None:
    """R-CH-02: a playlist address is rejected, and the reason says that it is a playlist."""
    refused = rejection("https://www.youtube.com/playlist?list=PLxyz")

    assert refused.code is ErrorCode.INVALID_CHANNEL_INPUT
    assert refused.details == {"reason": RejectedInput.PLAYLIST.value}


@pytest.mark.parametrize(
    "text",
    [
        "sample",
        "sample channel",
        "https://example.org/@sample",
        "https://www.youtube.com/",
        "https://www.youtube.com",
        "https://www.youtube.com/sample",
        "https://www.youtube.com/feed/subscriptions",
        "https://www.youtube.com/channel/not-a-channel-id",
        "https://www.youtube.com/channel/",
        "https://www.youtube.com/@sample/videos/more",
        "https://www.youtube.com/c/sample/videos/more",
        "ftp://www.youtube.com/@sample",
        "UCtooshort",
        "@",
        "@two words",
    ],
)
def test_anything_else_is_refused(text: str) -> None:
    """R-CH-02: what is neither a channel, a video nor a playlist is rejected as "other"."""
    refused = rejection(text)

    assert refused.code is ErrorCode.INVALID_CHANNEL_INPUT
    assert refused.details == {"reason": RejectedInput.OTHER.value}


@pytest.mark.parametrize("text", ["", "   ", "\n\t"])
def test_nothing_is_refused_as_empty(text: str) -> None:
    """R-CH-02: an empty field is rejected with a reason of its own."""
    refused = rejection(text)

    assert refused.details == {"reason": RejectedInput.EMPTY.value}
