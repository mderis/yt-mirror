import { fireEvent, screen, waitFor } from '@testing-library/vue'
import { describe, expect, it } from 'vitest'

import App from '@/App.vue'

import { errorBody, HEALTH, healthyApi, jsonResponse, mockFetch } from '../helpers/fetch'
import { renderWithApp } from '../helpers/render'

describe('the connection page', () => {
  it('R-ER-04: while the window connects, it says so', () => {
    mockFetch(() => new Promise<Response>(() => undefined))

    renderWithApp(App)

    expect(screen.getByRole('status').textContent).toContain('Connecting to yt-mirror')
    expect(screen.queryByRole('alert')).toBeNull()
  })

  it('R-ER-04: a window that cannot reach its server says so in plain words and under its code', async () => {
    mockFetch(() => Promise.reject(new TypeError('Failed to fetch')))

    renderWithApp(App)

    const alert = await screen.findByRole('alert')
    expect(alert.textContent).toContain('The window cannot reach yt-mirror.')
    expect(alert.textContent).toContain('Try again.')
    expect(alert.textContent).toContain('Error code: LOCAL_SERVER_UNREACHABLE')
  })

  it('R-ER-04: "Try again" is a real button that connects again and opens the app', async () => {
    const answers = [jsonResponse(errorBody('INTERNAL'), 500), jsonResponse(HEALTH)]
    healthyApi({ 'GET /api/health': () => answers.shift() as Response })
    renderWithApp(App)

    await fireEvent.click(await screen.findByRole('button', { name: 'Try again' }))

    await waitFor(() => expect(screen.getByRole('navigation', { name: 'Channels' })).toBeTruthy())
    expect(screen.queryByRole('alert')).toBeNull()
  })

  it('R-ER-02: an error whose code has no texts of its own gets a plain sentence and its code', async () => {
    mockFetch(() => jsonResponse(errorBody('UNAUTHORIZED'), 401))

    renderWithApp(App)

    const alert = await screen.findByRole('alert')
    expect(alert.textContent).toContain('yt-mirror answered with an error.')
    expect(alert.textContent).toContain('Error code: UNAUTHORIZED')
  })
})
