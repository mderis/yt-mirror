import { fireEvent, screen, waitFor, within } from '@testing-library/vue'
import { describe, expect, it } from 'vitest'

import { openApp, part } from '../helpers/app'
import { channel, CHANNEL_ID, OTHER_CHANNEL_ID, video } from '../helpers/catalogue'
import { errorBody, jsonResponse } from '../helpers/fetch'

const REMOVE = `DELETE /api/channels/${CHANNEL_ID}?keep_files=true`
const REMOVE_AND_TRASH = `DELETE /api/channels/${CHANNEL_ID}?keep_files=false`
const FILES_TO_TRASH = `GET /api/channels/${CHANNEL_ID}/files-to-trash`
const FOLDER = '/Users/sam/Movies/YouTube/Sample Channel'

/** The answer of a removal that left these files in the folder. */
function removedWith(left: { file: string; reason: string }[] = []) {
  return jsonResponse({ folder: FOLDER, files_trashed: 3, left })
}

/** Open the app on a channel and ask to remove it, through "More actions". */
async function askToRemove(options: Parameters<typeof openApp>[0]) {
  const app = await openApp({
    videos: [video(1)],
    ...options,
    answers: {
      [FILES_TO_TRASH]: jsonResponse({ files: 3, size_bytes: 1_250_000_000 }),
      ...options?.answers,
    },
  })
  await fireEvent.click(await screen.findByRole('button', { name: 'More actions' }))
  await fireEvent.click(await screen.findByRole('menuitem', { name: 'Remove channel' }))
  const dialog = await screen.findByRole('dialog', { name: 'Remove Sample Channel?' })
  return { app, dialog }
}

