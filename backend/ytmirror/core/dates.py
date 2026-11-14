"""Rules for dates. So far: approximate dates and their precision.

Implements the storing half of R-DT-04 (docs/DECISIONS.md D-060). A channel
listing gives every video a point in time that is "the moment of the listing
minus N units", where the unit is the one YouTube showed ("3 weeks ago") and
is not passed on. This module finds the unit again from the point, and says
in which range the real date lies and which moment of it to show.

The arithmetic follows what yt-dlp does with the words of YouTube: months
and years are counted on the calendar, and the result is rounded to the
nearest day. YouTube counts in days up to 13, in weeks from 2 to 4, in
months from 1 to 11, and then in years.

This module must not read a clock: every time is passed in. All times are
seconds since the Unix epoch, UTC.

Tests: backend/tests/unit/core/test_dates.py
"""

import calendar
import datetime

from ytmirror.core.channels import DatePrecision

DAY_S = 24 * 60 * 60
_HALF_DAY_S = DAY_S // 2
_WEEK_DAYS = 7
_MONTHS_IN_A_YEAR = 12
_WEEKS_SHOWN = (2, 3, 4)
_MONTHS_SHOWN = range(1, _MONTHS_IN_A_YEAR)
_MOST_YEARS = 40
# For a point that fits no rule exactly, for example when the listing took long.
_AT_LEAST_DAYS_FOR = (
    (DatePrecision.YEAR, 360),
    (DatePrecision.MONTH, 29),
    (DatePrecision.WEEK, 14),
)


def precision_of(point: int, listed_at: int) -> DatePrecision:
    """Return the unit in which YouTube gave an approximate date.

    Where two units fit, the coarser one is returned, so the range is never
    too narrow.

    Args:
        point: The approximate published time the listing gave.
        listed_at: When the listing was read.

    Returns:
        The unit: year, month, week or day.
    """
    listed = _moment(listed_at)
    if any(_rounded(_months_before(listed, _MONTHS_IN_A_YEAR * n)) == point for n in _years()):
        return DatePrecision.YEAR
    if any(_rounded(_months_before(listed, n)) == point for n in _MONTHS_SHOWN):
        return DatePrecision.MONTH
    if any(_rounded(listed - datetime.timedelta(weeks=n)) == point for n in _WEEKS_SHOWN):
        return DatePrecision.WEEK
    age_days = (_rounded(listed) - point) // DAY_S
    for unit, days in _AT_LEAST_DAYS_FOR:
        if age_days >= days:
            return unit
    return DatePrecision.DAY


def possible_range(point: int, precision: DatePrecision) -> tuple[int, int]:
    """Return the earliest and the latest moment the real date can be.

    "N units ago" means at least N and less than N + 1 units, so the real
    date lies up to one unit before the point. Half a day is added on both
    sides, because the point was rounded to the day.

    Args:
        point: The approximate published time the listing gave.
        precision: Its unit.

    Returns:
        The earliest and the latest possible moment.
    """
    return _one_unit_before(point, precision) - _HALF_DAY_S, point + _HALF_DAY_S


def moment_to_show(point: int, precision: DatePrecision) -> int:
    """Return the moment an approximate date is shown from: the middle of its range.

    The point of the listing is the latest possible date, never the middle.
    From the middle the worst error is half a unit (R-DT-04).

    Args:
        point: The approximate published time the listing gave.
        precision: Its unit.
    """
    return (_one_unit_before(point, precision) + point) // 2


def _one_unit_before(point: int, precision: DatePrecision) -> int:
    moment = _moment(point)
    if precision is DatePrecision.YEAR:
        return _seconds(_months_before(moment, _MONTHS_IN_A_YEAR))
    if precision is DatePrecision.MONTH:
        return _seconds(_months_before(moment, 1))
    if precision is DatePrecision.WEEK:
        return point - _WEEK_DAYS * DAY_S
    return point - DAY_S


def _years() -> range:
    return range(1, _MOST_YEARS + 1)


def _moment(seconds: int) -> datetime.datetime:
    return datetime.datetime.fromtimestamp(seconds, datetime.UTC)


def _seconds(moment: datetime.datetime) -> int:
    return calendar.timegm(moment.timetuple())


def _rounded(moment: datetime.datetime) -> int:
    """Round to the nearest day, as yt-dlp does for days, weeks, months and years."""
    return ((_seconds(moment) + _HALF_DAY_S) // DAY_S) * DAY_S


def _months_before(moment: datetime.datetime, months: int) -> datetime.datetime:
    """Go back whole months on the calendar. A day the month does not have becomes its last."""
    index = moment.year * _MONTHS_IN_A_YEAR + (moment.month - 1) - months
    year, month = divmod(index, _MONTHS_IN_A_YEAR)
    last_day = calendar.monthrange(year, month + 1)[1]
    return moment.replace(year=year, month=month + 1, day=min(moment.day, last_day))
