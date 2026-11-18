import { fireEvent, screen, waitFor, within } from '@testing-library/vue'
import { describe, expect, it } from 'vitest'

import type { Channel, Video } from '@/api/client'

import { openApp, part } from '../helpers/app'
import { channel, CHANNEL_ID, NOW, video } from '../helpers/catalogue'
import { jsonResponse } from '../helpers/fetch'

const QUEUED = jsonResponse({ jobs: [] }, 202)

function rowOf(number: number): HTMLElement {
  return part(`[data-video="${video(number).id}"]`)
}

function shownIds(): string[] {
  return [...document.querySelectorAll<HTMLElement>('[data-video]')].map(
    (element) => element.dataset.video ?? '',
  )
}

async function openWith(videos: Video[], changes: Partial<Channel> = {}, answers = {}) {
  const app = await openApp({
    channels: [channel({ videos: videos.length, ...changes })],
    videos,
    answers: {
      'POST /api/videos/mirror': QUEUED,
      'POST /api/videos/redownload': QUEUED,
      ...answers,
    },
  })
  await waitFor(() => part('[data-video]'))
  return app
}

describe('the tools of the channel page', () => {
  it('R-UI-04: the tabs show their counts and filter the list', async () => {
    await openWith([video(1), video(2, { status: 'synced', height: 1080 })])

    const tabs = screen.getByRole('group', { name: 'Show' })
    const synced = within(tabs).getByRole('button', { name: /Synced/ })
    expect(synced.textContent).toContain('1')
    await fireEvent.click(synced)

    await waitFor(() => expect(shownIds()).toEqual([video(2).id]))
    expect(synced.getAttribute('aria-pressed')).toBe('true')
  })

  it('R-UI-05: the search filters by title as the user types', async () => {
    await openWith([video(1, { title: 'Restoring a workbench' }), video(2, { title: 'Tools' })])

    await fireEvent.update(screen.getByRole('searchbox', { name: 'Filter by title' }), 'bench')

    await waitFor(() => expect(shownIds()).toEqual([video(1).id]))
  })

  it('R-UI-05: a search that finds nothing says so', async () => {
    await openWith([video(1)])

    await fireEvent.update(screen.getByRole('searchbox', { name: 'Filter by title' }), 'zzz')

    expect(await screen.findByText('No video matches')).toBeTruthy()
  })

  it('R-UI-06: the order can be changed', async () => {
    await openWith([video(1, { title: 'B' }), video(2, { title: 'A' })])

    await fireEvent.update(screen.getByRole('combobox', { name: 'Sort' }), 'title')

    await waitFor(() => expect(shownIds()).toEqual([video(2).id, video(1).id]))
  })

  it('R-UI-03: the toggle switches to the grid and remembers it for the app', async () => {
    const app = await openWith([video(1)], {}, { 'PUT /api/state/view': jsonResponse({}) })

    await fireEvent.click(screen.getByRole('button', { name: 'Grid view' }))

    await waitFor(() => expect(part('[role="list"][data-view="grid"]')).toBeTruthy())
    expect(app.lastBody('/api/state/view')).toEqual({ view: 'grid' })
  })
})

