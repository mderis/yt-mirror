"""Builds the macOS app bundle on the user's Mac (docs/ARCHITECTURE.md section 7.10).

Implements R-NA-02 and the bundle side of R-NA-01 and R-IN-05. The app must
appear as "yt-mirror" and never as "Python". macOS decides which app a
process belongs to from the place of its program file, so the bundle holds
a link to the app's Python under the app's own name, and a small script
that starts it (docs/DECISIONS.md D-048). The bundle is built locally, so
it needs no signing.

``./start`` runs this module as a program: ``python -m ytmirror.app.bundle``
makes sure the bundle is current and prints the path of the script in it
that starts the app. The bundle holds absolute paths. It is rebuilt when
the folder moved, and when the version, the icon source or the Python
environment changed.

This module must not start the app and must not draw: the ImageRenderer
port draws the icon.

Tests: backend/tests/integration/app/test_bundle.py
"""

import hashlib
import json
import os
import plistlib
import shutil
import sys
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import TextIO

from ytmirror import __version__
from ytmirror.app.config import AppPaths, detect_install_kind, resolve_paths
from ytmirror.app.container import build_container
from ytmirror.core.icon import ICON_PIXEL_SIZES, icns_file, icon_with_colours
from ytmirror.core.identity import app_identity
from ytmirror.core.models import MINIMUM_MACOS_MAJOR, AppIdentity
from ytmirror.ports.image_renderer import ImageRenderer

BUILDER_VERSION = 1
"""Raise this number when a change of this module must rebuild existing bundles."""

LAUNCHER_NAME = "launch"
ICON_NAME = "app"
ENTRY_MODULE = "ytmirror.app.main"
_STAGING_SUFFIX = ".building"
_EXECUTABLE = 0o755


@dataclass(frozen=True, slots=True)
class BundlePlan:
    """Everything that decides what the bundle looks like.

    Attributes:
        identity: The name and the bundle identifier of the app.
        version: The app version.
        bundle_dir: The ``.app`` folder to build.
        home_dir: The folder that holds ``data/`` and ``tools/``.
        environment_dir: The Python environment the app runs in.
        icon_source: The one source file of the icon.
        tokens_file: The token file the icon takes its colours from.
    """

    identity: AppIdentity
    version: str
    bundle_dir: Path
    home_dir: Path
    environment_dir: Path
    icon_source: Path
    tokens_file: Path

    @property
    def launcher(self) -> Path:
        """The script that macOS and ``./start`` run to start the app."""
        return self.bundle_dir / "Contents" / "MacOS" / LAUNCHER_NAME

    @property
    def program(self) -> Path:
        """The link to the app's Python, named after the app."""
        return self.bundle_dir / "Contents" / "MacOS" / self.identity.name

    @property
    def stamp_file(self) -> Path:
        """The file that records what the bundle was built from."""
        return self.bundle_dir / "Contents" / "Resources" / "build.json"


def plan_bundle(
    paths: AppPaths, identity: AppIdentity, version: str, environment_dir: Path
) -> BundlePlan:
    """Return the plan of the bundle that ``./start`` builds inside ``tools/``.

    Args:
        paths: Where the parts of this installation are.
        identity: The name and the bundle identifier of the app.
        version: The app version.
        environment_dir: The Python environment the app runs in.

    Returns:
        The plan. Nothing is created.
    """
    design = paths.code_root / "frontend" / "src" / "design"
    return BundlePlan(
        identity=identity,
        version=version,
        bundle_dir=paths.home_dir / "tools" / f"{identity.name}.app",
        home_dir=paths.home_dir,
        environment_dir=environment_dir,
        icon_source=design / "brand" / "icon.svg",
        tokens_file=design / "tokens.css",
    )


def fingerprint(plan: BundlePlan) -> dict[str, str]:
    """Return everything the bundle depends on, as text that can be compared.

    Args:
        plan: The plan of the bundle.

    Returns:
        The names, the version, every absolute path that is written into the
        bundle, and the content of the files it is built from.
    """
    return {
        "builder": str(BUILDER_VERSION),
        "name": plan.identity.name,
        "bundle_identifier": plan.identity.bundle_identifier,
        "version": plan.version,
        "bundle_dir": str(plan.bundle_dir),
        "home_dir": str(plan.home_dir),
        "environment_dir": str(plan.environment_dir),
        "environment": _digest(plan.environment_dir / "pyvenv.cfg"),
        "icon": _digest(plan.icon_source),
        "tokens": _digest(plan.tokens_file),
    }


def is_current(plan: BundlePlan) -> bool:
    """Return whether the bundle exists and was built from exactly this plan.

    Args:
        plan: The plan of the bundle.
    """
    try:
        built_from: object = json.loads(plan.stamp_file.read_text(encoding="utf-8"))
    except OSError, ValueError:
        return False
    return built_from == fingerprint(plan) and plan.launcher.is_file()


