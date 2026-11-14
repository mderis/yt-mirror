/** Runs around every test: removes rendered components and replaced globals, so tests stay independent. */
import { cleanup } from '@testing-library/vue'
import { afterEach, beforeEach, vi } from 'vitest'

import { fakeEventStream } from './helpers/events'

// jsdom has no event stream. Every test gets the stand-in, so that connecting works.
beforeEach(() => {
  fakeEventStream()
})

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
})
