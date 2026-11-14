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
/** From this many days on, the time of a check is told as its date. */
const DAYS_TOLD = 14

/** Building a formatter is slow, and a list of thousands of videos asks for the same few. */
const formatters = new Map<string, Intl.DateTimeFormat>()

function dateText(seconds: number, options: Intl.DateTimeFormatOptions, timeZone?: string): string {
  const key = `${JSON.stringify(options)} ${timeZone ?? ''}`
  let formatter = formatters.get(key)
  if (!formatter) {
    formatter = new Intl.DateTimeFormat(DATE_LOCALE, { ...options, timeZone })
    formatters.set(key, formatter)
  }
  return formatter.format(seconds * 1000)
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

const compactNumber = new Intl.NumberFormat(NUMBER_LOCALE, {
  notation: 'compact',
  maximumFractionDigits: 1,
})
const fullNumber = new Intl.NumberFormat(NUMBER_LOCALE)

/** A large count in short: "950", "48K", "1.2M". */
export function formatCount(count: number): string {
  return compactNumber.format(count)
}

/** A count in full, with separators: "1,200". */
export function formatNumber(count: number): string {
  return fullNumber.format(count)
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
  | { key: 'time.daysAgo'; count: number }
  | { key: 'time.onDate'; date: string }

/**
 * How long ago a check was: just now, minutes, hours, days, and from two weeks on the date.
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
  if (passed < DAYS_TOLD * DAY) {
    return { key: 'time.daysAgo', count: Math.floor(passed / DAY) }
  }
  return { key: 'time.onDate', date: formatDate(then, timeZone) }
}

/** The time zone of this Mac, by its name. */
function systemTimeZone(): string {
  return new Intl.DateTimeFormat().resolvedOptions().timeZone
}

/** How far a time zone is ahead of UTC at a moment, in seconds. */
function offsetOf(seconds: number, timeZone: string): number {
  const parts = new Intl.DateTimeFormat('en-US', {
    timeZone,
    hourCycle: 'h23',
    year: 'numeric',
    month: 'numeric',
    day: 'numeric',
    hour: 'numeric',
    minute: 'numeric',
    second: 'numeric',
  }).formatToParts(seconds * 1000)
  const part = (type: string): number => Number(parts.find((found) => found.type === type)?.value)
  const shown = Date.UTC(
    part('year'),
    part('month') - 1,
    part('day'),
    part('hour'),
    part('minute'),
    part('second'),
  )
  return shown / 1000 - seconds
}

/**
 * The moment a day begins in a time zone, in seconds since the epoch.
 *
 * @param day The day as a date field gives it: "2026-11-14".
 * @param timeZone The time zone. Without it, the zone of this Mac.
 * @returns The moment, or null when the text is no day.
 */
export function startOfDay(day: string, timeZone: string = systemTimeZone()): number | null {
  const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(day)
  if (!match) {
    return null
  }
  const asUtc = Date.UTC(Number(match[1]), Number(match[2]) - 1, Number(match[3])) / 1000
  // The offset at the guess can differ from the offset at the answer when the clocks change.
  const guess = asUtc - offsetOf(asUtc, timeZone)
  return asUtc - offsetOf(guess, timeZone)
}
