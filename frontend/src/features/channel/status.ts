/**
 * The one status line of a channel, as the sidebar shows it (R-FB-01,
 * R-CH-34, design: States.html): its words, its icon and its tone. The
 * backend decides which status it is. This module only gives it words.
 */
import { useI18n } from 'vue-i18n'

import type { Channel } from '@/api/client'
import type { IconName } from '@/components/icons'
import { formatNumber } from '@/format'
import { useAgo } from '@/format/useAgo'

/** A status line: never told by its tone alone, it always has words and an icon. */
export interface StatusLine {
  text: string
  icon: IconName
  tone: 'muted' | 'progress' | 'ok' | 'failed'
}

/** Whether the first listing of a channel is still to come or running (R-CH-11). */
export function isBeingListed(channel: Channel): boolean {
  return channel.first_listed_at === null && channel.last_check_error === null
}

/** Returns a function that gives the status line of a channel. */
export function useStatusLine(): (channel: Channel) => StatusLine {
  const { t } = useI18n()
  const agoText = useAgo()
  return (channel) => {
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
