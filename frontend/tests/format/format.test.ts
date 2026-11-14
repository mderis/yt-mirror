import { describe, expect, it } from 'vitest'

import {
  ago,
  formatApproximateDate,
  formatBytes,
  formatCount,
  formatDate,
  formatDuration,
  formatNumber,
  formatTime,
  startOfDay,
} from '@/format'

import { NOW } from '../helpers/catalogue'

/** 11 Nov 2026, 21:40:00 UTC. */
const MOMENT = 1_794_433_200

describe('how values are written for the user', () => {
  it('R-DT-02: a date is absolute and written in the time zone it is shown in', () => {
    expect(formatDate(MOMENT, 'UTC')).toBe('11 Nov 2026')
    expect(formatDate(MOMENT, 'Asia/Tehran')).toBe('12 Nov 2026')
    expect(formatDate(MOMENT, 'America/Los_Angeles')).toBe('11 Nov 2026')
  })

  it('R-DT-02: a time of day follows the time zone too', () => {
    expect(formatTime(MOMENT, 'UTC')).toBe('21:40')
    expect(formatTime(MOMENT, 'Asia/Tehran')).toBe('01:10')
    expect(formatTime(MOMENT + 3 * 3600, 'UTC')).toBe('00:40')
  })

  it('R-DT-04: an approximate date is written as far as its precision allows', () => {
    expect(formatApproximateDate(MOMENT, 'year', 'UTC')).toBe('2026')
    expect(formatApproximateDate(MOMENT, 'month', 'UTC')).toBe('Nov 2026')
    expect(formatApproximateDate(MOMENT, 'week', 'UTC')).toBe('11 Nov 2026')
    expect(formatApproximateDate(MOMENT, 'day', 'UTC')).toBe('11 Nov 2026')
  })

  it('R-DT-04: the year and the month of an approximate date follow the time zone', () => {
    const newYearsEve = 1_798_759_800 // 31 Dec 2026, 23:30:00 UTC

    expect(formatApproximateDate(newYearsEve, 'year', 'UTC')).toBe('2026')
    expect(formatApproximateDate(newYearsEve, 'year', 'Asia/Tehran')).toBe('2027')
    expect(formatApproximateDate(newYearsEve, 'month', 'Asia/Tehran')).toBe('Jan 2027')
  })

  it('R-CH-10: a duration is written as a player shows it', () => {
    expect(formatDuration(0)).toBe('00:00')
    expect(formatDuration(59)).toBe('00:59')
    expect(formatDuration(573)).toBe('09:33')
    expect(formatDuration(3600)).toBe('1:00:00')
    expect(formatDuration(6150)).toBe('1:42:30')
    expect(formatDuration(36_061)).toBe('10:01:01')
  })

  it('R-CH-10: a view count is written in short', () => {
    expect(formatCount(0)).toBe('0')
    expect(formatCount(950)).toBe('950')
    expect(formatCount(48_000)).toBe('48K')
    expect(formatCount(1_240_000)).toBe('1.2M')
    expect(formatCount(4_100_000)).toBe('4.1M')
  })

  it('R-CH-35: a number of videos is written in full, with separators', () => {
    expect(formatNumber(57)).toBe('57')
    expect(formatNumber(1200)).toBe('1,200')
    expect(formatNumber(6597)).toBe('6,597')
  })

  it('R-CH-35: a size on disk is written in megabytes, and from a thousand of them in gigabytes', () => {
    expect(formatBytes(0)).toBe('0 MB')
    expect(formatBytes(412_400_000)).toBe('412 MB')
    expect(formatBytes(999_400_000)).toBe('999 MB')
    expect(formatBytes(1_000_000_000)).toBe('1 GB')
    expect(formatBytes(41_240_000_000)).toBe('41.2 GB')
    expect(formatBytes(412_000_000_000)).toBe('412 GB')
  })

  it('R-CH-35: the time of a check is told as just now, minutes or hours ago', () => {
    expect(ago(NOW, NOW)).toEqual({ key: 'time.justNow' })
    expect(ago(NOW, NOW - 59)).toEqual({ key: 'time.justNow' })
    expect(ago(NOW, NOW - 60)).toEqual({ key: 'time.minutesAgo', count: 1 })
    expect(ago(NOW, NOW - 125)).toEqual({ key: 'time.minutesAgo', count: 2 })
    expect(ago(NOW, NOW - 3599)).toEqual({ key: 'time.minutesAgo', count: 59 })
    expect(ago(NOW, NOW - 3600)).toEqual({ key: 'time.hoursAgo', count: 1 })
    expect(ago(NOW, NOW - 86_399)).toEqual({ key: 'time.hoursAgo', count: 23 })
  })

  it('R-CH-35: from a day on, the time of a check is told in days, and from two weeks on as its date', () => {
    expect(ago(NOW, NOW - 86_400, 'UTC')).toEqual({ key: 'time.daysAgo', count: 1 })
    expect(ago(NOW, NOW - 3 * 86_400, 'UTC')).toEqual({ key: 'time.daysAgo', count: 3 })
    expect(ago(NOW, NOW - 14 * 86_400 + 1, 'UTC')).toEqual({ key: 'time.daysAgo', count: 13 })
    expect(ago(NOW, NOW - 14 * 86_400, 'UTC')).toEqual({ key: 'time.onDate', date: '31 Oct 2026' })
    expect(ago(NOW, NOW - 14 * 86_400 - 6 * 3600, 'Asia/Tehran')).toEqual({
      key: 'time.onDate',
      date: '31 Oct 2026',
    })
  })

  it('R-CH-35: a check whose time lies ahead of the clock of the window was just now', () => {
    expect(ago(NOW, NOW + 5)).toEqual({ key: 'time.justNow' })
  })

  it('R-MI-03, R-DT-02: the date of "only videos uploaded after" begins with that day in the time zone it is shown in', () => {
    // 1 Nov 2026, 00:00:00 UTC.
    const utcMidnight = 1_793_491_200

    expect(startOfDay('2026-11-01', 'UTC')).toBe(utcMidnight)
    expect(startOfDay('2026-11-01', 'Asia/Tehran')).toBe(utcMidnight - 3.5 * 3600)
    expect(startOfDay('2026-11-01', 'America/Los_Angeles')).toBe(utcMidnight + 7 * 3600)
    expect(formatDate(startOfDay('2026-11-01', 'Asia/Tehran') as number, 'Asia/Tehran')).toBe(
      '1 Nov 2026',
    )
  })

  it('R-MI-03, R-DT-02: the day begins at the right moment also on the days the clocks change', () => {
    // In Los Angeles the clocks go back on 1 Nov 2026 and forward on 8 Mar 2026.
    const zone = 'America/Los_Angeles'

    expect(startOfDay('2026-11-02', zone)).toBe(Date.UTC(2026, 10, 2, 8) / 1000)
    expect(startOfDay('2026-03-08', zone)).toBe(Date.UTC(2026, 2, 8, 8) / 1000)
    expect(startOfDay('2026-03-09', zone)).toBe(Date.UTC(2026, 2, 9, 7) / 1000)
  })

  it('R-MI-03, R-DT-02: without a time zone the day begins in the zone of the Mac', () => {
    const here = new Intl.DateTimeFormat().resolvedOptions().timeZone

    expect(startOfDay('2026-11-01')).toBe(startOfDay('2026-11-01', here))
  })

  it('R-MI-03: what is no day gives no date', () => {
    expect(startOfDay('')).toBeNull()
    expect(startOfDay('1 Nov 2026')).toBeNull()
  })
})
