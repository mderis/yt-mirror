"""Tests of ``ytmirror.app.container``: the real wiring."""

from tests.fixtures.fakes.clock import FakeClock
from tests.fixtures.fakes.native_app import FakeNativeApp
from tests.fixtures.fakes.system_probe import FakeSystemProbe
from ytmirror import __version__
from ytmirror.adapters.native_app_mac import MacNativeApp
from ytmirror.adapters.system_clock import SystemClock
from ytmirror.adapters.system_probe import MacSystemProbe
from ytmirror.app.config import AppPaths
from ytmirror.app.container import build_container
from ytmirror.core.models import InstallKind, Settings


def test_building_the_container_creates_no_files(paths: AppPaths) -> None:
    """R-QA-07: wiring the app has no side effects, so ``--doctor`` is safe to run."""
    build_container(paths)

    assert not paths.data_dir.exists()


def test_the_wired_services_work_together_on_a_real_database(paths: AppPaths) -> None:
    """R-QA-07: migrations, settings and health run against the real adapters."""
    container = build_container(paths)

    version = container.schema.bring_up_to_date()

    assert version == "0002"
    assert paths.database_file.is_file()
    assert container.settings.current() == Settings()
    assert container.diagnostics.health().schema_version == "0002"
    assert container.diagnostics.health().version == __version__


def test_the_container_describes_the_installation(paths: AppPaths) -> None:
    """infra: paths and install kind are known to the app, for ``app.config`` and the report."""
    (paths.code_root / ".git").mkdir()

    info = build_container(paths).info

    assert info.install_kind is InstallKind.CLONE
    assert info.data_dir == paths.data_dir
    assert info.database_file == paths.database_file
    assert info.frontend_dir == paths.frontend_dir
    assert info.uv_executable == paths.uv_executable


def test_real_adapters_are_used_unless_a_test_passes_fakes(paths: AppPaths) -> None:
    """infra: tests build the same container with fakes (ARCHITECTURE section 4, rule 6)."""
    clock = FakeClock()
    probe = FakeSystemProbe()
    native = FakeNativeApp()

    real = build_container(paths)
    faked = build_container(paths, clock=clock, probe=probe, native=native)

    assert isinstance(real.clock, SystemClock)
    assert isinstance(real.probe, MacSystemProbe)
    assert isinstance(real.native, MacNativeApp)
    assert faked.clock is clock
    assert faked.probe is probe
    assert faked.native is native
