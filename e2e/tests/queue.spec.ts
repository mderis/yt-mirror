import { renameSync } from 'node:fs'
import { join } from 'node:path'

import type { Locator, Page } from '@playwright/test'

import { expect, test, type FreshApp } from './fresh-app'

/**
 * The queue, end to end (docs/TESTING.md section 6, flows 2, 3, 6 and 10):
 * videos picked with their checkboxes and mirrored together, the order of the
 * waiting downloads, pause all, automatic retries and Retry, the disk space
 * guard and a channel folder that cannot be reached, auto-mirror's question
 * before a large start, paced automatic downloads, and a download that goes
 * on after the app started again. Every test starts an app of its own.
 */
test.describe.configure({ mode: 'default' })

const SMALL_ID = 'UCsmallchannel0000000001'
const FAILURES_ID = 'UCfailures00000000000008'
const FIRST = 'small000012'
const SECOND = 'small000011'
const THIRD = 'small000008'
const HELD = 'small000009'
const FIRST_TITLE = 'Building a cabin in the woods, part 12'
const SECOND_TITLE = 'Q and A, your questions answered'

interface QueueAnswer {
  queue: { downloading: number; waiting: number; paused: boolean }
  running: { video_id: string }[]
  waiting: { job_id: string; video_id: string; paced_until: number | null }[]
}

const row = (page: Page, videoId: string): Locator => page.locator(`[data-video="${videoId}"]`)
const queueBar = (page: Page): Locator => page.getByRole('region', { name: 'Downloads' })
const panel = (page: Page): Locator => page.getByRole('complementary', { name: 'Downloads' })

async function waitingOrder(app: FreshApp): Promise<string[]> {
  return ((await app.api('/queue')) as QueueAnswer).waiting.map((item) => item.video_id)
}

async function addChannel(app: FreshApp, handle: string, channelId: string): Promise<void> {
  await app.send('POST', '/channels/lookup', { text: handle })
  await app.send('POST', '/channels', { channel_id: channelId, auto_mirror: false })
  await expect
    .poll(async () => ((await app.api(`/channels/${channelId}`)) as { status: string }).status)
    .not.toBe('checking')
}

async function openChannel(page: Page, app: FreshApp, channelId = SMALL_ID): Promise<void> {
  await app.finishSetup()
  await addChannel(
    app,
    channelId === SMALL_ID ? '@samplechannelone' : '@failingdownloads',
    channelId,
  )
  await page.goto(app.firstUrl)
  await expect(page.locator('[data-video]').first()).toBeVisible()
}

test('R-MI-01, R-MI-07, R-QU-01: two videos picked with their checkboxes are mirrored from the bulk bar and synced', async ({
  page,
  freshApp,
}) => {
  await openChannel(page, freshApp)

  await page.getByRole('checkbox', { name: `Select: ${FIRST_TITLE}` }).check()
  await page.getByRole('checkbox', { name: `Select: ${SECOND_TITLE}` }).check()
  const bulk = page.getByRole('region', { name: 'Selected videos' })
  await expect(bulk).toContainText('2 selected')
  await bulk.getByRole('button', { name: 'Mirror 2' }).click()

  await expect(bulk).toBeHidden()
  await expect(row(page, FIRST).getByText('Synced · 270p')).toBeVisible({ timeout: 20_000 })
  await expect(row(page, SECOND).getByText('Synced · 270p')).toBeVisible({ timeout: 20_000 })
})

