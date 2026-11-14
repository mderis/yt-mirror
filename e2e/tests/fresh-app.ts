import { spawn, type ChildProcess } from 'node:child_process'
import { mkdtempSync, rmSync, writeFileSync } from 'node:fs'
import { createServer } from 'node:net'
import { tmpdir } from 'node:os'
import { join } from 'node:path'

import { test as base } from '@playwright/test'

import { TOOLS_URL } from '../settings'

/**
 * An app of its own for one test: started with the real launcher on empty
 * data and tool folders, so the test sees a true first run. The tools it
 * downloads are the stand-ins of fixtures/tools.
 */
export interface FreshApp {
  /** The address of the app. */
  url: string
  /** The first address of the window, with the session token. */
  firstUrl: string
  /** The folder the app installs its tools into. */
  toolDir: string
  /** Make the next downloads of a file fail, for this app only. */
  failDownload: (file: string, times?: number) => Promise<void>
  /** Ask the API of this app. */
  api: (path: string) => Promise<unknown>
  /** Stop the app and start it again on the same folders. */
  restart: () => Promise<void>
}

const TOKEN = 'fresh-app-token-not-a-secret'

function freePort(): Promise<number> {
  return new Promise((resolve, reject) => {
    const probe = createServer()
    probe.once('error', reject)
    probe.listen(0, '127.0.0.1', () => {
      const address = probe.address()
      probe.close(() => resolve(typeof address === 'object' && address ? address.port : 0))
    })
  })
}

async function waitUntilServing(url: string, process: ChildProcess): Promise<void> {
  const deadline = Date.now() + 120_000
  for (;;) {
    try {
      if ((await fetch(`${url}/`)).status === 200) {
        return
      }
    } catch {
      // Not listening yet.
    }
    if (process.exitCode !== null) {
      throw new Error(`The app ended before it served: exit code ${process.exitCode}`)
    }
    if (Date.now() > deadline) {
      throw new Error('The app did not serve in time')
    }
    await new Promise((resolve) => setTimeout(resolve, 100))
  }
}

function stop(process: ChildProcess): Promise<void> {
  return new Promise((resolve) => {
    if (process.exitCode !== null) {
      resolve()
      return
    }
    process.once('exit', () => resolve())
    process.kill('SIGTERM')
  })
}

export const test = base.extend<{ freshApp: FreshApp }>({
  freshApp: async ({}, use, testInfo) => {
    const name = `fresh-${testInfo.project.name}-${testInfo.testId}`
    const folder = mkdtempSync(join(tmpdir(), 'ytm-e2e-'))
    const port = await freePort()
    const url = `http://127.0.0.1:${port}`
    const manifest = join(folder, 'manifest.json')
    writeFileSync(manifest, await (await fetch(`${TOOLS_URL}/manifest/${name}`)).text())
    const env = {
      ...process.env,
      YTM_NO_WINDOW: '1',
      YTM_PORT: String(port),
      YTM_SESSION_TOKEN: TOKEN,
      YTM_DATA_DIR: join(folder, 'data'),
      YTM_TOOL_DIR: join(folder, 'tools'),
      YTM_TOOL_MANIFEST: manifest,
    }
    const start = async (): Promise<ChildProcess> => {
      const child = spawn('../start', [], { env, stdio: 'ignore' })
      await waitUntilServing(url, child)
      return child
    }
    let app = await start()
    await use({
      url,
      firstUrl: `${url}/?token=${TOKEN}`,
      toolDir: join(folder, 'tools'),
      failDownload: async (file, times = 1) => {
        await fetch(`${TOOLS_URL}/control/${name}/fail?file=${file}&times=${times}`, {
          method: 'POST',
        })
      },
      api: async (path) =>
        (
          await fetch(`${url}/api${path}`, { headers: { Authorization: `Bearer ${TOKEN}` } })
        ).json(),
      restart: async () => {
        await stop(app)
        app = await start()
      },
    })
    await stop(app)
    rmSync(folder, { recursive: true, force: true })
  },
})

export { expect } from '@playwright/test'
