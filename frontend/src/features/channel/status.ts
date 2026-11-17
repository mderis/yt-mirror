/**
 * The one status line of a channel, as the sidebar shows it (R-FB-01,
 * R-CH-34, design: States.html): its words, its icon and its tone. The
 * backend decides which status it is. This module only gives it words:
 * "Exact dates 340 of 1,000 · about 50 minutes left" (R-DT-14) and "Could
 * not check · retrying in 5 min" (R-CH-25) among them.
 */
import { useI18n } from 'vue-i18n'

import type { Channel } from '@/api/client'
import type { IconName } from '@/components/icons'
import { formatNumber, formatTime, roughTime } from '@/format'
import { clock } from '@/format/clock'
import { useAgo } from '@/format/useAgo'
import { useChannelsStore } from '@/stores/channels'

/** A status line: never told by its tone alone, it always has words and an icon. */
export interface StatusLine {
  text: string
  /** More about it, as the tooltip. */
  note?: string | undefined
  icon: IconName
  tone: 'muted' | 'progress' | 'ok' | 'failed'
}

/**
 * Whether the first listing of a channel is still to come or running (R-CH-11).
 * A first listing that failed is being listed again while its retry runs (R-CH-25).
 */
export function isBeingListed(channel: Channel): boolean {
  return (
    channel.first_listed_at === null &&
    (channel.last_check_error === null || channel.status === 'checking')
  )
}

/**
 * Returns a function that tells how far the exact dates of a channel are:
 * "Exact dates 340 of 1,000 · about 50 minutes left", or that they wait for
 * YouTube and until when. Null while none of its dates waits (R-DT-14, D-086).
 */
export function useExactDatesText(): (channel: Channel) => string | null {
  const { t } = useI18n()
  return (channel) => {
    const progress = channel.exact_dates ?? null
    if (progress === null) {
      return null
    }
    const values = { done: formatNumber(progress.done), total: formatNumber(progress.total) }
    const until = channel.waiting_until ?? null
    if (until !== null) {
      return t('channelStatus.exactDatesWaiting', {
        ...values,
        time: formatTime(until, clock.timeZone),
      })
    }
    if (progress.left_s === null) {
      return t('channelStatus.exactDates', values)
    }
    const left = roughTime(progress.left_s)
    return t('channelStatus.exactDatesLeft', {
      ...values,
      left: t(`rough.${left.unit}Left`, { count: left.count }, left.count),
    })
  }
}

/** Returns a function that gives the status line of a channel. */
export function useStatusLine(): (channel: Channel) => StatusLine {
  const { t } = useI18n()
  const agoText = useAgo()
  const channels = useChannelsStore()
  const exactDatesOf = useExactDatesText()
  return (channel) => {
    if (channel.status === 'mirroring' && channel.mirroring) {
      const done = Math.min(channel.mirroring.done + 1, channel.mirroring.total)
      return {
        text: t('channelStatus.mirroring', {
          done: formatNumber(done),
          total: formatNumber(channel.mirroring.total),
        }),
        icon: 'download',
        tone: 'progress',
      }
    }
    const exactDates = exactDatesOf(channel)
    if (channel.status === 'exact_dates' && exactDates !== null) {
      return { text: exactDates, icon: 'loading', tone: 'progress' }
    }
    if (channel.status === 'waiting_for_youtube') {
      const until = channels.youtubePause?.until ?? channel.waiting_until ?? undefined
      return {
        text: t('channelStatus.waitingForYouTube'),
        note:
          until === undefined
            ? undefined
            : t('channelStatus.nextAttempt', { time: formatTime(until, clock.timeZone) }),
        icon: 'clock',
        tone: 'muted',
      }
    }
    if (channel.status === 'folder_not_found') {
      return { text: t('channelStatus.folderNotFound'), icon: 'warning', tone: 'failed' }
    }
    if (channel.status === 'could_not_check') {
      const at = channel.retry_at ?? null
      if (at === null) {
        return { text: t('channelStatus.couldNotCheck'), icon: 'warning', tone: 'failed' }
      }
      const seconds = at - clock.now
      if (seconds <= 0) {
        return {
          text: t('channelStatus.couldNotCheckRetryingSoon'),
          icon: 'warning',
          tone: 'failed',
        }
      }
      const wait = roughTime(seconds)
      return {
        text: t('channelStatus.couldNotCheckRetrying', {
          in: t(`rough.${wait.unit}`, { count: wait.count }, wait.count),
        }),
        icon: 'warning',
        tone: 'failed',
      }
    }
    if (channel.status === 'new_videos') {
      const count = channel.new_videos
      return {
        text: t('channelStatus.newVideos', { count: formatNumber(count) }, count),
        icon: 'video',
        tone: 'progress',
      }
    }
    if (channel.status === 'paused') {
      return { text: t('channelStatus.paused'), icon: 'pause', tone: 'muted' }
    }
    if (channel.status === 'checking' || channel.last_check_at === null) {
      return { text: t('channelStatus.checking'), icon: 'retry', tone: 'muted' }
    }
    return {
      text: t('channelStatus.upToDate', { ago: agoText(channel.last_check_at) }),
      icon: 'check',
      tone: 'ok',
    }
  }
}