test('R-QU-02, R-UI-13, R-UI-12: the waiting downloads are put in order by keyboard and by drag, and cleared after a question', async ({
  page,
  freshApp,
}) => {
  await openChannel(page, freshApp)
  await freshApp.send('POST', '/queue/pause')
  await freshApp.send('POST', '/videos/mirror', { ids: [FIRST, SECOND, THIRD] })
  await page.reload()

  await queueBar(page).getByRole('button', { name: 'Show queue' }).click()
  const waiting = panel(page).locator('[data-waiting] li')
  await expect(waiting).toHaveCount(3)
  expect(await waitingOrder(freshApp)).toEqual([FIRST, SECOND, THIRD])

  await waiting.nth(2).focus()
  await page.keyboard.press('Alt+ArrowUp')
  await expect.poll(() => waitingOrder(freshApp)).toEqual([FIRST, THIRD, SECOND])

  await waiting.nth(2).dragTo(waiting.nth(0))
  await expect.poll(() => waitingOrder(freshApp)).toEqual([SECOND, FIRST, THIRD])

  await panel(page).getByRole('button', { name: 'Clear waiting' }).click()
  const question = page.getByRole('dialog', { name: 'Clear the waiting downloads?' })
  await question.getByRole('button', { name: 'Clear waiting' }).click()
  await expect.poll(() => waitingOrder(freshApp)).toEqual([])
  await expect(row(page, FIRST).getByText('Not downloaded')).toBeVisible()
})

test.describe('a held download', () => {
  test.use({ holdDownloads: true })

  test('R-QU-02, R-QU-05: pause all stops the running download and keeps it; resume all continues it', async ({
    page,
    freshApp,
  }) => {
    await openChannel(page, freshApp)
    await row(page, HELD).getByRole('button', { name: 'Mirror' }).click()
    await expect(row(page, HELD).getByText(/Downloading \d+%/)).toBeVisible({ timeout: 20_000 })

    await queueBar(page).getByRole('button', { name: 'Pause all' }).click()

    await expect(queueBar(page)).toContainText('All downloads paused')
    await expect(row(page, HELD).getByText('Queued')).toBeVisible()
    await queueBar(page).getByRole('button', { name: 'Resume all' }).click()
    await expect(row(page, HELD).getByText(/Downloading \d+%/)).toBeVisible({ timeout: 20_000 })
  })

  test('R-QU-05, R-QU-06: a download that runs when the app stops goes on after the next start', async ({
    page,
    freshApp,
  }) => {
    await openChannel(page, freshApp)
    await row(page, HELD).getByRole('button', { name: 'Mirror' }).click()
    await expect(row(page, HELD).getByText(/Downloading \d+%/)).toBeVisible({ timeout: 20_000 })

    await freshApp.restart()
    await page.goto(freshApp.firstUrl)

    await expect(row(page, HELD).getByText(/Downloading \d+%/)).toBeVisible({ timeout: 20_000 })
    const queue = (await freshApp.api('/queue')) as QueueAnswer
    expect(queue.running.map((item) => item.video_id)).toEqual([HELD])
  })
})

test('R-QU-07, R-QU-08: a failure that passes is tried again by itself; one that stays fails with Retry', async ({
  page,
  freshApp,
}) => {
  await openChannel(page, freshApp, FAILURES_ID)
  // NETWORK_UNREACHABLE passes; MEMBERS_ONLY stays.
  await freshApp.send('POST', '/videos/mirror', { ids: ['fail0000008', 'fail0000001'] })

  await expect(row(page, 'fail0000008').getByText(/Trying again at/)).toBeVisible({
    timeout: 20_000,
  })
  await expect(row(page, 'fail0000001').getByText('Failed')).toBeVisible({ timeout: 20_000 })
  await queueBar(page).getByRole('button', { name: 'Show queue' }).click()
  const failed = panel(page).locator('[data-failed-video="fail0000001"]')
  await expect(failed).toContainText('Members-only video')

  const retried = page.waitForRequest(
    (request) => request.method() === 'POST' && request.url().endsWith('/videos/fail0000001/retry'),
  )
  await failed.getByRole('button', { name: 'Retry' }).click()
  await retried
  await expect(row(page, 'fail0000001').getByText('Failed')).toBeVisible({ timeout: 20_000 })
})

