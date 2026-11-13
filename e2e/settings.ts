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
