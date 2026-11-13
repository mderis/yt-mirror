/**
 * The themes of yt-mirror and the code that picks one. Implements R-TH-04 and R-PL-05.
 *
 * A theme is one block of token values in tokens.css, selected by the
 * data-theme attribute on the root element. To add a theme: add its block to
 * tokens.css and its name here. No component changes.
 */

/** Every theme, with the colour scheme the browser should use for its own controls. */
export const THEMES = {
  light: { colorScheme: 'light' },
  dark: { colorScheme: 'dark' },
} as const

export type ThemeName = keyof typeof THEMES

/** What the user can choose: a theme, or "same as system". */
export type ThemeChoice = ThemeName | 'system'

export const THEME_NAMES = Object.keys(THEMES) as ThemeName[]

const SYSTEM_DARK_QUERY = '(prefers-color-scheme: dark)'

/**
 * Return the theme to show for a choice.
 *
 * @param choice - The user's choice.
 * @param systemPrefersDark - Whether the system is set to a dark appearance.
 */
export function resolveTheme(choice: ThemeChoice, systemPrefersDark: boolean): ThemeName {
  if (choice !== 'system') {
    return choice
  }
  return systemPrefersDark ? 'dark' : 'light'
}

/**
 * Show a theme on an element, and keep following the system when the choice is "system".
 *
 * @param choice - The user's choice.
 * @param root - The element that carries the theme. Default: the document root.
 * @param system - The system appearance. Default: the browser's media query.
 * @returns A function that stops following the system.
 */
export function applyTheme(
  choice: ThemeChoice,
  root: HTMLElement = document.documentElement,
  system: MediaQueryList = window.matchMedia(SYSTEM_DARK_QUERY),
): () => void {
  const show = (): void => {
    const theme = resolveTheme(choice, system.matches)
    root.dataset.theme = theme
    root.style.colorScheme = THEMES[theme].colorScheme
  }
  show()
  if (choice !== 'system') {
    return () => {}
  }
  system.addEventListener('change', show)
  return () => system.removeEventListener('change', show)
}
