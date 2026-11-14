"""Tests of ``ytmirror.app.bundle``: the app bundle that is built on the user's Mac."""

import io
import json
import os
import plistlib
import stat
import subprocess
import sys
from dataclasses import replace
from pathlib import Path

import pytest

from tests.fixtures.fakes.image_renderer import FakeImageRenderer
from ytmirror import __version__
from ytmirror.app.bundle import (
    BundlePlan,
    build_bundle,
    ensure_bundle,
    is_current,
    main,
    plan_bundle,
)
from ytmirror.app.config import AppPaths
from ytmirror.core.icon import ICON_PIXEL_SIZES
from ytmirror.core.models import AppIdentity

INSTALLED = AppIdentity("yt-mirror", "io.github.mderis.yt-mirror")
CLONE = AppIdentity("yt-mirror (dev)", "io.github.mderis.yt-mirror.dev")
TOKENS = """
[data-theme='light'] {
  --ytm-color-accent: #1f5fd1;
  --ytm-color-on-accent: #ffffff;
}
"""
ICON = '<svg viewBox="0 0 8 8"><rect fill="var(--ytm-color-accent)"/></svg>'


@pytest.fixture
def plan(tmp_path: Path) -> BundlePlan:
    """A plan whose inputs are small files in a temp folder."""
    environment = tmp_path / "home" / "tools" / "venv"
    (environment / "bin").mkdir(parents=True)
    (environment / "lib").mkdir()
    (environment / "bin" / "python").write_text("#!/bin/sh\n", encoding="utf-8")
    (environment / "pyvenv.cfg").write_text("home = /somewhere/bin\n", encoding="utf-8")
    design = tmp_path / "code" / "design"
    design.mkdir(parents=True)
    (design / "icon.svg").write_text(ICON, encoding="utf-8")
    (design / "tokens.css").write_text(TOKENS, encoding="utf-8")
    return BundlePlan(
        identity=INSTALLED,
        version="1.2.3",
        bundle_dir=tmp_path / "home" / "tools" / "yt-mirror.app",
        home_dir=tmp_path / "home",
        environment_dir=environment,
        icon_source=design / "icon.svg",
        tokens_file=design / "tokens.css",
    )


def info_of(plan: BundlePlan) -> dict[str, object]:
    """Return the Info.plist of the built bundle."""
    with (plan.bundle_dir / "Contents" / "Info.plist").open("rb") as file:
        return plistlib.load(file)


def test_the_bundle_says_who_the_app_is(plan: BundlePlan) -> None:
    """R-NA-02: a real app bundle with an Info.plist, a bundle identifier and an icon."""
    build_bundle(plan, FakeImageRenderer())

    info = info_of(plan)
    assert info["CFBundleName"] == "yt-mirror"
    assert info["CFBundleDisplayName"] == "yt-mirror"
    assert info["CFBundleIdentifier"] == "io.github.mderis.yt-mirror"
    assert info["CFBundleShortVersionString"] == "1.2.3"
    assert info["CFBundlePackageType"] == "APPL"
    assert info["LSMinimumSystemVersion"] == "15.0"
    executable = plan.bundle_dir / "Contents" / "MacOS" / str(info["CFBundleExecutable"])
    icon = plan.bundle_dir / "Contents" / "Resources" / f"{info['CFBundleIconFile']}.icns"
    assert os.access(executable, os.X_OK)
    assert icon.read_bytes()[:4] == b"icns"


def test_a_clone_gets_a_bundle_of_its_own_name_and_identifier(plan: BundlePlan) -> None:
    """R-NA-01, R-NA-02: a clone is "yt-mirror (dev)" with another bundle identifier."""
    clone = replace(
        plan, identity=CLONE, bundle_dir=plan.bundle_dir.with_name("yt-mirror (dev).app")
    )

    build_bundle(clone, FakeImageRenderer())

    info = info_of(clone)
    assert info["CFBundleName"] == "yt-mirror (dev)"
    assert info["CFBundleIdentifier"] == "io.github.mderis.yt-mirror.dev"
    assert clone.program.name == "yt-mirror (dev)"
    assert clone.program.is_symlink()


