# yt-mirror V1: Design

The designs for V1 are attached to this version of the repository in `docs/design/v1/`. Open `docs/design/v1/index.html` in a browser to see all of them. They are static HTML mockups: they define layout, wording and states. They contain no logic and are not the app.

The editable source of the designs is a design canvas outside the repository: https://claude.ai/artifact/HJuQA3PaS2Em4b9vgCL4MK (private to the maintainer). When a design changes, the HTML export in this folder must be regenerated so the repository stays the reference.

When a mockup and [SPEC.md](SPEC.md) disagree, the spec wins and the mockup must be fixed.

**Review status:** every screen in this folder was rendered in a headless Chrome and reviewed on 14 November 2026. Fixes from that review: bars that overlapped list rows, a dangling separator in the channel header, long status chips that pushed row actions onto a second line, a wrong default in the parallel downloads control, and frame heights that clipped or left empty space. The review used Chrome only. The app window uses WebKit, so the implementer must still check the real UI there. The app icon is a rough draft. Spacing and exact sizes are guidance. Structure, wording and states are binding.

## 1. Screen inventory

| File | Screen | Requirements |
|---|---|---|
| `Main.html` | Channel, list view, dark | R-UI-01 to R-UI-07, R-FB-01, R-FB-02 |
| `WebGrid.html` | Channel, grid view, dark | R-UI-03 |
| `ListLight.html`, `GridLight.html` | The same in the light theme | R-PL-05 |
| `Details.html` | Video details panel | R-UI-08, R-UI-09 |
| `Menus.html` | Context menus: synced video, other video, channel | R-UI-09, R-CH-30 |
| `StateLoading.html` | First listing of a channel | R-CH-11 |
| `StateError.html` | Check failed | R-CH-25 |
| `StateEmpty.html` | Empty filter result | R-UI-04 |
| `Setup.html` | First run: installing tools | R-IN-03 |
| `Welcome.html` | No channels yet | R-UI-02 |
| `AddChannel1.html`, `AddChannel2.html` | Add channel | R-CH-01 to R-CH-06 |
| `Adopt.html` | Match and repair existing files | R-AD-* |
| `Installer.html` | Terminal output of the installer | R-IN-01 |
| `Settings.html` | General settings | Section 10 of the spec |
| `ChannelSettings.html` | Per-channel settings | R-CH-30 to R-CH-33, R-EX-05 |
| `ExcludeConfirm.html` | Exclude a downloaded video | R-EX-04 |
| `ExcludePreview.html` | Auto-exclude preview | R-EX-06, R-EX-07 |
| `RemoveChannel.html` | Remove a channel | R-CH-32 |
| `QualityChange.html` | Quality changed | R-QL-05 |
| `Shortcuts.html` | Keyboard shortcuts | R-UI-13 |
| `AppUpdate.html` | App update | R-UP-01 to R-UP-03 |
| `Uninstall.html` | Uninstall | R-UN-01 |
| `ApiKeyGuide.html` | Optional API key guide | R-DT-12 |
| `ErrorDetails.html` | The pattern for every error | R-ER-01 |
| `ReportProblem.html` | Report a problem | R-HE-02 |
| `QuitConfirm.html` | Quit while downloading | R-QU-12 |
| `Downloads.html` | Queue panel | R-QU-* |
| `Activity.html` | Activity log | R-AC-* |
| `States.html` | Every indicator, banner, toast and notification | R-FB-* |
| `Help.html` | Built-in help | R-HE-01 |
| `SiteHome.html`, `SiteDocs.html` | Website | R-WS-* |
| `AppIcon.html` | App icon and logo | |

Not drawn, by decision: layouts narrower than the minimum window (R-PL-03), the native macOS folder picker, and the remaining website documentation pages (they use the `SiteDocs.html` template).

## 2. The theme center and its tokens

Requirements: R-TH-01 to R-TH-09 in [SPEC.md](SPEC.md). Decision: D-036.

Every visual value of the app lives in one folder, `frontend/src/design/`. Nothing outside that folder may contain a colour value, a font name, a pixel font size or a one-off spacing value.

```
frontend/src/design/
  tokens.css        Every token as a CSS variable. Shared values, then one block per theme
  theme.css         The Tailwind preset: maps the tokens to utility classes, and removes Tailwind's own palette and scales
  themes.ts         The list of themes, and the few lines that pick one (system, light, dark)
  fonts/            One folder per bundled font: the font files, their license, and a font.css that declares them
  brand/icon.svg    The one source of the app icon and logo (section 5)
  preview/          The theme preview page (development mode only)
```

### 2.1 Rules for tokens

