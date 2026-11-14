/**
 * Tells how long ago something happened, in the words of the texts and by
 * the clock of the interface: "2 min ago", "yesterday", "on 11 Nov 2026".
 */
import { useI18n } from 'vue-i18n'

import { clock } from './clock'
import { ago } from './index'

/** Returns a function that tells how long ago a moment (in seconds) was. */
export function useAgo(): (then: number) => string {
  const { t } = useI18n()
  return (then) => {
    const told = ago(clock.now, then, clock.timeZone)
    if (told.key === 'time.daysAgo') {
      return t(told.key, { count: told.count }, told.count)
    }
    return t(told.key, told)
  }
}
