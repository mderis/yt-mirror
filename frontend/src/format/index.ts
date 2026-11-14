/**
 * How values are written for the user: dates, durations, counts, sizes.
 *
 * Every function gets what it needs as arguments, the time zone and the
 * current time included, so nothing here depends on the machine it runs on
 * (docs/TESTING.md rule 4). Dates are absolute (R-DT-02): "11 Nov 2026".
 * Only the time of a check is told as "2 min ago".
 */
import type { DatePrecision } from '@/api/client'

const DATE_LOCALE = 'en-GB'
const NUMBER_LOCALE = 'en'
const MINUTE = 60
const HOUR = 60 * MINUTE
const DAY = 24 * HOUR
const KB = 1000

function dateText(seconds: number, options: Intl.DateTimeFormatOptions, timeZone?: string): string {
  return new Intl.DateTimeFormat(DATE_LOCALE, { ...options, timeZone }).format(seconds * 1000)
}

/** An exact date: "11 Nov 2026". */
export function formatDate(seconds: number, timeZone?: string): string {
  return dateText(seconds, { day: 'numeric', month: 'short', year: 'numeric' }, timeZone)
}

/** A time of day: "21:40". */
export function formatTime(seconds: number, timeZone?: string): string {
  return dateText(seconds, { hour: '2-digit', minute: '2-digit', hourCycle: 'h23' }, timeZone)
}

/**
 * An approximate date, as far as its precision allows (R-DT-04): "2005" for
 * years, "Mar 2026" for months, "11 Nov 2026" for weeks and days. The word
 * "around" in front of it comes from the texts.
 */
export function formatApproximateDate(
  seconds: number,
  precision: DatePrecision,
  timeZone?: string,
): string {
  if (precision === 'year') {
    return dateText(seconds, { year: 'numeric' }, timeZone)
  }
  if (precision === 'month') {
    return dateText(seconds, { month: 'short', year: 'numeric' }, timeZone)
  }
  return formatDate(seconds, timeZone)
}

/** A duration as a player shows it: "09:33", "1:42:30". */
export function formatDuration(seconds: number): string {
  const two = (value: number): string => String(value).padStart(2, '0')
  const hours = Math.floor(seconds / HOUR)
  const minutes = Math.floor((seconds % HOUR) / MINUTE)
  const rest = Math.floor(seconds % MINUTE)
  return hours > 0 ? `${hours}:${two(minutes)}:${two(rest)}` : `${two(minutes)}:${two(rest)}`
}

/** A large count in short: "950", "48K", "1.2M". */
export function formatCount(count: number): string {
  return new Intl.NumberFormat(NUMBER_LOCALE, {
    notation: 'compact',
    maximumFractionDigits: 1,
  }).format(count)
}

/** A count in full, with separators: "1,200". */
export function formatNumber(count: number): string {
  return new Intl.NumberFormat(NUMBER_LOCALE).format(count)
}

/** A size on disk: "412 MB", "41.2 GB". */
export function formatBytes(bytes: number): string {
  const megabytes = bytes / KB / KB
  if (megabytes < KB) {
    return `${Math.round(megabytes)} MB`
  }
  const gigabytes = megabytes / KB
  return `${gigabytes >= 100 ? Math.round(gigabytes) : Math.round(gigabytes * 10) / 10} GB`
}

/** How long ago something happened, as the key of a text and what goes into it. */
export type Ago =
  | { key: 'time.justNow' }
  | { key: 'time.minutesAgo'; count: number }
  | { key: 'time.hoursAgo'; count: number }
  | { key: 'time.onDate'; date: string }

/**
 * How long ago a check was: just now, minutes, hours, and from a day on the date.
 *
 * @param now The current time in seconds.
 * @param then The moment that is meant, in seconds.
 */
export function ago(now: number, then: number, timeZone?: string): Ago {
  const passed = Math.max(now - then, 0)
  if (passed < MINUTE) {
    return { key: 'time.justNow' }
  }
  if (passed < HOUR) {
    return { key: 'time.minutesAgo', count: Math.floor(passed / MINUTE) }
  }
  if (passed < DAY) {
    return { key: 'time.hoursAgo', count: Math.floor(passed / HOUR) }
  }
  return { key: 'time.onDate', date: formatDate(then, timeZone) }
}
