"""What a media file contains, made up. Fake of the MediaTools port."""

import dataclasses
from pathlib import Path

from tests.fixtures.fakes.file_system import FakeFileSystem
from ytmirror.core.errors import AppError, ErrorCode
from ytmirror.core.media import MediaFacts, SubtitleTrack

GOOD = MediaFacts(
    container="matroska,webm",
    duration_s=2.0,
    width=480,
    height=270,
    fps=25.0,
    vcodec="av1",
    acodec="opus",
    audio_channels=2,
    subtitles=(SubtitleTrack("eng", "English"),),
    attachments=("info.json", "cover.jpg"),
)
"""The facts of a complete file of two seconds."""


class FakeMediaTools:
    """Answers with the facts a test sets, or with those of a good file.

    Attributes:
        facts: The facts of particular files.
        unreadable: Files that cannot be read as media.
        probed: Every file that was read.
    """

    def __init__(self, files: FakeFileSystem | None = None) -> None:
        """Read every file as a good one.

        Args:
            files: The fake file system. A file there whose content is
                ``video:<id>`` carries that video ID as its tag, as a download does.
        """
        self._files = files
        self.facts: dict[Path, MediaFacts] = {}
        self.unreadable: set[Path] = set()
        self.probed: list[Path] = []

    def probe(self, path: Path) -> MediaFacts:
        """Return the facts of a file, or fail for an unreadable one."""
        self.probed.append(path)
        if path in self.unreadable:
            raise AppError(ErrorCode.VERIFY_FAILED, {"file": str(path)})
        if path in self.facts or self._files is None:
            return self.facts.get(path, GOOD)
        content = self._files.read_bytes(path) or b""
        if content.startswith(b"video:"):
            return dataclasses.replace(GOOD, tags={"video_id": content[6:].decode()})
        return GOOD
