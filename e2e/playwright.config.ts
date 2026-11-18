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
import { LIMIT_PIXELS, THRESHOLD } from './screenshot-limits.ts'

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

/**
 * With YTM_SCREENSHOT_DIR set, every screenshot is written into that folder instead of
 * being compared, so that screenshot-counts.ts can count each against the stored image,
 * and CI can make all images (docs/TESTING.md section 6).
 */
const madeScreenshots = process.env.YTM_SCREENSHOT_DIR
const viewport = { width: 1280, height: 800 }

export default defineConfig({
  testDir: './tests',
  // Installs the stand-in tools into the shared app, so that it is past its first run.
  globalSetup: './global-setup.ts',
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: 0,
  reporter: [['list'], ['html', { open: 'never' }]],
  // One image per browser, made and compared on the macOS of CI (TESTING.md section 6).
  snapshotPathTemplate: `${madeScreenshots ? resolve(madeScreenshots) : '{testDir}/__screenshots__'}/{testFileName}/{arg}-{projectName}{ext}`,
  ...(madeScreenshots ? { updateSnapshots: 'all' as const } : {}),
  expect: {
    // At most so many differing pixels, never a share of the image; a pixel differs from
    // the threshold on. Text that differs between machines gets a fixed box (screenshot.css).
    toHaveScreenshot: {
      maxDiffPixels: LIMIT_PIXELS,
      threshold: THRESHOLD,
      animations: 'disabled',
      stylePath: resolve(import.meta.dirname, 'screenshot.css'),
    },
  },
  use: {
    baseURL: APP_URL,
    trace: 'retain-on-failure',
    // Dates are shown in the time zone of the machine (R-DT-02). The tests fix it.
    timezoneId: 'UTC',
  },
  projects: [
    {
      name: 'webkit',
      use: { ...devices['Desktop Safari'], viewport },
    },
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
      command: `rm -rf ${DATA_DIR} && mkdir -p ${DATA_DIR} && echo 500000000000 > ${DATA_DIR}/shared-free-space && node fixtures/tools/tools.mjs build ${TOOLS_FIXTURE_DIR} ${TOOLS_PORT} && ../start`,
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
        // Files that a test deletes go here, never into the Trash of the person who runs it.
        YTM_TRASH_DIR: resolve(`${DATA_DIR}/shared-trash`),
        // No exact-date lookups without a key: the dates stay as the tests recorded them.
        YTM_FAKE_LOOKUPS_PER_HOUR: '0',
        // The disk space guard sees plenty of room, never the free space of the Mac (R-QU-10).
        YTM_FAKE_FREE_SPACE_FILE: resolve(`${DATA_DIR}/shared-free-space`),
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
