"""The ImageRenderer port: draws a vector image into pixels.

Used to generate the app icon from its one source file on the user's Mac
(R-NA-02, docs/DESIGN.md section 5).

Tests: backend/tests/integration/test_image_renderer_contract.py
"""

from typing import Protocol


class ImageRenderer(Protocol):
    """Turns an SVG image into a PNG image."""

    def svg_to_png(self, svg: str, size: int) -> bytes:
        """Draw an SVG image into a square PNG.

        Args:
            svg: The SVG text. It must not use CSS variables.
            size: The width and height of the PNG in pixels.

        Returns:
            The PNG file as bytes: 8 bits per channel, with transparency.

        Raises:
            ValueError: When the text is not an image that can be drawn.
        """
        ...
