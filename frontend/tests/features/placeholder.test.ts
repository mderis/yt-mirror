import { fireEvent, screen, waitFor } from '@testing-library/vue'
import { describe, expect, it } from 'vitest'

import App from '@/App.vue'

import {
  allToolsReady,
  errorBody,
  HEALTH,
  healthyApi,
  jsonResponse,
  mockFetch,
} from '../helpers/fetch'
import { renderWithApp } from '../helpers/render'

describe('the placeholder page', () => {
  it('infra: shows the app name, that it is running, and the version from the backend', async () => {
    healthyApi()

    renderWithApp(App)

    expect(screen.getByRole('heading', { level: 1 }).textContent).toContain('yt-mirror')
    expect(await screen.findByText('yt-mirror is running.')).toBeTruthy()
    expect(screen.getByText('Version 1.2.3')).toBeTruthy()
    expect(screen.queryByRole('alert')).toBeNull()
  })

  it('infra: shows a status while the answer of the backend is pending', async () => {
    let answer: (response: Response) => void = () => {}
    healthyApi({
      'GET /api/health': () => new Promise<Response>((resolve) => (answer = resolve)),
    })

    renderWithApp(App)

    expect((await screen.findByRole('status')).textContent).toContain('Connecting to yt-mirror')
    answer(jsonResponse(HEALTH))
    await screen.findByText('yt-mirror is running.')
    expect(screen.queryByRole('status')).toBeNull()
  })

  it('infra: explains a refused request in plain words and shows the error code', async () => {
    mockFetch(() => jsonResponse(errorBody('UNAUTHORIZED'), 401))

    renderWithApp(App)

    const alert = await screen.findByRole('alert')
    expect(alert.textContent).toContain('yt-mirror answered with an error.')
    expect(alert.textContent).toContain('Error code: UNAUTHORIZED')
    expect(screen.queryByText('yt-mirror is running.')).toBeNull()
  })

  it('infra: explains an unreachable server with the texts of its own error code', async () => {
    mockFetch(() => Promise.reject(new TypeError('Failed to fetch')))

    renderWithApp(App)

    const alert = await screen.findByRole('alert')
    expect(alert.textContent).toContain('The window cannot reach yt-mirror.')
    expect(alert.textContent).toContain('yt-mirror does not try again by itself here.')
    expect(alert.textContent).toContain('Try again. If that does not help, quit yt-mirror')
    expect(alert.textContent).toContain('Error code: LOCAL_SERVER_UNREACHABLE')
    expect(alert.textContent).not.toContain('yt-mirror answered with an error.')
  })

  it('infra: offers a real button that tries again and recovers', async () => {
    const answers = [jsonResponse(errorBody('INTERNAL'), 500), jsonResponse(HEALTH)]
    const fetchMock = healthyApi({ 'GET /api/health': () => answers.shift() as Response })
    renderWithApp(App)

    await fireEvent.click(await screen.findByRole('button', { name: 'Try again' }))

    await waitFor(() => expect(screen.getByText('Version 1.2.3')).toBeTruthy())
    expect(fetchMock.mock.calls.map(([path]) => path)).toEqual([
      '/api/health',
      '/api/health',
      '/api/tools',
    ])
    expect(screen.queryByRole('alert')).toBeNull()
    expect(allToolsReady().setup_required).toBe(false)
  })
})
