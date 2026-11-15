"""What a media file contains, made up. Fake of the MediaTools port."""

from pathlib import Path

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

    def __init__(self) -> None:
        """Read every file as a good one."""
        self.facts: dict[Path, MediaFacts] = {}
        self.unreadable: set[Path] = set()
        self.probed: list[Path] = []

    def probe(self, path: Path) -> MediaFacts:
        """Return the facts of a file, or fail for an unreadable one."""
        self.probed.append(path)
        if path in self.unreadable:
            raise AppError(ErrorCode.VERIFY_FAILED, {"file": str(path)})
        return self.facts.get(path, GOOD)
