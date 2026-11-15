"""The composition root: builds the adapters and the services.

This is the only module that knows which adapter implements which port
(docs/ARCHITECTURE.md section 4, rule 6). Tests build the same container
and pass fakes for the ports they want to control.

Tests: backend/tests/integration/app/test_container.py
"""

import os
import threading
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from ulid import ULID

from ytmirror import __version__
from ytmirror.adapters.child_processes_mac import MacChildProcesses
from ytmirror.adapters.db.app_meta_repository import SqlAppMetaRepository
from ytmirror.adapters.db.catalogue_repository import SqlCatalogueRepository
from ytmirror.adapters.db.engine import create_db_engine
from ytmirror.adapters.db.job_repository import SqlJobRepository
from ytmirror.adapters.db.schema import AlembicSchema
from ytmirror.adapters.db.settings_repository import SqlSettingsRepository
from ytmirror.adapters.filesystem_mac import MacFileSystem
from ytmirror.adapters.fixture_youtube import FixtureYouTube
from ytmirror.adapters.folder_picker_webview import WebviewFolderPicker
from ytmirror.adapters.image_cache import FileImageCache
from ytmirror.adapters.image_renderer_mac import MacImageRenderer
from ytmirror.adapters.media_tools import FfprobeMediaTools
from ytmirror.adapters.native_app_mac import MacNativeApp
from ytmirror.adapters.system_clock import SystemClock
from ytmirror.adapters.system_probe import MacSystemProbe
from ytmirror.adapters.tool_box import LocalToolBox
from ytmirror.adapters.ytdlp_gateway import GatewayTools, YtDlpGateway
from ytmirror.app.config import AppPaths, detect_install_kind
from ytmirror.core.channels import CheckKind
from ytmirror.core.models import AppInfo, ToolName
from ytmirror.core.toolchain import parse_manifest
from ytmirror.ports.child_processes import ChildProcesses
from ytmirror.ports.clock import Clock
from ytmirror.ports.file_system import JOB_LOG_FOLDER, FileSystem
from ytmirror.ports.folder_picker import FolderPicker
from ytmirror.ports.image_renderer import ImageRenderer
from ytmirror.ports.native_app import NativeApp
from ytmirror.ports.system_probe import SystemProbe
from ytmirror.ports.tool_box import ToolBox
from ytmirror.ports.youtube_gateway import YouTubeGateway
from ytmirror.services.catalogue import CatalogueService
from ytmirror.services.channel_views import ChannelViews
from ytmirror.services.channels import ChannelsService
from ytmirror.services.diagnostics import DiagnosticsService
from ytmirror.services.download_state import DownloadState
from ytmirror.services.downloader import DownloaderService
from ytmirror.services.events import EventBus
from ytmirror.services.job_logs import JobLogsService
from ytmirror.services.schema import SchemaService
from ytmirror.services.settings import SettingsService
from ytmirror.services.state import StateService
from ytmirror.services.thumbnails import ThumbnailService
from ytmirror.services.toolchain import ToolchainService
from ytmirror.services.youtube_access import YouTubeAccess


@dataclass(frozen=True, slots=True)
class Container:
    """Everything the entry point and the HTTP layer need.

    Attributes:
        info: Facts about this installation.
        clock: The source of time.
        probe: Read-only access to facts about the Mac.
        native: The running app as macOS sees it: menu bar, name, quitting.
        images: Draws the app icon from its source file.
        schema: Brings the database up to date.
        settings: Reads the general settings.
        diagnostics: Health and the environment report.
        events: The bus on which services publish changes for the interface.
        toolchain: Knows the tools the app needs and installs them.
        youtube: Everything the app asks of YouTube, with the pause of the whole app.
        views: The channels as the interface shows them.
        catalogue: Runs the checks of channels.
        thumbnails: Caches the pictures of the catalogue.
        channels: Looks channels up, adds, pauses and removes them.
        state: The snapshot of the app for the window.
        videos: Reads the catalogue of a channel.
        downloader: Downloads videos, one job after another (milestone M3).
        job_logs: Deletes the logs of jobs that are no longer kept.
    """

    info: AppInfo
    clock: Clock
    probe: SystemProbe
    native: NativeApp
    images: ImageRenderer
    schema: SchemaService
    settings: SettingsService
    diagnostics: DiagnosticsService
    events: EventBus
    toolchain: ToolchainService
    youtube: YouTubeAccess
    views: ChannelViews
    catalogue: CatalogueService
    thumbnails: ThumbnailService
    channels: ChannelsService
    state: StateService
    videos: SqlCatalogueRepository
    downloader: DownloaderService
    job_logs: JobLogsService


