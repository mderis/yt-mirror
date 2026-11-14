"""The generated app icon matches its source file (docs/DESIGN.md section 5).

The icon is expected to change, so these tests know nothing about what the
icon shows. They read the source file and check what must hold for every
icon that follows the design rule: one mark in one colour on a rounded
square in another, both colours taken from the tokens. They run on the
AppKit of this Mac, which is macOS 15 in CI.
"""

import importlib
import re
from collections import Counter
from pathlib import Path
from typing import Any

import pytest

from tests.fixtures.png import decode_rgba
from ytmirror.adapters.image_renderer_mac import MacImageRenderer
from ytmirror.core.icon import ICON_PIXEL_SIZES, icns_file, icon_with_colours, theme_tokens

DESIGN = Path(__file__).resolve().parents[3] / "frontend" / "src" / "design"
ICON_SOURCE = DESIGN / "brand" / "icon.svg"
TOKENS = DESIGN / "tokens.css"
SIZE = 512
OPAQUE = 255
SOLID_SHARE = 0.9
"""Share of the opaque pixels that must be exactly one of the two colours. The rest are edges."""


def _rgb(value: str) -> tuple[int, int, int]:
    text = value.lstrip("#")
    return int(text[0:2], 16), int(text[2:4], 16), int(text[4:6], 16)


@pytest.fixture(scope="module")
def tokens() -> dict[str, str]:
    """The token values the macOS icon uses."""
    return theme_tokens(TOKENS.read_text(encoding="utf-8"), "light")


@pytest.fixture(scope="module")
def pixels() -> list[tuple[int, int, int, int]]:
    """The real icon source, drawn by AppKit at 512 pixels, row by row."""
    svg = icon_with_colours(
        ICON_SOURCE.read_text(encoding="utf-8"), TOKENS.read_text(encoding="utf-8")
    )
    width, height, data = decode_rgba(MacImageRenderer().svg_to_png(svg, SIZE))
    assert (width, height) == (SIZE, SIZE)
    return [(data[i], data[i + 1], data[i + 2], data[i + 3]) for i in range(0, len(data), 4)]


def test_the_icon_is_drawn_in_the_two_token_colours_only(
    pixels: list[tuple[int, int, int, int]], tokens: dict[str, str]
) -> None:
    """R-NA-02: the icon has the accent and the on-accent colour of the light theme (D-054)."""
    accent = _rgb(tokens["--ytm-color-accent"])
    mark = _rgb(tokens["--ytm-color-on-accent"])
    opaque = Counter(pixel[:3] for pixel in pixels if pixel[3] == OPAQUE)

    (first, first_count), (second, second_count) = opaque.most_common(2)

    assert accent == (0x1F, 0x5F, 0xD1)
    assert mark == (0xFF, 0xFF, 0xFF)
    assert {first, second} == {accent, mark}
    assert first_count + second_count > SOLID_SHARE * sum(opaque.values())
    low = [min(a, m) - 1 for a, m in zip(accent, mark, strict=True)]
    high = [max(a, m) + 1 for a, m in zip(accent, mark, strict=True)]
    assert all(
        low[channel] <= colour[channel] <= high[channel]
        for colour in opaque
        for channel in range(3)
    ), "an opaque pixel is neither one of the two colours nor a blend of them"


def test_the_rounded_square_covers_exactly_the_area_the_source_gives_it(
    pixels: list[tuple[int, int, int, int]],
) -> None:
    """R-NA-02: the drawn icon has the geometry of the source file."""
    source = ICON_SOURCE.read_text(encoding="utf-8")
    view = re.search(r'viewBox="0 0 ([\d.]+) ([\d.]+)"', source)
    rect = re.search(r'<rect x="([\d.]+)" y="([\d.]+)" width="([\d.]+)" height="([\d.]+)"', source)
    assert view is not None and rect is not None, "the source is no mark on a rounded square"
    scale = SIZE / float(view.group(1))
    left, top, width, height = (float(value) * scale for value in rect.groups())

    drawn_columns = [x for x in range(SIZE) if any(pixels[y * SIZE + x][3] for y in range(SIZE))]
    drawn_rows = [y for y in range(SIZE) if any(pixels[y * SIZE + x][3] for x in range(SIZE))]

    assert float(view.group(1)) == float(view.group(2))
    assert abs(drawn_columns[0] - left) <= 1
    assert abs(drawn_columns[-1] + 1 - (left + width)) <= 1
    assert abs(drawn_rows[0] - top) <= 1
    assert abs(drawn_rows[-1] + 1 - (top + height)) <= 1


def test_outside_the_rounded_square_the_icon_is_transparent(
    pixels: list[tuple[int, int, int, int]],
) -> None:
    """R-NA-02: the corners are see-through, the middle of each edge is not."""
    corners = [pixels[0], pixels[SIZE - 1], pixels[SIZE * (SIZE - 1)], pixels[SIZE * SIZE - 1]]
    inset = SIZE // 8
    edge_middles = [
        pixels[inset * SIZE + SIZE // 2],
        pixels[(SIZE - inset) * SIZE + SIZE // 2],
        pixels[(SIZE // 2) * SIZE + inset],
        pixels[(SIZE // 2) * SIZE + SIZE - inset],
    ]

    assert all(pixel[3] == 0 for pixel in corners)
    assert all(pixel[3] == OPAQUE for pixel in edge_middles)


def test_drawing_the_same_source_twice_gives_the_same_image() -> None:
    """R-NA-02: the icon depends on its source file and on nothing else."""
    svg = icon_with_colours(
        ICON_SOURCE.read_text(encoding="utf-8"), TOKENS.read_text(encoding="utf-8")
    )
    renderer = MacImageRenderer()

    assert renderer.svg_to_png(svg, 128) == renderer.svg_to_png(svg, 128)


def test_macos_reads_the_generated_icon_file_with_every_size(tmp_path: Path) -> None:
    """R-NA-02: the icon file built from the source is one that macOS accepts."""
    svg = icon_with_colours(
        ICON_SOURCE.read_text(encoding="utf-8"), TOKENS.read_text(encoding="utf-8")
    )
    renderer = MacImageRenderer()
    icon = tmp_path / "app.icns"
    icon.write_bytes(icns_file({size: renderer.svg_to_png(svg, size) for size in ICON_PIXEL_SIZES}))

    appkit: Any = importlib.import_module("AppKit")
    image: Any = appkit.NSImage.alloc().initWithContentsOfFile_(str(icon))

    assert image is not None and image.isValid()
    widths = sorted({int(rep.pixelsWide()) for rep in image.representations()})
    assert widths == list(ICON_PIXEL_SIZES)
