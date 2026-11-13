/**
 * Every user-visible text of the app, in English (R-PL-06).
 *
 * Components never contain text. They refer to a key in this file. Use the
 * words of docs/GLOSSARY.md.
 */
export const en = {
  app: {
    name: 'yt-mirror',
  },
  placeholder: {
    running: 'yt-mirror is running.',
    version: 'Version {version}',
    connecting: 'Connecting to yt-mirror',
    failed: 'The window could not reach yt-mirror.',
    errorCode: 'Error code: {code}',
    retry: 'Try again',
  },
  themePreview: {
    title: 'Theme preview',
    intro: 'Every token and every shared component, in every theme. For development only.',
    theme: 'Theme: {name}',
    sample: 'The quick brown fox jumps over the lazy dog',
    groups: {
      color: 'Colours',
      'font-size': 'Font sizes',
      'font-weight': 'Font weights',
      font: 'Font families',
      'line-height': 'Line heights',
      space: 'Spacing step',
      radius: 'Corner radii',
      shadow: 'Shadows',
      duration: 'Animation durations',
    },
    brand: 'Brand icon',
    components: 'Shared components',
    noComponents:
      'No shared components exist yet. Each one is added here in the commit that creates it.',
    reducedMotion: 'With reduced motion: {value}',
    hoverMe: 'Hover to see the duration',
    spaceSteps: 'Multiples: 1, 2, 4, 8',
  },
} as const

export type Messages = typeof en
