"""Under which name and bundle identifier macOS knows this copy of the app.

Implements the naming part of R-NA-01 and R-NA-02. An installed copy and a
clone are two different apps to macOS, so that both can run on one Mac and be
told apart in the Dock (docs/DECISIONS.md D-047, D-051). This module only
decides the names. Building the app bundle is the job of ``app/bundle.py``.

Tests: backend/tests/unit/core/test_identity.py
"""

from ytmirror.core.models import APP_NAME, BUNDLE_IDENTIFIER, AppIdentity, InstallKind

DEV_NAME_SUFFIX = " (dev)"
DEV_IDENTIFIER_SUFFIX = ".dev"


def app_identity(install_kind: InstallKind) -> AppIdentity:
    """Return the identity of the app for one kind of installation.

    Implements R-NA-01 and R-NA-02.

    Args:
        install_kind: How this copy was installed.

    Returns:
        "yt-mirror" with the fixed bundle identifier for an installed copy, and
        "yt-mirror (dev)" with the identifier that ends in ``.dev`` for a clone.
    """
    if install_kind is InstallKind.CLONE:
        return AppIdentity(
            name=APP_NAME + DEV_NAME_SUFFIX,
            bundle_identifier=BUNDLE_IDENTIFIER + DEV_IDENTIFIER_SUFFIX,
        )
    return AppIdentity(name=APP_NAME, bundle_identifier=BUNDLE_IDENTIFIER)
