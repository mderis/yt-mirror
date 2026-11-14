"""Tests of ``ytmirror.core.dates``."""

import calendar
import datetime

import pytest

from ytmirror.core.channels import DatePrecision
from ytmirror.core.dates import DAY_S, moment_to_show, possible_range, precision_of

P = DatePrecision


def at(text: str) -> int:
    """Return a moment written as ``2026-11-14 06:42`` (UTC) as seconds since the epoch."""
    moment = datetime.datetime.strptime(text, "%Y-%m-%d %H:%M").replace(tzinfo=datetime.UTC)
    return calendar.timegm(moment.timetuple())


LISTED = at("2026-11-14 06:42")
"""When the real listings behind these cases were read (milestone M2)."""


@pytest.mark.parametrize(
    ("point", "said", "expected"),
    [
        ("2026-11-13 18:00", "12 hours ago", P.DAY),
        ("2026-11-13 00:00", "1 day ago", P.DAY),
        ("2026-11-07 00:00", "7 days ago", P.DAY),
        ("2026-11-05 00:00", "9 days ago", P.DAY),
        ("2026-11-01 00:00", "13 days ago", P.DAY),
        ("2026-10-31 00:00", "2 weeks ago", P.WEEK),
        ("2026-10-24 00:00", "3 weeks ago", P.WEEK),
        ("2026-10-17 00:00", "4 weeks ago", P.WEEK),
        ("2026-10-14 00:00", "1 month ago", P.MONTH),
        ("2026-07-14 00:00", "4 months ago", P.MONTH),
        ("2025-12-14 00:00", "11 months ago", P.MONTH),
        ("2025-11-14 00:00", "1 year ago", P.YEAR),
        ("2011-11-14 00:00", "15 years ago", P.YEAR),
        ("2005-11-14 00:00", "21 years ago", P.YEAR),
    ],
)
def test_the_unit_is_found_again_from_points_of_real_listings(
    point: str, said: str, expected: DatePrecision
) -> None:
    """R-DT-04: the unit YouTube gave is found from the point a real listing returned."""
    assert precision_of(at(point), LISTED) is expected, said


def test_a_point_later_than_the_start_of_the_listing_day_is_a_day() -> None:
    """R-DT-04: "2 hours ago" is rounded to the hour and counts as known to the day."""
    assert precision_of(at("2026-11-14 05:00"), LISTED) is P.DAY


def test_the_point_is_rounded_to_the_nearest_day_not_cut_off() -> None:
    """R-DT-04: in the evening "9 days ago" is rounded up to the next midnight, as yt-dlp does."""
    evening = at("2026-11-14 18:00")

    assert precision_of(at("2026-11-06 00:00"), evening) is P.DAY
    assert precision_of(at("2026-11-01 00:00"), evening) is P.WEEK
    assert precision_of(at("2025-11-15 00:00"), evening) is P.YEAR


def test_where_two_units_fit_the_coarser_one_is_taken() -> None:
    """R-DT-04: after a February of 28 days, "4 weeks ago" and "1 month ago" give one point."""
    listed = at("2027-03-14 06:00")

    assert precision_of(at("2027-02-14 00:00"), listed) is P.MONTH


def test_a_month_that_lacks_the_day_ends_on_its_last_day() -> None:
    """R-DT-04: one month before 31 March is the last day of February."""
    listed = at("2026-03-31 06:00")

    assert precision_of(at("2026-02-28 00:00"), listed) is P.MONTH
    assert precision_of(at("2025-03-31 00:00"), listed) is P.YEAR


@pytest.mark.parametrize(
    ("point", "expected"),
    [
        ("2026-11-10 00:00", P.DAY),
        ("2026-10-29 00:00", P.WEEK),
        ("2026-10-10 00:00", P.MONTH),
        ("2025-12-01 00:00", P.MONTH),
        ("2025-11-10 00:00", P.YEAR),
        ("2019-05-05 00:00", P.YEAR),
    ],
)
def test_a_point_that_fits_no_rule_gets_its_unit_from_its_age(
    point: str, expected: DatePrecision
) -> None:
    """R-DT-04: a point the arithmetic does not explain still gets a unit, never a finer one."""
    assert precision_of(at(point), LISTED) is expected


@pytest.mark.parametrize(
    ("precision", "earliest", "latest"),
    [
        (P.DAY, "2026-06-12 12:00", "2026-06-14 12:00"),
        (P.WEEK, "2026-06-06 12:00", "2026-06-14 12:00"),
        (P.MONTH, "2026-05-13 12:00", "2026-06-14 12:00"),
        (P.YEAR, "2025-06-13 12:00", "2026-06-14 12:00"),
    ],
)
def test_the_real_date_lies_up_to_one_unit_before_the_point(
    precision: DatePrecision, earliest: str, latest: str
) -> None:
    """R-DT-04: the range reaches one unit back from the point, with half a day for the rounding."""
    assert possible_range(at("2026-06-14 00:00"), precision) == (at(earliest), at(latest))


@pytest.mark.parametrize(
    ("precision", "middle"),
    [
        (P.DAY, "2026-06-13 12:00"),
        (P.WEEK, "2026-06-10 12:00"),
        (P.MONTH, "2026-05-29 12:00"),
        (P.YEAR, "2025-12-13 12:00"),
    ],
)
def test_an_approximate_date_is_shown_from_the_middle_of_its_range(
    precision: DatePrecision, middle: str
) -> None:
    """R-DT-04: the moment to show is half a unit before the point."""
    assert moment_to_show(at("2026-06-14 00:00"), precision) == at(middle)


def test_real_videos_lie_inside_the_range_of_their_listed_point() -> None:
    """R-DT-04: exact dates measured in milestone M2 fall into the range of the listed point."""
    measured = [
        ("2026-11-05 00:00", "2026-11-04 15:52"),
        ("2026-10-24 00:00", "2026-10-23 18:46"),
        ("2026-10-14 00:00", "2026-09-21 17:49"),
        ("2026-07-14 00:00", "2026-06-14 15:18"),
        ("2025-11-14 00:00", "2024-11-20 18:27"),
        ("2024-11-14 00:00", "2023-11-15 22:36"),
        ("2011-11-14 00:00", "2011-01-07 10:53"),
    ]

    for point, exact in measured:
        earliest, latest = possible_range(at(point), precision_of(at(point), LISTED))

        assert earliest <= at(exact) <= latest, point


def test_from_the_middle_the_error_is_at_most_half_a_unit() -> None:
    """R-DT-04: the worst measured case, a full year before the point, is half a year off."""
    point, exact = at("2025-11-14 00:00"), at("2024-11-14 18:00")

    shown = moment_to_show(point, P.YEAR)

    assert abs(shown - exact) <= 183 * DAY_S
    assert point - exact > 364 * DAY_S
