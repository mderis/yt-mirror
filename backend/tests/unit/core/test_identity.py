"""Tests of ``ytmirror.core.identity``."""

from ytmirror.core.identity import app_identity
from ytmirror.core.models import InstallKind


def test_an_installed_copy_is_yt_mirror_with_the_fixed_identifier() -> None:
    """R-NA-01, R-NA-02: the app appears as "yt-mirror", under its bundle identifier."""
    identity = app_identity(InstallKind.ARCHIVE)

    assert identity.name == "yt-mirror"
    assert identity.bundle_identifier == "io.github.mderis.yt-mirror"


def test_a_clone_is_another_app_that_can_be_told_apart() -> None:
    """R-NA-01, R-NA-02: a clone appears as "yt-mirror (dev)", with its own identifier."""
    installed = app_identity(InstallKind.ARCHIVE)
    clone = app_identity(InstallKind.CLONE)

    assert clone.name == "yt-mirror (dev)"
    assert clone.bundle_identifier == "io.github.mderis.yt-mirror.dev"
    assert clone.bundle_identifier != installed.bundle_identifier
