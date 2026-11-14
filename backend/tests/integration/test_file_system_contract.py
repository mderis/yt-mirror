"""Contract of the FileSystem port, run against the fake and the real adapter."""

from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

import pytest

from tests.fixtures.fakes.file_system import FakeFileSystem
from ytmirror.adapters.filesystem_mac import MacFileSystem
from ytmirror.core.errors import AppError, ErrorCode
from ytmirror.ports.file_system import VIDEO_FILE_ENDINGS, FileSystem


@dataclass(frozen=True)
class Subject:
    """One file system with a way to put files into a folder and to see what was shown."""

    files: FileSystem
    put: object
    shown: list[Path]


def put_files(subject: Subject, folder: Path, names: list[str]) -> None:
    """Create files in a folder of the subject."""
    subject.put(folder, names)  # pyright: ignore[reportCallIssue]  (a callable of the subject)


@pytest.fixture(params=["fake", "mac"])
def subject(request: pytest.FixtureRequest) -> Subject:
    """The fake and the real file system, one after the other."""
    if request.param == "fake":
        fake = FakeFileSystem()
        return Subject(fake, fake.add_files, fake.opened)
    shown: list[Path] = []

    def run(command: Sequence[str]) -> None:
        assert command[0] == "/usr/bin/open"
        shown.append(Path(command[1]))

    def write(folder: Path, names: list[str]) -> None:
        folder.mkdir(parents=True, exist_ok=True)
        for name in names:
            (folder / name).write_bytes(b"x")

    return Subject(MacFileSystem(run), write, shown)


def test_a_folder_is_created_with_its_parents(subject: Subject, tmp_path: Path) -> None:
    """R-FI-01: the folder of a channel is created, also when the library does not exist yet."""
    folder = tmp_path / "library" / "Sample Channel"

    subject.files.make_folder(folder)

    assert subject.files.folder_exists(folder) is True
    assert subject.files.folder_exists(tmp_path / "other") is False


def test_creating_a_folder_that_exists_keeps_what_is_in_it(
    subject: Subject, tmp_path: Path
) -> None:
    """R-FI-01: a folder that is already there is taken as it is, with its files."""
    folder = tmp_path / "Sample Channel"
    put_files(subject, folder, ["a.mkv"])

    subject.files.make_folder(folder)

    assert subject.files.count_video_files(folder) == 1


def test_video_files_are_counted_by_the_ending_of_their_names(
    subject: Subject, tmp_path: Path
) -> None:
    """R-CH-06: files that end in mkv, mp4, webm, mov, m4v or avi are video files."""
    folder = tmp_path / "Sample Channel"
    names = [f"video{ending}" for ending in VIDEO_FILE_ENDINGS]
    put_files(subject, folder, [*names, "UPPER.MKV", "notes.txt", "cover.jpg", ".hidden.mkv"])

    assert subject.files.count_video_files(folder) == 7
    assert VIDEO_FILE_ENDINGS == (".mkv", ".mp4", ".webm", ".mov", ".m4v", ".avi")


def test_a_folder_that_does_not_exist_has_no_video_files(subject: Subject, tmp_path: Path) -> None:
    """R-CH-06: nothing is said about a folder that is not there yet."""
    assert subject.files.count_video_files(tmp_path / "missing") == 0


def test_a_folder_is_shown_in_finder(subject: Subject, tmp_path: Path) -> None:
    """R-CH-30: "Open folder" shows the folder of the channel in Finder."""
    folder = tmp_path / "Sample Channel"
    subject.files.make_folder(folder)

    subject.files.open_folder(folder)

    assert subject.shown == [folder]


def test_a_missing_folder_cannot_be_shown(subject: Subject, tmp_path: Path) -> None:
    """R-CH-30: a folder that is gone is reported, not opened."""
    with pytest.raises(AppError) as failure:
        subject.files.open_folder(tmp_path / "missing")

    assert failure.value.code is ErrorCode.FOLDER_UNAVAILABLE
    assert subject.shown == []


def test_the_disk_of_a_folder_has_a_name_and_free_space(subject: Subject, tmp_path: Path) -> None:
    """R-UI-01: the free disk space is known for the disk of the library, also before it exists."""
    disk = subject.files.disk_of(tmp_path / "not" / "there" / "yet")

    assert disk.name
    assert disk.free_bytes > 0


def test_files_in_subfolders_are_not_counted(tmp_path: Path) -> None:
    """R-CH-06: only files directly in the folder count."""
    folder = tmp_path / "Sample Channel"
    (folder / "sub.mkv").mkdir(parents=True)
    (folder / "sub.mkv" / "inside.mkv").write_bytes(b"x")

    assert MacFileSystem().count_video_files(folder) == 0


def test_a_folder_that_cannot_be_created_is_reported_with_the_reason(tmp_path: Path) -> None:
    """R-FI-01: a folder below a file cannot exist, which is reported as unavailable."""
    blocker = tmp_path / "a-file"
    blocker.write_bytes(b"x")

    with pytest.raises(AppError) as failure:
        MacFileSystem().make_folder(blocker / "Sample Channel")

    assert failure.value.code is ErrorCode.FOLDER_UNAVAILABLE
    assert failure.value.details["folder"] == str(blocker / "Sample Channel")


def test_a_folder_that_macos_denies_is_reported_as_denied(tmp_path: Path) -> None:
    """R-FI-01: a place the app may not write to is reported as permission denied."""
    locked = tmp_path / "locked"
    locked.mkdir()
    locked.chmod(0o500)
    try:
        with pytest.raises(AppError) as failure:
            MacFileSystem().make_folder(locked / "Sample Channel")
    finally:
        locked.chmod(0o700)

    assert failure.value.code is ErrorCode.PERMISSION_DENIED


def test_the_fake_can_refuse_folders_like_the_real_one() -> None:
    """infra: the fake can deny a folder or make it unavailable, for the tests of the services."""
    fake = FakeFileSystem()
    fake.denied.add(Path("/denied"))
    fake.unavailable.add(Path("/Volumes/Gone/x"))

    with pytest.raises(AppError) as denied:
        fake.make_folder(Path("/denied"))
    with pytest.raises(AppError) as unavailable:
        fake.make_folder(Path("/Volumes/Gone/x"))

    assert denied.value.code is ErrorCode.PERMISSION_DENIED
    assert unavailable.value.code is ErrorCode.FOLDER_UNAVAILABLE
