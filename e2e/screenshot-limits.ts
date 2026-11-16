/**
 * How a screenshot is compared (docs/TESTING.md section 6), for the tests and
 * for screenshot-counts.ts alike.
 */

/** At most this many differing pixels, never a share of the image. */
export const LIMIT_PIXELS = 100

/** A pixel differs from this colour difference on. The same for both browsers. */
export const THRESHOLD = 0.02