1. **Tokens are CSS variables** named `--ytm-<group>-<name>`. The groups are `color`, `font`, `font-size`, `font-weight`, `line-height`, `space`, `radius`, `shadow` and `duration`.
2. **Names are semantic.** A name says what the value is for (`text-muted`, `surface-raised`, `accent`), never what it looks like (`blue-500`, `gray-2`).
3. **A theme is one block.** `tokens.css` has one block of shared values and one block per theme, selected by the `data-theme` attribute on the root element. Every theme block defines exactly the same tokens. A test checks this.
4. **"Same as system"** is not a third block. `themes.ts` reads the system setting and sets `data-theme` to `light` or `dark`, and follows the system when it changes.
5. **Adding a theme** means adding one block to `tokens.css` and its name to `themes.ts`. No component changes.
6. **Changing the app font** means putting the new font's folder into `fonts/` and changing the one `--ytm-font-text` line (or `--ytm-font-heading`). Every `font.css` in `fonts/` is loaded automatically.
7. **The Tailwind preset** in `theme.css` is the only bridge to utility classes. Tailwind's default colours, font sizes, weights, radii and shadows are switched off there, so a class such as `bg-blue-500` or `text-sm` does not exist. In Tailwind 4 a preset is a CSS file, not a JavaScript file.
8. **A lint check in CI** (`npm --prefix frontend run lint:theme`) fails when code outside the theme center uses a raw colour, a font name, a font size, a one-off spacing value, a Tailwind arbitrary value (`p-[13px]`), or a token that is not defined.
9. **The website** imports the same `tokens.css` (R-TH-07, built in milestone M10). The file therefore contains plain CSS only, nothing that needs Tailwind or the app.
10. **The theme preview page** (`./start --dev`, then `/theme-preview.html` on the development server) shows every token and every shared component in every theme side by side. It is the page the visual regression screenshots are taken from. A component is added to it in the same commit that creates the component.

### 2.2 Colour tokens

One value per theme. Utility classes use the token name, for example `bg-surface`, `text-text-muted`, `border-line`.

| Token | Dark | Light | Use |
|---|---|---|---|
| `bg` | `#0E1014` | `#F6F7F9` | Window background |
| `surface-side` | `#13161C` | `#FFFFFF` | Sidebar, panels |
| `surface` | `#161A21` | `#FFFFFF` | Cards, dialogs, fields |
| `surface-raised` | `#1E2633` | `#E3EDFF` | Selected item, menus, toasts |
| `line` | `#262C36` | `#E1E5EB` | Dividers |
| `line-strong` | `#323A47` | `#C2C9D3` | Control borders |
| `text` | `#E8EBF0` | `#1A1D23` | Primary text |
| `text-dim` | `#C6CCD6` | `#454D5A` | Secondary text |
| `text-muted` | `#9BA4B3` | `#5A6372` | Labels, metadata |
| `accent` | `#5B9BFF` | `#1F5FD1` | Primary buttons, focus, links |
| `on-accent` | `#0B1220` | `#FFFFFF` | Text on accent |
| `ok-bg` / `ok-text` | `#1B2A44` / `#A9C9FF` | `#E3EDFF` / `#123A85` | Synced, success |
| `warn` | `#F2A14A` | `#F2A14A` | Progress bars, "new" badge |
| `warn-bg` / `warn-text` | `#3A2A14` / `#F7C078` | `#FDEBD3` / `#7A4200` | In progress, attention |
| `err-bg` / `err-text` | `#3A1A1C` / `#FFA39B` | `#FDE7E5` / `#8E1B12` | Failures |
| `neutral-bg` / `neutral-text` | `#22262E` / `#B4BBC7` | `#ECEEF2` / `#454D5A` | Queued, excluded |
| `track` | `#2A303B` | `#DDE1E7` | Progress track, skeletons |

### 2.3 Type tokens

Fonts are bundled with the app in `fonts/`. The app must not load fonts from the network.

| Token | Value | Use |
|---|---|---|
| `font-text` | Inter, then the system font | All text |
| `font-heading` | Space Grotesk, then the system font | Headings and the wordmark |
| `font-mono` | The system monospace font | Technical details |

Font sizes. Utility classes use the token name, for example `text-title-sm`.

| Token | Value | Use |
|---|---|---|
| `font-size-label` | 12 px | Uppercase labels, small tags |
| `font-size-meta` | 13 px | Metadata lines, hints, chips |
| `font-size-body` | 14 px | Default text |
| `font-size-title-sm` | 15 px | Video titles in rows and cards |
| `font-size-body-lg` | 16 px | Emphasised body, channel name in dialogs, website body |
| `font-size-heading-sm` | 18 px | Section headings, wordmark |
| `font-size-heading-md` | 22 px | Dialog titles, details panel title |
| `font-size-heading-lg` | 28 px | Page titles |
| `font-size-display-md` | 36 px | Website page titles |
| `font-size-display-lg` | 52 px | Website hero only |

### 2.4 Shape and spacing tokens

