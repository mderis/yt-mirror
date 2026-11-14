"""The ImageRenderer port on macOS, through AppKit.

AppKit draws SVG by itself, so the icon can be built on the user's Mac
without Node.js or any other tool (R-NA-02, docs/DECISIONS.md D-045). This
module must not know what it draws.

Tests: backend/tests/integration/test_image_renderer_contract.py and
backend/tests/integration/test_icon_rendering.py
"""

import importlib
from typing import Any

_BITS_PER_CHANNEL = 8
_CHANNELS = 4


class MacImageRenderer:
    """Draws with the image classes of AppKit."""

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
        # pyobjc ships no type information, so its modules are handled as ``Any``.
        appkit: Any = importlib.import_module("AppKit")
        foundation: Any = importlib.import_module("Foundation")
        source: Any = foundation.NSData.dataWithBytes_length_(
            svg.encode("utf-8"), len(svg.encode("utf-8"))
        )
        image: Any = appkit.NSImage.alloc().initWithData_(source)
        if image is None or not image.isValid() or image.size().width <= 0:
            raise ValueError("AppKit cannot draw this image")
        bitmap: Any = appkit.NSBitmapImageRep.alloc().initWithBitmapDataPlanes_pixelsWide_pixelsHigh_bitsPerSample_samplesPerPixel_hasAlpha_isPlanar_colorSpaceName_bytesPerRow_bitsPerPixel_(  # noqa: E501
            None, size, size, _BITS_PER_CHANNEL, _CHANNELS, True, False,
            appkit.NSDeviceRGBColorSpace, 0, 0,
        )  # fmt: skip
        appkit.NSGraphicsContext.saveGraphicsState()
        try:
            appkit.NSGraphicsContext.setCurrentContext_(
                appkit.NSGraphicsContext.graphicsContextWithBitmapImageRep_(bitmap)
            )
            image.drawInRect_fromRect_operation_fraction_(
                foundation.NSMakeRect(0, 0, size, size),
                foundation.NSZeroRect,
                appkit.NSCompositingOperationSourceOver,
                1.0,
            )
        finally:
            appkit.NSGraphicsContext.restoreGraphicsState()
        png: Any = bitmap.representationUsingType_properties_(appkit.NSBitmapImageFileTypePNG, {})
        return bytes(png)
