"""Downloads on the volumes of external drives: exFAT and HFS+ (D-093, TESTING section 5).

exFAT, common on drives shared with Windows, has neither the swap of two files
nor the rename that refuses to overwrite. Everything is real but YouTube: the
container, the database, the file system of macOS on a disk image of its own,
ffmpeg and ffprobe. Each test attaches its image without showing it in
Finder, and detaches exactly that device at the end. The Trash stands in as a
folder on the same volume, as a rename cannot cross volumes.
"""

import calendar
import dataclasses
import itertools
import json
import plistlib
import subprocess
import time
from collections.abc import Iterator
from pathlib import Path

import pytest

from tests.fixtures.media import ffmpeg_dir
from ytmirror.adapters.filesystem_mac import MacFileSystem
from ytmirror.app.config import AppPaths
from ytmirror.app.container import Container, build_container
from ytmirror.core.channels import CheckKind, VideoStatus
from ytmirror.services.channels import NewChannel

pytestmark = pytest.mark.media

PLENTY_OF_ROOM = 500 * 10**9
"""The free space the disk guard sees, so the test never depends on the image's size (R-QU-10)."""
FULLWIDTH_COLON = chr(0xFF1A)
CHANNEL_ID = "UCrepairrepairrepairrep1"
VIDEO_ID = "ren00000001"
PUBLISHED = calendar.timegm(time.strptime("2026-03-29T00:30:00Z", "%Y-%m-%dT%H:%M:%SZ"))


@pytest.fixture(params=["ExFAT", "HFS+"], ids=["exfat", "hfs"])
def volume(request: pytest.FixtureRequest, tmp_path: Path) -> Iterator[Path]:
    """A mounted volume of the asked format, 64 MB, under the temp folder of the test."""
    image = tmp_path / "volume.dmg"
    mount = tmp_path / "mount"
    mount.mkdir()
    subprocess.run(
        [
            *("/usr/bin/hdiutil", "create", "-size", "64m", "-fs", request.param),
            *("-volname", "YTMTEST", "-layout", "NONE", str(image)),
        ],
        check=True,
        capture_output=True,
    )
    attached = subprocess.run(
        [
            *("/usr/bin/hdiutil", "attach", str(image), "-nobrowse"),
            *("-mountpoint", str(mount), "-plist"),
        ],
        check=True,
        capture_output=True,
    )
    device = plistlib.loads(attached.stdout)["system-entities"][0]["dev-entry"]
    try:
        yield mount
    finally:
        subprocess.run(["/usr/bin/hdiutil", "detach", device, "-force"], capture_output=True)


@pytest.fixture
def trash(volume: Path) -> Path:
    """The folder that stands in for the Trash, on the same volume."""
    folder = volume / "trash"
    folder.mkdir()
    return folder


@pytest.fixture
def app(paths: AppPaths, tmp_path: Path, volume: Path, trash: Path) -> Container:
    """The real container, its library on the volume, with a video that changes its title."""
    world = tmp_path / "youtube"
    world.mkdir()
    channel = {
        "id": CHANNEL_ID,
        "title": "Repair Channel",
        "handle": "@repairchannel",
        "listed_at": "2026-11-14T06:42:00Z",
        "video_count": 1,
        "videos": [
            {
                "id": VIDEO_ID,
                "title": "First title",
                "point": "2026-04-01",
                "published_at": "2026-03-29T00:30:00Z",
                "length_s": 2,
            }
        ],
        "checks": [{"retitle": {VIDEO_ID: "Second: title"}}, {}],
    }
    (world / "repair.json").write_text(json.dumps(channel), encoding="utf-8")
    numbers = itertools.count(1)

    def to_trash(path: Path) -> None:
        path.rename(trash / f"{next(numbers)}-{path.name}")

    container = build_container(
        dataclasses.replace(
            paths,
            fake_youtube=world,
            tool_dir=ffmpeg_dir().parent,
            default_library=volume / "library",
        ),
        files=MacFileSystem(trash=to_trash, free_bytes=lambda: PLENTY_OF_ROOM),
    )
    container.schema.bring_up_to_date()
    return container


def dates(file: Path) -> tuple[int, int]:
    """Return the creation and modification date of a file, as Finder shows them."""
    found = file.stat()
    return int(found.st_birthtime), int(found.st_mtime)


def in_trash(trash: Path) -> list[str]:
    """What went to the Trash, in order, without the files exFAT keeps beside a file (``._``)."""
    return sorted(
        (entry.name for entry in trash.iterdir() if not entry.name.startswith("._")),
        key=lambda name: int(name.split("-", 1)[0]),
    )


def visible(folder: Path) -> list[str]:
    """The names in a folder that Finder shows."""
    return sorted(entry.name for entry in folder.iterdir() if not entry.name.startswith("."))


def test_download_rename_redownload_and_delete_the_files_on_the_volume(
    app: Container, trash: Path
) -> None:
    """R-MI-01, R-FN-06, R-QL-06, R-CH-32, R-DT-07, R-DT-10, D-093: the whole life of a file."""
    app.channels.add(NewChannel(app.channels.lookup("@repairchannel").facts.channel_id))
    assert app.catalogue.work_once() is True
    app.downloader.mirror([VIDEO_ID])
    assert app.downloader.work_once() is True
    view = app.views.of(CHANNEL_ID)
    assert view is not None
    folder = Path(view.folder)
    assert visible(folder) == ["First title.mkv"]
    assert dates(folder / "First title.mkv") == (PUBLISHED, PUBLISHED)

    app.catalogue.request_check(CHANNEL_ID, CheckKind.QUICK)
    assert app.catalogue.work_once() is True
    renamed = folder / f"Second{FULLWIDTH_COLON} title.mkv"
    assert visible(folder) == [renamed.name]
    assert dates(renamed) == (PUBLISHED, PUBLISHED)

    old = renamed.stat().st_ino
    app.downloader.redownload([VIDEO_ID])
    assert app.downloader.work_once() is True
    video = app.videos.video(VIDEO_ID)
    assert video is not None
    assert (video.status, video.replacing, video.file_name) == (
        VideoStatus.SYNCED,
        None,
        renamed.name,
    )
    assert renamed.stat().st_ino != old
    assert dates(renamed) == (PUBLISHED, PUBLISHED)
    assert visible(folder) == [renamed.name]
    assert in_trash(trash) == [f"1-{renamed.name}"]

    removed = app.channels.remove(CHANNEL_ID, keep_files=False)

    assert removed.left == ()
    assert not renamed.exists()
    trashed = in_trash(trash)
    assert trashed[0] == f"1-{renamed.name}"
    assert [name for name in trashed[1:] if name.endswith(f"-{renamed.name}")] != []