| Token | Value | Use |
|---|---|---|
| `space` | 4 px | The spacing step. All spacing is a whole multiple of it (`p-4` is 16 px) |
| `radius-xs` | 4 px | Duration badges, small tags |
| `radius-sm` | 6 px | Menu items, view toggle, key caps |
| `radius-md` | 8 px | Buttons, inputs, selects |
| `radius-lg` | 12 px | Cards, menus, toasts, banners, info boxes |
| `radius-xl` | 16 px | Dialogs |
| `radius-full` | fully round | Status chips, pill buttons, avatars |

### 2.5 The mockups predate the final scale

The mockups in `docs/design/v1/` were drawn before the scale in sections 2.3 and 2.4 was fixed, and they are not edited. Where a mockup differs from the scale, the scale wins, with these rounding rules:

| In a mockup | Use |
|---|---|
| Font size 11 px | `label` (12) |
| Font size 19 px | `heading-sm` (18) |
| Font size 20 px | `heading-md` (22) |
| Font size 24 or 26 px | `heading-lg` (28) |
| Font size 30 or 32 px | `heading-lg` (28) in the app, `display-md` (36) on the website |
| Radius 10 or 14 px | `radius-lg` (12) |
| Any pill value (14 px on chips, 22 px, 30 px) | `radius-full` |

### 2.6 Line height, font weight and motion tokens

Approved by the maintainer in milestone M0. The mockups do not define these as rules. The values were read from the mockups and from rule 10 of section 3.

| Token | Value | Use |
|---|---|---|
| `line-height-heading` | 1.1 | `heading-lg`, `display-md`, `display-lg` |
| `line-height-text` | 1.45 | Everything else by default |
| `line-height-prose` | 1.6 | Long text: description, help, website body |
| `font-weight-regular` | 400 | Text |
| `font-weight-medium` | 500 | Buttons, emphasis, video titles |
| `font-weight-semibold` | 600 | Headings, the wordmark |
| `duration-fast` | 150 ms | Hover, press, toggles |
| `duration-base` | 200 ms | Menus, dialogs, panels, toasts |

Both durations become 0 ms when the system "reduce motion" setting is on.

### 2.7 Shadow tokens

One value per theme, like the colours. Utility classes: `shadow-raised`, `shadow-overlay`.

| Token | Dark | Light | Use |
|---|---|---|---|
| `shadow-raised` | `0 4px 12px rgb(0 0 0 / 0.35)` | `0 4px 12px rgb(16 24 40 / 0.12)` | Menus, toasts |
| `shadow-overlay` | `0 16px 48px rgb(0 0 0 / 0.5)` | `0 16px 48px rgb(16 24 40 / 0.2)` | Dialogs |

**To judge by the maintainer on the theme preview page.** No mockup uses a shadow: the designs separate layers with borders and surface colours. The maintainer asked for real, soft shadows in milestone M0. These values are a first proposal and are easy to change here and in `tokens.css`.

Targets: interactive elements are at least 44 px high, except dense table and toolbar controls (36 px minimum).

## 3. Rules for all screens

1. **Status is never colour alone.** Every status has an icon and a text label. Blue (synced) and orange (in progress) also differ in lightness.
2. **One primary button per view or dialog.**
3. **Dialogs** have a title that states the question or the outcome, a short body, and buttons whose labels are verbs ("Exclude", "Remove channel"), never "OK" or "Yes".
4. **Destructive actions** use the danger style and are never the default button.
5. **Errors** follow the four-part pattern in `ErrorDetails.html`.
6. **Dates** are absolute. An approximate date is always marked as such.
7. **Empty, loading and error states** exist for every list and panel.
8. **Icons** are inline stroke icons from one set. No emoji.
9. **Wording** uses the terms in [GLOSSARY.md](GLOSSARY.md) exactly. The same thing is never called two names.
10. **Motion** is short (150 to 200 ms) and respects the system "reduce motion" setting.

## 4. Component list

The frontend builds these shared components first, each with tests and a story-like demo page used for visual checks: Button, IconButton, Chip (status), ProgressBar, Checkbox, Radio group, Select, TextField, Toggle row, Dialog, Menu, Toast, Banner, Tabs, Sidebar item, Video row, Video card, Details panel, Skeleton, Empty state, Key cap.

## 5. App icon and logo

The icon in `AppIcon.html` is a draft and is expected to change. To make changing it a one-file job:

- There is exactly one source file: `frontend/src/design/brand/icon.svg` (square, single colour on a rounded square). It is part of the theme center (section 2).
- Everything else is generated from it by a build script and never edited by hand: the macOS launcher icon (`.icns`), the window icon, the favicon, the logo in the sidebar and on the website, and the social preview image.
- Colours in the SVG come from the `accent` and `on-accent` tokens.
- Replacing the icon means replacing that file and running the build. A test checks that every generated asset is newer than the source.

## 6. Versioning of designs

Each released version keeps its own folder: `docs/design/v1/`, later `docs/design/v2/`. A version's designs are frozen when it is released. Work on the next version starts by copying the folder.
