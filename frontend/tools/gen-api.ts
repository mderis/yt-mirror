/**
 * Generates src/api/schema.d.ts from the OpenAPI schema of the backend.
 *
 * Run with `npm --prefix frontend run gen:api`. The schema is the contract
 * between backend and frontend (docs/ARCHITECTURE.md section 8). CI runs this
 * and fails when the generated file differs from the committed one.
 */
import { execFileSync } from 'node:child_process'
import { mkdtempSync, readFileSync, rmSync, writeFileSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { dirname, join, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

import openapiTS, { astToString } from 'openapi-typescript'
import { format, resolveConfig } from 'prettier'

const frontendDir = resolve(dirname(fileURLToPath(import.meta.url)), '..')
const repoRoot = resolve(frontendDir, '..')
const target = join(frontendDir, 'src', 'api', 'schema.d.ts')

const HEADER = `/**
 * Generated from the OpenAPI schema of the backend. Do not edit by hand.
 * Regenerate with: npm --prefix frontend run gen:api
 */

`

const workDir = mkdtempSync(join(tmpdir(), 'ytm-openapi-'))
try {
  const schemaFile = join(workDir, 'openapi.json')
  // scripts/uv finds the uv of this clone, or one on PATH (as in CI).
  execFileSync(
    join(repoRoot, 'scripts', 'uv'),
    ['run', '--project', repoRoot, 'python', '-m', 'ytmirror.tools.export_openapi', schemaFile],
    { cwd: repoRoot, stdio: ['ignore', 'inherit', 'inherit'] },
  )
  const schema: unknown = JSON.parse(readFileSync(schemaFile, 'utf8'))
  const types = astToString(await openapiTS(schema as Parameters<typeof openapiTS>[0]))
  const options = await resolveConfig(target)
  writeFileSync(target, await format(HEADER + types, { ...options, filepath: target }))
  console.log(`Wrote ${target}`)
} finally {
  rmSync(workDir, { recursive: true, force: true })
}
