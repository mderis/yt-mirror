"""Contract of the FileSystem port, run against the fake and the real adapter."""

import os
import time
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

import pytest

from tests.fixtures.fakes.file_system import FakeFileSystem
from ytmirror.adapters.filesystem_mac import MacFileSystem
from ytmirror.core.errors import AppError, ErrorCode
from ytmirror.ports.file_system import VIDEO_FILE_ENDINGS, FileDates, FileSystem


@dataclass(frozen=True)
class Subject:
    """One file system, a way to put files into a folder, and what it showed, opened and trashed."""

    files: FileSystem
    put: object
    shown: list[Path]
    revealed: list[Path]
    played: list[Path]
    trashed: list[Path]


def put_files(subject: Subject, folder: Path, names: list[str]) -> None:
    """Create files in a folder of the subject."""
    subject.put(folder, names)  # pyright: ignore[reportCallIssue]  (a callable of the subject)


@pytest.fixture(params=["fake", "mac"])
def subject(request: pytest.FixtureRequest, tmp_path: Path) -> Subject:
    """The fake and the real file system, one after the other.

    The real one gets a stand-in for the Trash, a folder of the test, so that
    no test fills the Trash of the person who runs it.
    """
    if request.param == "fake":
        fake = FakeFileSystem()
        return Subject(fake, fake.add_files, fake.opened, fake.revealed, fake.played, fake.trashed)
    shown: list[Path] = []
    revealed: list[Path] = []
    played: list[Path] = []
    trashed: list[Path] = []
    trash_folder = tmp_path / "the-trash"

    def run(command: Sequence[str]) -> None:
        assert command[0] == "/usr/bin/open"
        if command[1] == "-R":
            revealed.append(Path(command[2]))
        elif Path(command[1]).is_dir():
            shown.append(Path(command[1]))
        else:
            played.append(Path(command[1]))

    def trash(path: Path) -> None:
        trash_folder.mkdir(exist_ok=True)
        path.rename(trash_folder / f"{len(trashed)}-{path.name}")
        trashed.append(path)

    def write(folder: Path, names: list[str]) -> None:
        folder.mkdir(parents=True, exist_ok=True)
        for name in names:
            (folder / name).write_bytes(b"x")

    return Subject(MacFileSystem(run, trash), write, shown, revealed, played, trashed)


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
    """R-ER-02: a folder below a file cannot exist, which is reported as unavailable."""
    blocker = tmp_path / "a-file"
    blocker.write_bytes(b"x")

    with pytest.raises(AppError) as failure:
        MacFileSystem().make_folder(blocker / "Sample Channel")

    assert failure.value.code is ErrorCode.FOLDER_UNAVAILABLE
    assert failure.value.details["folder"] == str(blocker / "Sample Channel")


def test_a_folder_that_macos_denies_is_reported_as_denied(tmp_path: Path) -> None:
    """R-ER-02: a place the app may not write to is reported as permission denied."""
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


# --- files of videos (milestone M3)

PUBLISHED = 1_262_349_045
"""2010-01-01 12:30:45 UTC: a published time far from the time a file is written."""


def test_both_dates_of_a_file_are_set_to_the_published_time(
    subject: Subject, tmp_path: Path
) -> None:
    """R-DT-07: the creation and the modification date are set and read back the same."""
    put_files(subject, tmp_path, ["video.mkv"])

    subject.files.set_dates(tmp_path / "video.mkv", PUBLISHED)

    dates = subject.files.read_dates(tmp_path / "video.mkv")
    assert (dates.created, dates.modified) == (PUBLISHED, PUBLISHED)


