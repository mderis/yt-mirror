"""The MediaTools port: reading what a finished video file contains.

A download is verified before its file is put in its place (docs/ARCHITECTURE.md
section 7.2, step 5), and the details panel shows the formats of the file
(R-UI-08).

Tests: backend/tests/integration/test_media_tools.py
"""

from pathlib import Path
from typing import Protocol

from ytmirror.core.media import MediaFacts


class MediaTools(Protocol):
    """Reads media files."""

    def probe(self, path: Path) -> MediaFacts:
        """Return what a media file contains.

        Args:
            path: The file.

        Raises:
            AppError: ``VERIFY_FAILED`` when the file cannot be read as media,
                ``TOOL_MISSING`` when ffprobe cannot be run.
        """
        ...
