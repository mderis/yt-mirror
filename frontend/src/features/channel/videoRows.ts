/**
 * What the rows of the video list show (R-CH-10), worked out once per
 * catalogue. A channel can have thousands of videos, so nothing here is
 * worked out again while the list is only looked at.
 *
 * A date that is not exact is written as its precision allows (R-DT-04), with
 * its state: waiting, updating or unavailable, and a note that says what the
 * state is and, for an unavailable one, why and when it is tried again (R-DT-13).
 */
import { computed, type ComputedRef } from 'vue'
import { useI18n } from 'vue-i18n'

import type { ErrorCode, Video } from '@/api/client'
import type { DateLabelState } from '@/components/DateLabel.vue'
import {
  formatApproximateDate,
  formatCount,
  formatDate,
  formatDuration,
  formatTime,
} from '@/format'
import { clock } from '@/format/clock'

/** One row of the list: the video and its texts. */
export interface VideoListRow {
  video: Video
  /** The date as text, whether it is only approximate, its state and what that means. */
  date: VideoDate
  /** The duration as text, or none. */
  duration: string | undefined
  /** The views as text, or null when the listing gave none. */
  views: string | null
}

/** The date of a video as a row shows it. */
export interface VideoDate {
  text: string
  approximate: boolean
  state: DateLabelState
  note: string
}

/** The reasons an unavailable date has a sentence of its own for (R-DT-13). */
const REASONS: readonly ErrorCode[] = [
  'BOT_CHECK',
  'RATE_LIMITED',
  'NETWORK_UNREACHABLE',
  'VIDEO_PRIVATE',
  'VIDEO_REMOVED',
  'MEMBERS_ONLY',
  'AGE_RESTRICTED',
  'GEO_BLOCKED',
  'NOT_YET_AVAILABLE',
]

/** Returns the function that writes the date of a video, as a row shows it. */
export function useDateOf(): (video: Video) => VideoDate {
  const { t } = useI18n()

  function noteOf(video: Video): { state: DateLabelState; note: string } {
    const date = video.date ?? null
    if (date?.state === 'updating') {
      return { state: 'updating', note: t('channel.list.dateUpdating') }
    }
    if (date?.state === 'unavailable') {
      const reason = date.reason !== null && REASONS.includes(date.reason) ? date.reason : null
      const why = t(`channel.list.dateWhy.${reason === null ? 'other' : reason.toLowerCase()}`)
      const note =
        date.retry_at === null
          ? t('channel.list.dateRetryLater', { why })
          : t('channel.list.dateRetryAt', { why, time: formatTime(date.retry_at, clock.timeZone) })
      return { state: 'unavailable', note }
    }
    return { state: 'waiting', note: t('channel.list.dateNote') }
  }

  return function dateOf(video: Video): VideoDate {
    if (video.published_precision !== null && video.published_around !== null) {
      const date = formatApproximateDate(
        video.published_around,
        video.published_precision,
        clock.timeZone,
      )
      return {
        text: t('channel.list.uploadedAround', { date }),
        approximate: true,
        ...noteOf(video),
      }
    }
    if (video.published_at !== null) {
      const date = formatDate(video.published_at, clock.timeZone)
      return {
        text: t('channel.list.uploaded', { date }),
        approximate: false,
        state: 'waiting',
        note: '',
      }
    }
    return { text: t('channel.list.datePending'), approximate: true, ...noteOf(video) }
  }
}

/** Returns the rows of a list of videos. They follow the videos and the time zone. */
export function useVideoRows(videos: () => readonly Video[]): ComputedRef<VideoListRow[]> {
  const { t } = useI18n()
  const dateOf = useDateOf()

  return computed(() =>
    videos().map((video) => ({
      video,
      date: dateOf(video),
      duration: video.duration_s === null ? undefined : formatDuration(video.duration_s),
      views:
        video.view_count === null
          ? null
          : t('channel.list.views', { count: formatCount(video.view_count) }),
    })),
  )
}