def _in_a_thread(work: Callable[[], None]) -> None:
    """Run work in the background. It ends with the app at the latest."""
    threading.Thread(target=work, name="background", daemon=True).start()


def _later(delay_s: float, work: Callable[[], None]) -> None:
    """Run work after a number of seconds, unless the app ended before."""
    timer = threading.Timer(delay_s, work)
    timer.daemon = True
    timer.start()


def build_container(
    paths: AppPaths,
    *,
    clock: Clock | None = None,
    probe: SystemProbe | None = None,
    native: NativeApp | None = None,
    images: ImageRenderer | None = None,
    tool_box: ToolBox | None = None,
    gateway: YouTubeGateway | None = None,
    files: FileSystem | None = None,
    picker: FolderPicker | None = None,
) -> Container:
    """Build the adapters and services for one run.

    Nothing is opened or created here: the database file appears when the
    schema is first brought up to date.

    Args:
        paths: Where the parts of this installation are.
        clock: A clock to use instead of the system clock. For tests.
        probe: A system probe to use instead of the real one. For tests.
        native: A stand-in for the app as macOS sees it. For tests.
        images: A stand-in for the image renderer. For tests.
        tool_box: A stand-in for the folder of downloaded tools. For tests.
        gateway: A stand-in for YouTube. For tests. Without one, the fake YouTube
            is used when ``paths.fake_youtube`` names a folder, otherwise the real one.
        files: A stand-in for the folders of this Mac. For tests.
        picker: A stand-in for the folder dialog of macOS. For tests.

    Returns:
        The wired container.
    """
    used_clock = clock if clock is not None else SystemClock()
    used_probe = probe if probe is not None else MacSystemProbe()
    info = AppInfo(
        version=__version__,
        install_kind=detect_install_kind(paths.code_root),
        home_dir=paths.home_dir,
        data_dir=paths.data_dir,
        database_file=paths.database_file,
        frontend_dir=paths.frontend_dir,
        uv_executable=paths.uv_executable,
    )
    engine = create_db_engine(paths.database_file)
    schema = AlembicSchema(engine, paths.database_file)
    events = EventBus()
    used_tool_box = tool_box if tool_box is not None else LocalToolBox(paths.tool_dir)
    toolchain = ToolchainService(
        specs=parse_manifest(paths.tool_manifest.read_text(encoding="utf-8")),
        tool_box=used_tool_box,
        probe=used_probe,
        meta=SqlAppMetaRepository(engine, used_clock),
        events=events,
        clock=used_clock,
        run_in_background=_in_a_thread,
        only_source=paths.only_tool_source,
    )
    settings = SettingsService(SqlSettingsRepository(engine, used_clock), paths.default_library)
    repository = SqlCatalogueRepository(engine, used_clock)
    used_files = files if files is not None else _file_system(paths)
    used_children = MacChildProcesses()
    used_picker = picker if picker is not None else WebviewFolderPicker()
    youtube = YouTubeAccess(
        _gateway(paths, used_clock, gateway, used_tool_box), used_clock, events, _later
    )
    downloads = DownloadState()
    views = ChannelViews(
        repository,
        settings,
        used_clock,
        events,
        youtube_paused=lambda: youtube.pause() is not None,
        downloads=downloads,
    )
    thumbnails = ThumbnailService(
        repository, youtube, FileImageCache(paths.cache_dir), views, _in_a_thread
    )
    catalogue = CatalogueService(
        repository,
        youtube,
        views,
        used_clock,
        _in_a_thread,
        after_check=lambda channel_id, kind: _after_check(channel_id, kind),
    )

    def _after_check(channel_id: str, kind: CheckKind) -> None:
        thumbnails.fill(channel_id, renew_avatar=kind is CheckKind.FULL)
        # A check takes over the title and the handle of the channel (R-CH-12, R-FI-05).
        channels.write_channel_file(channel_id)

    jobs = SqlJobRepository(engine, used_clock)
    media = FfprobeMediaTools(used_tool_box.program_path(ToolName.FFMPEG, "ffprobe"))
    downloader = DownloaderService(
        repository=repository,
        jobs=jobs,
        youtube=youtube,
        files=used_files,
        media=media,
        settings=settings,
        views=views,
        state=downloads,
        events=events,
        clock=used_clock,
        new_job_id=lambda: str(ULID()),
        job_logs=paths.logs_dir / JOB_LOG_FOLDER,
        run_in_background=_in_a_thread,
        stop_tools=lambda: _stop_tools(used_children, used_tool_box),
    )
    channels = ChannelsService(
        repository,
        youtube,
        used_files,
        used_picker,
        settings,
        views,
        catalogue,
        thumbnails,
        used_clock,
        _in_a_thread,
        close_downloads=downloader.channel_closed,
        media=media,
    )
    state = StateService(
        views, settings, used_files, used_picker, SqlAppMetaRepository(engine, used_clock), youtube
    )
    return Container(
        info=info,
        clock=used_clock,
        probe=used_probe,
        native=native if native is not None else MacNativeApp(),
        images=images if images is not None else MacImageRenderer(),
        schema=SchemaService(schema, used_clock, paths.data_dir / BACKUP_FOLDER),
        settings=settings,
        diagnostics=DiagnosticsService(info, schema, used_probe, toolchain),
        events=events,
        toolchain=toolchain,
        youtube=youtube,
        views=views,
        catalogue=catalogue,
        thumbnails=thumbnails,
        channels=channels,
        state=state,
        videos=repository,
        downloader=downloader,
        job_logs=JobLogsService(
            paths.logs_dir / JOB_LOG_FOLDER, repository, jobs, used_files, used_clock
        ),
    )


