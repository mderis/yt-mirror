import { mkdirSync, mkdtempSync, rmSync, writeFileSync } from 'node:fs'
import { dirname, join } from 'node:path'

import { beforeAll, describe, expect, it } from 'vitest'

import { checkText, classesIn, type LintContext, type RuleId } from '../../tools/theme-lint/rules'
import { lintSources, loadContext, scopeOf, sourceFiles } from '../../tools/theme-lint/scan'
import { DESIGN_DIR, FRONTEND_DIR, read } from '../helpers/files'

let context: LintContext

beforeAll(async () => {
  context = await loadContext()
})

function rulesFor(text: string, file = 'src/features/x/Thing.vue'): RuleId[] {
  return checkText(file, text, 'code', context).map((finding) => finding.rule)
}

function template(classes: string): string {
  return `<template>\n  <div class="${classes}" />\n</template>\n`
}

describe('the theme lint rules', () => {
  it('R-TH-06: accepts a component that uses only token-based classes', () => {
    const component = template(
      'flex h-11 items-center gap-2 rounded-md border border-line bg-surface px-4 font-heading text-body font-medium text-text-muted shadow-raised duration-fast hover:bg-accent/50 focus-visible:outline-2',
    )

    expect(checkText('src/components/Button.vue', component, 'code', context)).toEqual([])
  })

  it('R-TH-06: rejects raw colour values anywhere in a file', () => {
    expect(rulesFor(`<p style="color: #1f5fd1">x</p>`)).toContain('raw-colour')
    expect(rulesFor(`const c = '#FFF'`, 'src/a.ts')).toEqual(['raw-colour'])
    expect(rulesFor(`const c = 'rgb(0 0 0 / 0.5)'`, 'src/a.ts')).toEqual(['raw-colour'])
    expect(rulesFor(`const c = 'hsl(210, 50%, 40%)'`, 'src/a.ts')).toEqual(['raw-colour'])
    expect(rulesFor(`a { color: red; }`, 'src/a.css')).toEqual(['raw-colour'])
    expect(rulesFor(`<style>\n.a { background: papayawhip; }\n</style>`)).toEqual(['raw-colour'])
  })

  it('R-TH-06: does not mistake identifiers, anchors and entities for colours', () => {
    expect(rulesFor(`const el = document.querySelector('#app')`, 'src/a.ts')).toEqual([])
    expect(rulesFor(`class A { #cache = 1 }`, 'src/a.ts')).toEqual([])
    expect(rulesFor(`const s = '&#039;'`, 'src/a.ts')).toEqual([])
    expect(rulesFor(`const messages = { color: 'Colours', font: 'Fonts' }`, 'src/a.ts')).toEqual([])
  })

  it('R-TH-06: accepts colours that come from tokens or carry no value of their own', () => {
    const css = [
      'a { color: var(--ytm-color-accent); }',
      'a { background-color: transparent; }',
      'a { fill: currentColor; }',
      'a { border-color: color-mix(in oklab, var(--ytm-color-line) 50%, transparent); }',
    ].join('\n')

    expect(rulesFor(css, 'src/a.css')).toEqual([])
  })

  it('R-TH-06: rejects pixel and rem sizes, and allows hairlines and zero', () => {
    expect(rulesFor(`a { margin: 13px; }`, 'src/a.css')).toEqual(['raw-size'])
    expect(rulesFor(`a { padding: 0.75rem 1.5em; }`, 'src/a.css')).toEqual(['raw-size', 'raw-size'])
    expect(rulesFor(`const height = '44px'`, 'src/a.ts')).toEqual(['raw-size'])
    expect(rulesFor(`a { border-width: 1px; outline-offset: 0px; }`, 'src/a.css')).toEqual([])
    expect(rulesFor('const y = `${offset}px`', 'src/a.ts')).toEqual([])
    expect(rulesFor(`a { width: 50%; flex: 1; height: 100vh; }`, 'src/a.css')).toEqual([])
  })

  it('R-TH-06: rejects font names, font sizes, weights and line heights that are not tokens', () => {
    expect(rulesFor(`a { font-family: Helvetica, sans-serif; }`, 'src/a.css')).toEqual(['raw-font'])
    expect(rulesFor(`a { font-weight: 700; }`, 'src/a.css')).toEqual(['raw-font'])
    expect(rulesFor(`a { line-height: 1.3; }`, 'src/a.css')).toEqual(['raw-font'])
    expect(rulesFor(`a { font-size: 15px; }`, 'src/a.css').sort()).toEqual(['raw-font', 'raw-size'])
    expect(rulesFor(`const style = { fontWeight: 700 }`, 'src/a.ts')).toEqual(['raw-font'])
    expect(rulesFor(`const style = { fontFamily: 'Arial' }`, 'src/a.ts')).toEqual(['raw-font'])
  })

  it('R-TH-06: accepts font declarations that use tokens', () => {
    const css = [
      'a { font-family: var(--ytm-font-text); }',
      'a { font-size: var(--ytm-font-size-body); line-height: var(--ytm-line-height-text); }',
      'a { font-weight: inherit; }',
    ].join('\n')

    expect(rulesFor(css, 'src/a.css')).toEqual([])
    expect(rulesFor(`const s = { fontSize: 'var(--ytm-font-size-meta)' }`, 'src/a.ts')).toEqual([])
  })

  it('R-TH-06: rejects Tailwind arbitrary values of every form', () => {
    expect(rulesFor(template('p-[13px]'))).toContain('arbitrary-value')
    expect(rulesFor(template('text-[15px]'))).toContain('arbitrary-value')
    expect(rulesFor(template('bg-[#123456]'))).toContain('arbitrary-value')
    expect(rulesFor(template('hover:w-[calc(100%-2rem)]'))).toContain('arbitrary-value')
    expect(rulesFor(template('[mask-type:luminance]'))).toContain('arbitrary-value')
    expect(rulesFor(template('bg-(--my-colour)'))).toContain('arbitrary-value')
  })

  it('R-TH-06: does not mistake ordinary brackets for arbitrary values', () => {
    const script = [
      'const first = items[0]',
      'const total = a - [b].length',
      'interface Map { [key: string]: number }',
      "const el = root.querySelector('[data-theme=dark]')",
    ].join('\n')

    expect(rulesFor(script, 'src/a.ts')).toEqual([])
  })

  it('R-TH-06: rejects spacing that is neither half a step nor whole steps', () => {
    expect(rulesFor(template('p-1.5'))).toEqual(['off-scale'])
    expect(rulesFor(template('hover:gap-x-2.5'))).toEqual(['off-scale'])
    expect(rulesFor(template('-mt-0.25'))).toEqual(['off-scale'])
    expect(rulesFor(template('w-3.5 max-w-7.5'))).toEqual(['off-scale', 'off-scale'])
    expect(rulesFor(template('gap-0.75 p-10.5'))).toEqual(['off-scale', 'off-scale'])
    expect(rulesFor(template('p-4 gap-2 w-64 -mt-1 inset-0'))).toEqual([])
  })

  it('R-TH-06: accepts half a step, the 2 px step of the spacing scale', () => {
    expect(rulesFor(template('gap-0.5 p-0.5 -mt-0.5 hover:gap-x-0.5 inset-0.5'))).toEqual([])
  })

  it('R-TH-06: rejects one-off line heights and durations', () => {
    expect(rulesFor(template('leading-6'))).toEqual(['off-scale'])
    expect(rulesFor(template('duration-150'))).toEqual(['off-scale'])
    expect(rulesFor(template('leading-text duration-base'))).toEqual([])
  })

  it('R-TH-09: rejects a class that names a colour, size or radius the theme does not define', () => {
    for (const unknown of [
      'bg-blue-500',
      'text-gray-700',
      'text-sm',
      'text-xl',
      'font-bold',
      'font-sans',
      'rounded-2xl',
      'shadow-lg',
      'leading-tight',
      'max-w-md',
      'bg-surface-missing',
      'my-own-class',
    ]) {
      expect(rulesFor(template(unknown)), unknown).toEqual(['unknown-class'])
    }
  })

  it('R-TH-09: checks the classes inside bound class expressions too', () => {
    const component = `<template>
  <div :class="[active ? 'bg-accent text-on-accent' : 'bg-blue-500', \`rounded-\${size}\`, { 'text-sm': small }]" />
</template>`

    const findings = checkText('src/components/Chip.vue', component, 'code', context)

    expect(findings.map((finding) => finding.message)).toEqual([
      'bg-blue-500 is not a class of the theme. Use a token-based class',
      'rounded-${size} is not a class of the theme. Use a token-based class',
      'text-sm is not a class of the theme. Use a token-based class',
    ])
  })

  it('R-TH-09: lists the classes of static and bound attributes with their positions', () => {
    const text = `<a class="one two" :class="['three', cond && 'four five']" v-bind:class="\`six\`">`

    expect(classesIn(text).map((entry) => entry.name)).toEqual([
      'one',
      'two',
      'three',
      'four',
      'five',
      'six',
    ])
    expect(text.slice(classesIn(text)[1]?.index).startsWith('two')).toBe(true)
    expect(text.slice(classesIn(text)[3]?.index).startsWith('four')).toBe(true)
  })

  it('R-TH-09: rejects a reference to a token that is not defined, also inside the theme center', () => {
    const css = 'a { color: var(--ytm-color-acent); margin: var( --ytm-space ); }'

    const inCode = checkText('src/a.css', css, 'code', context)
    const inDesign = checkText('src/design/base.css', css, 'design', context)

    expect(inCode.map((finding) => finding.rule)).toEqual(['undefined-token'])
    expect(inDesign.map((finding) => finding.message)).toEqual([
      '--ytm-color-acent is not defined in tokens.css',
    ])
  })

  it('R-TH-01: lets the theme center itself hold raw values', () => {
    const tokensCss = read(DESIGN_DIR, 'tokens.css')

    expect(checkText('src/design/tokens.css', tokensCss, 'design', context)).toEqual([])
    expect(checkText('src/features/x.css', tokensCss, 'code', context).length).toBeGreaterThan(40)
  })

  it('R-TH-06: reports the file, the line and what to do', () => {
    const component = `<template>\n  <p>ok</p>\n  <p class="text-sm">x</p>\n</template>\n<style>\n.a { color: #fff; }\n</style>\n`

    const findings = checkText('src/features/x/Thing.vue', component, 'code', context)

    expect(findings).toEqual([
      {
        file: 'src/features/x/Thing.vue',
        line: 3,
        rule: 'unknown-class',
        message: 'text-sm is not a class of the theme. Use a token-based class',
      },
      {
        file: 'src/features/x/Thing.vue',
        line: 6,
        rule: 'raw-colour',
        message: '#fff is a raw colour. Use a colour token',
      },
    ])
  })
})