test('R-QU-10, R-FB-04: too little free space pauses the queue, and "Resume anyway" continues it', async ({
  page,
  freshApp,
}) => {
  await openChannel(page, freshApp)
  freshApp.setFreeSpace(1_000_000_000)

  await row(page, FIRST).getByRole('button', { name: 'Mirror' }).click()

  const banner = page.locator('[data-banner="disk-guard"]')
  await expect(banner).toContainText('Queue paused: only 1 GB free')
  await expect(row(page, FIRST).getByText('Queued')).toBeVisible()
  await banner.getByRole('button', { name: 'Resume anyway' }).click()
  await expect(row(page, FIRST).getByText('Synced · 270p')).toBeVisible({ timeout: 20_000 })
  await expect(banner).toBeHidden()
})

test('R-QU-11, R-FB-04: a channel folder that cannot be reached holds its downloads until "Try again"', async ({
  page,
  freshApp,
}) => {
  await openChannel(page, freshApp)
  const folder = join(freshApp.libraryDir, 'Sample Channel One')
  renameSync(folder, `${folder} away`)

  await row(page, FIRST).getByRole('button', { name: 'Mirror' }).click()

  const banner = page.locator('[data-banner="folder-away"]')
  await expect(banner).toContainText(
    'The folder of Sample Channel One cannot be reached. Its downloads wait.',
  )
  await expect(row(page, FIRST).getByText('Queued')).toBeVisible()
  renameSync(`${folder} away`, folder)
  await banner.getByRole('button', { name: 'Try again' }).click()
  await expect(row(page, FIRST).getByText('Synced · 270p')).toBeVisible({ timeout: 20_000 })
  await expect(banner).toBeHidden()
})

test.describe('auto-mirror', () => {
  // Two lookups an hour: the first automatic downloads start, the others are paced (D-090).
  test.use({ lookupsPerHour: 2 })

  test('R-MI-02, D-095: turning auto-mirror on asks first, and "Only new videos from now on" starts nothing', async ({
    page,
    freshApp,
  }) => {
    await openChannel(page, freshApp)

    await page.getByRole('checkbox', { name: 'Auto-mirror' }).check()
    const question = page.getByRole('dialog', { name: 'Start auto-mirror for Sample Channel One?' })
    await expect(question).toContainText('Auto-mirror would download 12 videos')
    await question.getByRole('button', { name: 'Only new videos from now on' }).click()

    await expect(question).toBeHidden()
    await expect(page.getByRole('checkbox', { name: 'Auto-mirror' })).toBeChecked()
    expect(((await freshApp.api('/queue')) as QueueAnswer).waiting).toEqual([])
    const channel = (await freshApp.api(`/channels/${SMALL_ID}`)) as { mirror_after: number }
    expect(channel.mirror_after).not.toBeNull()
  })

  test('R-MI-02, D-095: "Turn auto-mirror off" leaves it off', async ({ page, freshApp }) => {
    await openChannel(page, freshApp)

    await page.getByRole('checkbox', { name: 'Auto-mirror' }).check()
    await page
      .getByRole('dialog', { name: 'Start auto-mirror for Sample Channel One?' })
      .getByRole('button', { name: 'Turn auto-mirror off' })
      .click()

    await expect(page.getByRole('checkbox', { name: 'Auto-mirror' })).not.toBeChecked()
    expect(((await freshApp.api('/queue')) as QueueAnswer).waiting).toEqual([])
  })

  test('R-MI-02, R-DT-06, D-090: "Mirror all" queues every video, and the automatic ones beyond the budget are paced', async ({
    page,
    freshApp,
  }) => {
    await openChannel(page, freshApp)

    await page.getByRole('checkbox', { name: 'Auto-mirror' }).check()
    await page
      .getByRole('dialog', { name: 'Start auto-mirror for Sample Channel One?' })
      .getByRole('button', { name: /Mirror all 12 videos/ })
      .click()

    await expect
      .poll(async () =>
        ((await freshApp.api('/queue')) as QueueAnswer).waiting.some((item) => item.paced_until),
      )
      .toBe(true)
    await expect(
      page.getByText(/Waiting · paced to protect your access to YouTube · may start at/).first(),
    ).toBeVisible()
  })
})
