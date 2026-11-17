"""Date repair and the rename after a new title, on real files of macOS (TESTING section 5).

Everything is real but YouTube: the container, the database, the file
system of macOS, ffmpeg and ffprobe. Run in two time zones, as CI runs the
whole suite in both.
"""

import calendar
import dataclasses
import json
import os
import time
from collections.abc import Iterator
from pathlib import Path

import pytest

from tests.fixtures.media import ffmpeg_dir
from ytmirror.adapters.filesystem_mac import MacFileSystem
from ytmirror.app.config import AppPaths
from ytmirror.app.container import Container, build_container
from ytmirror.core.channels import CheckKind
from ytmirror.services.channels import NewChannel

FULLWIDTH_COLON = chr(0xFF1A)
"""How a colon of a title is stored in a file name (R-FN-02)."""

pytestmark = pytest.mark.media

CHANNEL_ID = "UCrepairrepairrepairrep1"
VIDEO_ID = "ren00000001"
PUBLISHED = calendar.timegm(time.strptime("2026-03-29T00:30:00Z", "%Y-%m-%dT%H:%M:%SZ"))
"""Shortly after the switch to summer time in Europe, a moment that time zones disagree on."""


@pytest.fixture(params=["UTC", "Asia/Tehran"])
def zone(request: pytest.FixtureRequest) -> Iterator[str]:
    """Run in a time zone (TESTING rule 4)."""
    before = os.environ.get("TZ")
    os.environ["TZ"] = request.param
    time.tzset()
    yield request.param
    if before is None:
        os.environ.pop("TZ", None)
    else:
        os.environ["TZ"] = before
    time.tzset()


@pytest.fixture
def app(paths: AppPaths, tmp_path: Path) -> Container:
    """The real container with a fake YouTube whose one video changes its title."""
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
    container = build_container(
        dataclasses.replace(paths, fake_youtube=world, tool_dir=ffmpeg_dir().parent),
        files=MacFileSystem(trash=lambda path: None),
    )
    container.schema.bring_up_to_date()
    return container


def synced_folder(app: Container) -> Path:
    """Add the channel, list it and mirror its video. Returns the channel folder."""
    app.channels.add(NewChannel(app.channels.lookup("@repairchannel").facts.channel_id))
    assert app.catalogue.work_once() is True
    app.downloader.mirror([VIDEO_ID])
    assert app.downloader.work_once() is True
    view = app.views.of(CHANNEL_ID)
    assert view is not None
    return Path(view.folder)


def dates(file: Path) -> tuple[int, int]:
    """Return the creation and modification date of a file, as Finder shows them."""
    found = file.stat()
    return int(found.st_birthtime), int(found.st_mtime)


def test_a_new_title_renames_the_real_file_and_keeps_its_dates(app: Container, zone: str) -> None:
    """R-FN-06, R-DT-10: after the check the file has the new title and the published dates."""
    folder = synced_folder(app)
    assert dates(folder / "First title.mkv") == (PUBLISHED, PUBLISHED)

    app.catalogue.request_check(CHANNEL_ID, CheckKind.QUICK)
    assert app.catalogue.work_once() is True

    renamed = folder / f"Second{FULLWIDTH_COLON} title.mkv"
    assert sorted(entry.name for entry in folder.iterdir()) == [".yt-mirror", renamed.name]
    assert dates(renamed) == (PUBLISHED, PUBLISHED)
    video = app.videos.video(VIDEO_ID)
    assert video is not None
    assert video.file_name == renamed.name


def test_a_check_repairs_real_file_dates_that_were_changed(app: Container, zone: str) -> None:
    """R-DT-09, R-CH-28: dates changed outside the app are set again at the next check."""
    folder = synced_folder(app)
    app.catalogue.request_check(CHANNEL_ID, CheckKind.QUICK)
    assert app.catalogue.work_once() is True
    file = folder / f"Second{FULLWIDTH_COLON} title.mkv"
    MacFileSystem().set_dates(file, PUBLISHED - 86_400)
    os.utime(file, (PUBLISHED + 999, PUBLISHED + 999))

    app.catalogue.request_check(CHANNEL_ID, CheckKind.QUICK)
    assert app.catalogue.work_once() is True

    assert dates(file) == (PUBLISHED, PUBLISHED)
