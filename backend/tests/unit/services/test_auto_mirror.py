"""Tests of auto-mirror: what it queues, when it asks first, and "Mirror everything missing"."""

from pathlib import Path
from typing import Any

from sqlalchemy import text

from tests.fixtures.world import SMALL_ID, World, channel_file
from ytmirror.core.auto_mirror import AutoMirrorAnswer
from ytmirror.core.channels import Channel
from ytmirror.core.dates import DAY_S
from ytmirror.core.jobs import ACTIVE_STATES, JobState


def channel_of(world: World) -> Channel:
    """Return the small channel as it is stored."""
    channel = world.repository.channel(SMALL_ID)
    assert channel is not None
    return channel


def queued(world: World) -> list[str]:
    """Return the videos that wait or run, in their order."""
    return [job.video_id for job in world.jobs.jobs(ACTIVE_STATES)]


def listed(tmp_path: Path, videos: int, **choices: Any) -> World:
    """A world with a channel of so many videos, added with these choices and listed."""
    world = World(tmp_path, channel_file(videos=videos))
    world.add_and_list(**choices)
    return world


def as_before_m5(world: World) -> None:
    """Make the channel what migration 0011 makes of one stored with auto-mirror on."""
    world.repository.update_channel(SMALL_ID, auto_mirror=True, auto_mirror_asked=False)


def test_a_channel_added_with_auto_mirror_queues_its_videos_as_automatic(tmp_path: Path) -> None:
    """R-MI-02, D-090: the choice of the add dialog queues every video, paced by the budget."""
    world = listed(tmp_path, 5, auto_mirror=True)

    assert sorted(queued(world)) == sorted(world.ids(SMALL_ID))
    assert {job.by_hand for job in world.jobs.jobs([JobState.WAITING])} == {False}


def test_a_large_start_from_before_m5_asks_first_and_queues_nothing(tmp_path: Path) -> None:
    """R-MI-02, D-095: a channel stored with auto-mirror on is asked first at the first start."""
    world = listed(tmp_path, 8)
    as_before_m5(world)

    world.auto_mirror.run_all()

    assert queued(world) == []
    view = world.views.of(SMALL_ID)
    assert view is not None
    assert view.auto_mirror_question is not None
    count, size = view.auto_mirror_question
    assert count == 8
    assert size > 0


def test_a_small_start_from_before_m5_needs_no_question(tmp_path: Path) -> None:
    """R-MI-02, D-095: at most 5 videos start at once, without a question."""
    world = listed(tmp_path, 5)
    as_before_m5(world)

    world.auto_mirror.run_all()

    assert len(queued(world)) == 5
    assert channel_of(world).auto_mirror_asked is True


def test_until_the_answer_nothing_is_mirrored_by_itself(tmp_path: Path) -> None:
    """R-MI-02, D-095: a check while the question waits queues nothing either."""
    world = listed(tmp_path, 8)
    as_before_m5(world)
    world.auto_mirror.run_all()

    world.check(SMALL_ID)

    assert queued(world) == []


def test_mirror_all_queues_every_video(tmp_path: Path) -> None:
    """R-MI-02, D-095: "Mirror all N videos" starts them, as automatic downloads."""
    world = listed(tmp_path, 8)
    as_before_m5(world)
    world.auto_mirror.run_all()

    world.auto_mirror.answer(SMALL_ID, AutoMirrorAnswer.MIRROR_ALL)

    assert len(queued(world)) == 8
    view = world.views.of(SMALL_ID)
    assert view is not None
    assert view.auto_mirror_question is None


def test_only_new_videos_sets_the_date_limit_to_today(tmp_path: Path) -> None:
    """R-MI-02, R-MI-03, D-095: "Only new videos from now on" mirrors nothing listed before."""
    world = listed(tmp_path, 8)
    as_before_m5(world)
    world.auto_mirror.run_all()

    world.auto_mirror.answer(SMALL_ID, AutoMirrorAnswer.ONLY_NEW)

    channel = channel_of(world)
    assert channel.mirror_after is not None
    assert world.now() - DAY_S < channel.mirror_after <= world.now()
    assert channel.auto_mirror is True
    assert queued(world) == []


def test_turn_auto_mirror_off(tmp_path: Path) -> None:
    """R-MI-02, D-095: the third answer turns auto-mirror off and starts nothing."""
    world = listed(tmp_path, 8)
    as_before_m5(world)
    world.auto_mirror.run_all()

    world.auto_mirror.answer(SMALL_ID, AutoMirrorAnswer.TURN_OFF)

    assert channel_of(world).auto_mirror is False
    assert queued(world) == []


def test_turning_auto_mirror_on_asks_before_a_large_start(tmp_path: Path) -> None:
    """R-MI-02, D-095: the toggle of the header asks too, and starts nothing before the answer."""
    world = listed(tmp_path, 8)

    world.auto_mirror.set_auto_mirror(SMALL_ID, on=True)

    assert queued(world) == []
    view = world.views.of(SMALL_ID)
    assert view is not None
    assert view.auto_mirror_question is not None


