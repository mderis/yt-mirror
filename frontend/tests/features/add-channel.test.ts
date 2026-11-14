import { fireEvent, screen, waitFor, within } from '@testing-library/vue'
import { describe, expect, it } from 'vitest'

import { openApp, part } from '../helpers/app'
import { channel, OTHER_CHANNEL_ID, video } from '../helpers/catalogue'
import { errorBody, jsonResponse } from '../helpers/fetch'

const NEW_ID = 'UCthird000000000000000003'
const LOOKUP = 'POST /api/channels/lookup'
const COUNT = `GET /api/channels/lookup/${NEW_ID}/video-count`
const preview = {
  channel_id: NEW_ID,
  title: 'Sample Channel Three',
  handle: '@samplechannelthree',
  has_avatar: true,
  existing: false,
  folder: '/Users/sam/Movies/YouTube/Sample Channel Three',
  video_files: 0,
}
const added = channel({
  id: NEW_ID,
  title: 'Sample Channel Three',
  status: 'checking',
  first_listed_at: null,
  last_check_at: null,
})

type Answers = NonNullable<Parameters<typeof openApp>[0]>['answers']

/** Open the app without channels and its add channel dialog. */
async function openDialog(answers: Answers = {}) {
  const app = await openApp({
    answers: {
      [LOOKUP]: jsonResponse(preview),
      [COUNT]: jsonResponse({ video_count: 57 }),
      ...answers,
    },
  })
  await fireEvent.click(
    within(screen.getByRole('navigation')).getByRole('button', { name: 'Add channel' }),
  )
  const dialog = await screen.findByRole('dialog', { name: 'Add a channel' })
  return { app, dialog }
}

/** Type a channel into step 1 and continue. */
async function lookUp(dialog: HTMLElement, text = '@samplechannelthree'): Promise<void> {
  await fireEvent.update(
    within(dialog).getByRole('textbox', { name: 'Channel link or @handle' }),
    text,
  )
  await fireEvent.click(within(dialog).getByRole('button', { name: 'Continue' }))
}

async function atStepTwo(answers: Answers = {}) {
  const opened = await openDialog(answers)
  await lookUp(opened.dialog)
  await within(opened.dialog).findByText('Found')
  return opened
}

