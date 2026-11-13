import { defineConfig, devices } from '@playwright/test'

import { APP_PORT, APP_URL, PREVIEW_PORT, PREVIEW_URL, SESSION_TOKEN } from './settings'

/**
 * End-to-end tests of yt-mirror (docs/TESTING.md section 6).
 *
 * They run against the real backend, started with the real launcher, and the
 * real built interface, in WebKit (the engine of the app window) and Chromium.
 *
 * Where the Chromium build of Playwright cannot be downloaded, an installed
 * Google Chrome can be used instead: YTM_E2E_CHROME_CHANNEL=chrome npm test
 */
const chromeChannel = process.env.YTM_E2E_CHROME_CHANNEL
const viewport = { width: 1280, height: 800 }

export default defineConfig({
  testDir: './tests',
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: 0,
  reporter: [['list'], ['html', { open: 'never' }]],
  // One baseline per browser. They are compared on every platform the tests run on.
  snapshotPathTemplate: '{testDir}/__screenshots__/{testFileName}/{arg}-{projectName}{ext}',
  expect: {
    toHaveScreenshot: { maxDiffPixelRatio: 0.02, animations: 'disabled' },
  },
  use: {
    baseURL: APP_URL,
    trace: 'retain-on-failure',
  },
  projects: [
    { name: 'webkit', use: { ...devices['Desktop Safari'], viewport } },
    {
      name: 'chromium',
      use: {
        ...devices['Desktop Chrome'],
        viewport,
        ...(chromeChannel ? { channel: chromeChannel } : {}),
      },
    },
  ],
  webServer: [
    {
      // The real launcher on a fresh data folder: also proves that a clone starts (R-IN-02).
      command: 'rm -rf .data && ../start',
      url: `${APP_URL}/`,
      env: {
        YTM_NO_WINDOW: '1',
        YTM_PORT: String(APP_PORT),
        YTM_SESSION_TOKEN: SESSION_TOKEN,
        YTM_DATA_DIR: '.data',
      },
      reuseExistingServer: false,
      // The first start downloads uv, Python and packages, and builds the interface.
      timeout: 600_000,
      stdout: 'pipe',
      stderr: 'pipe',
    },
    {
      // The development server, for the theme preview page only.
      command: `npm --prefix ../frontend run dev -- --port ${PREVIEW_PORT} --strictPort`,
      url: `${PREVIEW_URL}/theme-preview.html`,
      reuseExistingServer: false,
      timeout: 120_000,
    },
  ],
})
