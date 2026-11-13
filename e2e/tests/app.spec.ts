import AxeBuilder from '@axe-core/playwright'
import { expect, test, type Page } from '@playwright/test'

import { APP_URL, SESSION_TOKEN } from '../settings'

const FIRST_URL = `/?token=${SESSION_TOKEN}`

async function openApp(page: Page): Promise<void> {
  await page.goto(FIRST_URL)
  await expect(page.getByText('yt-mirror is running.')).toBeVisible()
  await page.evaluate(() => document.fonts.ready)
}

test('R-IN-02, R-PL-10: a started app shows the placeholder, and the token leaves the address', async ({
  page,
}) => {
  await openApp(page)

  expect(page.url()).toBe(`${APP_URL}/`)
  await expect(page.getByRole('heading', { level: 1, name: 'yt-mirror' })).toBeVisible()
  await expect(page.getByText(/^Version \d+\.\d+\.\d+/)).toBeVisible()
  await expect(page).toHaveTitle('yt-mirror')
})

test('R-PL-10: the session lives in a cookie that scripts cannot read', async ({
  page,
  context,
}) => {
  await openApp(page)

  const cookies = await context.cookies()
  const session = cookies.find((cookie) => cookie.name === 'ytm_session')

  expect(session?.httpOnly).toBe(true)
  expect(session?.sameSite).toBe('Strict')
  expect(await page.evaluate(() => document.cookie)).not.toContain('ytm_session')
})

test('R-PL-10: without a session the page loads, the API refuses, and the page says so', async ({
  page,
}) => {
  await page.goto('/')

  const alert = page.getByRole('alert')
  await expect(alert).toContainText('yt-mirror answered with an error.')
  await expect(alert).toContainText('Error code: UNAUTHORIZED')
  await expect(page.getByRole('button', { name: 'Try again' })).toBeVisible()
})

test('R-PL-10: a wrong token starts no session', async ({ page, request }) => {
  const response = await request.get('/?token=a-guess')

  expect(response.status()).toBe(401)
  expect((await response.json()).error.code).toBe('UNAUTHORIZED')
  await page.goto('/')
  await expect(page.getByRole('alert')).toContainText('UNAUTHORIZED')
})

test('R-PL-04: the API refuses another website even when it knows the token', async ({
  request,
}) => {
  const own = await request.get('/api/health', {
    headers: { Authorization: `Bearer ${SESSION_TOKEN}` },
  })
  const foreign = await request.get('/api/health', {
    headers: { Authorization: `Bearer ${SESSION_TOKEN}`, Origin: 'https://evil.example' },
  })

  expect(own.status()).toBe(200)
  expect((await own.json()).status).toBe('ok')
  expect(foreign.status()).toBe(403)
  expect((await foreign.json()).error.code).toBe('ORIGIN_REJECTED')
})

test('infra: "Try again" recovers once the session exists', async ({ page, context }) => {
  await page.goto('/')
  await expect(page.getByRole('alert')).toBeVisible()
  await context.addCookies([{ name: 'ytm_session', value: SESSION_TOKEN, url: APP_URL }])

  await page.getByRole('button', { name: 'Try again' }).click()

  await expect(page.getByText('yt-mirror is running.')).toBeVisible()
  await expect(page.getByRole('alert')).toHaveCount(0)
})

test('R-HE-03, R-TH-05: the app loads everything from itself, including its bundled fonts', async ({
  page,
}) => {
  const requested: string[] = []
  page.on('request', (request) => requested.push(request.url()))

  await openApp(page)

  const elsewhere = requested.filter(
    (url) => !url.startsWith(`${APP_URL}/`) && !url.startsWith('data:'),
  )
  expect(elsewhere).toEqual([])
  expect(requested.some((url) => /inter-latin-wght-normal.*\.woff2$/.test(url))).toBe(true)
  expect(requested.some((url) => /space-grotesk-latin-wght-normal.*\.woff2$/.test(url))).toBe(true)
  const fonts = await page.evaluate(() => ({
    text: getComputedStyle(document.body).fontFamily,
    heading: getComputedStyle(document.querySelector('h1') as Element).fontFamily,
    textLoaded: document.fonts.check('14px "Inter Variable"'),
    headingLoaded: document.fonts.check('600 28px "Space Grotesk Variable"'),
  }))
  expect(fonts.text).toContain('Inter Variable')
  expect(fonts.heading).toContain('Space Grotesk Variable')
  expect(fonts.textLoaded).toBe(true)
  expect(fonts.headingLoaded).toBe(true)
})

for (const theme of ['light', 'dark'] as const) {
  test.describe(`with the system set to ${theme}`, () => {
    test.use({ colorScheme: theme })

    test(`R-PL-05, R-TH-04: the app follows the system and shows the ${theme} theme`, async ({
      page,
    }) => {
      await openApp(page)

      const background = { light: 'rgb(246, 247, 249)', dark: 'rgb(14, 16, 20)' }[theme]
      await expect(page.locator('html')).toHaveAttribute('data-theme', theme)
      expect(await page.evaluate(() => getComputedStyle(document.body).backgroundColor)).toBe(
        background,
      )
    })

    test(`R-TH-09: the placeholder page looks as recorded in the ${theme} theme`, async ({
      page,
    }) => {
      await openApp(page)

      await expect(page).toHaveScreenshot(`placeholder-${theme}.png`, {
        // The version number changes with every release.
        mask: [page.getByText(/^Version /)],
      })
    })

    test(`R-UI-14: the placeholder page has no accessibility violations in the ${theme} theme`, async ({
      page,
    }) => {
      await openApp(page)

      const results = await new AxeBuilder({ page }).analyze()

      expect(results.violations.map((violation) => violation.id)).toEqual([])
    })
  })
}

test('R-PL-05: the theme changes when the system setting changes while the app is open', async ({
  page,
}) => {
  await page.emulateMedia({ colorScheme: 'light' })
  await openApp(page)
  await expect(page.locator('html')).toHaveAttribute('data-theme', 'light')

  await page.emulateMedia({ colorScheme: 'dark' })

  await expect(page.locator('html')).toHaveAttribute('data-theme', 'dark')
})