describe('the add channel dialog', () => {
  it('R-CH-01: step 1 asks for a channel link or a handle, and cannot go on without one', async () => {
    const { dialog } = await openDialog()

    const field = within(dialog).getByRole('textbox', { name: 'Channel link or @handle' })
    expect(document.activeElement).toBe(field)
    expect(within(dialog).getByText(/Shorts and live streams are skipped/)).toBeTruthy()
    expect(within(dialog).getByRole('button', { name: 'Continue' }).hasAttribute('disabled')).toBe(
      true,
    )
  })

  it('R-CH-03: the channel is shown with its name, handle and avatar before the user confirms', async () => {
    const { app, dialog } = await atStepTwo({ [COUNT]: jsonResponse({ video_count: null }) })

    const card = part('[data-preview]')
    expect(card.textContent).toContain('Sample Channel Three')
    expect(card.querySelector('[data-facts]')?.textContent).toBe('@samplechannelthree')
    expect(card.querySelector('img')?.getAttribute('src')).toBe(
      `/api/channels/lookup/${NEW_ID}/avatar`,
    )
    expect(app.requests()).not.toContain('POST /api/channels')
    expect(within(dialog).getByRole('button', { name: 'Add channel' })).toBeTruthy()
  })

  it('R-CH-03: the video count is filled in when YouTube gives one', async () => {
    await atStepTwo()

    await waitFor(() =>
      expect(part('[data-preview] [data-facts]').textContent).toBe(
        '@samplechannelthree · 57 videos',
      ),
    )
    expect(screen.getByText('All 57 videos now, and new ones as they appear.')).toBeTruthy()
  })

  it('R-CH-03: without a count the same dialog is shown, worded without a number', async () => {
    await atStepTwo({ [COUNT]: jsonResponse(errorBody('NETWORK_UNREACHABLE'), 502) })

    expect(screen.getByText('All videos now, and new ones as they appear.')).toBeTruthy()
    expect(part('[data-preview] [data-facts]').textContent).toBe('@samplechannelthree')
    expect(screen.queryByRole('alert')).toBeNull()
  })

  it('R-CH-03: the count never delays the preview', async () => {
    await atStepTwo({ [COUNT]: () => new Promise<Response>(() => undefined) })

    expect(part('[data-preview]').textContent).toContain('Sample Channel Three')
    expect(screen.getByText('All videos now, and new ones as they appear.')).toBeTruthy()
  })

  it('R-UI-11: while the channel is looked up the dialog says so, and "Continue" is busy', async () => {
    let answer: (response: Response) => void = () => {}
    const { dialog } = await openDialog({
      [LOOKUP]: () => new Promise<Response>((resolve) => (answer = resolve)),
    })

    await lookUp(dialog)
    const status = await within(dialog).findByRole('status')
    const busy = within(dialog).getByRole('button', { name: 'Continue' }).getAttribute('aria-busy')
    answer(jsonResponse(preview))

    expect(status.textContent).toContain('Looking up the channel...')
    expect(busy).toBe('true')
    expect(await within(dialog).findByText('Found')).toBeTruthy()
  })

  it.each([
    ['video', 'This is a video, not a channel.'],
    ['playlist', 'This is a playlist, not a channel.'],
    ['other', 'This is not a channel.'],
    ['empty', 'Paste a channel link'],
    ['a reason of a later version', 'This is not a channel.'],
  ])(
    'R-CH-02: what is no channel (%s) is rejected with a message that says what is accepted',
    async (reason, words) => {
      const { dialog } = await openDialog({
        [LOOKUP]: jsonResponse(errorBody('INVALID_CHANNEL_INPUT', { reason }), 422),
      })

      await lookUp(dialog, 'https://www.youtube.com/watch?v=abc')

      const alert = await within(dialog).findByRole('alert')
      expect(alert.textContent).toContain(words)
      expect(alert.textContent).toMatch(/a handle such as @name, or a channel ID\.$/)
      expect(within(dialog).queryByText('Found')).toBeNull()
    },
  )

  it('R-ER-02: a lookup that fails says what happened in the words of its error code', async () => {
    const { dialog } = await openDialog({
      [LOOKUP]: jsonResponse(errorBody('CHANNEL_NOT_FOUND'), 404),
    })

    await lookUp(dialog, '@nobody')

    const alert = await within(dialog).findByRole('alert')
    expect(alert.textContent).toBe(
      'YouTube has no channel with this address. Check the link or the handle, then try again.',
    )
  })

  it('R-CH-01: Enter in the field looks the channel up', async () => {
    const { dialog } = await openDialog()
    const field = within(dialog).getByRole('textbox', { name: 'Channel link or @handle' })

    await fireEvent.update(field, '@samplechannelthree')
    await fireEvent.keyDown(field, { key: 'Enter' })

    expect(await within(dialog).findByText('Found')).toBeTruthy()
  })

  it('R-CH-04: a channel that exists is opened instead of added, and the page says so', async () => {
    const other = channel({ id: OTHER_CHANNEL_ID, title: 'Other Channel' })
    const app = await openApp({
      channels: [channel(), other],
      videos: [video(1)],
      answers: {
        [LOOKUP]: jsonResponse({
          ...preview,
          channel_id: OTHER_CHANNEL_ID,
          title: 'Other Channel',
          existing: true,
        }),
        [`GET /api/channels/${OTHER_CHANNEL_ID}/videos`]: jsonResponse({ videos: [] }),
      },
    })
    await fireEvent.click(
      within(screen.getByRole('navigation')).getByRole('button', { name: 'Add channel' }),
    )
    const dialog = await screen.findByRole('dialog', { name: 'Add a channel' })

    await lookUp(dialog, '@other')

    expect(await screen.findByRole('heading', { level: 1, name: 'Other Channel' })).toBeTruthy()
    expect(screen.queryByRole('dialog')).toBeNull()
    const notice = part('[data-banner="existing"]')
    expect(notice.textContent).toContain('Other Channel was added before. Here it is.')
    expect(app.requests()).not.toContain('POST /api/channels')
    await fireEvent.click(within(notice).getByRole('button', { name: 'Dismiss' }))
    expect(document.querySelector('[data-banner="existing"]')).toBeNull()
  })

  it('R-CH-05: step 2 offers the folder, the quality and what to mirror, each with its default', async () => {
    const { dialog } = await atStepTwo()

    expect(part('[data-folder]').textContent?.trim()).toBe(
      '/Users/sam/Movies/YouTube/Sample Channel Three',
    )
    expect(
      within(dialog).getByText('Default: a folder named after the channel inside your library.'),
    ).toBeTruthy()
    const quality = within(dialog).getByRole('combobox', { name: 'Quality' }) as HTMLSelectElement
    expect(quality.value).toBe('default')
    expect([...quality.options].map((option) => option.textContent?.trim())).toEqual([
      'Use default (Best available)',
      '2160p (4K)',
      '1440p',
      '1080p',
      '720p',
      '480p',
    ])
    const choices = within(
      within(dialog).getByRole('group', { name: 'What to mirror' }),
    ).getAllByRole('radio') as HTMLInputElement[]
    expect(choices.map((choice) => choice.checked)).toEqual([true, false, false])
    expect(within(dialog).getByText('Let me pick videos myself')).toBeTruthy()
    expect(
      within(dialog).getByText('Mirror everything and keep it in sync (auto-mirror)'),
    ).toBeTruthy()
    expect(
      within(dialog).getByText('Auto-mirror, but only videos uploaded after a date'),
    ).toBeTruthy()
  })

  it('R-CH-05: with the defaults the channel is added to its default folder, to pick videos by hand', async () => {
    const { app, dialog } = await atStepTwo({
      'POST /api/channels': jsonResponse({ channel: added, existing: false }, 201),
      [`GET /api/channels/${NEW_ID}/videos`]: jsonResponse({ videos: [] }),
    })

    await fireEvent.click(within(dialog).getByRole('button', { name: 'Add channel' }))

    expect(
      await screen.findByRole('heading', { level: 1, name: 'Sample Channel Three' }),
    ).toBeTruthy()
    expect(screen.queryByRole('dialog')).toBeNull()
    expect(document.querySelector('[data-banner="existing"]')).toBeNull()
    expect(app.lastBody('/api/channels')).toEqual({
      channel_id: NEW_ID,
      folder: null,
      quality: null,
      auto_mirror: false,
      mirror_after: null,
    })
  })

  it('R-CH-05: "Choose..." takes the folder of the folder dialog, and Cancel there keeps what was shown', async () => {
    const answers = [
      jsonResponse({ folder: null, video_files: 0 }),
      jsonResponse({ folder: '/Volumes/Archive/Three', video_files: 0 }),
    ]
    const { app, dialog } = await atStepTwo({
      'POST /api/folders/choose': () => answers.shift() as Response,
      'POST /api/channels': jsonResponse({ channel: added, existing: false }, 201),
      [`GET /api/channels/${NEW_ID}/videos`]: jsonResponse({ videos: [] }),
    })
    const choose = within(dialog).getByRole('button', { name: 'Choose...' })

    await fireEvent.click(choose)
    await waitFor(() => expect(choose.getAttribute('aria-busy')).not.toBe('true'))
    const afterCancel = part('[data-folder]').textContent?.trim()
    await fireEvent.click(choose)
    await waitFor(() =>
      expect(part('[data-folder]').textContent?.trim()).toBe('/Volumes/Archive/Three'),
    )
    await fireEvent.click(within(dialog).getByRole('button', { name: 'Add channel' }))
    await screen.findByRole('heading', { level: 1, name: 'Sample Channel Three' })

    expect(afterCancel).toBe('/Users/sam/Movies/YouTube/Sample Channel Three')
    expect(app.lastBody('/api/channels')).toMatchObject({ folder: '/Volumes/Archive/Three' })
  })

  it('R-CH-06: a folder that already contains video files says how many', async () => {
    const { dialog } = await atStepTwo({
      [LOOKUP]: jsonResponse({ ...preview, video_files: 1 }),
      'POST /api/folders/choose': jsonResponse({
        folder: '/Volumes/Archive/Three',
        video_files: 42,
      }),
    })
    const first = part('[data-banner="existing-files"]').textContent?.trim()

    await fireEvent.click(within(dialog).getByRole('button', { name: 'Choose...' }))

    expect(first).toBe('This folder already contains 1 video file.')
    await waitFor(() =>
      expect(part('[data-banner="existing-files"]').textContent?.trim()).toBe(
        'This folder already contains 42 video files.',
      ),
    )
  })

  it('R-CH-06: a folder without video files says nothing about them', async () => {
    await atStepTwo()

    expect(document.querySelector('[data-banner="existing-files"]')).toBeNull()
  })

  it('R-CH-05: a chosen quality and "auto-mirror everything" are sent with the channel', async () => {
    const { app, dialog } = await atStepTwo({
      'POST /api/channels': jsonResponse({ channel: added, existing: false }, 201),
      [`GET /api/channels/${NEW_ID}/videos`]: jsonResponse({ videos: [] }),
    })

    await fireEvent.update(within(dialog).getByRole('combobox', { name: 'Quality' }), '1080')
    await fireEvent.click(
      within(dialog).getByRole('radio', { name: /Mirror everything and keep it in sync/ }),
    )
    await fireEvent.click(within(dialog).getByRole('button', { name: 'Add channel' }))
    await screen.findByRole('heading', { level: 1, name: 'Sample Channel Three' })

    expect(app.lastBody('/api/channels')).toMatchObject({
      quality: '1080',
      auto_mirror: true,
      mirror_after: null,
    })
  })

  it('R-CH-05, R-MI-03: "only videos uploaded after a date" needs the date, which begins with that day', async () => {
    const { app, dialog } = await atStepTwo({
      'POST /api/channels': jsonResponse({ channel: added, existing: false }, 201),
      [`GET /api/channels/${NEW_ID}/videos`]: jsonResponse({ videos: [] }),
    })
    const add = within(dialog).getByRole('button', { name: 'Add channel' })
    expect(within(dialog).queryByLabelText('Uploaded after')).toBeNull()

    await fireEvent.click(
      within(dialog).getByRole('radio', { name: /only videos uploaded after a date/ }),
    )
    const withoutDate = add.hasAttribute('disabled')
    await fireEvent.update(within(dialog).getByLabelText('Uploaded after'), '2026-11-01')
    await fireEvent.click(add)
    await screen.findByRole('heading', { level: 1, name: 'Sample Channel Three' })

    expect(withoutDate).toBe(true)
    // 1 Nov 2026, 00:00:00 in UTC, the time zone of these tests.
    expect(app.lastBody('/api/channels')).toMatchObject({
      auto_mirror: true,
      mirror_after: 1_793_491_200,
    })
  })

  it('R-CH-05: "Back" returns to step 1 with what was typed', async () => {
    const { dialog } = await atStepTwo()

    await fireEvent.click(within(dialog).getByRole('button', { name: 'Back' }))

    const field = within(dialog).getByRole('textbox', {
      name: 'Channel link or @handle',
    }) as HTMLInputElement
    expect(field.value).toBe('@samplechannelthree')
    expect(within(dialog).queryByText('Found')).toBeNull()
  })

  it('R-ER-02: a channel that cannot be added says why in the words of its error code, and the dialog stays', async () => {
    const { dialog } = await atStepTwo({
      'POST /api/channels': jsonResponse(errorBody('PERMISSION_DENIED'), 403),
    })

    await fireEvent.click(within(dialog).getByRole('button', { name: 'Add channel' }))

    const alert = await within(dialog).findByRole('alert')
    expect(alert.textContent).toContain('macOS does not let yt-mirror use this folder.')
    expect(alert.textContent).toContain('Choose another folder')
    expect(within(dialog).getByText('Found')).toBeTruthy()
  })

  it('R-ER-02: a folder dialog that fails says so in the dialog', async () => {
    const { dialog } = await atStepTwo({
      'POST /api/folders/choose': jsonResponse(errorBody('INTERNAL'), 500),
    })

    await fireEvent.click(within(dialog).getByRole('button', { name: 'Choose...' }))

    expect((await within(dialog).findByRole('alert')).textContent).toContain(
      'Something unexpected went wrong inside yt-mirror.',
    )
  })

  it('R-CH-05: "Cancel" and the close button leave the dialog without adding anything', async () => {
    const { app, dialog } = await openDialog()

    await fireEvent.click(within(dialog).getByRole('button', { name: 'Cancel' }))

    expect(screen.queryByRole('dialog')).toBeNull()
    expect(app.requests()).not.toContain('POST /api/channels')
    expect(app.requests()).not.toContain('POST /api/channels/lookup')
  })

  it('R-CH-11: a channel that was added shows that its video list is being read', async () => {
    const { dialog } = await atStepTwo({
      'POST /api/channels': jsonResponse({ channel: added, existing: false }, 201),
      [`GET /api/channels/${NEW_ID}/videos`]: jsonResponse({ videos: [] }),
    })

    await fireEvent.click(within(dialog).getByRole('button', { name: 'Add channel' }))

    await waitFor(() =>
      expect(part('[data-listing]').textContent?.trim()).toBe(
        'Reading the video list from YouTube...',
      ),
    )
    expect(
      within(screen.getByRole('navigation')).getByRole('button', { name: /Sample Channel Three/ }),
    ).toBeTruthy()
  })
})
