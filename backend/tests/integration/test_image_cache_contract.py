"""Contract of the ImageCache port, run against the fake and the real adapter."""

from pathlib import Path

import pytest

from tests.fixtures.fakes.image_cache import InMemoryImageCache
from ytmirror.adapters.image_cache import FileImageCache
from ytmirror.ports.image_cache import ImageCache, ImageKind

PICTURE = b"\x89PNG\r\n\x1a\n a picture"


@pytest.fixture(params=["fake", "files"])
def cache(request: pytest.FixtureRequest, tmp_path: Path) -> ImageCache:
    """The fake and the real cache, one after the other."""
    if request.param == "fake":
        return InMemoryImageCache()
    return FileImageCache(tmp_path / "cache")


def test_a_stored_picture_is_there_and_comes_back_unchanged(cache: ImageCache) -> None:
    """R-CH-16: a cached thumbnail is kept on this Mac, byte for byte."""
    cache.store(ImageKind.THUMBNAIL, "vid00000001", PICTURE)

    assert cache.has(ImageKind.THUMBNAIL, "vid00000001") is True
    assert cache.load(ImageKind.THUMBNAIL, "vid00000001") == PICTURE


def test_a_picture_that_was_never_stored_is_not_there(cache: ImageCache) -> None:
    """R-CH-16: what is not cached is simply missing, never an error."""
    assert cache.has(ImageKind.THUMBNAIL, "vid00000001") is False
    assert cache.load(ImageKind.THUMBNAIL, "vid00000001") is None


def test_thumbnails_and_avatars_are_kept_apart(cache: ImageCache) -> None:
    """R-CH-16: the avatar of a channel and the thumbnail of a video never mix."""
    cache.store(ImageKind.AVATAR, "UCaaaaaaaaaaaaaaaaaaaaaa", b"avatar")

    assert cache.has(ImageKind.THUMBNAIL, "UCaaaaaaaaaaaaaaaaaaaaaa") is False
    assert cache.load(ImageKind.AVATAR, "UCaaaaaaaaaaaaaaaaaaaaaa") == b"avatar"


def test_storing_again_replaces_the_picture(cache: ImageCache) -> None:
    """R-CH-16: a newer picture takes the place of the old one."""
    cache.store(ImageKind.AVATAR, "UCaaaaaaaaaaaaaaaaaaaaaa", b"old")
    cache.store(ImageKind.AVATAR, "UCaaaaaaaaaaaaaaaaaaaaaa", b"new")

    assert cache.load(ImageKind.AVATAR, "UCaaaaaaaaaaaaaaaaaaaaaa") == b"new"


def test_removed_pictures_are_gone_and_the_others_stay(cache: ImageCache) -> None:
    """R-CH-32: the pictures of a removed channel are dropped, those of others are kept."""
    for video in ("vid00000001", "vid00000002", "vid00000003"):
        cache.store(ImageKind.THUMBNAIL, video, PICTURE)

    cache.remove(ImageKind.THUMBNAIL, ["vid00000001", "vid00000002", "vid0000never"])

    assert cache.has(ImageKind.THUMBNAIL, "vid00000001") is False
    assert cache.has(ImageKind.THUMBNAIL, "vid00000002") is False
    assert cache.has(ImageKind.THUMBNAIL, "vid00000003") is True


@pytest.mark.parametrize("bad", ["../../etc/passwd", "a/b", "", ".", "a b", "x" * 65])
def test_an_id_that_is_no_id_is_refused(cache: ImageCache, bad: str) -> None:
    """R-PL-11: a picture is named by an ID, so nothing outside the cache can be reached."""
    with pytest.raises(ValueError, match="Not an ID"):
        cache.load(ImageKind.THUMBNAIL, bad)
    with pytest.raises(ValueError, match="Not an ID"):
        cache.store(ImageKind.THUMBNAIL, bad, PICTURE)
    with pytest.raises(ValueError, match="Not an ID"):
        cache.has(ImageKind.THUMBNAIL, bad)
    with pytest.raises(ValueError, match="Not an ID"):
        cache.remove(ImageKind.THUMBNAIL, [bad])


def test_pictures_are_files_in_the_cache_folder_and_nothing_is_left_half_written(
    tmp_path: Path,
) -> None:
    """R-CH-16, R-QA-06: one file per picture, in place only when complete."""
    cache = FileImageCache(tmp_path / "cache")
    assert not (tmp_path / "cache").exists()

    cache.store(ImageKind.THUMBNAIL, "vid00000001", PICTURE)
    cache.store(ImageKind.AVATAR, "UCaaaaaaaaaaaaaaaaaaaaaa", PICTURE)

    files = sorted(
        str(file.relative_to(tmp_path))
        for file in (tmp_path / "cache").rglob("*")
        if file.is_file()
    )
    assert files == ["cache/avatars/UCaaaaaaaaaaaaaaaaaaaaaa", "cache/thumbnails/vid00000001"]
