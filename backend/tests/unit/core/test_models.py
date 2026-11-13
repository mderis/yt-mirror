"""Tests of ``ytmirror.core.models``."""

import dataclasses

import pytest

from ytmirror.core.models import MINIMUM_MACOS_MAJOR, LogDetail, Settings


def test_settings_defaults_match_the_spec() -> None:
    """R-LG-01: the default of "Log detail" is Normal (docs/SPEC.md section 10)."""
    settings = Settings()

    assert settings.log_detail is LogDetail.NORMAL


def test_settings_cannot_be_changed_in_place() -> None:
    """infra: settings are values. A change makes a new object and goes through the repository."""
    settings = Settings()

    with pytest.raises(dataclasses.FrozenInstanceError):
        settings.log_detail = LogDetail.VERBOSE  # pyright: ignore[reportAttributeAccessIssue]  (the point of the test)


def test_minimum_macos_is_fifteen() -> None:
    """R-PL-01: the minimum is macOS 15 (docs/DECISIONS.md D-035)."""
    assert MINIMUM_MACOS_MAJOR == 15
