"""Contract of the ImageRenderer port, run against the fake and against AppKit."""

import pytest

from tests.fixtures.fakes.image_renderer import FakeImageRenderer
from tests.fixtures.png import decode_rgba, encode_rgba, size_of
from ytmirror.adapters.image_renderer_mac import MacImageRenderer
from ytmirror.ports.image_renderer import ImageRenderer

SQUARE = (
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 8 8">'
    '<rect width="8" height="8" fill="#1f5fd1"/></svg>'
)


@pytest.fixture(params=["fake", "mac"])
def renderer(request: pytest.FixtureRequest) -> ImageRenderer:
    """The fake and the real renderer."""
    return FakeImageRenderer() if request.param == "fake" else MacImageRenderer()


@pytest.mark.parametrize("size", [32, 256])
def test_the_image_has_the_asked_size(renderer: ImageRenderer, size: int) -> None:
    """R-NA-02: the icon is drawn at each size the icon file needs."""
    png = renderer.svg_to_png(SQUARE, size)

    assert size_of(png) == (size, size)


def test_the_image_is_plain_rgba_with_the_colour_of_the_source(renderer: ImageRenderer) -> None:
    """R-NA-02: a colour of the source arrives in the pixels unchanged."""
    width, height, pixels = decode_rgba(renderer.svg_to_png(SQUARE, 16))

    middle = (height // 2 * width + width // 2) * 4
    assert tuple(pixels[middle : middle + 4]) == (0x1F, 0x5F, 0xD1, 0xFF)


def test_text_that_is_no_image_is_refused(renderer: ImageRenderer) -> None:
    """R-NA-02: a broken icon source stops the build instead of giving an empty icon."""
    with pytest.raises(ValueError, match="image"):
        renderer.svg_to_png("this is not an image", 32)


def test_the_png_helper_of_the_tests_reads_what_it_writes() -> None:
    """infra: the PNG reader used to look at pixels agrees with the PNG writer."""
    pixels = bytes(range(256)) * 4

    assert decode_rgba(encode_rgba(16, 16, pixels)) == (16, 16, pixels)
