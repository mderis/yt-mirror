"""Contract of the ApiKeyStore port, run against the file of the app and the fake."""

import os
import stat
from collections.abc import Iterator
from pathlib import Path

import pytest

from tests.fixtures.fakes.api_key_store import InMemoryApiKeyStore
from ytmirror.adapters.api_key_file import FILE_NAME, ApiKeyFile
from ytmirror.core.errors import AppError, ErrorCode
from ytmirror.ports.api_key_store import ApiKeyStore

KEY = "stand-in-key-0001"


@pytest.fixture(params=["file", "fake"])
def store(request: pytest.FixtureRequest, tmp_path: Path) -> Iterator[ApiKeyStore]:
    """Each store, empty."""
    yield ApiKeyFile(tmp_path / "data") if request.param == "file" else InMemoryApiKeyStore()


def test_no_key_is_saved_at_first(store: ApiKeyStore) -> None:
    """R-DT-12: the key is off by default."""
    assert store.read() is None


def test_a_saved_key_is_read_back(store: ApiKeyStore) -> None:
    """R-DT-12: the key is kept on this Mac."""
    assert not store.is_saved()

    store.write(KEY)

    assert store.is_saved()
    assert store.read() == KEY


def test_a_new_key_takes_the_place_of_the_old(store: ApiKeyStore) -> None:
    """R-DT-12: saving again replaces the key."""
    store.write(KEY)
    store.write("another-key")

    assert store.read() == "another-key"


def test_a_removed_key_is_gone_and_removing_twice_is_fine(store: ApiKeyStore) -> None:
    """R-DT-12: removing the key changes nothing but speed."""
    store.write(KEY)
    store.remove()
    store.remove()

    assert store.read() is None


# --- the file of the app (D-085)


def test_the_key_file_is_in_the_data_folder_and_only_the_user_can_read_it(tmp_path: Path) -> None:
    """R-DT-12, D-085: data/youtube-api-key, mode 0600."""
    store = ApiKeyFile(tmp_path)

    store.write(KEY)

    path = tmp_path / FILE_NAME
    assert stat.S_IMODE(path.stat().st_mode) == 0o600
    assert path.read_text(encoding="utf-8") == f"{KEY}\n"


def test_writing_leaves_no_other_file_behind(tmp_path: Path) -> None:
    """R-DT-12: (D-085) the new file is renamed over the old one, and nothing else stays."""
    store = ApiKeyFile(tmp_path)
    store.write(KEY)
    store.write("another-key")

    assert sorted(path.name for path in tmp_path.iterdir()) == [FILE_NAME]


def test_the_file_is_never_readable_by_others_even_while_it_is_written(tmp_path: Path) -> None:
    """R-DT-12: (D-085) the new file is created with mode 0600, whatever the umask allows."""
    old = os.umask(0)
    try:
        ApiKeyFile(tmp_path).write(KEY)
    finally:
        os.umask(old)

    assert stat.S_IMODE((tmp_path / FILE_NAME).stat().st_mode) == 0o600


def test_a_key_file_others_could_read_is_made_private_when_read(tmp_path: Path) -> None:
    """R-DT-12: (D-085) a copied file with a wider mode is closed again before the key is used."""
    path = tmp_path / FILE_NAME
    path.write_text(KEY, encoding="utf-8")
    path.chmod(0o644)

    assert ApiKeyFile(tmp_path).read() == KEY
    assert stat.S_IMODE(path.stat().st_mode) == 0o600


@pytest.mark.parametrize("content", [b"", b"\n  \n", b"\xff\xfe not text"])
def test_a_key_file_without_a_readable_key_is_unreadable(tmp_path: Path, content: bytes) -> None:
    """R-DT-12: a file that holds no key counts as "saved but cannot be read"."""
    (tmp_path / FILE_NAME).write_bytes(content)

    with pytest.raises(AppError) as failure:
        ApiKeyFile(tmp_path).read()

    assert failure.value.code is ErrorCode.API_KEY_UNREADABLE


def test_a_key_file_the_app_may_not_read_is_unreadable_without_its_content(tmp_path: Path) -> None:
    """R-DT-12, R-LG-07: the error says why, never what the file holds."""
    folder = tmp_path / "data"
    ApiKeyFile(folder).write(KEY)
    folder.chmod(0o000)
    try:
        with pytest.raises(AppError) as failure:
            ApiKeyFile(folder).read()
    finally:
        folder.chmod(0o700)

    assert failure.value.code is ErrorCode.API_KEY_UNREADABLE
    assert KEY not in str(failure.value.details)


def test_a_key_that_cannot_be_written_leaves_nothing_behind(tmp_path: Path) -> None:
    """R-DT-12: (D-085) a failed save is an error, and no half file stays."""
    tmp_path.chmod(0o500)
    try:
        with pytest.raises(AppError) as failure:
            ApiKeyFile(tmp_path).write(KEY)
    finally:
        tmp_path.chmod(0o700)

    assert failure.value.code is ErrorCode.API_KEY_UNREADABLE
    assert list(tmp_path.iterdir()) == []


def test_a_copy_left_by_an_interrupted_save_is_deleted(tmp_path: Path) -> None:
    """R-DT-12, D-085: "Remove key" and the start delete a hidden copy of a key (review of M4)."""
    store = ApiKeyFile(tmp_path)
    store.write(KEY)
    leftover = tmp_path / f".{FILE_NAME}.0123456789abcdef.tmp"
    leftover.write_text(KEY, encoding="utf-8")

    store.clean_leftovers()
    second = tmp_path / f".{FILE_NAME}.fedcba9876543210.tmp"
    second.write_text(KEY, encoding="utf-8")
    store.remove()

    assert not leftover.exists()
    assert not second.exists()
    assert list(tmp_path.iterdir()) == []
