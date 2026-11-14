/** Opens the whole app against canned answers of the API, for tests of the screens. */
import { screen } from '@testing-library/vue'
import type { Mock } from 'vitest'

import type { AppState, Channel, Video } from '@/api/client'
import App from '@/App.vue'
import { clock } from '@/format/clock'

import { appState, CHANNEL_ID, NOW } from './catalogue'
import { fakeEventStream, type FakeEventSource } from './events'
import { healthyApi, jsonResponse } from './fetch'
import { renderWithApp } from './render'

type Answers = Parameters<typeof healthyApi>[0]

export interface OpenedApp {
  fetchMock: Mock<typeof fetch>
  /** The event stream of the window. */
  stream: () => FakeEventSource
  router: ReturnType<typeof renderWithApp>['router']
  /** The requests that were made, as "POST /api/channels". */
  requests: () => string[]
  /** The body of the last request to a path, read from JSON. */
  lastBody: (path: string) => unknown
}

/** An answer without content, as the API gives for "done". */
export function noContent(): () => Response {
  return () => new Response(null, { status: 204 })
}

/**
 * Open the app at the fixed time of the tests, in UTC.
 *
 * @param options.channels The channels of the sidebar.
 * @param options.videos The catalogue of the first channel.
 * @param options.state Other parts of the snapshot.
 * @param options.answers More answers of the API, by "METHOD /path".
 * @param options.route The address the window starts at.
 */
export async function openApp(
  options: {
    channels?: Channel[]
    videos?: Video[]
    state?: Partial<AppState>
    answers?: Answers
    route?: string
  } = {},
): Promise<OpenedApp> {
  clock.now = NOW
  clock.timeZone = 'UTC'
  const channels = options.channels ?? []
  const stream = fakeEventStream()
  const fetchMock = healthyApi({
    'GET /api/state': jsonResponse(appState({ channels, ...options.state })),
    'PUT /api/state/open-channel': jsonResponse(appState({ channels })),
    [`GET /api/channels/${channels[0]?.id ?? CHANNEL_ID}/videos`]: jsonResponse({
      videos: options.videos ?? [],
    }),
    ...options.answers,
  })
  const { router } = renderWithApp(App, options.route)
  await screen.findByRole('navigation', { name: 'Channels' })
  return {
    fetchMock,
    stream,
    router,
    requests: () =>
      fetchMock.mock.calls.map(([path, init]) => `${init?.method ?? 'GET'} ${String(path)}`),
    lastBody: (path) => {
      const call = fetchMock.mock.calls.findLast(([asked]) => asked === path)
      return JSON.parse(String(call?.[1]?.body ?? 'null'))
    },
  }
}

/** The element with a data attribute, or an error that names it. */
export function part(selector: string): HTMLElement {
  const found = document.querySelector<HTMLElement>(selector)
  if (!found) {
    throw new Error(`Nothing on the page matches ${selector}`)
  }
  return found
}