def test_a_move_keeps_both_dates(subject: Subject, tmp_path: Path) -> None:
    """R-DT-10: moving a file leaves its dates equal to the published time."""
    put_files(subject, tmp_path / "tmp", ["a1B2c3D4e5F.mkv"])
    subject.files.set_dates(tmp_path / "tmp" / "a1B2c3D4e5F.mkv", PUBLISHED)

    moved = subject.files.move(tmp_path / "tmp" / "a1B2c3D4e5F.mkv", tmp_path / "Trailer.mkv")

    assert moved is True
    assert subject.files.exists(tmp_path / "tmp" / "a1B2c3D4e5F.mkv") is False
    dates = subject.files.read_dates(tmp_path / "Trailer.mkv")
    assert (dates.created, dates.modified) == (PUBLISHED, PUBLISHED)


def test_a_move_never_overwrites_a_file(subject: Subject, tmp_path: Path) -> None:
    """R-FN-05: a file that is there is never overwritten: the move does not happen."""
    put_files(subject, tmp_path, ["new.mkv", "Trailer.mkv"])

    moved = subject.files.move(tmp_path / "new.mkv", tmp_path / "Trailer.mkv")

    assert moved is False
    assert subject.files.exists(tmp_path / "new.mkv") is True
    assert subject.files.size_of(tmp_path / "Trailer.mkv") == 1


def test_two_files_swap_places_and_keep_who_they_are(subject: Subject, tmp_path: Path) -> None:
    """R-QL-06, D-093: a re-download swaps its new file in; each file keeps its identity."""
    put_files(subject, tmp_path, ["new.mkv"])
    subject.files.write_file(tmp_path / "old.mkv", b"old file", overwrite=False, inside=tmp_path)
    old = subject.files.file_id(tmp_path / "old.mkv")
    new = subject.files.file_id(tmp_path / "new.mkv")

    subject.files.swap(tmp_path / "new.mkv", tmp_path / "old.mkv")

    assert subject.files.file_id(tmp_path / "old.mkv") == new
    assert subject.files.file_id(tmp_path / "new.mkv") == old
    assert subject.files.size_of(tmp_path / "new.mkv") == len(b"old file")


def test_a_file_is_written_whole_and_replaced_only_when_asked(
    subject: Subject, tmp_path: Path
) -> None:
    """R-MD-02, R-QA-06: files of the hidden folder are written at once, and replaced on request."""
    target = tmp_path / ".yt-mirror" / "a1B2c3D4e5F.info.json"

    subject.files.make_folder(tmp_path)
    first = subject.files.write_file(target, b"{}", overwrite=False, inside=tmp_path)
    kept = subject.files.write_file(target, b'{"new": 1}', overwrite=False, inside=tmp_path)
    replaced = subject.files.write_file(target, b'{"new": 2}', overwrite=True, inside=tmp_path)

    assert (first, kept, replaced) == (True, False, True)
    assert subject.files.size_of(target) == len(b'{"new": 2}')
    assert subject.files.file_names(tmp_path / ".yt-mirror") == ["a1B2c3D4e5F.info.json"]


def test_nothing_is_written_into_a_folder_that_went_to_the_trash(
    subject: Subject, tmp_path: Path
) -> None:
    """R-CH-32, R-FI-05: a write that comes after a removal never brings its folder back."""
    folder = tmp_path / "Sample Channel"
    put_files(subject, folder, ["a.mkv"])
    put_files(subject, tmp_path / "elsewhere", ["b.mkv"])
    subject.files.trash(folder)
    job = "01JD0000000000000000000001"

    with pytest.raises(AppError) as written:
        subject.files.write_file(
            folder / ".yt-mirror" / "channel.json", b"{}", overwrite=True, inside=folder
        )
    with pytest.raises(AppError) as made:
        subject.files.make_folder(folder / ".yt-mirror" / "tmp" / job, inside=folder)
    with pytest.raises(AppError) as moved:
        subject.files.move(tmp_path / "elsewhere" / "b.mkv", folder / "b.mkv")

    assert written.value.code is ErrorCode.FOLDER_UNAVAILABLE
    assert made.value.code is ErrorCode.FOLDER_UNAVAILABLE
    assert moved.value.code is ErrorCode.FOLDER_UNAVAILABLE
    assert subject.files.folder_exists(folder) is False


