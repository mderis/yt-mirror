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
  /**
   * The user text of each error code (R-ER-01, R-ER-02), by the text key of the code:
   * what happened, what yt-mirror is doing about it, what the user can do.
   * Milestone M7 adds the texts of the remaining codes.
   */
  errors: {
    local_server_unreachable: {
      happened: 'The window cannot reach yt-mirror.',
      doing: 'yt-mirror does not try again by itself here.',
      action: 'Try again. If that does not help, quit yt-mirror and start it again.',
    },
  },
  placeholder: {
    running: 'yt-mirror is running.',
    version: 'Version {version}',
    connecting: 'Connecting to yt-mirror',
    failed: 'yt-mirror answered with an error.',
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
