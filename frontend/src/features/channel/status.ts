/**
 * The one status line of a channel, as the sidebar shows it (R-FB-01,
 * R-CH-34, design: States.html): its words, its icon and its tone. The
 * backend decides which status it is. This module only gives it words.
 */
import { useI18n } from 'vue-i18n'

import type { Channel } from '@/api/client'
import type { IconName } from '@/components/icons'
import { formatNumber, formatTime } from '@/format'
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

/** Returns a function that gives the status line of a channel. */
export function useStatusLine(): (channel: Channel) => StatusLine {
  const { t } = useI18n()
  const agoText = useAgo()
  const channels = useChannelsStore()
  return (channel) => {
    if (channel.status === 'waiting_for_youtube') {
      const until = channels.youtubePause?.until
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
    if (channel.status === 'could_not_check') {
      return { text: t('channelStatus.couldNotCheck'), icon: 'warning', tone: 'failed' }
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
