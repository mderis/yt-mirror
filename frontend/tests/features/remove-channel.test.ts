import { fireEvent, screen, waitFor, within } from '@testing-library/vue'
import { describe, expect, it } from 'vitest'

import { noContent, openApp, part } from '../helpers/app'
import { channel, CHANNEL_ID, OTHER_CHANNEL_ID, video } from '../helpers/catalogue'
import { errorBody, jsonResponse } from '../helpers/fetch'

const REMOVE = `DELETE /api/channels/${CHANNEL_ID}`

/** Open the app on a channel and ask to remove it, through "More actions". */
async function askToRemove(options: Parameters<typeof openApp>[0]) {
  const app = await openApp({ videos: [video(1)], ...options })
  await fireEvent.click(await screen.findByRole('button', { name: 'More actions' }))
  await fireEvent.click(await screen.findByRole('menuitem', { name: 'Remove channel' }))
  const dialog = await screen.findByRole('dialog', { name: 'Remove Sample Channel?' })
  return { app, dialog }
}

describe('the remove channel dialog', () => {
  it('R-CH-32: removing a channel asks first, and says what goes and that the folder stays', async () => {
    const { app, dialog } = await askToRemove({ channels: [channel()] })

    expect(dialog.textContent).toContain(
      'The channel disappears from yt-mirror, including its exclude list and settings.',
    )
    expect(part('[data-folder]').textContent?.trim()).toBe(
      'Its folder and everything in it stay where they are: /Users/sam/Movies/YouTube/Sample Channel',
    )
    expect(app.requests()).not.toContain(REMOVE)
  })

  it('R-CH-32, R-UI-02: "Remove channel" removes it, and without channels the welcome screen is shown', async () => {
    const { app, dialog } = await askToRemove({
      channels: [channel()],
      answers: { [REMOVE]: noContent() },
    })

    await fireEvent.click(within(dialog).getByRole('button', { name: 'Remove channel' }))

    expect(
      await screen.findByRole('heading', { level: 1, name: 'Mirror your first channel' }),
    ).toBeTruthy()
    expect(screen.queryByRole('dialog')).toBeNull()
    expect(
      within(screen.getByRole('navigation')).queryByRole('button', { name: /Sample Channel/ }),
    ).toBeNull()
    expect(app.requests()).toContain(REMOVE)
  })

  it('R-CH-32: a removed channel leaves the sidebar, and the other channels stay', async () => {
    const other = channel({ id: OTHER_CHANNEL_ID, title: 'Other Channel' })
    const { dialog } = await askToRemove({
      channels: [channel(), other],
      answers: {
        [REMOVE]: noContent(),
        [`GET /api/channels/${OTHER_CHANNEL_ID}/videos`]: jsonResponse({ videos: [] }),
      },
    })

    await fireEvent.click(within(dialog).getByRole('button', { name: 'Remove channel' }))

    await waitFor(() => expect(screen.queryByRole('dialog')).toBeNull())
    const sidebar = within(screen.getByRole('navigation'))
    expect(sidebar.queryByRole('button', { name: /Sample Channel/ })).toBeNull()
    expect(sidebar.getByRole('button', { name: /Other Channel/ })).toBeTruthy()
  })

  it('R-UI-12: "Cancel" keeps the channel', async () => {
    const { app, dialog } = await askToRemove({ channels: [channel()] })

    await fireEvent.click(within(dialog).getByRole('button', { name: 'Cancel' }))

    expect(screen.queryByRole('dialog')).toBeNull()
    expect(screen.getByRole('heading', { level: 1, name: 'Sample Channel' })).toBeTruthy()
    expect(app.requests()).not.toContain(REMOVE)
  })

  it('R-ER-02: a removal that fails says why, and the channel and the dialog stay', async () => {
    const { dialog } = await askToRemove({
      channels: [channel()],
      answers: { [REMOVE]: jsonResponse(errorBody('INTERNAL'), 500) },
    })

    await fireEvent.click(within(dialog).getByRole('button', { name: 'Remove channel' }))

    expect((await within(dialog).findByRole('alert')).textContent).toContain(
      'Something unexpected went wrong inside yt-mirror.',
    )
    expect(screen.getByRole('heading', { level: 1, name: 'Sample Channel' })).toBeTruthy()
  })

  it('R-CH-32: "Remove channel" in the menu of a right-click asks the same question', async () => {
    await openApp({ channels: [channel()] })

    await fireEvent.contextMenu(
      within(screen.getByRole('navigation')).getByRole('button', { name: /Sample Channel/ }),
    )
    await fireEvent.click(await screen.findByRole('menuitem', { name: 'Remove channel' }))

    expect(await screen.findByRole('dialog', { name: 'Remove Sample Channel?' })).toBeTruthy()
  })
})
