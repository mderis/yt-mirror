/**
 * The clock of the interface: the current time, which texts such as
 * "checked 2 min ago" follow, and the time zone dates are shown in.
 *
 * It is one reactive object, so a test can set the time and the zone instead
 * of depending on the machine (docs/TESTING.md rule 4). The app lets it tick.
 */
import { reactive } from 'vue'

const TICK_MS = 30_000

export const clock = reactive<{
  /** The current time, in seconds since the Unix epoch. */
  now: number
  /** The time zone dates are shown in. Undefined means the zone of the Mac (R-DT-02). */
  timeZone: string | undefined
}>({ now: Math.floor(Date.now() / 1000), timeZone: undefined })

/** Let the clock follow the real time. Returns a function that stops it. */
export function startClock(): () => void {
  const tick = (): void => {
    clock.now = Math.floor(Date.now() / 1000)
  }
  tick()
  const timer = setInterval(tick, TICK_MS)
  return () => clearInterval(timer)
}