def test_turning_auto_mirror_on_with_few_videos_starts_them(tmp_path: Path) -> None:
    """R-MI-02: "now and after every check": a few videos start at once."""
    world = listed(tmp_path, 4)

    world.auto_mirror.set_auto_mirror(SMALL_ID, on=True)

    assert len(queued(world)) == 4


def test_a_paused_channel_queues_nothing_until_it_is_resumed(tmp_path: Path) -> None:
    """R-MI-02, R-CH-31: a paused channel's downloads do not run; resuming takes them up."""
    world = listed(tmp_path, 4)
    world.channels.set_paused(SMALL_ID, paused=True)

    world.auto_mirror.set_auto_mirror(SMALL_ID, on=True)
    assert queued(world) == []

    world.channels.set_paused(SMALL_ID, paused=False)
    assert len(queued(world)) == 4


def missing(world: World, count: int) -> list[str]:
    """Make the files of the first videos of the channel synced files that went missing."""
    ids = world.ids(SMALL_ID)[:count]
    with world.engine.begin() as connection:
        for video_id in ids:
            connection.execute(
                text("UPDATE videos SET status = 'file_missing', file_name = :name WHERE id = :id"),
                {"id": video_id, "name": f"{video_id}.mkv"},
            )
    return ids


def test_a_few_missing_files_are_downloaded_again_by_themselves(tmp_path: Path) -> None:
    """R-MI-06, D-092: with auto-mirror on, up to 5 missing files are queued again."""
    world = mirroring(tmp_path, 8)
    gone = missing(world, 5)

    world.check(SMALL_ID)

    assert set(gone) <= set(queued(world))


def test_more_missing_files_wait_for_the_user(tmp_path: Path) -> None:
    """R-MI-06, D-092: above 5 none of them is queued; the channel says how many are missing."""
    world = mirroring(tmp_path, 8)
    gone = missing(world, 6)

    world.check(SMALL_ID)

    assert not set(gone) & set(queued(world))
    view = world.views.of(SMALL_ID)
    assert view is not None
    assert view.missing_held == 6


def test_leave_them_missing_holds_until_more_are_missing(tmp_path: Path) -> None:
    """R-MI-06, D-092: "Leave them missing" holds until more files are missing."""
    world = mirroring(tmp_path, 8)
    missing(world, 6)
    world.check(SMALL_ID)

    world.auto_mirror.leave_missing(SMALL_ID)
    world.check(SMALL_ID)
    view = world.views.of(SMALL_ID)
    assert view is not None
    assert view.missing_held is None
    assert channel_of(world).missing_left == 6

    world.downloader.clear_waiting()
    missing(world, 7)
    world.check(SMALL_ID)
    view = world.views.of(SMALL_ID)
    assert view is not None
    assert view.missing_held == 7


def test_mirror_them_again_queues_the_missing_files_by_hand(tmp_path: Path) -> None:
    """R-MI-06, R-MI-04, D-092: the answer of the banner is an action of the user."""
    world = mirroring(tmp_path, 8)
    gone = missing(world, 6)
    world.check(SMALL_ID)

    jobs = world.auto_mirror.mirror_missing(SMALL_ID)

    assert set(gone) <= {job.video_id for job in jobs}
    assert {job.by_hand for job in jobs} == {True}
    view = world.views.of(SMALL_ID)
    assert view is not None
    assert view.missing_held is None


def test_mirror_everything_missing_does_not_turn_auto_mirror_on(tmp_path: Path) -> None:
    """R-MI-04: every eligible video is queued once, by hand; auto-mirror stays off."""
    world = listed(tmp_path, 5)

    jobs = world.auto_mirror.mirror_missing(SMALL_ID)

    assert sorted(job.video_id for job in jobs) == sorted(world.ids(SMALL_ID))
    assert channel_of(world).auto_mirror is False


def test_a_video_whose_date_cannot_decide_the_limit_gets_its_exact_date_first(
    tmp_path: Path,
) -> None:
    """R-MI-03: neither queued nor left out: it goes to the front of the exact-date fetch."""
    world = listed(tmp_path, 5)
    newest = world.repository.video(world.ids(SMALL_ID)[0])
    assert newest is not None and newest.published_at is not None
    world.repository.update_channel(
        SMALL_ID, auto_mirror=True, mirror_after=newest.published_at - DAY_S // 4
    )

    world.auto_mirror.run(SMALL_ID)

    assert newest.id not in queued(world)
    [first] = world.date_repository.pending(world.now(), limit=1, by_api=False)
    assert (first.video_id, first.urgent) == (newest.id, True)


# --- what the question counts, and when it is asked (review of M5: High 4)


