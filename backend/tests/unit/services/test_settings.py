"""Tests of ``ytmirror.services.settings``."""

from pathlib import Path

from tests.fixtures.fakes.settings_repository import InMemorySettingsRepository
from ytmirror.core.models import LogDetail, Settings
from ytmirror.services.settings import SettingsService

HOME_LIBRARY = Path("/Users/someone/Movies/YouTube")


def test_current_settings_are_the_defaults_when_nothing_was_stored() -> None:
    """R-SE-04: a setting that was never stored has its default."""
    service = SettingsService(InMemorySettingsRepository(), HOME_LIBRARY)

    assert service.current() == Settings()


def test_current_settings_come_from_the_repository() -> None:
    """R-SE-03: settings are read from where they are stored."""
    repository = InMemorySettingsRepository()
    repository.save(Settings(log_detail=LogDetail.VERBOSE))

    current = SettingsService(repository, HOME_LIBRARY).current()

    assert current.log_detail is LogDetail.VERBOSE


def test_the_default_library_is_the_movies_folder_of_this_mac() -> None:
    """R-FI-01, R-SE-04: the library folder defaults to ~/Movies/YouTube of the user."""
    service = SettingsService(InMemorySettingsRepository(), HOME_LIBRARY)

    assert service.current().library_folder == "~/Movies/YouTube"
    assert service.library_folder() == HOME_LIBRARY


def test_a_chosen_library_folder_is_used_as_it_is() -> None:
    """R-FI-01: a library folder the user chose replaces the default."""
    repository = InMemorySettingsRepository()
    repository.save(Settings(library_folder="/Volumes/Media/YouTube"))

    assert SettingsService(repository, HOME_LIBRARY).library_folder() == Path(
        "/Volumes/Media/YouTube"
    )
