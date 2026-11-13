/**
 * The command line of the theme lint: `npm run lint:theme` (R-TH-06).
 *
 * Prints one line per finding and ends with exit code 1 when there is any.
 */
import { lintSources } from './scan.ts'

const findings = await lintSources()
for (const finding of findings) {
  console.error(`${finding.file}:${finding.line}  ${finding.rule}  ${finding.message}`)
}
if (findings.length > 0) {
  console.error(
    `\n${findings.length} problem(s). Code outside src/design/ may use only tokens (docs/DESIGN.md section 2).`,
  )
  process.exit(1)
}
console.log('Theme lint: every source file uses only tokens.')