def test_the_icon_is_drawn_from_the_one_source_file_in_the_light_colours(plan: BundlePlan) -> None:
    """R-NA-02: the icon is generated from the single icon source file, at every size."""
    renderer = FakeImageRenderer()

    build_bundle(plan, renderer)

    assert sorted(size for _svg, size in renderer.drawn) == list(ICON_PIXEL_SIZES)
    assert {svg for svg, _size in renderer.drawn} == {
        '<svg viewBox="0 0 8 8"><rect fill="#1f5fd1"/></svg>'
    }


def test_the_app_runs_inside_the_bundle_under_its_own_name(plan: BundlePlan) -> None:
    """R-NA-01: the process is the app's Python, reached through a link named after the app.

    macOS takes the identity of a process from the place of its program
    file, so the app never appears as "Python" (docs/DECISIONS.md D-048).
    """
    build_bundle(plan, FakeImageRenderer())

    contents = plan.bundle_dir / "Contents"
    assert plan.program == contents / "MacOS" / "yt-mirror"
    assert plan.program.readlink() == plan.environment_dir / "bin" / "python"
    assert (contents / "lib").readlink() == plan.environment_dir / "lib"
    assert (contents / "pyvenv.cfg").read_text(encoding="utf-8") == "home = /somewhere/bin\n"
    script = plan.launcher.read_text(encoding="utf-8")
    assert script.startswith("#!/bin/sh\n")
    assert f"export YTM_HOME='{plan.home_dir}'\n" in script
    assert script.endswith(f"exec '{plan.program}' -m ytmirror.app.main \"$@\"\n")
    assert stat.S_IMODE(plan.launcher.stat().st_mode) == 0o755


def test_the_launcher_starts_the_program_with_the_arguments_it_was_given(
    plan: BundlePlan, tmp_path: Path
) -> None:
    """R-NA-02: ``./start`` starts the app through the bundle, flags included."""
    spaced = replace(
        plan,
        identity=CLONE,
        bundle_dir=tmp_path / "it's here" / "yt-mirror (dev).app",
        home_dir=tmp_path / "it's here",
    )
    spaced.bundle_dir.parent.mkdir()
    (plan.environment_dir / "bin" / "python").write_text(
        '#!/bin/sh\necho "home=$YTM_HOME"\nfor a in "$@"; do echo "arg=$a"; done\n',
        encoding="utf-8",
    )
    (plan.environment_dir / "bin" / "python").chmod(0o755)
    build_bundle(spaced, FakeImageRenderer())

    result = subprocess.run(
        [str(spaced.launcher), "--debug", "two words"],
        capture_output=True,
        text=True,
        check=True,
        env={"PATH": "/usr/bin:/bin"},
    )

    assert result.stdout.splitlines() == [
        f"home={tmp_path / "it's here"}",
        "arg=-m",
        "arg=ytmirror.app.main",
        "arg=--debug",
        "arg=two words",
    ]


def test_a_current_bundle_is_left_alone(plan: BundlePlan) -> None:
    """R-NA-02: the bundle is built once, not at every start."""
    renderer = FakeImageRenderer()

    assert ensure_bundle(plan, renderer) is True
    drawn = len(renderer.drawn)
    built_at = plan.launcher.stat().st_mtime_ns

    assert ensure_bundle(plan, renderer) is False
    assert len(renderer.drawn) == drawn
    assert plan.launcher.stat().st_mtime_ns == built_at
    assert is_current(plan)


