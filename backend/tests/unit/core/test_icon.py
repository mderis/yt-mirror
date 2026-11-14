"""Tests of ``ytmirror.core.icon``."""

import struct

import pytest

from ytmirror.core.icon import (
    ICNS_ENTRIES,
    ICON_PIXEL_SIZES,
    icns_file,
    icon_with_colours,
    theme_tokens,
)

TOKENS = """
:root { --ytm-space: 4px; }
[data-theme='dark'] {
  --ytm-color-accent: #5b9bff;
  --ytm-color-on-accent: #0b1220;
}
[data-theme='light'] {
  --ytm-color-accent: #1f5fd1;
  --ytm-color-on-accent: #ffffff;
}
"""
SVG = (
    '<svg viewBox="0 0 120 120"><rect fill="var(--ytm-color-accent)"/>'
    '<path stroke="var( --ytm-color-on-accent )"/></svg>'
)


def test_the_macos_icon_takes_the_colours_of_the_light_theme() -> None:
    """R-NA-02: the icon is generated from the one source file, in the light theme's colours."""
    coloured = icon_with_colours(SVG, TOKENS)

    assert 'fill="#1f5fd1"' in coloured
    assert 'stroke="#ffffff"' in coloured
    assert "var(" not in coloured


def test_a_change_of_a_token_changes_the_icon() -> None:
    """R-NA-02: the colours come from the token file, not from a copy of the values."""
    coloured = icon_with_colours(SVG, TOKENS.replace("#1f5fd1", "#123456"))

    assert 'fill="#123456"' in coloured


def test_an_icon_that_uses_an_undefined_token_is_refused() -> None:
    """R-NA-02: a token the theme lacks stops the build instead of drawing a wrong icon."""
    with pytest.raises(ValueError, match="--ytm-color-missing"):
        icon_with_colours('<svg><rect fill="var(--ytm-color-missing)"/></svg>', TOKENS)


def test_each_theme_block_is_read_by_itself() -> None:
    """R-NA-02: the values of one theme are not mixed with those of another."""
    assert theme_tokens(TOKENS, "dark") == {
        "--ytm-color-accent": "#5b9bff",
        "--ytm-color-on-accent": "#0b1220",
    }
    assert theme_tokens(TOKENS.replace("'", '"'), "light")["--ytm-color-accent"] == "#1f5fd1"


def test_a_theme_that_does_not_exist_is_an_error() -> None:
    """R-NA-02: the build names the missing theme instead of using other colours."""
    with pytest.raises(ValueError, match="'sepia'"):
        theme_tokens(TOKENS, "sepia")


def test_the_icon_file_holds_every_size_macos_asks_for() -> None:
    """R-NA-02: the bundle icon is a macOS icon file with the sizes from 16 to 512 points."""
    images = {size: b"PNG" + bytes([size % 251]) * (size // 16) for size in ICON_PIXEL_SIZES}

    data = icns_file(images)

    assert data[:4] == b"icns"
    assert struct.unpack(">I", data[4:8])[0] == len(data)
    found: list[tuple[str, bytes]] = []
    position = 8
    while position < len(data):
        entry_type = data[position : position + 4].decode("ascii")
        length = struct.unpack(">I", data[position + 4 : position + 8])[0]
        found.append((entry_type, data[position + 8 : position + length]))
        position += length
    assert [entry_type for entry_type, _image in found] == [name for name, _size in ICNS_ENTRIES]
    assert [image for _type, image in found] == [images[size] for _name, size in ICNS_ENTRIES]
    assert ICON_PIXEL_SIZES == (32, 64, 128, 256, 512, 1024)


def test_an_icon_file_is_not_written_with_a_size_missing() -> None:
    """R-NA-02: an incomplete icon is an error, not a half-filled file."""
    images = {size: b"PNG" for size in ICON_PIXEL_SIZES if size != 512}

    with pytest.raises(ValueError, match="512"):
        icns_file(images)
