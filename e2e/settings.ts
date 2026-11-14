/**
 * The fixed values the end-to-end tests and the servers they start agree on
 * (docs/ARCHITECTURE.md section 10).
 */

/** The port of the real backend, started by `../start` without a window. */
export const APP_PORT = 47801
export const APP_URL = `http://127.0.0.1:${APP_PORT}`

/** The session token of that backend. A real run creates a random one. */
export const SESSION_TOKEN = 'e2e-session-token-not-a-secret'

/** The development server that serves the theme preview page (R-TH-08). */
export const PREVIEW_PORT = 5174
export const PREVIEW_URL = `http://127.0.0.1:${PREVIEW_PORT}`

/** The web server that serves the stand-ins of the downloadable tools (fixtures/tools). */
export const TOOLS_PORT = 5175
export const TOOLS_URL = `http://127.0.0.1:${TOOLS_PORT}`

/** Where the stand-ins are built, and where the shared app keeps the ones it installed. */
export const DATA_DIR = '.data'
export const TOOLS_FIXTURE_DIR = `${DATA_DIR}/tool-downloads`
export const SHARED_TOOL_DIR = `${DATA_DIR}/shared-tools`

/** The fake YouTube: a recorded world of channels (docs/TESTING.md section 4). */
export const FAKE_YOUTUBE_DIR = 'fixtures/youtube'
/** The library folder of the shared app, so that no test touches `~/Movies/YouTube`. */
export const SHARED_LIBRARY_DIR = `${DATA_DIR}/shared-library`