@pytest.mark.parametrize(
    "what_changed", ["version", "icon", "tokens", "environment", "identity", "home"]
)
def test_the_bundle_is_rebuilt_when_something_it_was_built_from_changed(
    plan: BundlePlan, what_changed: str
) -> None:
    """R-IN-05, R-NA-02: a moved folder, a new version or a new icon rebuild the bundle."""
    ensure_bundle(plan, FakeImageRenderer())
    after = plan
    if what_changed == "version":
        after = replace(plan, version="1.2.4")
    elif what_changed == "icon":
        plan.icon_source.write_text(ICON.replace("8 8", "9 9"), encoding="utf-8")
    elif what_changed == "tokens":
        plan.tokens_file.write_text(TOKENS.replace("#1f5fd1", "#123456"), encoding="utf-8")
    elif what_changed == "environment":
        (plan.environment_dir / "pyvenv.cfg").write_text("home = /moved/bin\n", encoding="utf-8")
    elif what_changed == "identity":
        after = replace(plan, identity=AppIdentity("yt-mirror", "io.github.mderis.other"))
    else:
        after = replace(plan, home_dir=plan.home_dir.with_name("moved"))

    assert not is_current(after)
    assert ensure_bundle(after, FakeImageRenderer()) is True
    assert is_current(after)
    assert info_of(after)["CFBundleShortVersionString"] == after.version


def test_a_rebuild_leaves_nothing_of_the_old_bundle(plan: BundlePlan) -> None:
    """R-NA-02: the bundle is replaced as a whole, so nothing stale stays inside it."""
    build_bundle(plan, FakeImageRenderer())
    stale = plan.bundle_dir / "Contents" / "Resources" / "old-icon.icns"
    stale.write_bytes(b"old")

    build_bundle(replace(plan, version="2.0.0"), FakeImageRenderer())

    assert not stale.exists()
    assert not plan.bundle_dir.with_name("yt-mirror.app.building").exists()


def test_a_build_that_was_interrupted_does_not_count_as_a_bundle(plan: BundlePlan) -> None:
    """R-NA-02: leftovers of an interrupted build are cleared, not used."""
    leftover = plan.bundle_dir.with_name("yt-mirror.app.building")
    (leftover / "Contents").mkdir(parents=True)
    (leftover / "Contents" / "junk").write_text("x", encoding="utf-8")
    plan.bundle_dir.mkdir(parents=True)

    assert not is_current(plan)
    assert ensure_bundle(plan, FakeImageRenderer()) is True

    assert not leftover.exists()
    assert is_current(plan)
    assert json.loads(plan.stamp_file.read_text(encoding="utf-8"))["version"] == "1.2.3"


def test_the_plan_of_a_start_puts_the_bundle_into_the_tools_folder(paths: AppPaths) -> None:
    """R-NA-02: ``./start`` builds the bundle inside the app folder, from the brand icon."""
    plan = plan_bundle(paths, CLONE, "0.9.0", Path("/env"))

    assert plan.bundle_dir == paths.home_dir / "tools" / "yt-mirror (dev).app"
    assert plan.launcher == plan.bundle_dir / "Contents" / "MacOS" / "launch"
    assert plan.icon_source == paths.code_root / "frontend/src/design/brand/icon.svg"
    assert plan.tokens_file == paths.code_root / "frontend/src/design/tokens.css"
    assert plan.environment_dir == Path("/env")


def test_run_as_a_program_it_builds_the_real_bundle_and_prints_its_launcher(
    tmp_path: Path,
) -> None:
    """R-NA-02: one call builds the bundle with the real icon and says how to start it."""
    out = io.StringIO()

    exit_code = main([], {"YTM_HOME": str(tmp_path)}, out)

    launcher = Path(out.getvalue().strip())
    bundle = tmp_path / "tools" / "yt-mirror (dev).app"
    assert exit_code == 0
    assert launcher == bundle / "Contents" / "MacOS" / "launch"
    with (bundle / "Contents" / "Info.plist").open("rb") as file:
        info = plistlib.load(file)
    assert info["CFBundleIdentifier"] == "io.github.mderis.yt-mirror.dev"
    assert info["CFBundleShortVersionString"] == __version__
    assert (bundle / "Contents" / "MacOS" / "yt-mirror (dev)").resolve() == Path(
        sys.executable
    ).resolve()
    assert (bundle / "Contents" / "Resources" / "app.icns").stat().st_size > 10_000