BACKUP_FOLDER = "backups"
"""The folder in ``data/`` of the copies of the database made before migrations."""

TOOL_STOP_WAIT_S = 1.0
"""How long a tool the app started may take to end at quit before it is killed."""


def _stop_tools(children: ChildProcesses, tools: ToolBox) -> None:
    """Stop the ffmpeg, ffprobe and Deno the app started, when it quits (R-PL-13)."""
    children.stop(
        [
            tools.program_path(ToolName.FFMPEG, "ffmpeg"),
            tools.program_path(ToolName.FFMPEG, "ffprobe"),
            tools.program_path(ToolName.DENO, "deno"),
        ],
        wait_s=TOOL_STOP_WAIT_S,
    )


def _file_system(paths: AppPaths) -> FileSystem:
    """Return the file system of macOS, with a folder of its own as the Trash when tests ask."""
    trash_dir = paths.trash_dir
    if trash_dir is None:
        return MacFileSystem()

    def to_folder(path: Path) -> None:
        trash_dir.mkdir(parents=True, exist_ok=True)
        target = trash_dir / path.name
        number = 1
        while target.exists():
            number += 1
            target = trash_dir / f"{path.name} {number}"
        path.rename(target)

    return MacFileSystem(trash=to_folder)


def _gateway(
    paths: AppPaths, clock: Clock, given: YouTubeGateway | None, tools: ToolBox
) -> YouTubeGateway:
    """Return the gateway to YouTube: a given one, the fake from files, or the real one.

    Both write video files with the ffmpeg of the app folder. Deno keeps its
    cache in the app folder too, not in the user's Library (R-PL-15, D-078).
    """
    if given is not None:
        return given
    ffmpeg = tools.program_path(ToolName.FFMPEG, "ffmpeg")
    if paths.fake_youtube is not None:
        return FixtureYouTube(paths.fake_youtube, ffmpeg=ffmpeg)
    os.environ["DENO_DIR"] = str(paths.cache_dir / "deno")
    return YtDlpGateway(
        clock,
        tools=GatewayTools(
            ffmpeg_folder=ffmpeg.parent, deno=tools.program_path(ToolName.DENO, "deno")
        ),
    )