describe('the theme lint on the source tree', () => {
  it('R-TH-06, R-TH-09: the real source tree uses only tokens, and every token it uses is defined', async () => {
    expect(await lintSources()).toEqual([])
  })

  it('R-TH-06: checks every source file and both entry pages', () => {
    const files = sourceFiles()

    expect(files).toContain('index.html')
    expect(files).toContain('theme-preview.html')
    expect(files).toContain(join('src', 'App.vue'))
    expect(files).toContain(join('src', 'features', 'placeholder', 'PlaceholderPage.vue'))
    expect(files).toContain(join('src', 'design', 'theme.css'))
    expect(files.some((file) => file.includes(join('design', 'fonts', 'inter')))).toBe(false)
  })

  it('R-TH-01: treats only src/design as the theme center', () => {
    expect(scopeOf(join('src', 'design', 'preview', 'ThemePreview.vue'))).toBe('design')
    expect(scopeOf(join('src', 'designer', 'Other.vue'))).toBe('code')
    expect(scopeOf(join('src', 'features', 'placeholder', 'PlaceholderPage.vue'))).toBe('code')
    expect(scopeOf('index.html')).toBe('code')
  })

  it('R-TH-06, R-TH-09: finds problems in a source tree that has them', async () => {
    // Inside node_modules, so that the stylesheet of the throwaway tree can import Tailwind.
    const root = mkdtempSync(join(FRONTEND_DIR, 'node_modules', '.theme-lint-test-'))
    const write = (path: string, text: string): void => {
      mkdirSync(dirname(join(root, path)), { recursive: true })
      writeFileSync(join(root, path), text)
    }
    try {
      for (const file of ['tokens.css', 'theme.css', 'base.css', 'index.css']) {
        write(join('src', 'design', file), read(DESIGN_DIR, file))
      }
      write(join('src', 'design', 'extra.css'), 'a { color: var(--ytm-color-nope); }')
      write('index.html', '<div id="app"></div>')
      write('theme-preview.html', '<div id="app" style="color: #abc"></div>')
      write(join('src', 'Bad.vue'), '<template><p class="text-sm p-[3px]">x</p></template>')

      const findings = await lintSources(root)

      expect(findings.map((finding) => finding.rule).sort()).toEqual([
        'arbitrary-value',
        'raw-colour',
        'raw-size',
        'undefined-token',
        'unknown-class',
      ])
    } finally {
      rmSync(root, { recursive: true, force: true })
    }
  })
})