def test_folders_inside_a_folder_that_is_there_are_created(
    subject: Subject, tmp_path: Path
) -> None:
    """R-FI-03: the hidden folder and a temp folder are created inside the channel folder."""
    folder = tmp_path / "Sample Channel"
    subject.files.make_folder(folder)
    work = folder / ".yt-mirror" / "tmp" / "01JD0000000000000000000001"

    subject.files.make_folder(work, inside=folder)

    assert subject.files.folder_exists(work) is True
    with pytest.raises(ValueError, match="not in the subpath"):
        subject.files.make_folder(tmp_path / "other", inside=folder)


def test_visible_names_leave_hidden_ones_out(subject: Subject, tmp_path: Path) -> None:
    """R-FN-05: the names of a folder that count for collisions are the visible ones."""
    put_files(subject, tmp_path, ["Trailer.mkv", "notes.txt", ".DS_Store"])

    assert subject.files.file_names(tmp_path) == ["Trailer.mkv", "notes.txt"]
    assert subject.files.file_names(tmp_path / "missing") == []


def test_a_file_goes_to_the_trash_and_not_away_for_good(subject: Subject, tmp_path: Path) -> None:
    """R-CH-32: deleting files of a channel moves them to the Trash."""
    put_files(subject, tmp_path / "Sample Channel", ["Trailer.mkv"])

    subject.files.trash(tmp_path / "Sample Channel" / "Trailer.mkv")

    assert subject.trashed == [tmp_path / "Sample Channel" / "Trailer.mkv"]
    assert subject.files.exists(tmp_path / "Sample Channel" / "Trailer.mkv") is False
    assert subject.files.folder_exists(tmp_path / "Sample Channel") is True


def test_only_the_temp_folder_of_a_job_is_ever_deleted(subject: Subject, tmp_path: Path) -> None:
    """R-FI-03: the temp folder of a job is deleted with what is in it, and nothing else ever is."""
    channel = tmp_path / "Sample Channel"
    job_folder = channel / ".yt-mirror" / "tmp" / "01JD0000000000000000000001"
    put_files(subject, job_folder, ["a1B2c3D4e5F.mkv.part"])
    put_files(subject, channel, ["Trailer.mkv"])

    subject.files.remove_temp_folder(job_folder)
    subject.files.remove_temp_folder(job_folder)
    for not_a_job in (channel, channel / ".yt-mirror", channel / ".yt-mirror" / "tmp"):
        with pytest.raises(ValueError, match="not the temp folder of a job"):
            subject.files.remove_temp_folder(not_a_job)

    assert subject.files.exists(job_folder) is False
    assert subject.files.exists(channel / "Trailer.mkv") is True


def test_a_file_is_shown_in_finder_and_played(subject: Subject, tmp_path: Path) -> None:
    """R-UI-10: "Show in Finder" reveals the file, "Play" opens it with the default app."""
    put_files(subject, tmp_path, ["Trailer.mkv"])

    subject.files.reveal(tmp_path / "Trailer.mkv")
    subject.files.open_file(tmp_path / "Trailer.mkv")

    assert subject.revealed == [tmp_path / "Trailer.mkv"]
    assert subject.played == [tmp_path / "Trailer.mkv"]


def test_a_missing_file_is_neither_shown_nor_played(subject: Subject, tmp_path: Path) -> None:
    """R-UI-10, R-MI-06: a file gone from its folder is FILE_MISSING; a folder gone, unavailable."""
    folder = tmp_path / "Channel"
    subject.files.make_folder(folder)
    for action in (subject.files.reveal, subject.files.open_file):
        with pytest.raises(AppError) as gone_file:
            action(folder / "gone.mkv")
        with pytest.raises(AppError) as gone_folder:
            action(tmp_path / "No folder" / "gone.mkv")
        assert gone_file.value.code is ErrorCode.FILE_MISSING
        assert gone_folder.value.code is ErrorCode.FOLDER_UNAVAILABLE
    assert subject.revealed == subject.played == []


