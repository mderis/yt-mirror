# design: the theme center

Every visual value of yt-mirror lives in this folder and nowhere else (R-TH-01 to R-TH-09, docs/DESIGN.md section 2).

| File         | What it is                                                                                                          |
| ------------ | ------------------------------------------------------------------------------------------------------------------- |
| `tokens.css` | Every token as a CSS variable: shared values, then one block per theme. Plain CSS, so the website can import it too |
| `theme.css`  | The Tailwind preset. Maps tokens to utility classes and switches off Tailwind's own palette and scales              |
| `base.css`   | The few element defaults (page background, text font and size)                                                      |
| `index.css`  | The stylesheet entry: Tailwind, then the three files above                                                          |
| `index.ts`   | What the app imports: the stylesheet, the fonts and the theme switch                                                |
| `themes.ts`  | The list of themes and the code that picks one (system, light, dark)                                                |
| `tokens.ts`  | Reads `tokens.css` into data. Used by the preview page, the tests and the theme lint                                |
| `fonts/`     | One folder per bundled font: font files, license, and a `font.css` that declares them                               |
| `brand/`     | `icon.svg`, the one source of the app icon, and a component that shows it                                           |
| `preview/`   | The theme preview page, for development only                                                                        |

## How to

**Change a colour, a size, a radius:** change the value in `tokens.css`. Update the tables in docs/DESIGN.md section 2 in the same commit. A test compares the two.

**Add a token:** add it to `tokens.css` (every theme block, if it is a colour or a shadow), map it in `theme.css`, add it to docs/DESIGN.md. The preview page shows it without further work.

**Add a theme:** add one `[data-theme='name']` block to `tokens.css` with every colour and shadow token, and add the name to `THEMES` in `themes.ts`. No component changes.

**Change the app font:** put the new font's folder into `fonts/` (font files, license, `font.css`), then change the one `--ytm-font-text` line in `tokens.css`. Every `fonts/*/font.css` is loaded automatically.

## Rules

- Token names say what a value is for, never what it looks like.
- Outside this folder, code uses only token-based utility classes. `npm run lint:theme` enforces it.
- Fonts are files in this folder. Nothing is loaded from the network.

Tests: `frontend/tests/design/`.
