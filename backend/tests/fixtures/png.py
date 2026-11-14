"""Reads and writes small PNG images, for tests that look at pixels.

Only what the tests need: 8 bits per channel, red, green, blue and alpha,
not interlaced.
"""

import struct
import zlib

SIGNATURE = b"\x89PNG\r\n\x1a\n"
_RGBA = 6
_CHANNELS = 4


def encode_rgba(width: int, height: int, pixels: bytes) -> bytes:
    """Return a PNG file for ``width * height`` pixels of four bytes each."""

    def chunk(kind: bytes, data: bytes) -> bytes:
        body = kind + data
        return struct.pack(">I", len(data)) + body + struct.pack(">I", zlib.crc32(body))

    row_bytes = width * _CHANNELS
    rows = b"".join(
        b"\x00" + pixels[row * row_bytes : (row + 1) * row_bytes] for row in range(height)
    )
    header = struct.pack(">IIBBBBB", width, height, 8, _RGBA, 0, 0, 0)
    return (
        SIGNATURE
        + chunk(b"IHDR", header)
        + chunk(b"IDAT", zlib.compress(rows))
        + chunk(b"IEND", b"")
    )


def size_of(png: bytes) -> tuple[int, int]:
    """Return the width and the height that a PNG file states."""
    assert png[:8] == SIGNATURE, "not a PNG file"
    width, height = struct.unpack(">II", png[16:24])
    return width, height


def decode_rgba(png: bytes) -> tuple[int, int, bytes]:
    """Return width, height and the pixels of a PNG file, four bytes per pixel."""
    assert png[:8] == SIGNATURE, "not a PNG file"
    position = 8
    header = b""
    compressed = b""
    while position < len(png):
        (length,) = struct.unpack(">I", png[position : position + 4])
        kind = png[position + 4 : position + 8]
        data = png[position + 8 : position + 8 + length]
        if kind == b"IHDR":
            header = data
        elif kind == b"IDAT":
            compressed += data
        position += 12 + length
    width, height, depth, colour, _compression, _filter, interlace = struct.unpack(
        ">IIBBBBB", header
    )
    assert (depth, colour, interlace) == (8, _RGBA, 0), "only plain 8-bit RGBA is read here"
    raw = zlib.decompress(compressed)
    stride = width * _CHANNELS
    pixels = bytearray()
    previous = bytearray(stride)
    for row in range(height):
        start = row * (stride + 1)
        line = _unfilter(raw[start], bytearray(raw[start + 1 : start + 1 + stride]), previous)
        pixels += line
        previous = line
    return width, height, bytes(pixels)


def _unfilter(kind: int, line: bytearray, previous: bytearray) -> bytearray:
    for index in range(len(line)):
        left = line[index - _CHANNELS] if index >= _CHANNELS else 0
        up = previous[index]
        up_left = previous[index - _CHANNELS] if index >= _CHANNELS else 0
        if kind == 1:
            predicted = left
        elif kind == 2:
            predicted = up
        elif kind == 3:
            predicted = (left + up) // 2
        elif kind == 4:
            estimate = left + up - up_left
            nearest = min((left, up, up_left), key=lambda value: abs(estimate - value))
            predicted = nearest
        else:
            predicted = 0
        line[index] = (line[index] + predicted) & 0xFF
    return line