describe('selecting videos', () => {
  it('R-MI-07, R-MI-01: Shift-click selects a range, and the bulk bar mirrors it', async () => {
    const app = await openWith([video(1), video(2), video(3)])

    await fireEvent.click(within(rowOf(1)).getByRole('checkbox'))
    await fireEvent.click(within(rowOf(3)).getByRole('checkbox'), { shiftKey: true })

    const bar = await screen.findByRole('region', { name: 'Selected videos' })
    expect(bar.textContent).toContain('3 selected')
    await fireEvent.click(within(bar).getByRole('button', { name: 'Mirror 3' }))
    await waitFor(() =>
      expect(app.lastBody('/api/videos/mirror')).toEqual({
        ids: [video(1).id, video(2).id, video(3).id],
        first: false,
      }),
    )
    await waitFor(() =>
      expect(screen.queryByRole('region', { name: 'Selected videos' })).toBeNull(),
    )
  })

  it('R-MI-07: "select all shown" selects every shown video, and Clear none', async () => {
    await openWith([video(1), video(2)])

    await fireEvent.click(screen.getByRole('checkbox', { name: 'Select all shown' }))

    const bar = await screen.findByRole('region', { name: 'Selected videos' })
    expect(bar.textContent).toContain('2 selected')
    await fireEvent.click(within(bar).getByRole('button', { name: 'Clear' }))
    expect(screen.queryByRole('region', { name: 'Selected videos' })).toBeNull()
  })

  it('R-MI-07, R-MI-01: each button of the bar counts exactly the videos it acts on', async () => {
    await openWith([
      video(1),
      video(2, { status: 'synced', height: 1080 }),
      video(3, { status: 'failed' }),
    ])

    await fireEvent.click(within(rowOf(1)).getByRole('checkbox'))
    await fireEvent.click(within(rowOf(3)).getByRole('checkbox'), { shiftKey: true })

    const bar = await screen.findByRole('region', { name: 'Selected videos' })
    expect(bar.textContent).toContain('3 selected')
    expect(within(bar).getByRole('button', { name: 'Mirror 1' })).toBeTruthy()
    expect(within(bar).getByRole('button', { name: 'Re-download 1' })).toBeTruthy()
  })

  it('R-MI-07, R-UI-11: the bar is busy while its action runs, and a second press does nothing', async () => {
    let answer: (response: Response) => void = () => undefined
    const app = await openWith([video(1), video(2)], undefined, {
      'POST /api/videos/mirror': () => new Promise<Response>((resolve) => (answer = resolve)),
    })
    await fireEvent.click(within(rowOf(1)).getByRole('checkbox'))
    const bar = await screen.findByRole('region', { name: 'Selected videos' })
    const mirror = within(bar).getByRole('button', { name: 'Mirror 1' }) as HTMLButtonElement

    await fireEvent.click(mirror)
    await fireEvent.click(mirror)
    await fireEvent.keyDown(document.body, { key: 'm' })

    expect(app.requests().filter((request) => request === 'POST /api/videos/mirror')).toHaveLength(
      1,
    )
    expect(mirror.disabled).toBe(true)
    answer(new Response(JSON.stringify({ jobs: [] }), { status: 202 }))
  })

  it('R-MI-07: a selected video that leaves the tab is selected no more', async () => {
    const app = await openWith([video(1), video(2)])
    await fireEvent.click(screen.getByRole('button', { name: /^Not downloaded/ }))
    await fireEvent.click(within(rowOf(1)).getByRole('checkbox'))
    await fireEvent.click(within(rowOf(2)).getByRole('checkbox'))
    const bar = await screen.findByRole('region', { name: 'Selected videos' })
    expect(bar.textContent).toContain('2 selected')

    app.stream().videoUpdated(CHANNEL_ID, video(2, { status: 'synced', height: 1080 }))

    await waitFor(() => expect(bar.textContent).toContain('1 selected'))
    expect(within(bar).getByRole('button', { name: 'Mirror 1' })).toBeTruthy()
  })

  it('R-UI-13, R-MI-07: the row the arrow keys are on is outlined, not drawn as selected', async () => {
    await openWith([video(1), video(2)])

    await fireEvent.keyDown(document.body, { key: 'ArrowDown' })

    const current = part('[data-current]')
    expect(current.className).toContain('outline-accent')
    expect(current.className).not.toContain('bg-surface-raised')
    expect(within(current).getByRole('checkbox')).toHaveProperty('checked', false)
  })

  it('R-QL-06: the bulk bar downloads the selected synced videos again', async () => {
    const app = await openWith([video(1, { status: 'synced', height: 720 })])

    await fireEvent.click(within(rowOf(1)).getByRole('checkbox'))
    const bar = await screen.findByRole('region', { name: 'Selected videos' })
    await fireEvent.click(within(bar).getByRole('button', { name: 'Re-download 1' }))

    await waitFor(() =>
      expect(app.lastBody('/api/videos/redownload')).toEqual({ ids: [video(1).id] }),
    )
  })
})

describe('the menu of a video', () => {
  async function menuOf(number: number): Promise<HTMLElement> {
    await fireEvent.click(within(rowOf(number)).getByRole('button', { name: /More actions for/ }))
    return screen.findByRole('menu')
  }

  it('R-UI-09: a video without a file offers Mirror and "Mirror first"', async () => {
    const app = await openWith([video(1)])

    const menu = await menuOf(1)
    expect(
      within(menu)
        .getAllByRole('menuitem')
        .map((item) => item.textContent?.trim()),
    ).toEqual(['Mirror', 'Mirror first (top of queue)', 'Details', 'Open on YouTube'])
    await fireEvent.click(within(menu).getByRole('menuitem', { name: /Mirror first/ }))
    await waitFor(() =>
      expect(app.lastBody('/api/videos/mirror')).toEqual({ ids: [video(1).id], first: true }),
    )
  })

  it('R-UI-09, R-QL-06: a synced video offers Play, Show in Finder and Re-download', async () => {
    await openWith([video(1, { status: 'synced', height: 1080 })])

    const menu = await menuOf(1)

    expect(
      within(menu)
        .getAllByRole('menuitem')
        .map((item) => item.textContent?.trim()),
    ).toEqual(['Play', 'Show in Finder', 'Details', 'Open on YouTube', 'Re-download'])
  })

  it('R-UI-09: a right-click on a row opens its menu at the pointer', async () => {
    await openWith([video(1)])

    await fireEvent.contextMenu(rowOf(1), { clientX: 40, clientY: 60 })

    expect(await screen.findByRole('menu')).toBeTruthy()
  })

  it('R-UI-09, R-CH-14: a video removed from YouTube offers neither Mirror nor Retry', async () => {
    await openWith([video(1, { gone: true })])

    const menu = await menuOf(1)

    expect(within(menu).queryByRole('menuitem', { name: 'Mirror' })).toBeNull()
  })
})