describe('the remove channel dialog', () => {
  it('R-CH-32: removing a channel asks first, and offers to keep the files or move them to the Trash', async () => {
    const { app, dialog } = await askToRemove({
      channels: [channel({ synced: 212, size_bytes: 41_200_000_000 })],
    })

    expect(dialog.textContent).toContain(
      'The channel disappears from yt-mirror, including its exclude list and settings.',
    )
    expect(part('[data-downloaded]').textContent?.trim()).toBe('212 downloaded videos (41.2 GB)')
    const keep = within(dialog).getByRole('radio', { name: /Keep the files/ })
    const trash = within(dialog).getByRole('radio', { name: /Delete the files/ })
    expect((keep as HTMLInputElement).checked).toBe(true)
    expect((trash as HTMLInputElement).checked).toBe(false)
    expect(dialog.textContent).toContain('They stay in /Users/sam/Movies/YouTube/Sample Channel.')
    await waitFor(() =>
      expect(dialog.textContent).toContain(
        '3 files (1.3 GB) go to the Trash, so you can still get them back. Other files in the folder stay where they are.',
      ),
    )
    expect(app.requests()).not.toContain(REMOVE)
  })

  it('R-CH-32: while the downloads of the channel stop, the dialog says so and stays open', async () => {
    const { dialog } = await askToRemove({
      channels: [channel({ status: 'mirroring' })],
      videos: [video(1, { status: 'downloading' }), video(2, { status: 'processing' }), video(3)],
      // The removal waits for the downloads to stop, and has not answered yet.
      answers: { [REMOVE]: () => new Promise<Response>(() => undefined) },
    })

    await fireEvent.click(within(dialog).getByRole('button', { name: 'Remove channel' }))

    expect((await within(dialog).findByRole('status')).textContent?.trim()).toBe(
      'Stopping 2 downloads...',
    )
    const cancel = within(dialog).getByRole('button', { name: 'Cancel' }) as HTMLButtonElement
    expect(cancel.disabled).toBe(true)
  })

  it('R-CH-32: "Delete the files" asks the backend to move the files to the Trash', async () => {
    const { app, dialog } = await askToRemove({
      channels: [channel()],
      answers: { [REMOVE_AND_TRASH]: removedWith() },
    })

    await fireEvent.click(within(dialog).getByRole('radio', { name: /Delete the files/ }))
    await fireEvent.click(within(dialog).getByRole('button', { name: 'Remove channel' }))

    await waitFor(() => expect(app.requests()).toContain(REMOVE_AND_TRASH))
    expect(app.requests()).not.toContain(REMOVE)
  })

  it('R-CH-32, R-UI-02: "Remove channel" removes it, and without channels the welcome screen is shown', async () => {
    const { app, dialog } = await askToRemove({
      channels: [channel()],
      answers: { [REMOVE]: removedWith() },
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
        [REMOVE]: removedWith(),
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

  it('R-CH-32: a removal refused because a download is still finishing says so and keeps the channel', async () => {
    const { dialog } = await askToRemove({
      channels: [channel()],
      answers: { [REMOVE_AND_TRASH]: jsonResponse(errorBody('CHANNEL_BUSY'), 409) },
    })

    await fireEvent.click(within(dialog).getByRole('radio', { name: /Delete the files/ }))
    await fireEvent.click(within(dialog).getByRole('button', { name: 'Remove channel' }))

    const alert = await within(dialog).findByRole('alert')
    expect(alert.textContent).toContain(
      'The channel was not removed: a download or a check of it is still finishing.',
    )
    expect(alert.textContent).toContain(
      'Its folder and files are as they were. Its waiting checks were dropped and, once no check was running, its downloads were cancelled.',
    )
    expect(alert.textContent).toContain(
      'Try again in a minute. If you keep the channel, mirror its videos again.',
    )
    expect(alert.textContent).not.toContain('Nothing else was changed')
    expect(screen.getByRole('heading', { level: 1, name: 'Sample Channel' })).toBeTruthy()
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

  it('R-CH-32: every file that stayed is named with its reason once the channel is gone', async () => {
    const left = [
      { file: 'Locked 1.mkv', reason: 'trash_refused' },
      { file: 'Q and A.mkv', reason: 'another_video' },
      { file: 'Unreadable.mkv', reason: 'not_checked' },
      { file: 'Linked.mkv', reason: 'outside_folder' },
      ...Array.from({ length: 8 }, (_, index) => ({
        file: `Locked ${index + 2}.mkv`,
        reason: 'trash_refused',
      })),
    ]
    const { dialog } = await askToRemove({
      channels: [channel(), channel({ id: OTHER_CHANNEL_ID, title: 'Other Channel' })],
      answers: { [REMOVE_AND_TRASH]: removedWith(left) },
    })

    await fireEvent.click(within(dialog).getByRole('radio', { name: /Delete the files/ }))
    await fireEvent.click(within(dialog).getByRole('button', { name: 'Remove channel' }))

    const message = await screen.findByRole('dialog', { name: 'Sample Channel was removed' })
    expect(within(message).getByRole('alert').textContent).toContain(
      `12 files stayed in ${FOLDER}:`,
    )
    const items = [...part('[data-files-left]').querySelectorAll('li')].map((item) =>
      item.textContent?.replace(/\s+/g, ' ').trim(),
    )
    expect(items).toHaveLength(10)
    expect(items.slice(0, 4)).toEqual([
      'Locked 1.mkv macOS did not let it go to the Trash',
      'Q and A.mkv another video is inside',
      'Unreadable.mkv its video could not be checked',
      'Linked.mkv it leads outside the folder',
    ])
    expect(message.textContent).toContain('and 2 more')
    expect(screen.queryByRole('dialog', { name: 'Remove Sample Channel?' })).toBeNull()

    await fireEvent.click(within(message).getByRole('button', { name: 'OK' }))

    expect(screen.queryByRole('dialog')).toBeNull()
  })

  it('R-CH-32: a removal where every file went says nothing more', async () => {
    const { dialog } = await askToRemove({
      channels: [channel(), channel({ id: OTHER_CHANNEL_ID, title: 'Other Channel' })],
      answers: { [REMOVE_AND_TRASH]: removedWith() },
    })

    await fireEvent.click(within(dialog).getByRole('radio', { name: /Delete the files/ }))
    await fireEvent.click(within(dialog).getByRole('button', { name: 'Remove channel' }))

    await waitFor(() => expect(screen.queryByRole('dialog')).toBeNull())
  })
})
