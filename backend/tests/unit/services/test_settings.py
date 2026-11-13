"""Tests of ``ytmirror.services.settings``."""

from tests.fixtures.fakes.settings_repository import InMemorySettingsRepository
from ytmirror.core.models import LogDetail, Settings
from ytmirror.services.settings import SettingsService


def test_current_settings_are_the_defaults_when_nothing_was_stored() -> None:
    """R-SE-04: a setting that was never stored has its default."""
    service = SettingsService(InMemorySettingsRepository())

    assert service.current() == Settings()


def test_current_settings_come_from_the_repository() -> None:
    """R-SE-03: settings are read from where they are stored."""
    repository = InMemorySettingsRepository()
    repository.save(Settings(log_detail=LogDetail.VERBOSE))

    current = SettingsService(repository).current()

    assert current.log_detail is LogDetail.VERBOSE