def test_a_symlink_out_of_the_channel_folder_is_found(tmp_path: Path) -> None:
    """R-CH-32: a path that leads out of the channel folder through a symlink is told apart."""
    channel = tmp_path / "Sample Channel"
    elsewhere = tmp_path / "elsewhere"
    channel.mkdir()
    elsewhere.mkdir()
    (elsewhere / "precious.mkv").write_bytes(b"x")
    (channel / "Trailer.mkv").write_bytes(b"x")
    (channel / "link.mkv").symlink_to(elsewhere / "precious.mkv")
    (channel / "linked-folder").symlink_to(elsewhere)
    files = MacFileSystem()

    assert files.is_inside(channel / "Trailer.mkv", channel) is True
    assert files.is_inside(channel / "link.mkv", channel) is False
    assert files.is_inside(channel / "linked-folder" / "precious.mkv", channel) is False


def test_the_temp_folder_of_a_job_is_not_followed_through_a_symlink(tmp_path: Path) -> None:
    """R-FI-03: a temp folder that is a symlink is refused, so nothing outside is deleted."""
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    (elsewhere / "precious.mkv").write_bytes(b"x")
    temp = tmp_path / "Sample Channel" / ".yt-mirror" / "tmp"
    temp.mkdir(parents=True)
    (temp / "01JD0000000000000000000001").symlink_to(elsewhere)

    with pytest.raises(ValueError, match="not the temp folder of a job"):
        MacFileSystem().remove_temp_folder(temp / "01JD0000000000000000000001")

    assert (elsewhere / "precious.mkv").exists()


