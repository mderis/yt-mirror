/**
 * The theme center of yt-mirror (docs/DESIGN.md section 2). Implements R-TH-01.
 *
 * Importing this module loads the stylesheet and every bundled font.
 * See README.md in this folder for how to change a value, a font or a theme.
 */
import './index.css'
import './fonts'

export { applyTheme, resolveTheme, THEMES, THEME_NAMES } from './themes'
export type { ThemeChoice, ThemeName } from './themes'