def ensure_bundle(plan: BundlePlan, renderer: ImageRenderer) -> bool:
    """Build the bundle unless it is current.

    Implements R-NA-02, and the bundle part of R-IN-05: a bundle whose paths
    no longer fit is rebuilt.

    Args:
        plan: The plan of the bundle.
        renderer: Draws the icon.

    Returns:
        True when the bundle was built, False when it was current already.
    """
    if is_current(plan):
        return False
    build_bundle(plan, renderer)
    return True


def build_bundle(plan: BundlePlan, renderer: ImageRenderer) -> None:
    """Build the bundle from scratch and put it in place of an older one.

    The bundle is built next to its final place and swapped in at the end,
    so a start that is interrupted leaves no half-built bundle behind.

    Args:
        plan: The plan of the bundle.
        renderer: Draws the icon.
    """
    staging = plan.bundle_dir.with_name(plan.bundle_dir.name + _STAGING_SUFFIX)
    shutil.rmtree(staging, ignore_errors=True)
    contents = staging / "Contents"
    (contents / "MacOS").mkdir(parents=True)
    (contents / "Resources").mkdir()

    with (contents / "Info.plist").open("wb") as info_file:
        plistlib.dump(_info(plan), info_file)
    icon = icon_with_colours(
        plan.icon_source.read_text(encoding="utf-8"),
        plan.tokens_file.read_text(encoding="utf-8"),
    )
    (contents / "Resources" / f"{ICON_NAME}.icns").write_bytes(
        icns_file({size: renderer.svg_to_png(icon, size) for size in ICON_PIXEL_SIZES})
    )
    # Python takes a folder with a pyvenv.cfg and a lib folder for its environment. These
    # two make the link below a full stand-in for the environment's own Python.
    shutil.copyfile(plan.environment_dir / "pyvenv.cfg", contents / "pyvenv.cfg")
    (contents / "lib").symlink_to(plan.environment_dir / "lib")
    (contents / "MacOS" / plan.identity.name).symlink_to(plan.environment_dir / "bin" / "python")
    launcher = contents / "MacOS" / LAUNCHER_NAME
    launcher.write_text(_launcher_script(plan), encoding="utf-8")
    launcher.chmod(_EXECUTABLE)
    (contents / "Resources" / plan.stamp_file.name).write_text(
        json.dumps(fingerprint(plan), indent=2), encoding="utf-8"
    )

    shutil.rmtree(plan.bundle_dir, ignore_errors=True)
    staging.rename(plan.bundle_dir)


def main(
    argv: Sequence[str] | None = None,
    env: Mapping[str, str] | None = None,
    out: TextIO | None = None,
) -> int:
    """Make sure the bundle of this installation is current and print its launcher.

    Args:
        argv: Not used. The program takes no arguments.
        env: The environment variables. Default: the real ones.
        out: Where the path of the launcher is written. Default: standard output.

    Returns:
        The process exit code.
    """
    del argv
    paths = resolve_paths(os.environ if env is None else env)
    identity = app_identity(detect_install_kind(paths.code_root))
    plan = plan_bundle(paths, identity, __version__, Path(sys.prefix))
    ensure_bundle(plan, build_container(paths).images)
    (sys.stdout if out is None else out).write(f"{plan.launcher}\n")
    return 0


def _info(plan: BundlePlan) -> dict[str, object]:
    return {
        "CFBundleName": plan.identity.name,
        "CFBundleDisplayName": plan.identity.name,
        "CFBundleIdentifier": plan.identity.bundle_identifier,
        "CFBundleExecutable": LAUNCHER_NAME,
        "CFBundleIconFile": ICON_NAME,
        "CFBundlePackageType": "APPL",
        "CFBundleInfoDictionaryVersion": "6.0",
        "CFBundleShortVersionString": plan.version,
        "CFBundleVersion": plan.version,
        "LSMinimumSystemVersion": f"{MINIMUM_MACOS_MAJOR}.0",
        "NSHighResolutionCapable": True,
    }


def _launcher_script(plan: BundlePlan) -> str:
    return (
        "#!/bin/sh\n"
        f"# Starts {plan.identity.name} inside its app bundle, so that macOS knows it by its\n"
        "# own name (docs/DECISIONS.md D-048). Written by ytmirror.app.bundle and rebuilt\n"
        "# when needed: do not edit.\n"
        f"export YTM_HOME={_quoted(str(plan.home_dir))}\n"
        f'exec {_quoted(str(plan.program))} -m {ENTRY_MODULE} "$@"\n'
    )


def _quoted(text: str) -> str:
    """Return the text as one word of a shell script."""
    return "'" + text.replace("'", "'\\''") + "'"


def _digest(file: Path) -> str:
    return hashlib.sha256(file.read_bytes()).hexdigest()


if __name__ == "__main__":
    raise SystemExit(main())