def test_dates_are_the_same_in_every_time_zone(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """R-DT-02, R-DT-07: the dates are stored as UTC moments, whatever the time zone of the Mac."""
    files = MacFileSystem()
    for zone in ("UTC", "Asia/Tehran", "America/St_Johns"):
        monkeypatch.setenv("TZ", zone)
        time.tzset()
        file = tmp_path / f"{zone.replace('/', '-')}.mkv"
        file.write_bytes(b"x")
        files.set_dates(file, PUBLISHED)
        assert files.read_dates(file) == FileDates(PUBLISHED, PUBLISHED)
    monkeypatch.undo()
    time.tzset()


def test_dates_that_macos_refuses_are_reported(tmp_path: Path) -> None:
    """R-DT-07: a file whose dates cannot be set fails with DATES_NOT_APPLIED."""
    with pytest.raises(AppError) as failure:
        MacFileSystem().set_dates(tmp_path / "missing.mkv", PUBLISHED)

    assert failure.value.code is ErrorCode.DATES_NOT_APPLIED
    assert failure.value.details["step"] == "creation date"


def test_a_file_that_appears_while_it_is_written_is_not_overwritten(tmp_path: Path) -> None:
    """R-FN-05: when the target appears during the write, it stays, and no temp file is left."""
    target = tmp_path / ".yt-mirror" / "cover.jpg"
    files = MacFileSystem()
    real_write = os.fdopen

    def write_and_race(handle: int, mode: str) -> object:
        target.write_bytes(b"theirs")
        return real_write(handle, mode)

    with pytest.MonkeyPatch.context() as patch:
        patch.setattr("ytmirror.adapters.filesystem_mac.os.fdopen", write_and_race)
        written = files.write_file(target, b"ours", overwrite=False, inside=tmp_path)

    assert written is False
    assert target.read_bytes() == b"theirs"
    assert sorted(path.name for path in target.parent.iterdir()) == ["cover.jpg"]


def test_failed_file_operations_get_their_error_codes(tmp_path: Path) -> None:
    """R-ER-02: a denied write, a missing file to move and a failed Trash have codes."""
    locked = tmp_path / "locked"
    locked.mkdir()
    locked.chmod(0o500)

    def refusing_trash(path: Path) -> None:
        raise OSError(1, "Operation not permitted", str(path))

    files = MacFileSystem(trash=refusing_trash)
    try:
        with pytest.raises(AppError) as denied:
            files.write_file(locked / "x.json", b"{}", overwrite=True, inside=locked)
    finally:
        locked.chmod(0o700)
    with pytest.raises(AppError) as missing:
        files.move(tmp_path / "gone.mkv", tmp_path / "there.mkv")
    with pytest.raises(AppError) as trash:
        files.trash(tmp_path / "locked")

    assert denied.value.code is ErrorCode.PERMISSION_DENIED
    assert missing.value.code is ErrorCode.FOLDER_UNAVAILABLE
    assert trash.value.code is ErrorCode.PERMISSION_DENIED
    assert files.size_of(tmp_path / "gone.mkv") == 0


def test_only_the_log_of_a_job_is_ever_deleted_from_the_log_folder(
    subject: Subject, tmp_path: Path
) -> None:
    """R-LG-01: a file named like a job log, in the jobs folder, and nothing else."""
    logs = tmp_path / "logs" / "jobs"
    job_log = "01JD0000000000000000000001.log"
    put_files(subject, logs, [job_log, "notes.txt"])
    put_files(subject, tmp_path / "logs", [job_log])

    subject.files.remove_job_log(logs / job_log)
    for not_a_job_log in (logs / "notes.txt", tmp_path / "logs" / job_log):
        with pytest.raises(ValueError, match="not the log of a job"):
            subject.files.remove_job_log(not_a_job_log)

    assert subject.files.file_names(logs) == ["notes.txt"]
    assert subject.files.file_names(tmp_path / "logs") == [job_log, "jobs"]


def test_a_temp_folder_whose_name_is_no_job_id_is_refused(subject: Subject, tmp_path: Path) -> None:
    """R-FI-03: only a folder named by a job ID is a temp folder; ".." or another name never is."""
    temp = tmp_path / "Sample Channel" / ".yt-mirror" / "tmp"
    put_files(subject, temp / "not-a-job", ["x.part"])

    for not_a_job in (temp / "not-a-job", temp / ".."):
        with pytest.raises(ValueError, match="not the temp folder of a job"):
            subject.files.remove_temp_folder(not_a_job)

    assert subject.files.exists(temp / "not-a-job" / "x.part")


def test_only_a_clear_not_found_in_a_folder_that_is_there_is_gone(
    subject: Subject, tmp_path: Path
) -> None:
    """R-MI-06: a file that is there, or whose folder is gone, is not "gone"."""
    folder = tmp_path / "Channel"
    put_files(subject, folder, ["Video.mkv"])

    assert subject.files.is_gone(folder / "Other.mkv")
    assert not subject.files.is_gone(folder / "Video.mkv")
    assert not subject.files.is_gone(tmp_path / "No folder" / "Video.mkv")


def test_a_file_in_a_folder_that_cannot_be_searched_is_not_gone(tmp_path: Path) -> None:
    """R-MI-06: without permission to look, a file is never taken for missing."""
    folder = tmp_path / "Locked"
    folder.mkdir()
    (folder / "Video.mkv").write_bytes(b"x")
    folder.chmod(0o600)
    try:
        assert not MacFileSystem().is_gone(folder / "Video.mkv")
        assert not MacFileSystem().is_gone(folder / "Other.mkv")
    finally:
        folder.chmod(0o700)


def test_a_test_can_give_every_disk_its_free_space(tmp_path: Path) -> None:
    """R-QU-10: the disk space guard is tested with a free space of the test's choosing."""
    files = MacFileSystem(free_bytes=lambda: 9_000_000_000)

    assert files.disk_of(tmp_path).free_bytes == 9_000_000_000
    assert MacFileSystem(free_bytes=lambda: None).disk_of(tmp_path).free_bytes > 0
