"""Tests of ``ytmirror.core.channels``."""

import pytest

from ytmirror.core.channels import ChannelFacts, ChannelReference, ReferenceKind


@pytest.mark.parametrize(
    ("kind", "value", "address"),
    [
        (ReferenceKind.HANDLE, "@sample", "https://www.youtube.com/@sample"),
        (
            ReferenceKind.CHANNEL_ID,
            "UCaaaaaaaaaaaaaaaaaaaaaa",
            "https://www.youtube.com/channel/UCaaaaaaaaaaaaaaaaaaaaaa",
        ),
        (ReferenceKind.CUSTOM_NAME, "sample", "https://www.youtube.com/c/sample"),
        (ReferenceKind.USER_NAME, "sample", "https://www.youtube.com/user/sample"),
    ],
)
def test_every_form_of_naming_a_channel_has_an_address_at_youtube(
    kind: ReferenceKind, value: str, address: str
) -> None:
    """R-CH-01: a handle, a channel ID, a custom name and a user name each lead to a channel."""
    reference = ChannelReference(kind, value)

    assert reference.address == address


def test_the_canonical_address_of_a_channel_is_built_from_its_id() -> None:
    """R-CH-30: the address under which a channel is opened on YouTube comes from its ID."""
    facts = ChannelFacts("UCaaaaaaaaaaaaaaaaaaaaaa", "Sample", "@sample", None)

    assert facts.url == "https://www.youtube.com/channel/UCaaaaaaaaaaaaaaaaaaaaaa"
