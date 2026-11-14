"""Draws every image as one flat colour. Fake of the ImageRenderer port."""

from tests.fixtures.png import encode_rgba

FLAT_COLOUR = bytes((31, 95, 209, 255))


class FakeImageRenderer:
    """Returns a real PNG of the asked size, and remembers what it was asked to draw."""

    def __init__(self) -> None:
        """Start with nothing drawn."""
        self.drawn: list[tuple[str, int]] = []

    def svg_to_png(self, svg: str, size: int) -> bytes:
        """Return a flat square, or refuse text that is not an SVG image."""
        if "<svg" not in svg:
            raise ValueError("This is not an SVG image")
        self.drawn.append((svg, size))
        return encode_rgba(size, size, FLAT_COLOUR * (size * size))
