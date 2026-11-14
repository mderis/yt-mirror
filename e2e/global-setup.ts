import { APP_URL, SESSION_TOKEN } from './settings'

/**
 * Brings the shared app past its first run: installs the stand-in tools
 * through the API, as the first-run screen would. The tests of the first run
 * itself start apps of their own (tests/fresh-app.ts).
 */
const headers = { Authorization: `Bearer ${SESSION_TOKEN}` }

interface Tools {
  tools: { name: string; status: string }[]
  setup_required: boolean
}

async function tools(): Promise<Tools> {
  return (await (await fetch(`${APP_URL}/api/tools`, { headers })).json()) as Tools
}

export default async function globalSetup(): Promise<void> {
  for (const name of ['ffmpeg', 'deno']) {
    const started = await fetch(`${APP_URL}/api/tools/${name}/install`, { method: 'POST', headers })
    if (started.status !== 202) {
      throw new Error(`The shared app refused to install ${name}: ${started.status}`)
    }
  }
  const deadline = Date.now() + 60_000
  for (;;) {
    const state = await tools()
    if (!state.setup_required && state.tools.every((tool) => tool.status === 'ok')) {
      return
    }
    if (Date.now() > deadline) {
      throw new Error(`The shared app did not finish its setup: ${JSON.stringify(state)}`)
    }
    await new Promise((resolve) => setTimeout(resolve, 200))
  }
}