describe('what a row says while it waits', () => {
  it('R-DT-06, D-090: a paced download says until when it waits', async () => {
    await openWith([video(1, { status: 'queued', job_id: 'J1', paced_until: NOW + 3600 })])

    expect(rowOf(1).textContent).toContain(
      'Waiting · paced to protect your access to YouTube · may start at',
    )
  })

  it('R-QU-07: a download that failed in a way that passes says when it is tried again', async () => {
    await openWith([
      video(1, {
        status: 'queued',
        job_id: 'J1',
        retry_at: NOW + 60,
        error_code: 'NETWORK_UNREACHABLE',
      }),
    ])

    expect(rowOf(1).querySelector('[data-retry-at]')?.textContent).toContain('Trying again at')
  })

  it('R-QL-07: a file below the quality of its channel is marked', async () => {
    await openWith([video(1, { status: 'synced', height: 480, below_target: true })])

    expect(rowOf(1).querySelector('[data-below-target]')?.textContent).toContain(
      'Lower than target quality',
    )
  })

  it('R-QL-06, D-093: a synced video that is downloaded again stays synced and shows it', async () => {
    await openWith([video(1, { status: 'synced', height: 480, job_id: 'J1' })])

    expect(rowOf(1).textContent).toContain('Queued to download again')
  })
})

describe('auto-mirror', () => {
  it('R-MI-02: the checkbox of the header turns auto-mirror on', async () => {
    const app = await openWith(
      [video(1)],
      {},
      {
        [`PUT /api/channels/${CHANNEL_ID}/auto-mirror`]: jsonResponse(
          channel({ auto_mirror: true }),
        ),
      },
    )

    await fireEvent.click(screen.getByRole('checkbox', { name: 'Auto-mirror' }))

    await waitFor(() =>
      expect(app.lastBody(`/api/channels/${CHANNEL_ID}/auto-mirror`)).toEqual({ on: true }),
    )
  })

  it('R-MI-02, D-095: a large start asks first, and each answer is sent', async () => {
    const app = await openWith(
      [video(1)],
      {
        auto_mirror: true,
        auto_mirror_question: { count: 8, estimated_bytes: 3_200_000_000 },
      },
      {
        [`POST /api/channels/${CHANNEL_ID}/auto-mirror/answer`]: jsonResponse(
          channel({ auto_mirror: true }),
        ),
      },
    )

    const dialog = await screen.findByRole('dialog', { name: /Start auto-mirror/ })
    expect(dialog.textContent).toContain('8 videos')
    await fireEvent.click(
      within(dialog).getByRole('button', { name: 'Only new videos from now on' }),
    )

    await waitFor(() =>
      expect(app.lastBody(`/api/channels/${CHANNEL_ID}/auto-mirror/answer`)).toEqual({
        answer: 'only_new',
      }),
    )
  })

  it('R-MI-06, D-092: many missing files wait for the user with two answers', async () => {
    const app = await openWith(
      [video(1)],
      { auto_mirror: true, missing_held: 6 },
      {
        [`POST /api/channels/${CHANNEL_ID}/missing/leave`]: jsonResponse(channel()),
      },
    )

    const banner = part('[data-banner="missing-held"]')
    expect(banner.textContent).toContain('6 files of this channel are missing')
    await fireEvent.click(within(banner).getByRole('button', { name: 'Leave them missing' }))

    await waitFor(() =>
      expect(app.requests()).toContain(`POST /api/channels/${CHANNEL_ID}/missing/leave`),
    )
  })

  it('R-MI-06, D-092: "Mirror them again" queues the missing files, not the whole channel', async () => {
    const app = await openWith(
      [video(1)],
      { auto_mirror: true, missing_held: 6 },
      {
        [`POST /api/channels/${CHANNEL_ID}/missing/mirror`]: jsonResponse({ jobs: [] }, 202),
      },
    )

    const banner = part('[data-banner="missing-held"]')
    await fireEvent.click(within(banner).getByRole('button', { name: 'Mirror them again' }))

    await waitFor(() =>
      expect(app.requests()).toContain(`POST /api/channels/${CHANNEL_ID}/missing/mirror`),
    )
    expect(app.requests()).not.toContain(`POST /api/channels/${CHANNEL_ID}/mirror-missing`)
  })

  it('R-FB-03: many videos changed at once load the list of the open channel again', async () => {
    const app = await openWith([video(1)])
    const loads = (): number =>
      app.requests().filter((request) => request === `GET /api/channels/${CHANNEL_ID}/videos`)
        .length
    const before = loads()

    app.stream().videosChanged(CHANNEL_ID, 300)

    await waitFor(() => expect(loads()).toBe(before + 1))
  })
})
