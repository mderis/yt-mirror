/** Runs around every test: removes rendered components and replaced globals, so tests stay independent. */
import { cleanup } from '@testing-library/vue'
import { afterEach, vi } from 'vitest'

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
})
