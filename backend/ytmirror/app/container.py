"""The composition root: builds the adapters and the services.

This is the only module that knows which adapter implements which port
(docs/ARCHITECTURE.md section 4, rule 6). Tests build the same container
and pass fakes for the ports they want to control.

Tests: backend/tests/integration/app/test_container.py
"""

import threading
from collections.abc import Callable
from dataclasses import dataclass

from ytmirror import __version__
from ytmirror.adapters.db.app_meta_repository import SqlAppMetaRepository
from ytmirror.adapters.db.engine import create_db_engine
from ytmirror.adapters.db.schema import AlembicSchema
from ytmirror.adapters.db.settings_repository import SqlSettingsRepository
from ytmirror.adapters.image_renderer_mac import MacImageRenderer
from ytmirror.adapters.native_app_mac import MacNativeApp
from ytmirror.adapters.system_clock import SystemClock
from ytmirror.adapters.system_probe import MacSystemProbe
from ytmirror.adapters.tool_box import LocalToolBox
from ytmirror.app.config import AppPaths, detect_install_kind
from ytmirror.core.models import AppInfo
from ytmirror.core.toolchain import parse_manifest
from ytmirror.ports.clock import Clock
from ytmirror.ports.image_renderer import ImageRenderer
from ytmirror.ports.native_app import NativeApp
from ytmirror.ports.system_probe import SystemProbe
from ytmirror.ports.tool_box import ToolBox
from ytmirror.services.diagnostics import DiagnosticsService
from ytmirror.services.events import EventBus
from ytmirror.services.schema import SchemaService
from ytmirror.services.settings import SettingsService
from ytmirror.services.toolchain import ToolchainService


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


def _in_a_thread(work: Callable[[], None]) -> None:
    """Run work in the background. It ends with the app at the latest."""
    threading.Thread(target=work, name="background", daemon=True).start()


def build_container(
    paths: AppPaths,
    *,
    clock: Clock | None = None,
    probe: SystemProbe | None = None,
    native: NativeApp | None = None,
    images: ImageRenderer | None = None,
    tool_box: ToolBox | None = None,
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
    return Container(
        info=info,
        clock=used_clock,
        probe=used_probe,
        native=native if native is not None else MacNativeApp(),
        images=images if images is not None else MacImageRenderer(),
        schema=SchemaService(schema, used_clock),
        settings=SettingsService(SqlSettingsRepository(engine, used_clock), paths.default_library),
        diagnostics=DiagnosticsService(info, schema, used_probe, toolchain),
        events=events,
        toolchain=toolchain,
    )
