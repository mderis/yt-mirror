"""The file system adapter on an exFAT volume, as an external drive often is (D-093).

exFAT has neither the swap of two files nor the rename that refuses to
overwrite (both answer ENOTSUP, measured on macOS 27 on 2026-11-18). These
tests attach a small exFAT disk image of their own, without showing it in
Finder, and detach exactly that device at the end.
"""

import plistlib
import subprocess
from collections.abc import Iterator
from pathlib import Path

import pytest

from ytmirror.adapters.filesystem_mac import MacFileSystem
from ytmirror.ports.file_system import SwapNotSupportedError

PUBLISHED = 1_700_000_000


@pytest.fixture(scope="module")
def exfat(tmp_path_factory: pytest.TempPathFactory) -> Iterator[Path]:
    """A mounted exFAT volume of 20 MB, under the temp folder of the tests."""
    folder = tmp_path_factory.mktemp("exfat")
    image = folder / "volume.dmg"
    mount = folder / "mount"
    mount.mkdir()
    subprocess.run(
        [
            *("/usr/bin/hdiutil", "create", "-size", "20m", "-fs", "ExFAT"),
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
def folder(exfat: Path, request: pytest.FixtureRequest) -> Path:
    """A fresh folder on the volume for one test."""
    place = exfat / request.node.name[:40]
    place.mkdir()
    return place


def test_a_file_is_moved_to_its_place_on_exfat(folder: Path) -> None:
    """R-QL-06, R-FN-01, D-093: a download is put in place on a volume without a safe rename."""
    files = MacFileSystem(trash=lambda _path: None)
    source = folder / "new.mkv"
    source.write_bytes(b"new")

    assert files.move(source, folder / "Video.mkv") is True

    assert (folder / "Video.mkv").read_bytes() == b"new"
    assert not source.exists()


def test_a_move_never_overwrites_on_exfat(folder: Path) -> None:
    """R-QL-06, D-093: the name of another file is never taken over, also on exFAT."""
    files = MacFileSystem(trash=lambda _path: None)
    source = folder / "new.mkv"
    source.write_bytes(b"new")
    (folder / "Video.mkv").write_bytes(b"the user's file")

    assert files.move(source, folder / "Video.mkv") is False

    assert (folder / "Video.mkv").read_bytes() == b"the user's file"
    assert source.read_bytes() == b"new"


def test_a_swap_says_the_volume_cannot_swap_and_changes_nothing(folder: Path) -> None:
    """R-QL-06, D-093: ENOTSUP is not a folder that cannot be reached; nothing moved."""
    files = MacFileSystem(trash=lambda _path: None)
    (folder / "a.mkv").write_bytes(b"new")
    (folder / "b.mkv").write_bytes(b"old")

    with pytest.raises(SwapNotSupportedError):
        files.swap(folder / "a.mkv", folder / "b.mkv")

    assert (folder / "a.mkv").read_bytes() == b"new"
    assert (folder / "b.mkv").read_bytes() == b"old"


def test_a_file_keeps_its_identity_and_dates_through_a_move_on_exfat(folder: Path) -> None:
    """R-DT-10, D-093: the marker finds the old file by its identity; the dates stay."""
    files = MacFileSystem(trash=lambda _path: None)
    source = folder / "old.mkv"
    source.write_bytes(b"old")
    files.set_dates(source, PUBLISHED)
    identity = files.file_id(source)

    assert files.move(source, folder / ".Video.mkv.yt-mirror-old") is True

    moved = folder / ".Video.mkv.yt-mirror-old"
    assert files.file_id(moved) == identity
    dates = files.read_dates(moved)
    assert (dates.created, dates.modified) == (PUBLISHED, PUBLISHED)
