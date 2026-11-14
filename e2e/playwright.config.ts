import { resolve } from 'node:path'

import { defineConfig, devices } from '@playwright/test'

import {
  APP_PORT,
  APP_URL,
  DATA_DIR,
  FAKE_YOUTUBE_DIR,
  PREVIEW_PORT,
  PREVIEW_URL,
  SESSION_TOKEN,
  SHARED_LIBRARY_DIR,
  SHARED_TOOL_DIR,
  TOOLS_FIXTURE_DIR,
  TOOLS_PORT,
  TOOLS_URL,
} from './settings'

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
  // Installs the stand-in tools into the shared app, so that it is past its first run.
  globalSetup: './global-setup.ts',
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
    // Dates are shown in the time zone of the machine (R-DT-02). The tests fix it.
    timezoneId: 'UTC',
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
      // The stand-ins of the downloadable tools are packed first: the app reads their manifest.
      command: `rm -rf ${DATA_DIR} && node fixtures/tools/tools.mjs build ${TOOLS_FIXTURE_DIR} ${TOOLS_PORT} && ../start`,
      url: `${APP_URL}/`,
      env: {
        YTM_NO_WINDOW: '1',
        YTM_PORT: String(APP_PORT),
        YTM_SESSION_TOKEN: SESSION_TOKEN,
        YTM_DATA_DIR: `${DATA_DIR}/shared-data`,
        YTM_TOOL_DIR: SHARED_TOOL_DIR,
        YTM_TOOL_MANIFEST: `${TOOLS_FIXTURE_DIR}/manifest.json`,
        // No test asks the real YouTube or writes into the real library.
        YTM_FAKE_YOUTUBE: resolve(FAKE_YOUTUBE_DIR),
        YTM_LIBRARY_DIR: resolve(SHARED_LIBRARY_DIR),
      },
      reuseExistingServer: false,
      // The first start downloads uv, Python and packages, and builds the interface.
      timeout: 600_000,
      stdout: 'pipe',
      stderr: 'pipe',
    },
    {
      // Serves the stand-ins of the downloadable tools (fixtures/tools/tools.mjs).
      command: `node fixtures/tools/tools.mjs serve ${TOOLS_FIXTURE_DIR} ${TOOLS_PORT}`,
      url: `${TOOLS_URL}/ready`,
      reuseExistingServer: false,
      timeout: 120_000,
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
