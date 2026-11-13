import { fireEvent, screen, waitFor } from '@testing-library/vue'
import { describe, expect, it } from 'vitest'

import App from '@/App.vue'

import { errorBody, HEALTH, jsonResponse, mockFetch } from '../helpers/fetch'
import { renderWithApp } from '../helpers/render'

describe('the placeholder page', () => {
  it('R-IN-02: shows the app name, that it is running, and the version from the backend', async () => {
    mockFetch(() => jsonResponse(HEALTH))

    renderWithApp(App)

    expect(screen.getByRole('heading', { level: 1 }).textContent).toContain('yt-mirror')
    expect(await screen.findByText('yt-mirror is running.')).toBeTruthy()
    expect(screen.getByText('Version 1.2.3')).toBeTruthy()
    expect(screen.queryByRole('alert')).toBeNull()
  })

  it('R-UI-11: shows a status while the answer of the backend is pending', async () => {
    let answer: (response: Response) => void = () => {}
    mockFetch(() => new Promise<Response>((resolve) => (answer = resolve)))

    renderWithApp(App)

    expect((await screen.findByRole('status')).textContent).toContain('Connecting to yt-mirror')
    answer(jsonResponse(HEALTH))
    await screen.findByText('yt-mirror is running.')
    expect(screen.queryByRole('status')).toBeNull()
  })

  it('R-ER-01: explains a failure in plain words and shows the error code', async () => {
    mockFetch(() => jsonResponse(errorBody('UNAUTHORIZED'), 401))

    renderWithApp(App)

    const alert = await screen.findByRole('alert')
    expect(alert.textContent).toContain('The window could not reach yt-mirror.')
    expect(alert.textContent).toContain('Error code: UNAUTHORIZED')
    expect(screen.queryByText('yt-mirror is running.')).toBeNull()
  })

  it('R-ER-01: shows no error code line when the backend could not be reached at all', async () => {
    mockFetch(() => Promise.reject(new TypeError('Failed to fetch')))

    renderWithApp(App)

    const alert = await screen.findByRole('alert')
    expect(alert.textContent).toContain('The window could not reach yt-mirror.')
    expect(alert.textContent).not.toContain('Error code')
  })

  it('R-ER-03: offers a real button that tries again and recovers', async () => {
    const answers = [jsonResponse(errorBody('INTERNAL'), 500), jsonResponse(HEALTH)]
    const fetchMock = mockFetch(() => answers.shift() as Response)
    renderWithApp(App)

    await fireEvent.click(await screen.findByRole('button', { name: 'Try again' }))

    await waitFor(() => expect(screen.getByText('Version 1.2.3')).toBeTruthy())
    expect(fetchMock).toHaveBeenCalledTimes(2)
    expect(screen.queryByRole('alert')).toBeNull()
  })
})
