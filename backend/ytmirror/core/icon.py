"""The app icon as data: its colours and the macOS icon file format.

The one source of the icon is ``frontend/src/design/brand/icon.svg``
(docs/DESIGN.md section 5). Its colours are tokens. The macOS icon is one
image and cannot follow the theme, so it takes the values of the light
theme (docs/DECISIONS.md D-054). This module is part of R-NA-02. It must
not read files and must not draw: it works on text and bytes.

Tests: backend/tests/unit/core/test_icon.py
"""

import re
import struct
from collections.abc import Mapping

ICON_THEME = "light"
"""The theme whose token values the macOS icon uses (docs/DECISIONS.md D-054)."""

ICNS_ENTRIES: tuple[tuple[str, int], ...] = (
    ("ic11", 32),
    ("ic12", 64),
    ("ic07", 128),
    ("ic13", 256),
    ("ic08", 256),
    ("ic14", 512),
    ("ic09", 512),
    ("ic10", 1024),
)
"""The images of a macOS icon file: entry type and size in pixels.

In points these are 16 and 32 at double density, then 128, 256 and 512, each
at single and at double density. Every entry holds a PNG image.
"""

ICON_PIXEL_SIZES: tuple[int, ...] = tuple(sorted({size for _type, size in ICNS_ENTRIES}))
"""Every pixel size that has to be drawn for the macOS icon."""

_ICNS_MAGIC = b"icns"
_HEADER_BYTES = 8
_TOKEN_USE = re.compile(r"var\(\s*(--[a-z0-9-]+)\s*\)")
_TOKEN_VALUE = re.compile(r"(--[a-z0-9-]+)\s*:\s*([^;]+);")


def theme_tokens(tokens_css: str, theme: str) -> dict[str, str]:
    """Return the token values of one theme block of the token file.

    Args:
        tokens_css: The text of ``frontend/src/design/tokens.css``.
        theme: The name of the theme, for example ``light``.

    Returns:
        Token name (with its two leading dashes) to value.

    Raises:
        ValueError: When the file has no block for the theme.
    """
    block = re.search(
        r"\[data-theme=[\'\"]" + re.escape(theme) + r"[\'\"]\]\s*\{([^}]*)\}", tokens_css
    )
    if block is None:
        raise ValueError(f"The token file has no theme called {theme!r}")
    return {name: value.strip() for name, value in _TOKEN_VALUE.findall(block.group(1))}


def icon_with_colours(svg: str, tokens_css: str) -> str:
    """Return the icon source with every token replaced by its value.

    Implements the colour rule of docs/DESIGN.md section 5 for the macOS
    icon: the values of the light theme (D-054).

    Args:
        svg: The text of the icon source file.
        tokens_css: The text of the token file.

    Returns:
        The SVG text without any ``var(...)``.

    Raises:
        ValueError: When the icon uses a token that the theme does not define.
    """
    tokens = theme_tokens(tokens_css, ICON_THEME)

    def value_of(use: re.Match[str]) -> str:
        name = use.group(1)
        if name not in tokens:
            raise ValueError(f"The icon uses the token {name}, which the {ICON_THEME} theme lacks")
        return tokens[name]

    return _TOKEN_USE.sub(value_of, svg)


def icns_file(png_by_size: Mapping[int, bytes]) -> bytes:
    """Pack PNG images into a macOS icon file (``.icns``).

    Args:
        png_by_size: One PNG image per pixel size of ``ICON_PIXEL_SIZES``.

    Returns:
        The bytes of the icon file.

    Raises:
        ValueError: When a size is missing.
    """
    missing = [size for size in ICON_PIXEL_SIZES if size not in png_by_size]
    if missing:
        raise ValueError(f"The icon lacks the sizes {missing}")
    entries = b"".join(
        entry_type.encode("ascii")
        + struct.pack(">I", _HEADER_BYTES + len(png_by_size[size]))
        + png_by_size[size]
        for entry_type, size in ICNS_ENTRIES
    )
    return _ICNS_MAGIC + struct.pack(">I", _HEADER_BYTES + len(entries)) + entries
