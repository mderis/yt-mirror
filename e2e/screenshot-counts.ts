/**
 * Count the differing pixels of every screenshot against the stored image
 * (docs/TESTING.md section 6), passing or not: Playwright itself says the
 * count only when an image fails.
 *
 * The images are made by a run with YTM_SCREENSHOT_DIR set (playwright.config.ts).
 * They are compared with Playwright's own comparator, at the threshold of the
 * tests. The table is written as Markdown, for the summary of a CI job.
 *
 * Usage: node screenshot-counts.ts <made folder> [stored folder]
 * Exits with 1 when a stored image was not made (its test did not run), or
 * when an image is over the limit.
 */
import { existsSync, readdirSync, readFileSync } from 'node:fs'
import { createRequire } from 'node:module'
import { join, relative } from 'node:path'

import { LIMIT_PIXELS, THRESHOLD } from './screenshot-limits.ts'

interface Comparator {
  (actual: Buffer, expected: Buffer, options: object): { errorMessage: string } | null
}

const require = createRequire(import.meta.url)
const core = require('playwright-core/lib/coreBundle') as {
  utils: { getComparator: (mimeType: string) => Comparator }
}
const compare = core.utils.getComparator('image/png')

function images(folder: string): string[] {
  if (!existsSync(folder)) {
    return []
  }
  return readdirSync(folder, { recursive: true, encoding: 'utf8' })
    .filter((name) => name.endsWith('.png'))
    .sort()
}

/** The differing pixels, or the reason there is no count. */
function differing(made: Buffer, stored: Buffer): number | string {
  const result = compare(made, stored, { threshold: THRESHOLD, maxDiffPixels: 0 })
  if (result === null) {
    return 0
  }
  const count = /(\d+) pixels \(ratio/.exec(result.errorMessage)
  return count ? Number(count[1]) : (result.errorMessage.split('.')[0] ?? 'not compared')
}

const [madeFolder, storedFolder = join(import.meta.dirname, 'tests', '__screenshots__')] =
  process.argv.slice(2)
if (madeFolder === undefined) {
  console.error('Usage: node screenshot-counts.ts <made folder> [stored folder]')
  process.exit(2)
}

const made = new Set(images(madeFolder))
const stored = new Set(images(storedFolder))
const rows: string[] = []
let failed = false
for (const name of [...new Set([...made, ...stored])].sort()) {
  let count: number | string
  if (!made.has(name)) {
    count = 'not made: its test did not run'
    failed = true
  } else if (!stored.has(name)) {
    count = 'new: no stored image'
  } else {
    count = differing(readFileSync(join(madeFolder, name)), readFileSync(join(storedFolder, name)))
  }
  const over = typeof count === 'number' && count > LIMIT_PIXELS
  const missing = typeof count === 'string' && !count.startsWith('new')
  failed ||= over || missing
  const verdict = over ? 'over the limit' : missing ? 'missing' : 'ok'
  rows.push(`| ${relative('.', name)} | ${count} | ${verdict} |`)
}

console.log(`### Screenshots: differing pixels against the stored images`)
console.log('')
console.log(
  `Threshold ${THRESHOLD}, limit ${LIMIT_PIXELS} pixels. ${made.size} made, ${stored.size} stored.`,
)
console.log('')
console.log('| Image | Differing pixels | |')
console.log('|---|---|---|')
for (const row of rows) {
  console.log(row)
}
process.exit(failed ? 1 : 0)
