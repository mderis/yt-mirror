/**
 * Stand-ins for the tools the app downloads, for the end-to-end tests
 * (docs/TESTING.md section 6, flow 1).
 *
 * The real tools are 30 MB each and come from the internet. The tests use
 * tiny shell scripts instead, packed like the real downloads and served from
 * this Mac. The app is pointed at them with YTM_TOOL_MANIFEST.
 *
 *   node tools.mjs build <folder>         Pack the stand-ins and write the manifests.
 *   node tools.mjs serve <folder> <port>  Serve them.
 *
 * Every download address contains a name chosen by the test that uses it:
 * /t/<name>/<file>. A test can make a file fail for its own name only, so
 * tests that run side by side do not disturb each other:
 *
 *   POST /control/<name>/fail?file=ffmpeg.zip&times=1
 *   GET  /manifest/<name>   The manifest whose addresses carry that name.
 */
import { execFileSync } from 'node:child_process'
import { createHash } from 'node:crypto'
import { chmodSync, existsSync, mkdirSync, readFileSync, rmSync, writeFileSync } from 'node:fs'
import { createServer } from 'node:http'
import { join } from 'node:path'

const PROGRAMS = {
  ffmpeg: 'ffmpeg version 0.0.1-e2e',
  ffprobe: 'ffprobe version 0.0.1-e2e',
  deno: 'deno 0.0.1-e2e',
}
const ARCHIVES = [
  { file: 'ffmpeg.zip', kind: 'zip', programs: ['ffmpeg'] },
  { file: 'ffprobe.zip', kind: 'zip', programs: ['ffprobe'] },
  { file: 'both.tar.xz', kind: 'tar.xz', programs: ['ffmpeg', 'ffprobe'] },
  { file: 'deno.zip', kind: 'zip', programs: ['deno'] },
]
const BASE = '{{BASE}}'
export const SHARED_NAME = 'shared'

function build(folder, port) {
  rmSync(folder, { recursive: true, force: true })
  const programs = join(folder, 'programs')
  mkdirSync(programs, { recursive: true })
  for (const [name, output] of Object.entries(PROGRAMS)) {
    writeFileSync(join(programs, name), `#!/bin/sh\necho '${output}'\n`)
    chmodSync(join(programs, name), 0o755)
  }
  const entries = {}
  for (const { file, kind, programs: names } of ARCHIVES) {
    const target = join(folder, file)
    if (kind === 'zip') {
      execFileSync('/usr/bin/zip', ['-q', '-j', target, ...names.map((n) => join(programs, n))])
    } else {
      execFileSync('/usr/bin/tar', ['-cJf', target, '-C', programs, ...names])
    }
    entries[file] = {
      url: `${BASE}/${file}`,
      sha256: createHash('sha256').update(readFileSync(target)).digest('hex'),
      kind,
      programs: names,
    }
  }
  const both = (files) => ({ arm64: files, x86_64: files })
  const template = {
    tools: {
      ffmpeg: {
        programs: ['ffmpeg', 'ffprobe'],
        check: ['-version'],
        sources: [
          {
            name: 'first-source',
            version: '0.0.1',
            ...both([entries['ffmpeg.zip'], entries['ffprobe.zip']]),
          },
          { name: 'second-source', version: '0.0.1', ...both([entries['both.tar.xz']]) },
        ],
      },
      deno: {
        programs: ['deno'],
        check: ['--version'],
        sources: [{ name: 'deno', version: '0.0.1', ...both([entries['deno.zip']]) }],
      },
    },
  }
  writeFileSync(join(folder, 'manifest.template.json'), JSON.stringify(template, null, 2))
  writeFileSync(join(folder, 'manifest.json'), manifestFor(folder, port, SHARED_NAME))
}

function manifestFor(folder, port, name) {
  const template = readFileSync(join(folder, 'manifest.template.json'), 'utf8')
  return template.replaceAll(BASE, `http://127.0.0.1:${port}/t/${name}`)
}

function serve(folder, port) {
  /** How often the next requests for a file must fail, by "<name>/<file>". */
  const failures = new Map()
  const server = createServer((request, response) => {
    const url = new URL(request.url ?? '/', `http://127.0.0.1:${port}`)
    const [, area, name, file] = url.pathname.split('/')
    const answer = (status, body, type = 'text/plain') => {
      response.writeHead(status, {
        'Content-Type': type,
        'Content-Length': Buffer.byteLength(body),
      })
      response.end(body)
    }
    if (url.pathname === '/ready') {
      return answer(existsSync(join(folder, 'manifest.template.json')) ? 200 : 503, 'ready')
    }
    if (area === 'manifest' && name) {
      return answer(200, manifestFor(folder, port, name), 'application/json')
    }
    if (area === 'control' && name && file === 'fail' && request.method === 'POST') {
      const key = `${name}/${url.searchParams.get('file')}`
      failures.set(key, Number(url.searchParams.get('times') ?? '1'))
      return answer(200, 'ok')
    }
    if (area === 't' && name && ARCHIVES.some((archive) => archive.file === file)) {
      const left = failures.get(`${name}/${file}`) ?? 0
      if (left > 0) {
        failures.set(`${name}/${file}`, left - 1)
        return answer(503, 'This download fails because a test asked for it.')
      }
      return answer(200, readFileSync(join(folder, file)), 'application/octet-stream')
    }
    return answer(404, 'not found')
  })
  server.listen(port, '127.0.0.1')
}

const [command, folder, port] = process.argv.slice(2)
if (command === 'build') {
  build(folder, Number(port))
} else if (command === 'serve') {
  serve(folder, Number(port))
} else {
  console.error('usage: node tools.mjs build|serve <folder> <port>')
  process.exit(2)
}
