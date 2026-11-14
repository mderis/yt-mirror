/**
 * What the rows of the video list show (R-CH-10), worked out once per
 * catalogue. A channel can have thousands of videos, so nothing here is
 * worked out again while the list is only looked at.
 *
 * A date that is not exact is written as its precision allows (R-DT-04).
 */
import { computed, type ComputedRef } from 'vue'
import { useI18n } from 'vue-i18n'

import type { Video } from '@/api/client'
import { formatApproximateDate, formatCount, formatDate, formatDuration } from '@/format'
import { clock } from '@/format/clock'

/** One row of the list: the video and its texts. */
export interface VideoListRow {
  video: Video
  /** The date as text, and whether it is only approximate. */
  date: { text: string; approximate: boolean }
  /** The duration as text, or none. */
  duration: string | undefined
  /** The views as text, or null when the listing gave none. */
  views: string | null
}

/** Returns the rows of a list of videos. They follow the videos and the time zone. */
export function useVideoRows(videos: () => readonly Video[]): ComputedRef<VideoListRow[]> {
  const { t } = useI18n()

  function dateOf(video: Video): VideoListRow['date'] {
    if (video.published_precision !== null && video.published_around !== null) {
      const date = formatApproximateDate(
        video.published_around,
        video.published_precision,
        clock.timeZone,
      )
      return { text: t('channel.list.uploadedAround', { date }), approximate: true }
    }
    if (video.published_at !== null) {
      const date = formatDate(video.published_at, clock.timeZone)
      return { text: t('channel.list.uploaded', { date }), approximate: false }
    }
    return { text: t('channel.list.datePending'), approximate: true }
  }

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