def question_count(world: World) -> int | None:
    """How many videos the question of the channel names, or None without a question."""
    view = world.views.of(SMALL_ID)
    assert view is not None
    return None if view.auto_mirror_question is None else view.auto_mirror_question[0]


def test_six_videos_are_asked_about_first(tmp_path: Path) -> None:
    """R-MI-02, D-095: the limit is 5: at exactly 6 the user is asked."""
    world = listed(tmp_path, 6)
    as_before_m5(world)

    world.auto_mirror.run_all()

    assert question_count(world) == 6
    assert queued(world) == []


def test_the_question_counts_missing_files_too(tmp_path: Path) -> None:
    """R-MI-02, R-MI-06, D-095: 3 new and 3 missing files are 6 downloads: asked first."""
    world = listed(tmp_path, 6)
    missing(world, 3)
    as_before_m5(world)

    world.auto_mirror.run_all()

    assert question_count(world) == 6
    assert queued(world) == []


def test_the_question_counts_videos_that_wait_for_their_exact_date(tmp_path: Path) -> None:
    """R-MI-02, R-MI-03, D-095: undecided videos would start once their dates arrive."""
    world = listed(tmp_path, 7)
    first = world.repository.video(world.ids(SMALL_ID)[0])
    assert first is not None and first.published_at is not None
    with world.engine.begin() as connection:
        connection.execute(
            text(
                "UPDATE videos SET published_exact = 0, published_precision = 'year', "
                "published_at = :point WHERE channel_id = :channel"
            ),
            {"channel": SMALL_ID, "point": first.published_at},
        )
    # Each date can lie anywhere in the year before its point: none decides the limit.
    world.repository.update_channel(
        SMALL_ID,
        auto_mirror=True,
        auto_mirror_asked=False,
        mirror_after=first.published_at - 10 * DAY_S,
    )

    world.auto_mirror.run(SMALL_ID)

    assert question_count(world) == 7
    assert channel_of(world).auto_mirror_asked is False


def test_a_channel_not_listed_yet_is_asked_after_its_first_listing(tmp_path: Path) -> None:
    """R-MI-02, D-095: before the listing nothing is counted, asked or queued."""
    world = World(tmp_path, channel_file(videos=8))
    world.add(auto_mirror=True)

    world.auto_mirror.run(SMALL_ID)

    assert queued(world) == []
    assert channel_of(world).auto_mirror_asked is False
    world.work()
    assert question_count(world) == 8
    assert queued(world) == []


def test_a_channel_added_with_auto_mirror_is_asked_before_a_large_start(tmp_path: Path) -> None:
    """R-MI-02, D-095: the add dialog shows no size: the question comes after the listing."""
    world = listed(tmp_path, 8, auto_mirror=True)

    assert question_count(world) == 8
    assert queued(world) == []


# --- missing files (review of M5: mediums)


def mirroring(tmp_path: Path, videos: int) -> World:
    """A channel added with auto-mirror, answered with "Mirror all", every video synced."""
    world = listed(tmp_path, videos, auto_mirror=True)
    if question_count(world) is not None:
        world.auto_mirror.answer(SMALL_ID, AutoMirrorAnswer.MIRROR_ALL)
    world.download_all()
    return world


def test_the_limit_of_missing_files_counts_those_queued_already(tmp_path: Path) -> None:
    """R-MI-06, D-092: 3 queued and 3 more missing are 6: the new ones wait for the user."""
    world = mirroring(tmp_path, 8)
    first = missing(world, 3)
    world.check(SMALL_ID)
    assert set(first) <= set(queued(world))

    later = missing(world, 6)[3:]
    world.check(SMALL_ID)

    assert not set(later) & set(queued(world))
    view = world.views.of(SMALL_ID)
    assert view is not None
    assert view.missing_held == 6


def test_mirror_them_again_queues_exactly_the_missing_files(tmp_path: Path) -> None:
    """R-MI-06, D-092: "Mirror them again" never queues the videos that were never mirrored."""
    world = mirroring(tmp_path, 9)
    gone = missing(world, 6)
    never = world.ids(SMALL_ID)[-2:]
    with world.engine.begin() as connection:
        for video_id in never:
            connection.execute(
                text(
                    "UPDATE videos SET status = 'not_downloaded', file_name = NULL WHERE id = :id"
                ),
                {"id": video_id},
            )
    # Auto-mirror leaves the never mirrored ones alone: they lie before its date limit.
    world.repository.update_channel(SMALL_ID, mirror_after=4_000_000_000)
    world.check(SMALL_ID)
    assert not set(never) & set(queued(world))

    jobs = world.auto_mirror.mirror_them_again(SMALL_ID)

    assert sorted(job.video_id for job in jobs) == sorted(gone)
    assert sorted(queued(world)) == sorted(gone)
    assert [job.by_hand for job in jobs] == [True] * 6
