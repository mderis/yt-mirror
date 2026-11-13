"""The composition root: builds the adapters and the services.

This is the only module that knows which adapter implements which port
(docs/ARCHITECTURE.md section 4, rule 6). Tests build the same container
and pass fakes for the ports they want to control.

Tests: backend/tests/integration/app/test_container.py
"""

from dataclasses import dataclass

from ytmirror import __version__
from ytmirror.adapters.db.engine import create_db_engine
from ytmirror.adapters.db.schema import AlembicSchema
from ytmirror.adapters.db.settings_repository import SqlSettingsRepository
from ytmirror.adapters.system_clock import SystemClock
from ytmirror.adapters.system_probe import MacSystemProbe
from ytmirror.app.config import AppPaths, detect_install_kind
from ytmirror.core.models import AppInfo
from ytmirror.ports.clock import Clock
from ytmirror.ports.system_probe import SystemProbe
from ytmirror.services.diagnostics import DiagnosticsService
from ytmirror.services.schema import SchemaService
from ytmirror.services.settings import SettingsService


@dataclass(frozen=True, slots=True)
class Container:
    """Everything the entry point and the HTTP layer need.

    Attributes:
        info: Facts about this installation.
        clock: The source of time.
        probe: Read-only access to facts about the Mac.
        schema: Brings the database up to date.
        settings: Reads the general settings.
        diagnostics: Health and the environment report.
    """

    info: AppInfo
    clock: Clock
    probe: SystemProbe
    schema: SchemaService
    settings: SettingsService
    diagnostics: DiagnosticsService


def build_container(
    paths: AppPaths, *, clock: Clock | None = None, probe: SystemProbe | None = None
) -> Container:
    """Build the adapters and services for one run.

    Nothing is opened or created here: the database file appears when the
    schema is first brought up to date.

    Args:
        paths: Where the parts of this installation are.
        clock: A clock to use instead of the system clock. For tests.
        probe: A system probe to use instead of the real one. For tests.

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
    return Container(
        info=info,
        clock=used_clock,
        probe=used_probe,
        schema=SchemaService(schema, used_clock),
        settings=SettingsService(SqlSettingsRepository(engine, used_clock)),
        diagnostics=DiagnosticsService(info, schema, used_probe),
    )
