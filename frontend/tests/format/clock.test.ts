import { afterEach, describe, expect, it, vi } from 'vitest'

import { clock, startClock } from '@/format/clock'

import { NOW } from '../helpers/catalogue'

afterEach(() => vi.useRealTimers())

describe('the clock of the interface', () => {
  it('R-CH-35: the time that "checked 2 min ago" is told from keeps up with the real time', () => {
    vi.useFakeTimers()
    vi.setSystemTime(NOW * 1000)

    const stop = startClock()
    const atStart = clock.now
    vi.advanceTimersByTime(60_000)
    const later = clock.now
    stop()
    vi.advanceTimersByTime(60_000)

    expect(atStart).toBe(NOW)
    expect(later).toBe(NOW + 60)
    expect(clock.now).toBe(NOW + 60)
  })

  it('R-DT-02: dates are shown in the time zone of the Mac unless another one is set', () => {
    expect(clock.timeZone).toBeUndefined()
  })
})
